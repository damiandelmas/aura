"""Small Desks session-history bridge for Aura session binding.

Aura owns live fleet/seat orchestration. Desks owns identity continuity. The
only write Aura performs here is appending an already-bound runtime session id
to the Desks identity's canonical `sessions.json` list.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


def _desks_root() -> Path:
    return Path(os.environ.get("DESKS_ROOT", Path.home() / ".desks")).expanduser()


def append_identity_session(
    identity_id: str | None,
    session_id: str | None,
    *,
    desks_root: str | Path | None = None,
) -> dict:
    """Append `session_id` to `~/.desks/identities/<id>/sessions.json`.

    The file is intentionally kept as a JSON array of strings because that is
    the current Desks identity contract created by the profile merge.
    """
    if not identity_id:
        return {"ok": False, "skipped": True, "reason": "missing-identity-id"}
    if not session_id:
        return {"ok": False, "skipped": True, "reason": "missing-session-id"}

    root = Path(desks_root).expanduser() if desks_root is not None else _desks_root()
    identity_dir = root / "identities" / identity_id
    if not identity_dir.is_dir():
        return {
            "ok": False,
            "skipped": True,
            "reason": "identity-dir-missing",
            "identity_id": identity_id,
        }

    path = identity_dir / "sessions.json"
    try:
        if path.exists():
            current = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(current, list):
                return {
                    "ok": False,
                    "skipped": True,
                    "reason": "sessions-json-not-list",
                    "identity_id": identity_id,
                    "path": str(path),
                }
        else:
            current = []
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "ok": False,
            "skipped": True,
            "reason": "sessions-json-read-failed",
            "detail": str(exc),
            "identity_id": identity_id,
            "path": str(path),
        }

    if session_id in current:
        return {
            "ok": True,
            "changed": False,
            "identity_id": identity_id,
            "session_id": session_id,
            "path": str(path),
        }

    current.append(session_id)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
        tmp.replace(path)
    except OSError as exc:
        return {
            "ok": False,
            "skipped": True,
            "reason": "sessions-json-write-failed",
            "detail": str(exc),
            "identity_id": identity_id,
            "path": str(path),
        }

    return {
        "ok": True,
        "changed": True,
        "identity_id": identity_id,
        "session_id": session_id,
        "path": str(path),
    }
