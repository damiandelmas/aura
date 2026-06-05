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


# --- Universal body-integrity veto (bind_guard / _bind_registry_session) -------
# Every bind writer now flows through the body veto in _bind_registry_session, so a
# real session id can never bind onto a contaminated/wrong body. These tests pin
# that single chokepoint.

def _contaminated_package_record(scout_root: str, manager_root: str) -> dict:
    # Registry says this seat is the scout package, but its runtime home / capsule
    # ref / native state were wired to the MANAGER body (the factory-v2 class).
    return {
        "fleet": "flexchat-shopify-factory-v2",
        "name": "scout",
        "runtime": "codex",
        "registered": True,
        "agent_package_id": "i_scout",
        "agent_package_root": scout_root,
        "runtime_home": manager_root,            # contradicts scout root
        "native_state_ref": f"{manager_root}/.codex",
    }


def test_bind_registry_session_refuses_contaminated_body(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from commands import sessions

    scout_root = str(tmp_path / "i_scout")
    manager_root = str(tmp_path / "i_manager")
    result = sessions._bind_registry_session(
        fleet="flexchat-shopify-factory-v2",
        seat="scout",
        previous=_contaminated_package_record(scout_root, manager_root),
        session_id="019e8f82-4174-7a81-ae19-dd3301971628",
        source="codex-jsonl:nonce",
        confidence="exact",
        evidence={"reason": "test"},
        cwd=scout_root,
        event="session_bound_nonce",
    )

    assert result["ok"] is False
    assert result["error"] == "body-gate-refused"
    assert result["reason"] == "package-env-mismatch"
    assert result["registry_updated"] is False


def test_bind_registry_session_repair_bypasses_body_veto(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from commands import sessions

    scout_root = str(tmp_path / "i_scout")
    manager_root = str(tmp_path / "i_manager")
    result = sessions._bind_registry_session(
        fleet="flexchat-shopify-factory-v2",
        seat="scout",
        previous=_contaminated_package_record(scout_root, manager_root),
        session_id="019e8f82-4174-7a81-ae19-dd3301971628",
        source="tmux-pane:env",
        confidence="exact",
        evidence={"reason": "operator-repair"},
        cwd=scout_root,
        event="session_bound_pane",
        repair=True,
    )

    assert result["ok"] is True
    assert result["runtime_session_id"] == "019e8f82-4174-7a81-ae19-dd3301971628"


def test_bind_registry_session_allows_clean_package_body(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from commands import sessions

    root = str(tmp_path / "i_scout")
    result = sessions._bind_registry_session(
        fleet="flexchat-shopify-factory-v2",
        seat="scout",
        previous={
            "fleet": "flexchat-shopify-factory-v2",
            "name": "scout",
            "runtime": "codex",
            "registered": True,
            "agent_package_id": "i_scout",
            "agent_package_root": root,
            "runtime_home": root,
            "native_state_ref": f"{root}/.codex",
        },
        session_id="019e8f82-4174-7a81-ae19-dd3301971628",
        source="codex-jsonl:nonce",
        confidence="exact",
        evidence={"reason": "test"},
        cwd=root,
        event="session_bound_nonce",
    )

    assert result["ok"] is True


def test_bind_registry_session_allows_non_package_seat(monkeypatch, tmp_path):
    # Plain `aura spawn` codex seat (no package) — the recovery-pain-scout/engineer
    # class. not-package -> veto must let it bind.
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from commands import sessions

    result = sessions._bind_registry_session(
        fleet="flex-community",
        seat="recovery-pain-scout",
        previous={
            "fleet": "flex-community",
            "name": "recovery-pain-scout",
            "runtime": "codex",
            "registered": True,
        },
        session_id="019e8f82-4174-7a81-ae19-dd3301971628",
        source="codex-jsonl:nonce",
        confidence="exact",
        evidence={"reason": "test"},
        cwd="/home/axp/projects/flex/outreach/sandbox/recovery-pain-scout",
        event="session_bound_nonce",
    )

    assert result["ok"] is True
    assert result["runtime_session_id"] == "019e8f82-4174-7a81-ae19-dd3301971628"
