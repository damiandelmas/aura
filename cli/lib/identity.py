"""Shared Aura process identity helpers."""

from __future__ import annotations

import os
import re


_SERVICE_SENDER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


def current_seat_ref(default: str | None = "cli") -> str | None:
    """Return the best sender identity for the current Aura process."""
    fleet = os.environ.get("AURA_FLEET")
    seat = os.environ.get("AURA_SEAT") or os.environ.get("AURA_AGENT_NAME")
    if fleet and seat:
        return f"{fleet}:{seat}"
    if seat:
        return seat

    try:
        from lib import reports

        context = reports.infer_context()
    except Exception:
        context = {}
    fleet = context.get("fleet")
    seat = context.get("seat")
    if fleet and seat:
        return f"{fleet}:{seat}"
    if seat:
        return str(seat)
    return default


def sender(value: str | None = None, default: str | None = "cli") -> str | None:
    """Use explicit sender when provided, otherwise infer current seat."""
    return value or current_seat_ref(default=default)


def managed_sender(value: str | None = None, default: str | None = None) -> str | None:
    """Return a canonical managed Aura sender ref, or None when unresolved.

    Semantic Aura messages require accountable seat provenance. Raw tmux window
    labels such as ``fleet:bash`` are not enough unless they resolve to a
    current registry row.
    """
    candidate = sender(value, default=default)
    if not candidate:
        return None
    try:
        from lib import registry

        record = registry.get_agent(candidate)
    except Exception:
        record = None
    if not record:
        return None
    return record.get("seat_ref") or registry.seat_ref(record.get("fleet"), record.get("name") or record.get("seat"))


def service_sender(value: str | None) -> str | None:
    """Return canonical service provenance for explicit harness senders."""
    raw = (value or "").strip()
    if raw.startswith("service:"):
        raw = raw.split(":", 1)[1]
    if not raw or not _SERVICE_SENDER_RE.fullmatch(raw):
        return None
    return f"service:{raw}"


def resolve_semantic_sender(
    value: str | None = None,
    *,
    service: str | None = None,
    default: str | None = None,
) -> dict:
    """Resolve semantic message provenance.

    Normal agent messages must resolve to a managed Aura seat. Explicit service
    messages are allowed only through the service channel so scripts do not need
    to pretend they are seats.
    """
    if value and service:
        return {
            "ok": False,
            "reason": "sender-conflict",
            "error": "use either --as or --as-service, not both",
        }
    if service:
        sender = service_sender(service)
        if not sender:
            return {
                "ok": False,
                "reason": "invalid-service-sender",
                "error": "service sender must match [A-Za-z0-9][A-Za-z0-9_.-]{0,127}",
            }
        return {"ok": True, "sender": sender, "sender_kind": "service"}

    sender = managed_sender(value, default=default)
    if sender:
        return {"ok": True, "sender": sender, "sender_kind": "seat"}
    return {
        "ok": False,
        "reason": "sender-not-inferred",
        "error": "could not resolve a managed Aura sender; register/adopt this terminal, pass --as fleet:seat for a managed seat, or use --as-service for explicit harness traffic",
    }
