"""Canonical Aura state path helpers."""

from __future__ import annotations

import os
from pathlib import Path


DEFAULT_STATE_DIRNAME = ".aura"


def state_root() -> Path:
    configured = os.environ.get("AURA_STATE_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / DEFAULT_STATE_DIRNAME).resolve()


def registry_path() -> Path:
    configured = os.environ.get("AURA_REGISTRY_PATH")
    if configured:
        return Path(configured).expanduser().resolve()
    return state_root() / "registry" / "seats.json"


def seat_aliases_path() -> Path:
    configured = os.environ.get("AURA_SEAT_ALIASES_PATH")
    if configured:
        return Path(configured).expanduser().resolve()
    return state_root() / "registry" / "seat-aliases.json"


def fleet_registry_path() -> Path:
    configured = os.environ.get("AURA_FLEETS_PATH")
    if configured:
        return Path(configured).expanduser().resolve()
    return state_root() / "registry" / "fleets.json"


def delivery_log_path() -> Path:
    configured = os.environ.get("AURA_DELIVERY_LOG")
    if configured:
        return Path(configured).expanduser().resolve()
    return state_root() / "registry" / "deliveries.jsonl"


def seats_root() -> Path:
    return state_root() / "seats"


def seat_dir(seat: str) -> Path:
    return seats_root() / seat


def fleets_root() -> Path:
    return state_root() / "fleets"


def fleet_dir(fleet: str) -> Path:
    return fleets_root() / fleet
