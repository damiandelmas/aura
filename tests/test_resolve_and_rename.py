"""M1+M3 adversarial tests for the locked identity-resolution rewrite.

Covers resolve_live (physical, alias-blind), strict same-live-incarnation,
rename distinct-pane rejection, get_agent alias back-compat, and the
physical-only _canonical_bind_target.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


def test_resolve_live_never_follows_alias(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from lib import registry

    registry.upsert_agent({
        "name": "A",
        "fleet": "fleet-a",
        "runtime": "codex",
        "seat_instance_id": "si_a",
        "pane_ref": "tmux:fleet-a:%100",
    })
    registry.upsert_agent({
        "name": "B",
        "fleet": "fleet-a",
        "runtime": "codex",
        "seat_instance_id": "si_b",
        "pane_ref": "tmux:fleet-a:%200",
    })
    registry.add_alias("fleet-a:A", "fleet-a:B", reason="rename")

    # A's row still exists -> resolve_live returns A, never B.
    row = registry.resolve_live("fleet-a:A")
    assert row is not None
    assert row["name"] == "A"
    assert row["seat_instance_id"] == "si_a"

    # Remove A's row; resolve_live must NOT follow the alias to B.
    registry.remove_agent("A", fleet="fleet-a")
    assert registry.resolve_live("fleet-a:A") is None


def test_resolve_live_fleet_explicit_no_namescan(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from lib import registry

    registry.upsert_agent({
        "name": "x",
        "fleet": "fleet-b",
        "runtime": "codex",
        "pane_ref": "tmux:fleet-b:%10",
    })

    # Explicit fleet that has no matching row -> None, no name-scan fallback.
    assert registry.resolve_live("fleet-a:x") is None
    assert registry.resolve_live("x", fleet="fleet-a") is None
    # Sanity: the correct fleet does resolve.
    assert registry.resolve_live("fleet-b:x") is not None


def test_resolve_live_ambiguous_returns_none(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    # current_fleet prefers neither fleet (third, unrelated fleet).
    monkeypatch.setenv("AURA_FLEET", "fleet-c")
    from lib import registry

    registry.upsert_agent({
        "name": "dup",
        "fleet": "fleet-a",
        "runtime": "codex",
        "pane_ref": "tmux:fleet-a:%1",
    })
    registry.upsert_agent({
        "name": "dup",
        "fleet": "fleet-b",
        "runtime": "codex",
        "pane_ref": "tmux:fleet-b:%2",
    })

    assert registry.resolve_live("dup") is None


def test_same_live_incarnation_requires_si_and_pane(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from lib import registry

    base = {"seat_instance_id": "si_1", "pane_ref": "tmux:f:%1"}

    # same si + same pane -> True
    assert registry._same_live_incarnation(dict(base), dict(base)) is True
    # same si, different pane -> False
    assert registry._same_live_incarnation(
        dict(base),
        {"seat_instance_id": "si_1", "pane_ref": "tmux:f:%2"},
    ) is False
    # si only (no pane) -> False
    assert registry._same_live_incarnation(
        {"seat_instance_id": "si_1"},
        {"seat_instance_id": "si_1"},
    ) is False
    # missing rows -> False
    assert registry._same_live_incarnation(None, dict(base)) is False


def test_rename_rejects_distinct_pane_same_si(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from lib import registry

    registry.upsert_agent({
        "name": "operator",
        "fleet": "aura-refresh-test",
        "runtime": "codex",
        "seat_instance_id": "si_same",
        "pane_ref": "tmux:aura-refresh-test:%341",
    })
    registry.upsert_agent({
        "name": "pilot",
        "fleet": "aura-refresh-test",
        "runtime": "codex",
        "seat_instance_id": "si_same",
        "pane_ref": "tmux:aura-refresh-test:%342",
    })

    result = registry.rename_agent("aura-refresh-test:operator", new_name="pilot")

    assert result["ok"] is False
    assert result["reason"] == "target-registry-exists"
    assert set(registry.read_registry().keys()) == {
        "aura-refresh-test:operator",
        "aura-refresh-test:pilot",
    }


def test_get_agent_still_follows_alias(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from lib import registry

    registry.upsert_agent({
        "name": "new",
        "fleet": "unit-fleet",
        "runtime": "codex",
        "pane_ref": "tmux:unit-fleet:%5",
    })
    registry.add_alias("unit-fleet:old", "unit-fleet:new", reason="rename")

    resolved = registry.get_agent("unit-fleet:old")
    assert resolved is not None
    assert resolved["name"] == "new"
    assert resolved["resolved_from"] == "unit-fleet:old"
    assert resolved["alias_chain"] == ["unit-fleet:old"]


def test_canonical_bind_target_physical_only(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from lib import registry
    from commands import sessions

    # Stale alias old->new; only new has a live row.
    registry.upsert_agent({
        "name": "new",
        "fleet": "bind-fleet",
        "runtime": "codex",
        "pane_ref": "tmux:bind-fleet:%9",
    })
    registry.add_alias("bind-fleet:old", "bind-fleet:new", reason="rename")

    # Binding the stale name resolves physically only: no row -> previous None.
    fleet, seat, previous, alias_chain = sessions._canonical_bind_target(
        registry, fleet="bind-fleet", seat="old"
    )
    assert fleet == "bind-fleet"
    assert seat == "old"
    assert previous is None
    assert alias_chain == []

    # Binding the live name returns its row, still no alias chain.
    fleet, seat, previous, alias_chain = sessions._canonical_bind_target(
        registry, fleet="bind-fleet", seat="new"
    )
    assert previous is not None
    assert previous["name"] == "new"
    assert alias_chain == []
