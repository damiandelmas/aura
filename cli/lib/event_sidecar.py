"""Aura-to-sidecar adapter boundary for external event delivery."""

from __future__ import annotations

import os
from pathlib import Path
import json
import shutil
import subprocess
from typing import Any

from lib import delivery
from lib.events import now_iso


SIDECAR_NAME = "clawhip"


def _clawhip_bin() -> str | None:
    configured = os.environ.get("AURA_CLAWHIP_BIN") or os.environ.get("CLAWHIP_BIN")
    if configured:
        path = Path(configured).expanduser()
        return str(path) if path.exists() else None
    return shutil.which("clawhip")


def _unavailable(reason: str = "clawhip command not found") -> dict[str, Any]:
    return {
        "ok": False,
        "sidecar": SIDECAR_NAME,
        "category": "sidecar-unavailable",
        "reason": reason,
        "retryable": True,
    }


def reply_handle(source_seat: str) -> str:
    return source_seat if source_seat.startswith("@{") else f"@{{{source_seat}}}"


def aura_event(kind: str, *, source: str | None = None, target: str | None = None, payload: dict | None = None, meta: dict | None = None) -> dict[str, Any]:
    return {
        "schema": "aura.event.v1",
        "kind": kind,
        "source": source,
        "target": target,
        "payload": payload or {},
        "meta": {"sidecar": SIDECAR_NAME, **(meta or {})},
        "at": now_iso(),
    }


def status() -> dict[str, Any]:
    binary = _clawhip_bin()
    if not binary:
        return _unavailable()
    result = _run_json([binary, "status"])
    if result.get("ok"):
        return {
            "ok": True,
            "sidecar": SIDECAR_NAME,
            "binary": binary,
            "configured": True,
            "status": result.get("data"),
        }
    return {
        "ok": True,
        "sidecar": SIDECAR_NAME,
        "binary": binary,
        "configured": True,
        "status_error": result,
    }


def _run_json(cmd: list[str]) -> dict[str, Any]:
    try:
        result = subprocess.run(cmd, text=True, capture_output=True, timeout=20)
    except OSError as exc:
        return {"ok": False, "error": str(exc), "cmd": cmd}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "sidecar-timeout", "cmd": cmd}
    data = None
    if result.stdout.strip():
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            data = {"stdout": result.stdout[-2000:]}
    if result.returncode == 0:
        return {"ok": True, "cmd": cmd, "returncode": result.returncode, "data": data}
    return {
        "ok": False,
        "cmd": cmd,
        "returncode": result.returncode,
        "data": data,
        "error": result.stderr[-2000:] or result.stdout[-2000:] or "sidecar command failed",
    }


def emit_event(kind: str, payload: dict, *, meta: dict | None = None) -> dict[str, Any]:
    event = aura_event(kind, payload=payload, meta=meta)
    sidecar = status()
    if not sidecar.get("ok"):
        return {**sidecar, "event": event}
    binary = sidecar["binary"]
    result = _run_json([binary, "emit", kind, f"payload={json.dumps(event)}"])
    return {
        "ok": result.get("ok", False),
        "sidecar": SIDECAR_NAME,
        "event": event,
        "state": "delivered" if result.get("ok") else "failed",
        "sidecar_result": result,
    }


def deliver_human_message(source_seat: str, text: str, *, channel: str | None = None) -> dict[str, Any]:
    handle = reply_handle(source_seat)
    rendered = f"{handle} {text}"
    event = aura_event(
        "human.message.outbound",
        source=source_seat,
        target=channel or "human:default",
        payload={"text": text, "reply_handle": handle, "rendered": rendered},
    )
    sidecar = status()
    if not sidecar.get("ok"):
        return {**sidecar, "event": event, "rendered": rendered}
    binary = sidecar["binary"]
    cmd = [binary, "send", "--message", rendered]
    if channel:
        cmd.extend(["--channel", channel])
    result = _run_json(cmd)
    record = delivery.new_delivery_record(
        delivery_type="sidecar_delivery",
        sender=source_seat,
        target=channel or "human:default",
        backend=SIDECAR_NAME,
        state="delivered" if result.get("ok") else "failed",
        sidecar_event=event,
        sidecar_result=result,
    )
    delivery.append_attempt(record, state="sidecar-send", evidence={"cmd": cmd, "ok": result.get("ok")})
    delivery.append_record(record)
    return {
        "ok": result.get("ok", False),
        "sidecar": SIDECAR_NAME,
        "event": event,
        "rendered": rendered,
        "state": "delivered" if result.get("ok") else "failed",
        "sidecar_result": result,
        "delivery_record": record,
    }


def register_runtime(seat: dict, runtime: dict, *, channel: str | None = None) -> dict[str, Any]:
    seat_key = seat.get("seat_key") or f"{seat.get('fleet')}:{seat.get('name')}"
    payload = {
        "seat_key": seat_key,
        "reply_handle": reply_handle(seat_key),
        "runtime": runtime.get("runtime") or seat.get("runtime"),
        "backend": seat.get("backend") or "tmux",
        "pane_ref": seat.get("pane_ref"),
        "session_ref": runtime.get("session_ref") or runtime.get("runtime_session_id") or seat.get("session_id"),
        "channel_target": channel,
    }
    event = aura_event("runtime.register", source=seat_key, target="sidecar:clawhip", payload=payload)
    sidecar = status()
    if not sidecar.get("ok"):
        return {**sidecar, "event": event, "registration": payload}
    binary = sidecar["binary"]
    result = _run_json([binary, "emit", "runtime.register", f"payload={json.dumps(event)}"])
    return {
        "ok": result.get("ok", False),
        "sidecar": SIDECAR_NAME,
        "event": event,
        "registration": payload,
        "state": "registered" if result.get("ok") else "failed",
        "sidecar_result": result,
    }


def ingest_human_reply(message: dict) -> dict[str, Any]:
    return {
        "ok": True,
        "sidecar": SIDECAR_NAME,
        "event": aura_event("human.message.inbound", source=message.get("source"), payload=message),
        "state": "parsed",
    }


def verify_bindings(scope: str | None = None) -> dict[str, Any]:
    sidecar = status()
    result = {
        "scope": scope,
        "missing": [],
        "forbidden": [],
        "not_found": [],
        "name_mismatch": [],
    }
    if not sidecar.get("ok"):
        return {**sidecar, "bindings": result}
    binary = sidecar["binary"]
    cmd = [binary, "config", "verify-bindings", "--json"]
    if scope:
        cmd.extend(["--scope", scope])
    sidecar_result = _run_json(cmd)
    if sidecar_result.get("ok") and isinstance(sidecar_result.get("data"), dict):
        result.update(sidecar_result["data"])
    return {
        "ok": bool(sidecar_result.get("ok")),
        "sidecar": SIDECAR_NAME,
        "bindings": result,
        "sidecar_result": sidecar_result,
    }
