"""Tests for `aura sessions` row contract."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


def test_sessions_rows_emit_fleet_seat_and_target(monkeypatch):
    from commands import sessions

    monkeypatch.setattr(
        sessions.list_cmd,
        "run",
        lambda _args: [
            {
                "seat": "specialist-cell",
                "fleet": "flex-specialists",
                "runtime": "codex",
                "terminal": "alive",
                "runtime_session_id": "019dec35-4cd3-7550-83d3-53d50e837e5d",
                "runtime_session_binding": "bound",
                "runtime_session_bind_method": "argv-resume",
            }
        ],
    )

    result = sessions.run(argparse.Namespace(
        sessions_action=None,
        fleet=None,
        live=True,
        include_hidden=True,
    ))

    assert result["ok"] is True
    assert result["rows"][0]["seat"] == "specialist-cell"
    assert "name" not in result["rows"][0]
    assert "runtime_session_confidence" not in result["rows"][0]
    assert result["rows"][0]["target"] == "flex-specialists:specialist-cell"
    assert result["rows"][0]["seat_ref"] == "flex-specialists:specialist-cell"


def test_sessions_rows_fall_back_to_legacy_name(monkeypatch):
    from commands import sessions

    monkeypatch.setattr(
        sessions.list_cmd,
        "run",
        lambda _args: [
            {
                "name": "engineer",
                "fleet": "flex-leaders-2",
                "runtime": "codex",
                "terminal": "alive",
            }
        ],
    )

    result = sessions.run(argparse.Namespace(
        sessions_action=None,
        fleet=None,
        live=True,
        include_hidden=True,
    ))

    assert result["rows"][0]["seat"] == "engineer"
    assert "name" not in result["rows"][0]
    assert result["rows"][0]["target"] == "flex-leaders-2:engineer"


def test_sessions_fleets_counts_same_seat_name_per_fleet(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("AURA_FLEET", "fleet-a")

    from commands import sessions
    from lib import registry, terminal

    registry.upsert_agent({
        "name": "lead",
        "fleet": "fleet-a",
        "runtime": "codex",
        "registered": True,
        "terminal_ref": "fleet-a:lead",
        "runtime_session_id": "session-a",
        "runtime_session_source": "argv:codex-resume",
        "identity_provider": "desks",
        "identity_id": "r_a",
    })
    registry.upsert_agent({
        "name": "lead",
        "fleet": "fleet-b",
        "runtime": "codex",
        "registered": True,
        "terminal_ref": "fleet-b:lead",
        "runtime_session_id": "session-b",
        "runtime_session_source": "argv:codex-resume",
    })

    monkeypatch.setattr(terminal, "configure_session", lambda fleet: fleet)
    monkeypatch.setattr(terminal, "target_exists", lambda target: target in {"fleet-a:lead", "fleet-b:lead"})
    monkeypatch.setattr(terminal, "capture_output", lambda target, lines=20: ["ready"])

    result = sessions.run(argparse.Namespace(sessions_action="fleets"))

    by_fleet = {row["fleet"]: row for row in result["fleets"]}
    assert by_fleet["fleet-a"]["registry_seats"] == 1
    assert by_fleet["fleet-b"]["registry_seats"] == 1
    assert by_fleet["fleet-a"]["live_seats"] == 1
    assert by_fleet["fleet-b"]["live_seats"] == 1
    assert by_fleet["fleet-a"]["bound_seats"] == 1
    assert by_fleet["fleet-b"]["bound_seats"] == 1
