import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


def test_placement_add_show_list_and_remove(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from lib import registry
    from commands import placement

    registry.upsert_agent({
        "fleet": "logical-fleet",
        "name": "worker",
        "runtime": "codex",
        "pane_ref": "tmux:physical-fleet:%42",
        "seat_instance_id": "si_worker",
    })

    added = placement.run(argparse.Namespace(
        placement_action="add",
        placement="flex-systems",
        seat_ref="logical-fleet:worker",
        role="lead",
        kind="workstream",
        label="Flex Systems",
    ))

    assert added["ok"] is True
    assert added["movement"] == "none"
    record = added["placement"]
    assert record["placement_id"] == "pl_flex-systems"
    assert record["kind"] == "workstream"
    assert record["members"][0]["seat_ref"] == "logical-fleet:worker"
    assert record["members"][0]["role"] == "lead"
    assert record["members"][0]["physical_fleet"] == "physical-fleet"

    listed = placement.run(argparse.Namespace(placement_action="list"))
    assert listed["counts"] == {"placements": 1}

    shown = placement.run(argparse.Namespace(placement_action="show", placement="flex-systems"))
    assert shown["placement"]["members"][0]["runtime"] == "codex"

    removed = placement.run(argparse.Namespace(
        placement_action="remove",
        placement="flex-systems",
        seat_ref="logical-fleet:worker",
    ))
    assert removed["ok"] is True
    assert removed["removed"] == 1
    assert removed["placement"]["members"] == []


def test_placement_rejects_unknown_member(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from commands import placement

    result = placement.run(argparse.Namespace(
        placement_action="add",
        placement="flex-systems",
        seat_ref="missing:seat",
        role=None,
        kind="group",
        label=None,
    ))

    assert result["ok"] is False
    assert result["error"] == "seat not found: missing:seat"


def test_seat_status_and_dashboard_include_placements(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from lib import registry, placements, seat_status, dashboard_identity

    registry.upsert_agent({"fleet": "fleet", "name": "worker", "runtime": "shell", "pane_ref": "tmux:fleet:%1"})
    placements.add_member("ops", "fleet:worker", role="operator", kind="statusline")

    status = seat_status.build_from_record(registry.get_agent("fleet:worker"), terminal=None)
    assert status["placements"][0]["name"] == "ops"
    dash = dashboard_identity.build_dashboard_identity("fleet:worker", terminal=None)
    assert dash["placements"][0]["role"] == "operator"
    assert "Placements: ops" in dash["text"]
