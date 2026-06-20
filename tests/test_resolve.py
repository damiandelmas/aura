"""The resolver seam — pure dispatch + the fleet-id resolver (self-registered)."""

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


def test_literal_passthrough():
    from lib import resolve
    assert resolve.resolve("plain-value") == "plain-value"
    assert resolve.resolve("placement:linear-getflex-eng") == "placement:linear-getflex-eng"


def test_unknown_scheme_passthrough_never_raises():
    from lib import resolve
    # op:// / runway:// deref is a LATER registration — today they pass through RAW.
    assert resolve.resolve("op://flex/Linear/getflex/api key") == "op://flex/Linear/getflex/api key"
    assert resolve.resolve("runway://flex/eng") == "runway://flex/eng"


def test_non_string_passthrough():
    from lib import resolve
    assert resolve.resolve(None) is None
    assert resolve.resolve(42) == 42


def test_register_and_dispatch():
    from lib import resolve
    resolve.register("test-scheme", lambda path, ctx: {"got": path, "ctx": ctx})
    assert resolve.resolve("test-scheme://abc", {"k": 1}) == {"got": "abc", "ctx": {"k": 1}}
    assert "test-scheme" in resolve.registered_schemes()


def test_resolve_map_over_config_blob():
    from lib import resolve
    resolve.register("echo", lambda path, ctx: f"E:{path}")
    blob = {"A": "echo://x", "B": "literal", "C": ["echo://y", "lit2"]}
    out = resolve.resolve_map(blob)
    assert out == {"A": "E:x", "B": "literal", "C": ["E:y", "lit2"]}
    assert resolve.resolve_map(None) == {}


def test_fleet_id_resolver_self_registered(monkeypatch):
    from lib import resolve, fleets  # importing fleets self-registers fleet-id
    assert "fleet-id" in resolve.registered_schemes()

    monkeypatch.setattr(fleets, "read_fleets",
                        lambda: {"f_live": {"fleet_id": "f_live", "current_name": "flexchat-sales"}})
    live = resolve.resolve("fleet-id://f_live")
    assert live == {"fleet_id": "f_live", "name": "flexchat-sales", "status": "live"}

    dead = resolve.resolve("fleet-id://f_gone")
    assert dead["status"] == "stale" and dead["name"] is None and dead["fleet_id"] == "f_gone"
