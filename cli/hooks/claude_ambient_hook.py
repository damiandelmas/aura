#!/usr/bin/env python3
"""Claude Code ambient (fleet-roster) hook for boxed Aura seats.

Topology-awareness injection, the claude twin of the recovered codex ambient hook
— but **push, not poll**. Heavy roster builds happen only when membership actually
changed (a pending-flag set by the membership event source). Per-prompt cost is a
single file-stat. Binding is NOT done here (that is claude_bind_hook.py).

  SessionStart      → inject ambient packet once (born orientation).
                      source=="compact" → prepend a compaction-recovery note.
  UserPromptSubmit  → stat <box>/.hook-state/ambient-pending.json
                        absent  → exit 0, no subprocess  (the cost-bug guard)
                        present → `aura ambient self` once → inject → clear flag
  PostCompact       → set the pending-flag so the next prompt re-orients.

Quiet by contract: stdout only the documented hookSpecificOutput JSON; all failures
swallowed (evidence to side-channel), never fatal to the runtime.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

AURA_BIN = "/home/axp/.local/bin/aura"
HOOK_EVENTS = {"SessionStart", "UserPromptSubmit", "PostCompact"}
# NOTE: doc-recovery on source=compact is owned by the other lane's
# aura_compact_recovery_hook.py. This hook only provides ambient orientation
# (no recovery-note prefix) to de-conflict the double-inject.


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


def _pending_key(fleet: str, seat: str) -> str:
    return f"{fleet}__{seat}".replace("/", "_")


def pending_path() -> Path:
    """Cross-process pending-refresh flag — written by the membership emitter (aura
    CLI), read here. Lives under AURA_STATE_DIR keyed by seat identity (NOT in the
    box) so the emitter resolves the same path without knowing the box layout. Both
    sides have AURA_STATE_DIR + AURA_FLEET + AURA_SEAT in env on every managed launch.
    """
    state_dir = os.environ.get("AURA_STATE_DIR") or str(Path.home() / ".aura")
    fleet = os.environ.get("AURA_FLEET") or "unknown"
    seat = os.environ.get("AURA_SEAT") or os.environ.get("AURA_AGENT_NAME") or "unknown"
    return Path(state_dir) / "ambient-pending" / f"{_pending_key(fleet, seat)}.json"


def fingerprint_path() -> Path:
    # Hook-private state (written and read only here) stays box-local.
    return hook_state_dir() / "ambient-last.json"


def emit_additional_context(text: str, hook_event_name: str) -> None:
    sys.stdout.write(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": hook_event_name,
            "additionalContext": text,
        }
    }))
    sys.stdout.flush()


def ambient_self() -> dict[str, Any]:
    try:
        result = subprocess.run(
            [AURA_BIN, "ambient", "self"],
            capture_output=True, text=True, timeout=8.0,
        )
    except Exception as exc:  # noqa: BLE001 - hooks must never raise into the runtime
        return {"ok": False, "error": "aura-ambient-hook-failed", "reason": str(exc)}
    if result.returncode != 0:
        return {"ok": False, "error": "aura-ambient-command-failed",
                "reason": (result.stderr or result.stdout).strip()[:500]}
    try:
        obj = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "error": "aura-ambient-invalid-json"}
    return obj if isinstance(obj, dict) else {"ok": False, "error": "aura-ambient-invalid-packet"}


def semantic_fingerprint(packet: dict[str, Any]) -> str:
    """Hash only the fields whose change should re-inject (roster set + warnings)."""
    if not packet.get("ok"):
        sem: dict[str, Any] = {"ok": False, "error": packet.get("error")}
    else:
        fleet = packet.get("fleet") if isinstance(packet.get("fleet"), list) else []
        sem = {
            "ok": True,
            "target": packet.get("target"),
            "fleet": sorted(str(r.get("target") or "") for r in fleet),
            "warnings": sorted(str(w) for w in packet.get("warnings") or []),
        }
    return hashlib.sha256(json.dumps(sem, sort_keys=True).encode("utf-8")).hexdigest()


def repair_context(packet: dict[str, Any]) -> str:
    return (
        "[AURA AMBIENT]\nstatus: unresolved\n"
        f"error: {packet.get('error') or 'ambient-unresolved'}\n"
        "instruction: do not guess your Aura fleet:seat; ask the operator to repair binding.\n"
        "[/AURA AMBIENT]"
    )


def remember(fp: str) -> None:
    try:
        path = fingerprint_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"fingerprint": fp}), encoding="utf-8")
    except OSError:
        return


def last_fingerprint() -> str | None:
    try:
        return json.loads(fingerprint_path().read_text(encoding="utf-8")).get("fingerprint")
    except (OSError, json.JSONDecodeError, AttributeError):
        return None


def set_pending(reason: str) -> None:
    try:
        path = pending_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"schema": "aura.ambient_pending.v1", "reason": reason}),
                        encoding="utf-8")
    except OSError:
        return


def take_pending() -> bool:
    """True if a pending refresh is set; clear it (consume)."""
    path = pending_path()
    if not path.exists():
        return False
    try:
        path.unlink()
    except OSError:
        pass
    return True


def inject_packet(hook_event_name: str) -> None:
    packet = ambient_self()
    fp = semantic_fingerprint(packet)
    if packet.get("ok") and isinstance(packet.get("text"), str):
        emit_additional_context(str(packet["text"]), hook_event_name)
    else:
        emit_additional_context(repair_context(packet), hook_event_name)
    remember(fp)


def main() -> int:
    event = load_event()
    name = event.get("hook_event_name") or "SessionStart"
    if name not in HOOK_EVENTS:
        return 0

    if name == "SessionStart":
        # ambient orientation on every start, including source=compact; doc-recovery
        # is the other lane's aura_compact_recovery_hook (no double-inject).
        inject_packet(name)
        return 0

    if name == "PostCompact":
        set_pending("postcompact")
        return 0

    # UserPromptSubmit: the cost-bug guard — stat the flag, no subprocess unless set.
    if name == "UserPromptSubmit":
        if not take_pending():
            return 0
        inject_packet(name)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001 - never fatal to the runtime
        raise SystemExit(0)
