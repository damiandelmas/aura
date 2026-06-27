#!/usr/bin/env python3
"""Compact-recovery hook for Aura-managed Codex and Claude Code seats."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib import compact_recovery


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_payload() -> dict[str, Any]:
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _event(payload: dict[str, Any]) -> str:
    return compact_recovery.first_string(
        sys.argv[1] if len(sys.argv) > 1 else None,
        payload.get("hook_event_name"),
        payload.get("hookEventName"),
        payload.get("event"),
        os.environ.get("CODEX_HOOK_EVENT"),
    ) or ""


def _runtime() -> str:
    return compact_recovery.first_string(os.environ.get("AURA_RUNTIME"), os.environ.get("RUNTIME")) or "codex"


def _compact_summary(payload: dict[str, Any]) -> str | None:
    value = compact_recovery.first_string(
        payload.get("compact_summary"),
        payload.get("compactSummary"),
        payload.get("summary"),
    )
    if value:
        return value
    nested = payload.get("payload")
    if isinstance(nested, dict):
        return compact_recovery.first_string(nested.get("compact_summary"), nested.get("summary"))
    return None


def _session_id(payload: dict[str, Any]) -> str:
    return compact_recovery.first_string(
        payload.get("session_id"),
        payload.get("sessionId"),
        os.environ.get("CODEX_THREAD_ID"),
        os.environ.get("CLAUDE_SESSION_ID"),
        os.environ.get("AURA_RUNTIME_SESSION_ID"),
    ) or "unknown-session"


def _state_root() -> Path:
    explicit = compact_recovery.first_string(os.environ.get("AURA_COMPACT_RECOVERY_STATE_DIR"))
    if explicit:
        return Path(explicit).expanduser()
    codex_home = compact_recovery.first_string(os.environ.get("CODEX_HOME"))
    if codex_home:
        return Path(codex_home).expanduser() / "aura-compact-recovery"
    return Path.cwd() / ".aura-compact-recovery"


def _target() -> str | None:
    fleet = compact_recovery.first_string(os.environ.get("AURA_FLEET"), os.environ.get("AURA_TMUX_SESSION"))
    seat = compact_recovery.first_string(os.environ.get("AURA_SEAT"), os.environ.get("AURA_AGENT_NAME"))
    return f"{fleet}:{seat}" if fleet and seat else None


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _move_record(source: Path, prefix: str) -> Path:
    destination = source.parent / f"{prefix}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}.json"
    shutil.move(str(source), str(destination))
    return destination


def _pending_path() -> Path:
    return _state_root() / "pending-post-compact.json"


def _aura_bin() -> str:
    return compact_recovery.first_string(os.environ.get("AURA_BIN")) or "/home/axp/.local/bin/aura"


def _inject_with_aura_send(message: str, *, session_id: str) -> dict[str, Any]:
    target = _target()
    if not target:
        return {"ok": False, "reason": "missing-target"}
    command = [
        _aura_bin(),
        "send",
        target,
        message,
        "--as-service",
        "compact-recovery",
        "--force",
        "--dedupe-key",
        f"compact-recovery:{target}:{session_id}",
    ]
    try:
        completed = subprocess.run(command, text=True, capture_output=True, timeout=30, check=False)
    except Exception as exc:
        return {"ok": False, "reason": "aura-send-exception", "error": str(exc), "command": command}
    parsed: dict[str, Any] | None = None
    if completed.stdout.strip():
        try:
            parsed = json.loads(completed.stdout)
        except Exception:
            parsed = None
    parsed_ok = isinstance(parsed, dict) and parsed.get("ok") is True
    return {
        "ok": parsed_ok or (completed.returncode == 0 and parsed is None),
        "returncode": completed.returncode,
        "stdout": completed.stdout[-1000:],
        "stderr": completed.stderr[-1000:],
        "parsed": parsed,
        "command": command,
    }


def _context(payload: dict[str, Any], *, compact_summary: str | None = None) -> tuple[Path | None, str]:
    doc_path, doc_text = compact_recovery.read_recovery_document(compact_recovery.recovery_document_path())
    return doc_path, compact_recovery.render_recovery_context(
        document_path=doc_path,
        document_text=doc_text,
        runtime=_runtime(),
        compact_summary=compact_summary if compact_summary is not None else _compact_summary(payload),
    )


def _handle_claude_compact(payload: dict[str, Any]) -> int:
    _, context = _context(payload)
    sys.stdout.write(context)
    return 0


def _handle_postcompact(payload: dict[str, Any]) -> int:
    session_id = _session_id(payload)
    doc_path, context = _context(payload)
    pending = _pending_path()
    record = {
        "created_at": _now(),
        "event": "PostCompact",
        "runtime": _runtime(),
        "session_id": session_id,
        "document": str(doc_path) if doc_path else None,
        "compact_summary": _compact_summary(payload),
        "target": _target(),
        "state": "pending",
    }
    _write_json(pending, record)
    if os.environ.get("AURA_COMPACT_RECOVERY_INJECT", "1") not in {"0", "false", "False"}:
        result = _inject_with_aura_send(context, session_id=session_id)
        record["aura_send"] = result
        if result.get("ok"):
            parsed = result.get("parsed") if isinstance(result.get("parsed"), dict) else {}
            deferred = bool(parsed.get("deferred"))
            record["state"] = "deferred" if deferred else "injected"
            record["injected_at"] = _now()
            _write_json(pending, record)
            destination = _move_record(pending, "deferred" if deferred else "injected")
            verb = "deferred" if deferred else "injected"
            print(json.dumps({"systemMessage": f"Aura compact recovery {verb} follow-up context: {destination}"}))
            return 0
        _write_json(pending, record)
    print(json.dumps({"systemMessage": f"Aura compact recovery stored pending context: {pending}"}))
    return 0


def _handle_user_prompt_submit(payload: dict[str, Any]) -> int:
    pending = _pending_path()
    if not pending.is_file():
        return 0
    try:
        record = json.loads(pending.read_text(encoding="utf-8"))
    except Exception:
        record = {}
    pending_summary = record.get("compact_summary") if isinstance(record.get("compact_summary"), str) else None
    doc_path, context = _context(payload, compact_summary=_compact_summary(payload) or pending_summary)
    record["state"] = "consumed-on-user-prompt"
    record["consumed_at"] = _now()
    record["document"] = str(doc_path) if doc_path else record.get("document")
    _write_json(pending, record)
    _move_record(pending, "consumed")
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": context,
        }
    }))
    return 0


def main() -> int:
    payload = _read_payload()
    event = _event(payload)
    if event == "ClaudeCompact":
        return _handle_claude_compact(payload)
    if event == "PostCompact":
        return _handle_postcompact(payload)
    if event == "UserPromptSubmit":
        return _handle_user_prompt_submit(payload)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        raise SystemExit(0)
