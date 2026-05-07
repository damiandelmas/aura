"""Operator-facing dashboard identity surface."""

from __future__ import annotations

from typing import Any

from lib import seat_status


def _identity_name(status: dict[str, Any]) -> str | None:
    identity = status.get("identity")
    if isinstance(identity, dict):
        return identity.get("name")
    return status.get("identity_label")


def _identity_position(status: dict[str, Any]) -> str | None:
    identity = status.get("identity")
    if isinstance(identity, dict):
        current = identity.get("current")
        if isinstance(current, dict) and current.get("position"):
            return current.get("position")
    org = status.get("org")
    if isinstance(org, dict):
        return org.get("role")
    return None


def build_dashboard_identity(target: str, *, terminal=None) -> dict[str, Any]:
    status = seat_status.build_seat_status(target, terminal=terminal)
    if not status.get("ok"):
        return {
            "ok": False,
            "schema": "aura.dashboard_identity.v1",
            "target": target,
            "error": status.get("error") or "seat-not-found",
        }

    identity_name = _identity_name(status)
    identity_position = _identity_position(status)
    runtime = status.get("runtime") or "unknown"
    binding = status.get("runtime_session_binding") or "unknown"
    session = status.get("runtime_session_id")
    session_display = f"{binding} {session}" if session else binding
    target_ref = status.get("target") or status.get("seat_ref") or target
    compact_parts = [
        target_ref,
        status.get("seat_instance_id"),
        f"{runtime} {binding}",
        identity_name,
    ]
    compact = " | ".join(str(part) for part in compact_parts if part)

    lines = [
        f"Aura: {target_ref}",
        f"Seat: {status.get('seat') or status.get('name')}",
        f"Fleet: {status.get('fleet')}",
        f"Instance: {status.get('seat_instance_id') or 'unknown'}",
        f"Session: {session_display}",
    ]
    if identity_name or identity_position:
        identity_display = identity_name or "unknown"
        if identity_position:
            identity_display = f"{identity_display} / {identity_position}"
        lines.append(f"Identity: {identity_display}")

    return {
        "ok": True,
        "schema": "aura.dashboard_identity.v1",
        "target": target_ref,
        "fleet": status.get("fleet"),
        "seat": status.get("seat") or status.get("name"),
        "seat_instance_id": status.get("seat_instance_id"),
        "runtime": status.get("runtime"),
        "runtime_session_binding": binding,
        "runtime_session_id": session,
        "managed_state": status.get("managed_state"),
        "liveness": status.get("liveness"),
        "identity": status.get("identity"),
        "org": status.get("org"),
        "risk_flags": status.get("risk_flags") or [],
        "compact": compact,
        "lines": lines,
        "text": "\n".join(lines),
    }
