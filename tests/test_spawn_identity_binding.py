"""Tests for spawn identity binding cleanup."""

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
    state_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("AURA_STATE_DIR", str(state_root))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")
    return state_root


class FakeTerminal:
    SESSION_NAME = "unitfleet"
    BACKEND_NAME = "tmux"
    last_env = None

    @staticmethod
    def create_window(name, workdir, detached=False, command=None, env=None, unset_env=None):
        FakeTerminal.last_env = env
        return {
            "ok": True,
            "target": f"unitfleet:{name}",
            "pane_id": "%9",
        }


def _args(tmp_path, **overrides):
    values = {
        "name": "worker",
        "runtime": "command",
        "launch_command": "true",
        "resume_session": None,
        "cwd": str(tmp_path),
        "profile": None,
        "model": None,
        "context": None,
        "work": None,
        "prompt": None,
        "as_pane": True,
        "identity_provider": None,
        "identity_id": None,
        "identity_label": None,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_fresh_spawn_does_not_inherit_stale_identity_binding(aura_state, tmp_path):
    from commands import spawn
    from lib import registry

    registry.upsert_agent({
        "name": "worker",
        "seat": "worker",
        "fleet": "unitfleet",
        "runtime": "codex",
        "status": "dead",
        "pane_ref": "tmux:unitfleet:%old",
        "desks_identity_id": "r_old",
        "identity_provider": "desks",
        "identity_id": "r_old",
        "identity_label": "old:name",
        "seat_instance_id": "si_oldoldold01",
        "runtime_session_id": "old-session",
        "runtime_session_binding": "bound",
    })

    result = spawn._spawn_terminal_runtime(_args(tmp_path), FakeTerminal, lambda base: base)

    assert result["ok"] is True
    record = registry.get_agent("unitfleet:worker")
    assert record["pane_ref"] == "tmux:unitfleet:%9"
    assert record["seat_instance_id"].startswith("si_")
    assert record["seat_instance_id"] != "si_oldoldold01"
    assert "desks_identity_id" not in record
    assert "identity_provider" not in record
    assert "identity_id" not in record
    assert "identity_label" not in record
    assert "runtime_session_id" not in record
    assert record["runtime_session_binding"] == "unbound"


def test_spawn_identity_args_set_generic_identity_in_one_operation(aura_state, tmp_path):
    from commands import spawn
    from lib import registry

    args = _args(
        tmp_path,
        identity_provider="desks",
        identity_id="r_direct",
        identity_label="flex:systems:operations:lead",
    )

    result = spawn._spawn_terminal_runtime(args, FakeTerminal, lambda base: base)

    assert result["ok"] is True
    assert result["identity_provider"] == "desks"
    assert result["identity_id"] == "r_direct"
    assert result["identity_label"] == "flex:systems:operations:lead"
    assert result["desks_identity_id"] == "r_direct"
    assert result["seat_instance_id"].startswith("si_")
    record = registry.get_agent("unitfleet:worker")
    assert record["identity_provider"] == "desks"
    assert record["identity_id"] == "r_direct"
    assert record["identity_label"] == "flex:systems:operations:lead"
    assert record["desks_identity_id"] == "r_direct"
    assert record["seat_instance_id"] == result["seat_instance_id"]
    assert FakeTerminal.last_env["AURA_IDENTITY_PROVIDER"] == "desks"
    assert FakeTerminal.last_env["AURA_IDENTITY_ID"] == "r_direct"


def test_spawn_identity_args_require_provider_and_id(aura_state, tmp_path):
    from commands import spawn

    result = spawn._spawn_terminal_runtime(
        _args(tmp_path, identity_provider="desks"),
        FakeTerminal,
        lambda base: base,
    )

    assert result["ok"] is False
    assert result["error"] == "identity-provider-and-id-required"
