"""Agent-facing Aura map built from canonical seat status."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from lib import seat_status


def _target(row: dict[str, Any]) -> str | None:
    return row.get("target") or row.get("seat_ref")


def _slim_identity(row: dict[str, Any]) -> dict[str, Any] | None:
    identity = row.get("identity")
    if not isinstance(identity, dict):
        return None
    slim = {
        "id": identity.get("id"),
        "name": identity.get("name"),
    }
    current = identity.get("current")
    if isinstance(current, dict) and current.get("position"):
        slim["current"] = {"position": current.get("position")}
    return {key: value for key, value in slim.items() if value}


def _map_entry(row: dict[str, Any], *, include_fleet: bool = False) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "target": _target(row),
        "seat": row.get("seat") or row.get("name"),
        "managed_state": row.get("managed_state"),
        "runtime_session_binding": row.get("runtime_session_binding"),
    }
    if include_fleet:
        entry["fleet"] = row.get("fleet")
    identity = _slim_identity(row)
    if identity:
        entry["identity"] = identity
    return {key: value for key, value in entry.items() if value is not None}


def _unit_from_rows(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    product = next((row.get("desks_product") or (row.get("org") or {}).get("product") for row in rows if row.get("desks_product") or row.get("org")), None)
    unit = next((row.get("desks_unit") or (row.get("org") or {}).get("unit") for row in rows if row.get("desks_unit") or (row.get("org") or {}).get("unit")), None)
    programs = sorted({
        (row.get("org") or {}).get("program")
        for row in rows
        if isinstance(row.get("org"), dict) and (row.get("org") or {}).get("program")
    })
    if not product and not unit and not programs:
        return None
    unit_map: dict[str, Any] = {}
    if product:
        unit_map["product"] = product
    if unit:
        unit_map["unit"] = unit
    if programs:
        unit_map["programs"] = programs
    return unit_map


def _desks_root() -> Path:
    return Path(os.environ.get("DESKS_ROOT", Path.home() / ".desks")).expanduser()


def _roles_path(product: str | None) -> Path | None:
    if not product:
        return None
    root = _desks_root() / "organizations" / str(product)
    for candidate in (
        root / "current" / "roles.md",
        root / "current-roles.md",
        root / "roles.md",
    ):
        if candidate.is_file():
            return candidate
    return None


def _parse_position_notes(path: Path | None) -> dict[str, str]:
    if not path:
        return {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    notes: dict[str, str] = {}
    current: str | None = None
    buffer: list[str] = []
    for line in lines:
        if line.startswith("### "):
            if current and buffer:
                notes[current] = " ".join(part.strip() for part in buffer if part.strip())
            current = line.removeprefix("### ").strip()
            buffer = []
            continue
        if line.startswith("## "):
            if current and buffer:
                notes[current] = " ".join(part.strip() for part in buffer if part.strip())
            current = None
            buffer = []
            continue
        if current:
            buffer.append(line)
    if current and buffer:
        notes[current] = " ".join(part.strip() for part in buffer if part.strip())
    return notes


def _position_for(row: dict[str, Any]) -> str | None:
    identity = row.get("identity")
    if isinstance(identity, dict):
        current = identity.get("current")
        if isinstance(current, dict) and current.get("position"):
            return current.get("position")
    org = row.get("org")
    if isinstance(org, dict):
        return org.get("role")
    return None


def build_agent_map(target: str, *, terminal=None) -> dict[str, Any]:
    self_status = seat_status.build_seat_status(target, terminal=terminal)
    if not self_status.get("ok"):
        return {
            "ok": False,
            "schema": "aura.agent_map.v1",
            "target": target,
            "error": self_status.get("error") or "seat-not-found",
        }
    if self_status.get("managed_state") == "stopped":
        return {
            "ok": False,
            "schema": "aura.agent_map.v1",
            "target": target,
            "error": "seat-stopped",
            "managed_state": self_status.get("managed_state"),
        }

    fleet = self_status.get("fleet")
    rows = seat_status.list_seat_statuses(fleet=fleet, include_hidden=False, terminal=terminal)
    self_target = _target(self_status)
    colleagues = [
        row for row in rows
        if _target(row) != self_target
        and not row.get("hidden")
        and row.get("managed_state") not in {"stopped", "missing_pane"}
    ]
    scoped_rows = [self_status, *colleagues]
    unit = _unit_from_rows(scoped_rows)
    product = (unit or {}).get("product")
    notes_by_position = _parse_position_notes(_roles_path(product))
    wanted_positions = [_position_for(row) for row in scoped_rows]
    position_notes = {
        position: notes_by_position[position]
        for position in wanted_positions
        if position and notes_by_position.get(position)
    }
    agent_map = {
        "ok": True,
        "schema": "aura.agent_map.v1",
        "target": self_target,
        "self": _map_entry(self_status, include_fleet=True),
        "fleet": [_map_entry(row) for row in colleagues],
        "unit": unit,
        "position_notes": position_notes,
    }
    agent_map["packet"] = format_agent_map(agent_map)
    return agent_map


def _format_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _format_mapping(lines: list[str], data: dict[str, Any], *, indent: int = 0) -> None:
    prefix = " " * indent
    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f"{prefix}{key}:")
            _format_mapping(lines, value, indent=indent + 2)
        elif isinstance(value, list):
            lines.append(f"{prefix}{key}:")
            for item in value:
                if isinstance(item, dict):
                    lines.append(f"{prefix}  - {next(iter(item.keys()))}: {_format_scalar(next(iter(item.values())))}")
                    rest = dict(list(item.items())[1:])
                    if rest:
                        _format_mapping(lines, rest, indent=indent + 4)
                else:
                    lines.append(f"{prefix}  - {_format_scalar(item)}")
        else:
            lines.append(f"{prefix}{key}: {_format_scalar(value)}")


def format_agent_map(agent_map: dict[str, Any]) -> str:
    lines = ["[AURA AGENT MAP]"]
    if agent_map.get("self"):
        lines.append("self:")
        _format_mapping(lines, agent_map["self"], indent=2)
    lines.append("fleet:")
    for row in agent_map.get("fleet") or []:
        if not row:
            continue
        first_key, first_value = next(iter(row.items()))
        lines.append(f"  - {first_key}: {_format_scalar(first_value)}")
        rest = dict(list(row.items())[1:])
        if rest:
            _format_mapping(lines, rest, indent=4)
    unit = agent_map.get("unit")
    if isinstance(unit, dict) and unit:
        lines.append("unit:")
        _format_mapping(lines, unit, indent=2)
    position_notes = agent_map.get("position_notes") or {}
    if position_notes:
        lines.append("position_notes:")
        for position, note in position_notes.items():
            lines.append(f"  {position}:")
            lines.append(f"    {note}")
    lines.append("[/AURA AGENT MAP]")
    return "\n".join(lines)
