#!/usr/bin/env python3
"""Aura Claude Code SessionStart hook binder.

Installed as a user-level Claude Code SessionStart hook. For an Aura-spawned
seat (AURA_FLEET/AURA_SEAT in the environment) it binds the session id from the
hook payload to the seat row through the gated registry writer. For any other
Claude session it exits silently and does nothing.

It is strictly quiet on stdout: Claude Code injects SessionStart hook stdout
into the model's context, so any output here would pollute every session.
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
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _first_string(*values) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _target() -> str | None:
    fleet = _first_string(os.environ.get("AURA_FLEET"), os.environ.get("AURA_TMUX_SESSION"))
    seat = _first_string(os.environ.get("AURA_SEAT"), os.environ.get("AURA_AGENT_NAME"))
    return f"{fleet}:{seat}" if fleet and seat else None


def _retryable(result: dict) -> bool:
    return str(result.get("error") or "") in {
        "target seat is not registered; adopt or spawn it before hook binding",
        "seat-instance-mismatch",
    }


def main() -> int:
    payload = _read_payload()
    event = _first_string(payload.get("hook_event_name"), payload.get("event")) or "SessionStart"
    if event != "SessionStart":
        return 0

    target = _target()
    if not target:
        # Not an Aura seat — an ordinary personal Claude session. Do nothing.
        return 0

    session_id = _first_string(
        payload.get("session_id"),
        payload.get("sessionId"),
        os.environ.get("CLAUDE_SESSION_ID"),
    )
    if not session_id:
        return 0

    from commands import sessions

    args = argparse.Namespace(
        sessions_action="bind-hook",
        runtime="claude-code",
        target=target,
        session_id=session_id,
        nonce=None,
        transcript_path=_first_string(payload.get("transcript_path"), payload.get("transcriptPath")),
        hook_event=event,
        seat_instance_id=os.environ.get("AURA_SEAT_INSTANCE_ID"),
    )

    deadline = time.time() + float(os.environ.get("AURA_CLAUDE_BIND_HOOK_TIMEOUT", "10"))
    while True:
        try:
            result = sessions.run(args) or {}
        except Exception as exc:  # never break the session over a binding side effect
            result = {"ok": False, "error": str(exc)}
        if result.get("ok") or not _retryable(result) or time.time() >= deadline:
            break
        time.sleep(float(os.environ.get("AURA_CLAUDE_BIND_HOOK_RETRY_DELAY", "0.25")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
