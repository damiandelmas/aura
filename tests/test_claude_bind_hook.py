"""Tests for the Claude Code SessionStart bind hook."""
from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))

HOOK = ROOT / "cli" / "hooks" / "claude_bind_hook.py"


def _run_hook(monkeypatch, payload: dict) -> int:
    spec = importlib.util.spec_from_file_location("claude_bind_hook", HOOK)
    mod = importlib.util.module_from_spec(spec)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    spec.loader.exec_module(mod)
    return mod.main()


@pytest.fixture
def hook_state(monkeypatch, tmp_path):
    state = tmp_path / ".aura"
    state.mkdir()
    monkeypatch.setenv("AURA_STATE_DIR", str(state))
    for var in ("AURA_FLEET", "AURA_SEAT", "AURA_AGENT_NAME", "AURA_SEAT_INSTANCE_ID",
                "AURA_TMUX_SESSION", "CLAUDE_SESSION_ID", "AURA_RUNTIME"):
        monkeypatch.delenv(var, raising=False)
    return state


def test_hook_binds_claude_seat_through_gate(hook_state, monkeypatch):
    from lib import registry

    registry.upsert_agent({
        "name": "architect",
        "fleet": "salesfleet",
        "runtime": "claude-code",
        "seat_instance_id": "si_test0001",
        "runtime_session_binding": "unbound",
    })

    monkeypatch.setenv("AURA_FLEET", "salesfleet")
    monkeypatch.setenv("AURA_SEAT", "architect")
    monkeypatch.setenv("AURA_SEAT_INSTANCE_ID", "si_test0001")

    rc = _run_hook(monkeypatch, {
        "hook_event_name": "SessionStart",
        "session_id": "c4e128a2-1111-2222-3333-444444444444",
        "transcript_path": "/tmp/fake.jsonl",
    })
    assert rc == 0

    row = registry.resolve_live("architect", fleet="salesfleet")
    assert row["runtime_session_id"] == "c4e128a2-1111-2222-3333-444444444444"
    assert row["runtime_session_binding"] == "bound"
    assert str(row.get("runtime_session_source", "")).startswith("claude-hook:")


def test_hook_is_a_silent_noop_for_personal_sessions(hook_state, monkeypatch, capsys):
    """No AURA env → not an Aura seat → exit 0, write nothing, print nothing."""
    rc = _run_hook(monkeypatch, {
        "hook_event_name": "SessionStart",
        "session_id": "deadbeef-0000-0000-0000-000000000000",
    })
    assert rc == 0
    assert capsys.readouterr().out == ""

    from lib import registry
    assert registry.read_registry() == {}


def test_hook_respects_seat_instance_mismatch(hook_state, monkeypatch):
    """A stale launch env (old instance id) must not bind onto the new occupant."""
    from lib import registry

    registry.upsert_agent({
        "name": "architect",
        "fleet": "salesfleet",
        "runtime": "claude-code",
        "seat_instance_id": "si_current",
        "runtime_session_binding": "unbound",
    })

    monkeypatch.setenv("AURA_FLEET", "salesfleet")
    monkeypatch.setenv("AURA_SEAT", "architect")
    monkeypatch.setenv("AURA_SEAT_INSTANCE_ID", "si_stale")
    monkeypatch.setenv("AURA_CLAUDE_BIND_HOOK_TIMEOUT", "0.5")
    monkeypatch.setenv("AURA_CLAUDE_BIND_HOOK_RETRY_DELAY", "0.1")

    rc = _run_hook(monkeypatch, {
        "hook_event_name": "SessionStart",
        "session_id": "deadbeef-1111-0000-0000-000000000000",
    })
    assert rc == 0

    row = registry.resolve_live("architect", fleet="salesfleet")
    assert row["runtime_session_binding"] == "unbound"
    assert row.get("runtime_session_id") in (None, "")
