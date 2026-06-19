#!/usr/bin/env python3
"""Claude Code keeper memory hook for boxed Aura seats.

The claude twin of aura_keeper_hook.py. Detaches a background keeper memory job at
runtime boundaries — never synthesizes memory in-process (heavy work is off-plane,
done by the SDK keeper worker). Cadence is **message count** (not context percent):
first trace after N user/assistant messages, then every N — counted from the claude
transcript jsonl. The superseded 25/50/75 percent design is intentionally absent.

  Stop        → if stop_hook_active: no-op. Else count transcript user/assistant
                messages; if a 15-message boundary is newly crossed, detach
                `aura keeper run memory --boundary m<N>`.
  PreCompact  → detach `aura keeper run memory --boundary precompact`.

Quiet by contract: no stdout; failures swallowed; fired boundaries deduped per
session in <box>/.hook-state/keeper-hook.jsonl.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

AURA_BIN = "/home/axp/.local/bin/aura"
FIRST_TRACE_MESSAGES = int(os.environ.get("AURA_KEEPER_FIRST_TRACE_MESSAGES", "15"))
TRACE_INTERVAL_MESSAGES = int(os.environ.get("AURA_KEEPER_TRACE_INTERVAL_MESSAGES", "15"))


def load_event() -> dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return obj if isinstance(obj, dict) else {}


def hook_state_dir() -> Path:
    base = os.environ.get("CLAUDE_CONFIG_DIR")
    root = Path(base) if base else (Path.cwd() / ".claude")
    return root / ".hook-state"


def log_path() -> Path:
    return hook_state_dir() / "keeper-hook.jsonl"


def self_target() -> str | None:
    fleet = os.environ.get("AURA_FLEET")
    seat = os.environ.get("AURA_SEAT") or os.environ.get("AURA_AGENT_NAME")
    return f"{fleet}:{seat}" if fleet and seat else None


def count_messages(transcript_path: str | None) -> int:
    """Count user/assistant turns in the claude transcript jsonl."""
    if not transcript_path:
        return 0
    path = Path(transcript_path)
    if not path.exists():
        return 0
    count = 0
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            role = row.get("role") or (row.get("message") or {}).get("role") or row.get("type")
            if role in ("user", "assistant"):
                count += 1
    except OSError:
        return 0
    return count


def fired_boundaries(session_id: str | None) -> set[str]:
    fired: set[str] = set()
    path = log_path()
    if not session_id or not path.exists():
        return fired
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("session_id") == session_id and row.get("event") == "launched":
                fired.add(str(row.get("boundary")))
    except OSError:
        return fired
    return fired


def record(session_id: str | None, boundary: str, event: str, **extra: Any) -> None:
    try:
        path = log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        row = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "session_id": session_id, "boundary": boundary, "event": event, **extra}
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
    except OSError:
        return


def detach_keeper(target: str, boundary: str) -> None:
    try:
        subprocess.Popen(
            [AURA_BIN, "keeper", "run", "memory", "--target", target, "--boundary", boundary],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception:  # noqa: BLE001 - never fatal
        return


def due_boundary(message_count: int) -> str | None:
    """Highest message-count boundary newly reached; None if below first trace."""
    if message_count < FIRST_TRACE_MESSAGES:
        return None
    n = ((message_count - FIRST_TRACE_MESSAGES) // TRACE_INTERVAL_MESSAGES) * TRACE_INTERVAL_MESSAGES
    return f"m{FIRST_TRACE_MESSAGES + n}"


def handle_stop(event: dict[str, Any]) -> None:
    if event.get("stop_hook_active"):
        return
    target = self_target()
    if not target:
        return
    session_id = event.get("session_id")
    boundary = due_boundary(count_messages(event.get("transcript_path")))
    if boundary is None or boundary in fired_boundaries(session_id):
        return
    detach_keeper(target, boundary)
    record(session_id, boundary, "launched")


def handle_precompact(event: dict[str, Any]) -> None:
    target = self_target()
    if not target:
        return
    detach_keeper(target, "precompact")
    record(event.get("session_id"), "precompact", "launched")


def main() -> int:
    event = load_event()
    name = event.get("hook_event_name")
    if name == "Stop":
        handle_stop(event)
    elif name == "PreCompact":
        handle_precompact(event)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001 - never fatal to the runtime
        raise SystemExit(0)
