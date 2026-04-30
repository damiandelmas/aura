"""Objective registry for Aura Ether coordination."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from typing import Any

from lib import state
from lib.events import now_iso


def objectives_root() -> Path:
    return state.state_root() / "objectives"


def objective_path(objective_id: str) -> Path:
    safe = objective_id.replace("/", "_")
    return objectives_root() / f"{safe}.json"


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


def create_objective(
    objective_id: str,
    *,
    title: str | None = None,
    seats: list[str] | None = None,
    watched_signals: list[str] | None = None,
    policies: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = now_iso()
    record = {
        "schema": "aura.objective.v1",
        "objective_id": objective_id,
        "title": title or objective_id,
        "status": "active",
        "seats": sorted(set(seats or [])),
        "watched_signals": watched_signals or [
            "delivery.blocked",
            "delivery.delivered",
            "delivery.ambiguous",
            "seat.ready",
            "seat.busy",
            "receipt.created",
            "human_gate",
        ],
        "policies": {
            "non_actuating": True,
            "defer_blocked_messages": True,
            **(policies or {}),
        },
        "created_at": now,
        "updated_at": now,
    }
    _atomic_write(objective_path(objective_id), record)
    return record


def load_objective(objective_id: str) -> dict[str, Any]:
    path = objective_path(objective_id)
    if not path.exists():
        raise FileNotFoundError(f"objective not found: {objective_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_objective(record: dict[str, Any]) -> dict[str, Any]:
    record["updated_at"] = now_iso()
    _atomic_write(objective_path(record["objective_id"]), record)
    return record


def list_objectives(*, include_archived: bool = False) -> list[dict[str, Any]]:
    root = objectives_root()
    if not root.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not include_archived and record.get("status") == "archived":
            continue
        rows.append(record)
    return rows


def add_seats(objective_id: str, seats: list[str]) -> dict[str, Any]:
    record = load_objective(objective_id)
    record["seats"] = sorted(set(record.get("seats") or []) | set(seats))
    return save_objective(record)


def archive_objective(objective_id: str) -> dict[str, Any]:
    record = load_objective(objective_id)
    record["status"] = "archived"
    return save_objective(record)
