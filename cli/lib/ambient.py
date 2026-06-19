"""Ambient Aura context packets for runtime hooks."""

from __future__ import annotations

import os
from typing import Any

from lib import reports, seat_status
from lib import agent_map as agent_map_lib


def _target(row: dict[str, Any]) -> str | None:
    return row.get("target") or row.get("seat_ref")


def _is_routable(row: dict[str, Any]) -> bool:
    return row.get("liveness") == "alive" and row.get("managed_state") not in {"missing_pane", "stopped"}


def _row_matches_pane(row: dict[str, Any], pane: str | None) -> bool:
    if not pane:
        return False
    for key in ("pane_ref", "terminal_ref", "backend_ref"):
        value = str(row.get(key) or "")
        if value == pane or value.endswith(f":{pane}"):
            return True
    return False


def _identity(row: dict[str, Any]) -> dict[str, Any] | None:
    identity = row.get("identity")
    if isinstance(identity, dict):
        result = {
            "id": identity.get("id"),
            "name": identity.get("name"),
            "current": identity.get("current") if isinstance(identity.get("current"), dict) else {},
        }
        return {key: value for key, value in result.items() if value}
    name = row.get("identity_label")
    if not name:
        return None
    return {"name": name}


def _position(row: dict[str, Any]) -> str | None:
    identity = row.get("identity")
    if isinstance(identity, dict):
        current = identity.get("current")
        if isinstance(current, dict) and current.get("position"):
            return current.get("position")
    org = row.get("org")
    if isinstance(org, dict):
        return org.get("role")
    return None


def _resolve_self_target(*, terminal=None) -> dict[str, Any]:
    context = reports.infer_context()
    env_fleet = context.get("fleet")
    env_seat = context.get("seat")
    env_target = f"{env_fleet}:{env_seat}" if env_fleet and env_seat else None
    rows = seat_status.list_seat_statuses(include_hidden=True, terminal=terminal)

    pane_matches = [row for row in rows if _row_matches_pane(row, context.get("pane"))]
    live_pane_matches = [row for row in pane_matches if _is_routable(row)]
    if len(live_pane_matches) == 1:
        return {"ok": True, "target": _target(live_pane_matches[0]), "source": "tmux-pane"}
    if len(live_pane_matches) > 1:
        return {
            "ok": False,
            "error": "tmux-pane-mapped-to-multiple-live-seats",
            "reason": "current tmux pane is recorded on multiple live Aura seats; repair registry mapping",
            "match_count": len(live_pane_matches),
        }

    if env_target:
        env_match = next((row for row in rows if _target(row) == env_target), None)
        if env_match and _is_routable(env_match):
            return {"ok": True, "target": env_target, "source": "aura-env"}

    session_id = context.get("runtime_session_id") or context.get("session_id")
    if session_id:
        matches = [
            row for row in rows
            if session_id in {row.get("runtime_session_id"), row.get("session_id")}
        ]
        live_matches = [row for row in matches if _is_routable(row)]
        if len(live_matches) == 1:
            return {"ok": True, "target": _target(live_matches[0]), "source": "runtime-session"}
        if len(live_matches) > 1:
            return {
                "ok": False,
                "error": "runtime-session-mapped-to-multiple-live-seats",
                "reason": "current runtime session is recorded on multiple live Aura seats; repair session binding",
                "match_count": len(live_matches),
            }
        if matches:
            return {
                "ok": False,
                "error": "self-target-not-live",
                "reason": "runtime session matched Aura rows, but none are live/routable",
                "match_count": len(matches),
            }

    if env_target:
        return {
            "ok": False,
            "error": "self-target-not-live",
            "reason": "AURA_FLEET/AURA_SEAT named a seat, but it is not live/routable",
        }
    return {"ok": False, "error": "self-target-not-resolved"}


