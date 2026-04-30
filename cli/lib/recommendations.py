"""Append-only recommendation ledger for Aura Ether."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from lib import state
from lib.events import now_iso


def recommendations_path() -> Path:
    return state.state_root() / "ether" / "recommendations.jsonl"


def new_recommendation_id() -> str:
    return f"ether-rec-{uuid.uuid4().hex[:12]}"


def append_recommendation(record: dict[str, Any]) -> dict[str, Any]:
    path = recommendations_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if "schema" not in record:
        record["schema"] = "aura.ether.recommendation.v1"
    record.setdefault("recommendation_id", new_recommendation_id())
    record.setdefault("status", "open")
    record.setdefault("created_at", now_iso())
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")
    return record


def iter_recommendations(limit: int | None = None) -> list[dict[str, Any]]:
    path = recommendations_path()
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if limit is not None:
        lines = lines[-limit:]
    rows = []
    for line in lines:
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def current_recommendations(limit: int | None = None) -> list[dict[str, Any]]:
    """Return the latest ledger row for each recommendation id."""
    latest: dict[str, dict[str, Any]] = {}
    for row in iter_recommendations():
        recommendation_id = row.get("recommendation_id")
        if not recommendation_id:
            continue
        latest[recommendation_id] = row
    rows = list(latest.values())
    if limit is not None:
        rows = rows[-limit:]
    return rows


def list_recommendations(
    *,
    objective_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    rows = current_recommendations()
    if objective_id:
        rows = [row for row in rows if row.get("objective_id") == objective_id]
    if status:
        rows = [row for row in rows if row.get("status") == status]
    return rows[-limit:]


def find_open(
    *,
    objective_id: str,
    state: str | None = None,
    target: str | None = None,
    provenance_key: tuple[str, str] | None = None,
) -> dict[str, Any] | None:
    for row in reversed(current_recommendations()):
        if row.get("objective_id") != objective_id:
            continue
        if row.get("status") != "open":
            continue
        if state and row.get("state") != state:
            continue
        rec = row.get("recommendation") or {}
        if target and rec.get("target") != target:
            continue
        if provenance_key:
            key, value = provenance_key
            found = any(item.get(key) == value for item in row.get("provenance") or [])
            if not found:
                continue
        return row
    return None


def mark_matching_open(
    *,
    objective_id: str,
    state: str | None = None,
    target: str | None = None,
    status: str,
    reason: str | None = None,
) -> list[dict[str, Any]]:
    marked = []
    for row in current_recommendations():
        if row.get("objective_id") != objective_id:
            continue
        if row.get("status") != "open":
            continue
        if state and row.get("state") != state:
            continue
        rec = row.get("recommendation") or {}
        if target and rec.get("target") != target:
            continue
        updated = {
            **row,
            "status": status,
            "updated_at": now_iso(),
            "event": "status_update",
        }
        if reason:
            updated["resolution_reason"] = reason
        append_recommendation(updated)
        marked.append(updated)
    return marked


def mark_recommendation(recommendation_id: str, status: str) -> dict[str, Any] | None:
    found = None
    for row in current_recommendations():
        if row.get("recommendation_id") == recommendation_id:
            found = {**row, "status": status, "updated_at": now_iso()}
            break
    if not found:
        return None
    append_recommendation({
        **found,
        "schema": "aura.ether.recommendation.v1",
        "event": "status_update",
    })
    return found
