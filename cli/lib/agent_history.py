"""Derived package-agent history projection."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lib import agent_packages, registry, session_ledger, state


SCHEMA = "aura.agent_history.v1"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _agent_ref(record: dict[str, Any]) -> str | None:
    if record.get("seat_ref"):
        return str(record["seat_ref"])
    seat = record.get("seat") or record.get("name")
    if not seat:
        return None
    fleet = record.get("fleet")
    return f"{fleet}:{seat}" if fleet else str(seat)


def _session_id(record: dict[str, Any]) -> str | None:
    value = record.get("runtime_session_id") or record.get("session_id")
    return str(value) if value else None


def _keeper_thread_ids() -> set[str]:
    root = state.state_root() / "keeper-jobs"
    if not root.is_dir():
        return set()
    thread_ids: set[str] = set()
    for result_path in root.glob("memory.*/result.json"):
        try:
            payload = json.loads(result_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        for key in ("thread_id", "keeper_thread_id"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                thread_ids.add(value.strip())
    return thread_ids


def _is_keeper_session(record: dict[str, Any], keeper_thread_ids: set[str]) -> bool:
    session_id = _session_id(record)
    return bool(session_id and session_id in keeper_thread_ids)


def _matches_agent(record: dict[str, Any] | None, agent_id: str) -> bool:
    if not isinstance(record, dict):
        return False
    if record.get("agent_package_id") == agent_id:
        return True
    return record.get("identity_provider") == "aura-agent" and record.get("identity_id") == agent_id


def _row_matches_agent(row: dict[str, Any], agent_id: str) -> bool:
    if _matches_agent(row, agent_id):
        return True
    for key in ("before", "after"):
        if _matches_agent(row.get(key), agent_id):
            return True
    return False


def _merged_row(row: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    before = row.get("before")
    after = row.get("after")
    if isinstance(before, dict):
        merged.update(before)
    if isinstance(after, dict):
        merged.update(after)
    merged.update({key: value for key, value in row.items() if key not in {"before", "after"}})
    return merged


def _entry(record: dict[str, Any], *, event: str | None = None, timestamp: str | None = None) -> dict[str, Any]:
    data = {
        "ref": _agent_ref(record),
        "session_id": _session_id(record),
        "event": event,
        "timestamp": timestamp,
        "runtime": record.get("runtime"),
        "cwd": record.get("cwd") or record.get("runtime_session_cwd") or record.get("workdir"),
        "aura_launch_id": record.get("aura_launch_id"),
        "seat_instance_id": record.get("seat_instance_id"),
    }
    return {key: value for key, value in data.items() if value not in (None, "")}


def _dedupe_history(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[tuple[str | None, str | None, str | None], dict[str, Any]] = {}
    for entry in entries:
        key = (entry.get("ref"), entry.get("session_id"), entry.get("event"))
        previous = deduped.get(key)
        if previous is None or str(entry.get("timestamp") or "") >= str(previous.get("timestamp") or ""):
            deduped[key] = entry
    return sorted(deduped.values(), key=lambda item: (str(item.get("timestamp") or ""), str(item.get("ref") or "")))


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass


def build(ref: str) -> dict[str, Any]:
    agent = agent_packages.resolve(ref)
    agent_id = str(agent["agent_id"])
    keeper_thread_ids = _keeper_thread_ids()

    current = []
    for key, row in registry.read_registry().items():
        if not _matches_agent(row, agent_id):
            continue
        if _is_keeper_session(row, keeper_thread_ids):
            continue
        entry = _entry({**row, "seat_ref": row.get("seat_ref") or key})
        if entry:
            current.append(entry)

    history = []
    for row in session_ledger.iter_records():
        if not _row_matches_agent(row, agent_id):
            continue
        merged = _merged_row(row)
        if _is_keeper_session(merged, keeper_thread_ids):
            continue
        history.append(_entry(merged, event=row.get("event"), timestamp=row.get("timestamp")))

    return {
        "schema": SCHEMA,
        "identity": agent_id,
        "generated_at": now_iso(),
        "current": sorted(current, key=lambda item: (str(item.get("ref") or ""), str(item.get("session_id") or ""))),
        "history": _dedupe_history(history),
    }


def write(ref: str) -> Path:
    agent = agent_packages.resolve(ref)
    path = Path(agent["root"]) / "aura.json"
    _atomic_write_json(path, build(ref))
    return path
