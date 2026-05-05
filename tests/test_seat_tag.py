"""Tests for `aura seat tag` (plan 011 phase 1)."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


@pytest.fixture
def aura_state(monkeypatch, tmp_path):
    state_root = tmp_path / ".aura"
    state_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("AURA_STATE_DIR", str(state_root))
    monkeypatch.setenv("AURA_FLEET", "test-fleet")
    monkeypatch.delenv("DESKS_CALLER", raising=False)
    monkeypatch.delenv("DESKS_REHOME", raising=False)
    return state_root


def _seed_seat(target="test-fleet:engineer", **extras):
    from lib import registry

    fleet, seat = target.split(":", 1)
    record = {
        "name": seat,
        "seat": seat,
        "fleet": fleet,
        "runtime": "codex",
        "backend": "tmux",
        "pane_ref": f"tmux:{fleet}:%48",
        "status": "alive",
        "registered": True,
        **extras,
    }
    return registry.upsert_agent(record)


def test_tag_writes_allowed_keys_and_returns_updated_record(aura_state):
    from commands import seat as seat_cmd
    from lib import registry

    _seed_seat()

    args = argparse.Namespace(
        seat_action="tag",
        target="test-fleet:engineer",
        set=["desks_identity_id=r_6be5b613"],
        unset=[],
    )
    result = seat_cmd._tag(args, registry)

    assert result["ok"] is True
    assert result["changed"] == ["desks_identity_id"]
    assert result["record"]["desks_identity_id"] == "r_6be5b613"


def test_tag_unset_removes_key_when_value_empty(aura_state):
    from commands import seat as seat_cmd
    from lib import registry

    _seed_seat(desks_identity_id="r_old")

    args = argparse.Namespace(
        seat_action="tag",
        target="test-fleet:engineer",
        set=["desks_identity_id="],
        unset=[],
    )
    result = seat_cmd._tag(args, registry)

    assert result["ok"] is True
    assert "desks_identity_id" not in result["record"]
    assert result["changed"] == ["desks_identity_id"]


def test_tag_explicit_unset_flag_removes_key(aura_state):
    from commands import seat as seat_cmd
    from lib import registry

    _seed_seat(flex_project_root="/home/axp/projects/flexsearch")

    args = argparse.Namespace(
        seat_action="tag",
        target="test-fleet:engineer",
        set=[],
        unset=["flex_project_root"],
    )
    result = seat_cmd._tag(args, registry)

    assert result["ok"] is True
    assert "flex_project_root" not in result["record"]


def test_tag_rejects_key_outside_allowlist(aura_state):
    from commands import seat as seat_cmd
    from lib import registry

    _seed_seat()

    args = argparse.Namespace(
        seat_action="tag",
        target="test-fleet:engineer",
        set=["arbitrary_key=value"],
        unset=[],
    )
    result = seat_cmd._tag(args, registry)

    assert result["ok"] is False
    assert result["error"].startswith("key-not-in-allowlist")
    # registry must not be mutated.
    record = registry.get_agent("test-fleet:engineer")
    assert "arbitrary_key" not in record


def test_tag_rejects_target_without_registry_row(aura_state):
    from commands import seat as seat_cmd
    from lib import registry

    args = argparse.Namespace(
        seat_action="tag",
        target="test-fleet:nope",
        set=["desks_identity_id=r_x"],
        unset=[],
    )
    result = seat_cmd._tag(args, registry)

    assert result["ok"] is False
    assert result["error"] == "no-such-seat"


def test_tag_appends_session_ledger_event_with_before_after(aura_state):
    from commands import seat as seat_cmd
    from lib import registry, session_ledger

    _seed_seat(desks_identity_id="r_old")

    args = argparse.Namespace(
        seat_action="tag",
        target="test-fleet:engineer",
        set=["desks_identity_id=r_new"],
        unset=[],
    )
    seat_cmd._tag(args, registry)

    rows = session_ledger.iter_records()
    matches = [r for r in rows if r.get("event") == "seat_metadata_tagged"]
    assert matches, "expected a seat_metadata_tagged event"
    row = matches[-1]
    assert row["seat_ref"] == "test-fleet:engineer"
    evidence = row.get("evidence", {})
    assert evidence.get("set_keys") == ["desks_identity_id"]
    assert evidence.get("changed_keys") == ["desks_identity_id"]
    assert evidence.get("before") == {"desks_identity_id": "r_old"}
    assert evidence.get("after") == {"desks_identity_id": "r_new"}


def test_tag_is_idempotent_on_no_change(aura_state):
    from commands import seat as seat_cmd
    from lib import registry, session_ledger

    _seed_seat(desks_identity_id="r_same")

    args = argparse.Namespace(
        seat_action="tag",
        target="test-fleet:engineer",
        set=["desks_identity_id=r_same"],
        unset=[],
    )
    result = seat_cmd._tag(args, registry)

    assert result["ok"] is True
    assert result["changed"] == []
    rows = session_ledger.iter_records()
    matches = [r for r in rows if r.get("event") == "seat_metadata_tagged"]
    # The tag still wrote a ledger row for audit trail, but changed_keys is empty.
    assert matches, "ledger row should still be appended for audit purposes"
    assert matches[-1]["evidence"]["changed_keys"] == []


def test_tag_records_caller_from_environment(monkeypatch, aura_state):
    from commands import seat as seat_cmd
    from lib import registry, session_ledger

    monkeypatch.setenv("DESKS_CALLER", "desks-resolve")
    _seed_seat()

    args = argparse.Namespace(
        seat_action="tag",
        target="test-fleet:engineer",
        set=["desks_identity_id=r_6be5b613"],
        unset=[],
    )
    seat_cmd._tag(args, registry)

    rows = session_ledger.iter_records()
    matches = [r for r in rows if r.get("event") == "seat_metadata_tagged"]
    assert matches[-1]["evidence"]["caller"] == "desks-resolve"


def test_tag_rehome_flag_recorded_in_evidence(monkeypatch, aura_state):
    from commands import seat as seat_cmd
    from lib import registry, session_ledger

    monkeypatch.setenv("DESKS_CALLER", "desks-resolve")
    monkeypatch.setenv("DESKS_REHOME", "true")
    _seed_seat()

    args = argparse.Namespace(
        seat_action="tag",
        target="test-fleet:engineer",
        set=["desks_identity_id=r_6be5b613"],
        unset=[],
    )
    seat_cmd._tag(args, registry)

    rows = session_ledger.iter_records()
    matches = [r for r in rows if r.get("event") == "seat_metadata_tagged"]
    assert matches[-1]["evidence"]["rehome"] is True


def test_tag_rejects_malformed_set_pair(aura_state):
    from commands import seat as seat_cmd
    from lib import registry

    _seed_seat()

    args = argparse.Namespace(
        seat_action="tag",
        target="test-fleet:engineer",
        set=["no_equals_sign"],
        unset=[],
    )
    result = seat_cmd._tag(args, registry)
    assert result["ok"] is False
    assert result["error"] == "malformed-set-pair"

    args = argparse.Namespace(
        seat_action="tag",
        target="test-fleet:engineer",
        set=["=missing-key"],
        unset=[],
    )
    result = seat_cmd._tag(args, registry)
    assert result["ok"] is False
    assert result["error"] == "malformed-set-pair"


def test_tag_does_not_mutate_routing_fields(aura_state):
    from commands import seat as seat_cmd
    from lib import registry

    seeded = _seed_seat()
    original_pane = seeded["pane_ref"]

    args = argparse.Namespace(
        seat_action="tag",
        target="test-fleet:engineer",
        set=["desks_identity_id=r_6be5b613"],
        unset=[],
    )
    result = seat_cmd._tag(args, registry)

    assert result["ok"] is True
    assert result["record"]["pane_ref"] == original_pane
    assert result["record"]["fleet"] == "test-fleet"
    assert result["record"]["seat"] == "engineer"