def _row_packet(row: dict[str, Any], *, role_summaries: dict[str, str]) -> dict[str, Any]:
    position = _position(row)
    packet: dict[str, Any] = {
        "target": _target(row),
        "fleet": row.get("fleet"),
        "seat": row.get("seat") or row.get("name"),
        "identity": _identity(row),
        "identity_current_position": position,
        "role_summary": role_summaries.get(position or ""),
        "runtime_session_binding": row.get("runtime_session_binding"),
        "managed_state": row.get("managed_state"),
    }
    return {key: value for key, value in packet.items() if value is not None}


def _seat_label(row: dict[str, Any]) -> str:
    return str(row.get("seat") or row.get("name") or _target(row) or "unknown")


def _fleet_seat_list(rows: list[dict[str, Any]]) -> str:
    seats = [_seat_label(row) for row in rows if isinstance(row, dict)]
    return ", ".join(seats) if seats else "none"


def _format_ambient(packet: dict[str, Any]) -> str:
    lines = ["[AURA AMBIENT]"]
    self_packet = packet.get("self")
    fleet = packet.get("fleet") if isinstance(packet.get("fleet"), list) else []
    if isinstance(self_packet, dict):
        seat = _seat_label(self_packet)
        fleet_name = self_packet.get("fleet") or "unknown"
        target = self_packet.get("target") or f"{fleet_name}:{seat}"
        lines.extend([
            "AURA",
            "",
            f"You are {seat}.",
            f"You are in the {fleet_name} fleet.",
            f"Your target is {target}.",
            f"The other seats in your fleet are: {_fleet_seat_list(fleet)}.",
        ])
    lines.append("[/AURA AMBIENT]")
    return "\n".join(lines)


def build_ambient(target: str, *, terminal=None, refresh: bool = False) -> dict[str, Any]:
    if target == "self":
        resolved = _resolve_self_target(terminal=terminal)
        target = resolved.get("target") or ""
        if not resolved.get("ok") or not target:
            return {
                "ok": False,
                "schema": "aura.ambient.v1",
                "target": "self",
                "error": resolved.get("error") or "self-target-not-resolved",
                "reason": resolved.get("reason"),
                "match_count": resolved.get("match_count"),
            }

    status = seat_status.build_seat_status(target, terminal=terminal)
    if not status.get("ok"):
        return {
            "ok": False,
            "schema": "aura.ambient.v1",
            "target": target,
            "error": status.get("error") or "seat-not-found",
        }

    map_result = agent_map_lib.build_agent_map(target, terminal=terminal, require_routable=False)
    role_summaries = map_result.get("position_notes") if map_result.get("ok") else {}
    role_summaries = role_summaries if isinstance(role_summaries, dict) else {}

    fleet_rows = [
        row for row in seat_status.list_seat_statuses(fleet=status.get("fleet"), include_hidden=False, terminal=terminal)
        if _target(row) != _target(status)
        and not row.get("hidden")
        and row.get("managed_state") not in {"stopped", "missing_pane"}
    ]
    unit = map_result.get("unit") if map_result.get("ok") else None
    warnings = list(status.get("risk_flags") or [])
    if os.environ.get("AURA_FLEET") and os.environ.get("AURA_FLEET") != status.get("fleet"):
        warnings.append("env-fleet-mismatch")
    if (os.environ.get("AURA_SEAT") or os.environ.get("AURA_AGENT_NAME")) and (
        os.environ.get("AURA_SEAT") or os.environ.get("AURA_AGENT_NAME")
    ) != (status.get("seat") or status.get("name")):
        warnings.append("env-seat-mismatch")

    packet = {
        "ok": True,
        "schema": "aura.ambient.v1",
        "target": _target(status),
        "refresh": bool(refresh),
        "self": {
            **_row_packet(status, role_summaries=role_summaries),
            "seat_instance_id": status.get("seat_instance_id"),
            "runtime_session_id": status.get("runtime_session_id"),
        },
        "fleet": [_row_packet(row, role_summaries=role_summaries) for row in fleet_rows],
        "unit": unit,
        "warnings": sorted(set(warnings)),
    }
    packet["text"] = _format_ambient(packet)
    return packet
