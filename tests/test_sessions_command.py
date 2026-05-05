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
