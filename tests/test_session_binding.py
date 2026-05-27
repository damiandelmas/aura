"""Tests for Aura runtime session binding."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


def test_bind_registry_session_records_aura_session_only(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("DESKS_ROOT", str(tmp_path / ".desks"))

    from commands import sessions

    result = sessions._bind_registry_session(
        fleet="flex-managers",
        seat="project",
        previous={
            "fleet": "flex-managers",
            "name": "project",
            "runtime": "codex",
            "identity_provider": "desks",
            "identity_id": "r_pm000001",
        },
        session_id="019dd71c-c846-7070-b5be-33a32117699a",
        source="argv:codex-resume",
        confidence="exact",
        evidence={"reason": "test"},
        cwd="/repo/flex",
        event="session_bound_current",
    )

    assert result["ok"] is True
    assert result["runtime_session_id"] == "019dd71c-c846-7070-b5be-33a32117699a"
    assert "desks_session_recorded" not in result
    assert "desks_session" not in result
    assert not (tmp_path / ".desks").exists()


def test_bind_hook_records_codex_session_as_exact(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("DESKS_ROOT", str(tmp_path / ".desks"))
    monkeypatch.setenv("AURA_FLEET", "aura-user-sandbox")
    monkeypatch.setenv("AURA_SEAT", "scout")

    from lib import registry, runtime_session
    from commands import sessions

    registry.upsert_agent({
        "name": "scout",
        "fleet": "aura-user-sandbox",
        "runtime": "codex",
        "registered": True,
        "seat_instance_id": "si_scout",
        "runtime_session_binding": "unbound",
        "cwd": "/home/axp/projects/desks",
    })

    result = sessions._bind_hook(type("Args", (), {
        "target": None,
        "runtime": "codex",
        "session_id": "019e0512-675f-7f13-be1f-83e821eef950",
        "nonce": None,
        "transcript_path": "/home/axp/.codex/sessions/rollout.jsonl",
        "hook_event": "SessionStart",
        "seat_instance_id": "si_scout",
    })())

    assert result["ok"] is True
    assert result["target"] == "aura-user-sandbox:scout"
    assert result["runtime_session_source"] == "codex-hook:session-start"
    assert result["runtime_session_binding"] == "bound"
    assert result["runtime_session_bind_method"] == "codex-hook"

    row = registry.get_agent("scout", fleet="aura-user-sandbox")
    assert row["runtime_session_id"] == "019e0512-675f-7f13-be1f-83e821eef950"
    assert runtime_session.is_bound_session(row) is True


def test_bind_hook_rejects_wrong_seat_instance(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("AURA_FLEET", "aura-user-sandbox")
    monkeypatch.setenv("AURA_SEAT", "scout")

    from lib import registry
    from commands import sessions

    registry.upsert_agent({
        "name": "scout",
        "fleet": "aura-user-sandbox",
        "runtime": "codex",
        "registered": True,
        "seat_instance_id": "si_current",
    })

    result = sessions._bind_hook(type("Args", (), {
        "target": None,
        "runtime": "codex",
        "session_id": "019e0512-675f-7f13-be1f-83e821eef950",
        "nonce": None,
        "transcript_path": None,
        "hook_event": "SessionStart",
        "seat_instance_id": "si_old",
    })())

    assert result["ok"] is False
    assert result["error"] == "seat-instance-mismatch"
