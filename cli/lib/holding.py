"""Holding records for unresolved runtime bodies."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any

from lib import state


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_holding_id() -> str:
    return f"hold_{uuid.uuid4().hex[:12]}"


def records_root() -> Path:
    return state.state_root() / "holding" / "records"


def record_path(holding_id: str) -> Path:
    return records_root() / f"{holding_id}.json"


def _atomic_write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="holding-", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass


def load(holding_id: str) -> dict[str, Any] | None:
    path = record_path(holding_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def save(record: dict[str, Any]) -> dict[str, Any]:
    holding_id = str(record.get("holding_id") or "")
    if not holding_id:
        raise ValueError("holding_id is required")
    updated = {**record, "updated_at": now_iso()}
    _atomic_write(record_path(holding_id), updated)
    return updated


def list_records(
    *,
    state_filter: str | None = None,
    fleet: str | None = None,
    include_resolved: bool = False,
) -> list[dict[str, Any]]:
    root = records_root()
    if not root.exists():
        return []
    records: list[dict[str, Any]] = []
    resolved_states = {"adopted", "archived", "released"}
    include_resolved = include_resolved or bool(state_filter in resolved_states)
    for path in sorted(root.glob("hold_*.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(value, dict):
            continue
        if state_filter and value.get("state") != state_filter:
            continue
        if not include_resolved and value.get("state") in resolved_states:
            continue
        if fleet and value.get("fleet_hint") != fleet:
            continue
        records.append(value)
    records.sort(key=lambda row: row.get("updated_at") or row.get("created_at") or "")
    return records


def find_active_by_pane(pane_ref: str) -> dict[str, Any] | None:
    for record in list_records(include_resolved=False):
        if record.get("pane_ref") == pane_ref:
            return record
    return None


def create_from_candidate(candidate: dict[str, Any], *, note: str | None = None) -> dict[str, Any]:
    pane_ref = str(candidate.get("pane_ref") or "")
    if pane_ref:
        existing = find_active_by_pane(pane_ref)
        if existing:
            return existing
    now = now_iso()
    record = {
        "holding_id": new_holding_id(),
        "state": "holding",
        "source": candidate.get("source") or "tmux",
        "created_at": now,
        "updated_at": now,
        "fleet_hint": candidate.get("tmux_session") or candidate.get("fleet_hint"),
        "seat_hint": candidate.get("window_name") or candidate.get("seat_hint"),
        "pane_ref": pane_ref,
        "window_name": candidate.get("window_name"),
        "window_index": candidate.get("window_index"),
        "pane_index": candidate.get("pane_index"),
        "pane_id": candidate.get("pane_id"),
        "pane_pid": candidate.get("pane_pid"),
        "command": candidate.get("active_command") or candidate.get("command"),
        "cwd": candidate.get("cwd"),
        "runtime_hint": candidate.get("runtime_hint"),
        "runtime_session_id": None,
        "runtime_session_binding": "unbound",
        "notes": [note] if note else [],
        "resolution": None,
    }
    _atomic_write(record_path(record["holding_id"]), record)
    return record


def resolve(
    holding_id: str,
    *,
    state: str,
    target: str | None = None,
    reason: str | None = None,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    record = load(holding_id)
    if not record:
        return None
    now = now_iso()
    updated = {
        **record,
        "state": state,
        "updated_at": now,
        "resolution": {
            "state": state,
            "target": target,
            "reason": reason,
            "evidence": evidence or {},
            "resolved_at": now,
        },
    }
    _atomic_write(record_path(holding_id), updated)
    return updated
