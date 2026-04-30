"""Deferred delivery outbox for busy terminal targets."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import uuid
from typing import Any

from lib import state
from lib.events import now_iso, now_epoch


def _aura_bin() -> str:
    return os.environ.get("AURA_BIN") or str((Path(__file__).resolve().parents[1] / "aura"))


def deferred_root() -> Path:
    return state.state_root() / "deferred" / "deliveries"


def deferred_path(deferred_id: str) -> Path:
    return deferred_root() / f"{deferred_id}.json"


def new_deferred_id() -> str:
    return f"aura-defer-{uuid.uuid4().hex[:12]}"


def parse_duration(value: str | int | float | None, *, default: float) -> float:
    if value is None:
        return float(default)
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().lower()
    if not text:
        return float(default)
    unit = text[-1]
    number = text[:-1] if unit in {"s", "m", "h"} else text
    try:
        amount = float(number)
    except ValueError as exc:
        raise ValueError(f"invalid duration: {value}") from exc
    if unit == "m":
        return amount * 60
    if unit == "h":
        return amount * 3600
    return amount


def _atomic_write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def create(
    *,
    target: str,
    message: str,
    sender: str,
    dedupe_key: str,
    transport: str = "tmux",
    retry_every_seconds: float = 15,
    ttl_seconds: float = 900,
    blocked_reason: str | None = None,
    blocked_message_id: str | None = None,
) -> dict[str, Any]:
    created = now_epoch()
    record = {
        "schema": "aura.deferred_delivery.v1",
        "deferred_id": new_deferred_id(),
        "target": target,
        "message": message,
        "sender": sender,
        "transport": transport,
        "dedupe_key": dedupe_key,
        "status": "pending",
        "blocked_reason": blocked_reason,
        "blocked_message_id": blocked_message_id,
        "attempts": [],
        "retry_every_seconds": float(retry_every_seconds),
        "ttl_seconds": float(ttl_seconds),
        "created_at": now_iso(),
        "created_epoch": created,
        "expires_epoch": created + float(ttl_seconds),
        "next_run_epoch": created,
        "updated_at": now_iso(),
    }
    _atomic_write(deferred_path(record["deferred_id"]), record)
    return record


def load(deferred_id: str) -> dict[str, Any]:
    path = deferred_path(deferred_id)
    if not path.exists():
        raise FileNotFoundError(f"deferred delivery not found: {deferred_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def save(record: dict[str, Any]) -> dict[str, Any]:
    record["updated_at"] = now_iso()
    _atomic_write(deferred_path(record["deferred_id"]), record)
    return record


def list_records(*, status: str | None = None) -> list[dict[str, Any]]:
    root = deferred_root()
    if not root.exists():
        return []
    rows = []
    for path in sorted(root.glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if status and record.get("status") != status:
            continue
        rows.append(record)
    return rows


def due_records(*, now: float | None = None, limit: int | None = None) -> list[dict[str, Any]]:
    now = now_epoch() if now is None else now
    rows = [
        record for record in list_records()
        if record.get("status") in {"pending", "retrying"}
        and float(record.get("next_run_epoch") or 0) <= now
    ]
    rows.sort(key=lambda record: float(record.get("next_run_epoch") or 0))
    if limit is not None:
        rows = rows[: int(limit)]
    return rows


def spawn_daemon(deferred_id: str) -> dict[str, Any]:
    log_path = deferred_path(deferred_id).with_suffix(".log")
    cmd = [_aura_bin(), "deferred", "daemon", deferred_id]
    with log_path.open("ab") as log:
        proc = subprocess.Popen(
            cmd,
            stdout=log,
            stderr=log,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
    record = load(deferred_id)
    record["daemon"] = {"pid": proc.pid, "log": str(log_path), "cmd": cmd}
    save(record)
    return record["daemon"]


def run_due(*, limit: int | None = None) -> dict[str, Any]:
    records = due_records(limit=limit)
    results = [run_once(record["deferred_id"]) for record in records]
    return {
        "ok": True,
        "count": len(results),
        "delivered": sum(1 for result in results if result.get("state") == "delivered"),
        "blocked": sum(1 for result in results if result.get("state") == "blocked"),
        "failed": sum(1 for result in results if result.get("state") == "failed"),
        "expired": sum(1 for result in results if result.get("reason") == "expired"),
        "results": results,
    }


def run_once(deferred_id: str) -> dict[str, Any]:
    record = load(deferred_id)
    if record.get("status") not in {"pending", "retrying"}:
        return {"ok": True, "ran": False, "reason": f"status={record.get('status')}", "record": record}
    now = now_epoch()
    if now >= float(record.get("expires_epoch") or 0):
        record["status"] = "expired"
        record["expired_at"] = now_iso()
        save(record)
        return {"ok": False, "ran": False, "reason": "expired", "record": record}

    cmd = [
        _aura_bin(),
        "send",
        record["target"],
        record["message"],
        "--as",
        record.get("sender") or "deferred",
        "--transport",
        record.get("transport") or "tmux",
        "--dedupe-key",
        record["dedupe_key"],
    ]
    result = subprocess.run(cmd, text=True, capture_output=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError:
        parsed = {"ok": False, "error": result.stderr[-1000:] or result.stdout[-1000:]}
    attempt = {
        "at": now_iso(),
        "returncode": result.returncode,
        "result": parsed,
    }
    record.setdefault("attempts", []).append(attempt)
    recovery = None
    if parsed.get("blocked") and parsed.get("reason") in {"target-busy", "target-input-queued", "target-input-active", "submit-unverified"}:
        if parsed.get("reason") == "target-input-queued":
            recovery = _maybe_nudge_queued_input(record)
        record["status"] = "retrying"
        record["next_run_epoch"] = now_epoch() + float(record.get("retry_every_seconds") or 15)
        if recovery:
            record.setdefault("recovery_attempts", []).append(recovery)
        save(record)
        return {"ok": True, "ran": True, "state": "blocked", "recovery": recovery, "record": record}
    parsed_delivered = parsed.get("ok") and parsed.get("state") != "failed"
    if parsed_delivered:
        record["status"] = "delivered"
        record["delivered_at"] = now_iso()
        record["delivery_result"] = parsed
        save(record)
        return {"ok": True, "ran": True, "state": "delivered", "record": record}
    record["status"] = "failed"
    record["failed_at"] = now_iso()
    record["failure_result"] = parsed
    save(record)
    return {"ok": False, "ran": True, "state": "failed", "record": record}


def daemon(deferred_id: str) -> dict[str, Any]:
    while True:
        record = load(deferred_id)
        if record.get("status") not in {"pending", "retrying"}:
            return {"ok": True, "status": record.get("status"), "record": record}
        delay = max(0.0, float(record.get("next_run_epoch") or 0) - now_epoch())
        if delay:
            time.sleep(min(delay, 60.0))
            continue
        run_once(deferred_id)


def _queued_input_nudge_count(record: dict[str, Any]) -> int:
    return sum(
        1
        for attempt in record.get("recovery_attempts", [])
        if attempt.get("action") == "nudge-queued-input"
    )


def _maybe_nudge_queued_input(record: dict[str, Any]) -> dict[str, Any] | None:
    """Submit already-queued input once so deferred delivery can make progress.

    A target-input-queued blocker means Aura refused to paste over existing
    input. For Codex panes that state can persist indefinitely. One Enter nudge
    submits that existing queued prompt; the deferred message itself is retried
    on a later pass rather than being pasted over it.
    """
    if _queued_input_nudge_count(record) >= 1:
        return {
            "at": now_iso(),
            "action": "nudge-queued-input",
            "skipped": True,
            "reason": "max-queued-input-nudges-reached",
        }

    cmd = [
        _aura_bin(),
        "send",
        record["target"],
        "",
        "--as",
        record.get("sender") or "deferred",
        "--transport",
        record.get("transport") or "tmux",
        "--nudge",
    ]
    result = subprocess.run(cmd, text=True, capture_output=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError:
        parsed = {"ok": False, "error": result.stderr[-1000:] or result.stdout[-1000:]}
    return {
        "at": now_iso(),
        "action": "nudge-queued-input",
        "returncode": result.returncode,
        "result": parsed,
    }
