"""Shared Aura process identity helpers."""

from __future__ import annotations

import os


def current_seat_ref(default: str = "cli") -> str:
    """Return the best sender identity for the current Aura process."""
    fleet = os.environ.get("AURA_FLEET")
    seat = os.environ.get("AURA_SEAT") or os.environ.get("AURA_AGENT_NAME")
    if fleet and seat:
        return f"{fleet}:{seat}"
    if seat:
        return seat
    return default


def sender(value: str | None = None, default: str = "cli") -> str:
    """Use explicit sender when provided, otherwise infer current seat."""
    return value or current_seat_ref(default=default)
