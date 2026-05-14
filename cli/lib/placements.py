"""Aura placement registry.

Placements are grouping/link records over logical Aura seats. They do not move
terminals and they are not routing targets.
"""

from __future__ import annotations

import json
import re
import os
import tempfile
from pathlib import Path
from typing import Any

from lib import registry, state


def placements_path() -> Path:
    return state.state_root() / "registry" / "placements.json"


def _safe_id(name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(name).strip()).strip(".-").lower()
    return slug or "placement"


def _placement_id(name: str) -> str:
    value = str(name)
    return value if value.startswith("pl_") else f"pl_{_safe_id(value)}"


def read_placements() -> dict[str, dict[str, Any]]:
    path = placements_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(key): value for key, value in data.items() if isinstance(value, dict)}


def write_placements(data: dict[str, dict[str, Any]]) -> None:
    path = placements_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="placements-", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
            f.write("\n")
        Path(tmp).replace(path)
    finally:
        try:
            Path(tmp).unlink()
        except FileNotFoundError:
            pass


def _write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}-", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
            f.write("\n")
        Path(tmp).replace(path)
    finally:
        try:
            Path(tmp).unlink()
        except FileNotFoundError:
            pass


def _canonical_member(seat_ref: str, *, role: str | None = None) -> dict[str, Any]:
    record = registry.get_agent(seat_ref)
    if not record:
        raise ValueError(f"seat not found: {seat_ref}")
    logical_ref = record.get("seat_ref") or registry.seat_ref(record.get("fleet"), record.get("name") or record.get("seat"))
    return {
        "seat_ref": logical_ref,
        "role": role,
        "logical_fleet": record.get("logical_fleet") or record.get("fleet"),
        "logical_seat": record.get("logical_name") or record.get("seat") or record.get("name"),
        "physical_fleet": record.get("physical_fleet"),
        "pane_ref": record.get("pane_ref"),
        "runtime": record.get("runtime"),
        "seat_instance_id": record.get("seat_instance_id"),
    }


def list_placements() -> list[dict[str, Any]]:
    return sorted(read_placements().values(), key=lambda row: (row.get("kind") or "", row.get("name") or ""))


def get_placement(name: str) -> dict[str, Any] | None:
    data = read_placements()
    pid = _placement_id(name)
    return data.get(pid) or next((row for row in data.values() if row.get("name") == name), None)


def add_member(
    placement: str,
    seat_ref: str,
    *,
    role: str | None = None,
    kind: str = "group",
    label: str | None = None,
    source: str = "operator",
) -> dict[str, Any]:
    data = read_placements()
    pid = _placement_id(placement)
    record = data.get(pid) or {
        "schema": "aura.placement.v1",
        "placement_id": pid,
        "kind": kind,
        "name": placement,
        "label": label or placement,
        "members": [],
        "source": source,
    }
    member = _canonical_member(seat_ref, role=role)
    members = [m for m in record.get("members", []) if m.get("seat_ref") != member["seat_ref"]]
    members.append({k: v for k, v in member.items() if v is not None})
    record["members"] = sorted(members, key=lambda m: m.get("seat_ref") or "")
    record.setdefault("kind", kind)
    record.setdefault("label", label or placement)
    record.setdefault("source", source)
    data[pid] = record
    write_placements(data)
    return record


def remove_member(placement: str, seat_ref: str) -> dict[str, Any]:
    data = read_placements()
    record = get_placement(placement)
    if not record:
        return {"ok": False, "error": f"placement not found: {placement}"}
    pid = record["placement_id"]
    resolved = registry.get_agent(seat_ref)
    canonical = (resolved or {}).get("seat_ref") or seat_ref
    before = len(record.get("members", []))
    record["members"] = [m for m in record.get("members", []) if m.get("seat_ref") != canonical]
    data[pid] = record
    write_placements(data)
    return {"ok": True, "placement": record, "removed": before - len(record.get("members", []))}


def placements_for_seat(seat_ref: str | None) -> list[dict[str, Any]]:
    if not seat_ref:
        return []
    resolved = registry.get_agent(seat_ref)
    canonical = (resolved or {}).get("seat_ref") or seat_ref
    found: list[dict[str, Any]] = []
    for record in list_placements():
        for member in record.get("members", []):
            if member.get("seat_ref") != canonical:
                continue
            found.append({
                "placement_id": record.get("placement_id"),
                "kind": record.get("kind"),
                "name": record.get("name"),
                "label": record.get("label"),
                "role": member.get("role"),
            })
    return found
