"""Tests for stable Aura fleet identity commands."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


def test_fleets_resolve_creates_stable_id_for_named_fleet(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from commands import fleets

    first = fleets.run(argparse.Namespace(fleets_action="resolve", target="flex-specialists"))
    second = fleets.run(argparse.Namespace(fleets_action="resolve", target="flex-specialists"))

    assert first["ok"] is True
    assert first["fleet"]["fleet_id"].startswith("f_")
    assert second["fleet"]["fleet_id"] == first["fleet"]["fleet_id"]
    assert second["fleet"]["current_name"] == "flex-specialists"
    assert second["fleet"]["tmux_session"] == "flex-specialists"


def test_sessions_fleets_includes_fleet_ids(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from commands import sessions
    from lib import registry, session_ledger

    registry.upsert_agent({
        "name": "worker",
        "seat": "worker",
        "fleet": "unitfleet",
        "runtime": "codex",
        "registered": True,
        "runtime_session_id": "session-1",
        "runtime_session_binding": "bound",
        "desks_identity_id": "r_test",
    })
    session_ledger.append_seat_event(
        event="seat_spawned",
        after=registry.get_agent("worker", fleet="unitfleet"),
        source_command="test",
    )
    monkeypatch.setattr(
        sessions.list_cmd,
        "run",
        lambda _args: [
            {
                "name": "worker",
                "fleet": "unitfleet",
                "terminal": "alive",
                "runtime": "codex",
                "runtime_session_id": "session-1",
                "runtime_session_binding": "bound",
            }
        ],
    )

    result = sessions.run(argparse.Namespace(sessions_action="fleets"))

    assert result["ok"] is True
    assert result["live"][0]["fleet"] == "unitfleet"
    assert result["live"][0]["fleet_id"].startswith("f_")
    assert result["live"][0]["live_seats"] == 1
    assert result["live"][0]["bound_seats"] == 1


def test_fleet_history_builds_restore_commands(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from commands import fleets
    from lib import registry, session_ledger

    current = registry.upsert_agent({
        "name": "worker",
        "seat": "worker",
        "fleet": "unitfleet",
        "runtime": "codex",
        "cwd": str(tmp_path),
        "registered": True,
        "runtime_session_id": "session-1",
        "runtime_session_binding": "bound",
        "desks_identity_id": "r_test",
    })
    session_ledger.append_seat_event(
        event="seat_spawned",
        after=current,
        source_command="test",
    )
    session_ledger.append_seat_event(
        event="seat_cut",
        before=current,
        source_command="test",
    )
    monkeypatch.setattr(
        fleets.list_cmd,
        "run",
        lambda _args: [],
    )

    result = fleets.run(argparse.Namespace(fleets_action="history", target="unitfleet"))

    assert result["ok"] is True
    assert result["state"] == "historical"
    assert result["fleet_id"].startswith("f_")
    assert result["seats"][0]["seat"] == "worker"
    assert result["seats"][0]["restore"]["ready"] is True
    assert "--fleet-id" in result["seats"][0]["restore"]["command"]
    assert "--resume-session session-1" in result["seats"][0]["restore"]["command"]
    assert result["seats"][0]["restore"]["post_bind_command"] == "aura seat tag unitfleet:worker --set desks_identity_id=r_test"
