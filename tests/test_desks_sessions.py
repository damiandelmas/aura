"""Tests for Aura's minimal Desks sessions.json bridge."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


def test_append_identity_session_creates_and_dedupes(tmp_path):
    from lib import desks_sessions

    identity = tmp_path / ".desks" / "identities" / "r_test1234"
    identity.mkdir(parents=True)

    first = desks_sessions.append_identity_session(
        "r_test1234",
        "019dd71c-c846-7070-b5be-33a32117699a",
        desks_root=tmp_path / ".desks",
    )
    second = desks_sessions.append_identity_session(
        "r_test1234",
        "019dd71c-c846-7070-b5be-33a32117699a",
        desks_root=tmp_path / ".desks",
    )

    assert first["ok"] is True
    assert first["changed"] is True
    assert second["ok"] is True
    assert second["changed"] is False
    assert json.loads((identity / "sessions.json").read_text(encoding="utf-8")) == [
        "019dd71c-c846-7070-b5be-33a32117699a"
    ]


def test_bind_registry_session_updates_desks_sessions_json(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("DESKS_ROOT", str(tmp_path / ".desks"))

    identity = tmp_path / ".desks" / "identities" / "r_pm000001"
    identity.mkdir(parents=True)
    (identity / "sessions.json").write_text("[]\n", encoding="utf-8")

    from commands import sessions

    result = sessions._bind_registry_session(
        fleet="flex-managers",
        seat="project",
        previous={
            "fleet": "flex-managers",
            "name": "project",
            "runtime": "codex",
            "desks_identity_id": "r_pm000001",
        },
        session_id="019dd71c-c846-7070-b5be-33a32117699a",
        source="argv:codex-resume",
        confidence="exact",
        evidence={"reason": "test"},
        cwd="/repo/flex",
        event="session_bound_current",
    )

    assert result["ok"] is True
    assert result["desks_session_recorded"] is True
    assert json.loads((identity / "sessions.json").read_text(encoding="utf-8")) == [
        "019dd71c-c846-7070-b5be-33a32117699a"
    ]
