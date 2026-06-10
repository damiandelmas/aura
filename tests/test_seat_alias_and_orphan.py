"""M5 operator surface: seat alias ls/rm + live-born-pane-without-row flag."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


@pytest.fixture
def aura_state(monkeypatch, tmp_path):
    state_root = tmp_path / ".aura"
    desks_root = tmp_path / ".desks"
    state_root.mkdir(parents=True, exist_ok=True)
    desks_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("AURA_STATE_DIR", str(state_root))
    monkeypatch.setenv("DESKS_ROOT", str(desks_root))
    monkeypatch.setenv("AURA_FLEET", "runway-engineering")
    return state_root


def _alias_args(alias_action, **kw):
    base = {
        "seat_action": "alias",
        "alias_action": alias_action,
        "source": None,
        "target": None,
        "fleet": None,
        "confirm": False,
        "dry_run": False,
    }
    base.update(kw)
    return argparse.Namespace(**base)


# ---------------------------------------------------------------------------
# alias ls
# ---------------------------------------------------------------------------

def test_alias_ls_empty(aura_state):
    from commands import seat

    result = seat.run(_alias_args("ls"))
    assert result["ok"] is True
    assert result["aliases"] == []
    assert result["count"] == 0


def test_alias_ls_filters(aura_state):
    from commands import seat
    from lib import registry

    registry.add_alias("fleet-a:old", "fleet-a:new", reason="rename")
    registry.add_alias("fleet-a:older", "fleet-a:new", reason="rename")
    registry.add_alias("fleet-b:gone", "fleet-b:here", reason="rename")

    # No filter -> all three.
    everything = seat.run(_alias_args("ls"))
    assert everything["count"] == 3
    # sorted by source
    assert [r["source"] for r in everything["aliases"]] == [
        "fleet-a:old",
        "fleet-a:older",
        "fleet-b:gone",
    ]

    by_source = seat.run(_alias_args("ls", source="fleet-a:old"))
    assert by_source["count"] == 1
    assert by_source["aliases"][0]["target"] == "fleet-a:new"

    by_target = seat.run(_alias_args("ls", target="fleet-a:new"))
    assert {r["source"] for r in by_target["aliases"]} == {"fleet-a:old", "fleet-a:older"}

    by_fleet = seat.run(_alias_args("ls", fleet="fleet-b"))
    assert by_fleet["count"] == 1
    assert by_fleet["aliases"][0]["source"] == "fleet-b:gone"


def test_alias_ls_schema_tolerant_missing_fields(aura_state):
    from commands import seat
    from lib import registry

    # Write a deliberately minimal/odd alias ledger that lacks reason/created_at
    # and carries an extra (optional) breadcrumb. ls must not require any of them.
    registry.write_aliases({
        "fleet-a:old": {"source": "fleet-a:old", "target": "fleet-a:new"},
        "fleet-a:legacy": {
            "target": "fleet-a:new",
            "retired_occupant": "si_abc123",
        },
    })

    result = seat.run(_alias_args("ls"))
    assert result["ok"] is True
    assert result["count"] == 2
    by_source = {r["source"]: r for r in result["aliases"]}
    assert by_source["fleet-a:old"]["target"] == "fleet-a:new"
    assert by_source["fleet-a:old"]["reason"] is None
    assert by_source["fleet-a:old"]["created_at"] is None
    # optional breadcrumb is surfaced only when present
    assert by_source["fleet-a:legacy"].get("retired_occupant") == "si_abc123"
    assert "retired_occupant" not in by_source["fleet-a:old"]


# ---------------------------------------------------------------------------
# alias rm
# ---------------------------------------------------------------------------

def test_alias_rm_requires_confirm(aura_state):
    from commands import seat
    from lib import registry

    registry.add_alias("fleet-a:old", "fleet-a:new", reason="rename")

    result = seat.run(_alias_args("rm", source="fleet-a:old"))
    assert result["ok"] is True
    assert result["dry_run"] is True
    assert result["removed"] is False
    # ledger untouched
    assert "fleet-a:old" in registry.read_aliases()


def test_alias_rm_dry_run_no_write(aura_state):
    from commands import seat
    from lib import registry

    registry.add_alias("fleet-a:old", "fleet-a:new", reason="rename")

    # Even with --confirm, --dry-run must not write.
    result = seat.run(_alias_args("rm", source="fleet-a:old", confirm=True, dry_run=True))
    assert result["ok"] is True
    assert result["dry_run"] is True
    assert result["removed"] is False
    assert "fleet-a:old" in registry.read_aliases()


def test_alias_rm_removes(aura_state):
    from commands import seat
    from lib import registry

    registry.add_alias("fleet-a:old", "fleet-a:new", reason="rename")
    registry.add_alias("fleet-a:keep", "fleet-a:new", reason="rename")

    result = seat.run(_alias_args("rm", source="fleet-a:old", confirm=True))
    assert result["ok"] is True
    assert result["dry_run"] is False
    assert result["removed"] is True
    assert result["alias"]["source"] == "fleet-a:old"
    assert result["alias"]["target"] == "fleet-a:new"

    aliases = registry.read_aliases()
    assert "fleet-a:old" not in aliases
    # alias rm touches the alias ledger only; sibling rows survive
    assert "fleet-a:keep" in aliases


def test_alias_rm_not_found(aura_state):
    from commands import seat
    from lib import registry

    registry.add_alias("fleet-a:keep", "fleet-a:new", reason="rename")

    result = seat.run(_alias_args("rm", source="fleet-a:missing", confirm=True))
    assert result["ok"] is False
    assert result["error"] == "alias-not-found"
    # nothing removed
    assert "fleet-a:keep" in registry.read_aliases()


def test_alias_rm_ledger_only_does_not_touch_registry(aura_state):
    from commands import seat
    from lib import registry

    registry.upsert_agent({
        "name": "new",
        "fleet": "fleet-a",
        "runtime": "codex",
        "registered": True,
        "pane_ref": "tmux:fleet-a:%10",
    })
    registry.add_alias("fleet-a:old", "fleet-a:new", reason="rename")

    seat.run(_alias_args("rm", source="fleet-a:old", confirm=True))

    # The live registry row for the rename target is untouched by alias rm.
    assert registry.resolve_live("fleet-a:new") is not None


# ---------------------------------------------------------------------------
# seat_status observability flag
# ---------------------------------------------------------------------------

class _FakeTerminal:
    """Terminal where the registered pane_ref is NOT alive."""

    alive: set[str] = set()

    @classmethod
    def target_exists(cls, target):
        return target in cls.alive

    @staticmethod
    def capture_output(_target, _lines=20):
        return ["ready"]


def test_seat_status_flags_live_born_pane_without_row(aura_state, monkeypatch):
    from lib import seat_status, tmux_mirror

    monkeypatch.setattr(
        tmux_mirror, "list_physical_panes", lambda **_kw: {"ok": True, "panes": []}
    )

    # Aura-born seat (has aura_launch_id) whose registered pane is missing.
    record = {
        "name": "born-orphan",
        "seat": "born-orphan",
        "fleet": "runway-engineering",
        "runtime": "codex",
        "registered": True,
        "seat_instance_id": "si_born001",
        "aura_launch_id": "launch_born001",
        "pane_ref": "tmux:runway-engineering:%900",
    }

    row = seat_status.build_from_record(record, terminal=_FakeTerminal, live_pane_ids=set())

    assert row["liveness"] == "missing"
    assert "missing_pane" in row["risk_flags"]
    assert "live_born_pane_without_row" in row["risk_flags"]


def test_seat_status_no_born_flag_without_launch_id(aura_state, monkeypatch):
    from lib import seat_status, tmux_mirror

    monkeypatch.setattr(
        tmux_mirror, "list_physical_panes", lambda **_kw: {"ok": True, "panes": []}
    )

    # Missing pane but no aura_launch_id -> only missing_pane, no born flag.
    record = {
        "name": "plain-orphan",
        "seat": "plain-orphan",
        "fleet": "runway-engineering",
        "runtime": "codex",
        "registered": True,
        "seat_instance_id": "si_plain001",
        "pane_ref": "tmux:runway-engineering:%901",
    }

    row = seat_status.build_from_record(record, terminal=_FakeTerminal, live_pane_ids=set())

    assert row["liveness"] == "missing"
    assert "missing_pane" in row["risk_flags"]
    assert "live_born_pane_without_row" not in row["risk_flags"]
