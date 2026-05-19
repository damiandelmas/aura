#!/usr/bin/env python3
"""Aura Codex SessionStart hook binder.

Runs inside Aura-owned boxed Codex homes.  It is intentionally quiet on stdout:
Codex hook stdout is part of the native hook protocol, while Aura only needs a
best-effort registry/capsule binding side effect.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

CLI_ROOT = Path(__file__).resolve().parents[1]
if str(CLI_ROOT) not in sys.path:
    sys.path.insert(0, str(CLI_ROOT))


def _read_payload() -> dict:
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except Exception as exc:
        return {"_parse_error": str(exc), "_raw_preview": raw[:500]}
    return parsed if isinstance(parsed, dict) else {"_non_object_payload": parsed}


def _first_string(*values) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _hook_event(payload: dict) -> str:
    return _first_string(
        payload.get("hook_event_name"),
        payload.get("hookEventName"),
        payload.get("event"),
        payload.get("name"),
    ) or "SessionStart"


def _session_id(payload: dict) -> str | None:
    return _first_string(
        payload.get("session_id"),
        payload.get("sessionId"),
        payload.get("thread_id"),
        payload.get("threadId"),
        os.environ.get("CODEX_THREAD_ID"),
        os.environ.get("AURA_RUNTIME_SESSION_ID"),
        os.environ.get("AURA_SESSION_ID"),
    )


def _transcript_path(payload: dict) -> str | None:
    return _first_string(payload.get("transcript_path"), payload.get("transcriptPath"))


def _target() -> str | None:
    fleet = _first_string(os.environ.get("AURA_FLEET"), os.environ.get("AURA_TMUX_SESSION"))
    seat = _first_string(os.environ.get("AURA_SEAT"), os.environ.get("AURA_AGENT_NAME"))
    return f"{fleet}:{seat}" if fleet and seat else None


def _is_package_agent_root(root: Path) -> bool:
    if _first_string(os.environ.get("AURA_AGENT_PACKAGE_ID"), os.environ.get("AURA_AGENT_PACKAGE_ROOT")):
        return True
    try:
        resolved = root.expanduser().resolve()
    except Exception:
        resolved = root.expanduser()
    if (resolved / "manifest.json").exists():
        return True
    if (resolved / "agent.json").exists():
        try:
            body = json.loads((resolved / "agent.json").read_text(encoding="utf-8"))
        except Exception:
            body = {}
        if str(body.get("schema") or "").startswith("aura.agent_"):
            return True
    return False


def _log_path() -> Path | None:
    root = _first_string(os.environ.get("AURA_RUNTIME_CAPSULE_REF"), os.environ.get("AURA_CODEX_BOX"))
    if not root:
        return None
    root_path = Path(root).expanduser()
    if _is_package_agent_root(root_path):
        return None
    return root_path / "receipts" / "codex-bind-hook.jsonl"


def _append_log(entry: dict) -> None:
    path = _log_path()
    if not path:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, sort_keys=True) + "\n")
    except Exception:
        pass


def _retryable(result: dict) -> bool:
    error = str(result.get("error") or "")
    return error in {
        "target seat is not registered; adopt or spawn it before hook binding",
        "seat-instance-mismatch",
    }


def main() -> int:
    payload = _read_payload()
    session_id = _session_id(payload)
    target = _target()
    event = _hook_event(payload)
    if event != "SessionStart":
        return 0
    if not session_id or not target:
        _append_log({
            "ok": False,
            "reason": "missing-session-or-target",
            "session_id_present": bool(session_id),
            "target": target,
            "event": event,
        })
        return 0

    from commands import sessions

    args = argparse.Namespace(
        sessions_action="bind-hook",
        runtime=os.environ.get("AURA_RUNTIME") or "codex",
        target=target,
        session_id=session_id,
        nonce=None,
        transcript_path=_transcript_path(payload),
        hook_event=event,
        seat_instance_id=os.environ.get("AURA_SEAT_INSTANCE_ID"),
    )
    deadline = time.time() + float(os.environ.get("AURA_CODEX_BIND_HOOK_TIMEOUT", "10"))
    attempt = 0
    result: dict = {}
    while True:
        attempt += 1
        try:
            result = sessions.run(args) or {}
        except Exception as exc:  # keep native hook non-fatal
            result = {"ok": False, "error": str(exc)}
        if result.get("ok") or not _retryable(result) or time.time() >= deadline:
            break
        time.sleep(float(os.environ.get("AURA_CODEX_BIND_HOOK_RETRY_DELAY", "0.25")))

    _append_log({
        "ok": bool(result.get("ok")),
        "attempts": attempt,
        "target": target,
        "session_id": session_id,
        "event": event,
        "result": {key: result.get(key) for key in (
            "ok",
            "error",
            "runtime_session_id",
            "runtime_session_source",
            "runtime_capsule_session",
        ) if key in result},
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
