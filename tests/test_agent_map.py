from __future__ import annotations

import argparse
import json
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
    monkeypatch.setenv("AURA_FLEET", "flex-systems-archeology")
    return tmp_path


class FakeTerminal:
    SESSION_NAME = "flex-systems-archeology"
    alive = {
        "tmux:flex-systems-archeology:%1",
        "tmux:flex-systems-archeology:%2",
    }

    @staticmethod
    def configure_session(fleet):
        return fleet

    @classmethod
    def target_exists(cls, target):
        return target in cls.alive

    @staticmethod
    def capture_output(_target, _lines=20):
        return ["ready"]


def _write_desks_org(root: Path):
    desks_root = root / ".desks"
    for identity_id, current_name in {
        "r_self": "flex:systems:lead:archeology",
        "r_peer": "flex:systems:specialist:workstreams",
    }.items():
        identity_dir = desks_root / "identities" / identity_id
        identity_dir.mkdir(parents=True)
        (identity_dir / "identity.json").write_text(
            json.dumps({
                "schema": "desks.identity.v1",
                "identity_id": identity_id,
                "current_name": current_name,
                "aliases": [],
            }),
            encoding="utf-8",
        )
    current = desks_root / "organizations" / "flex" / "current"
    current.mkdir(parents=True)
    (current / "organization.yaml").write_text(
        """
product: flex
units:
  - unit: systems
    programs:
      - program: archeology
        fleets:
          - fleet/project: flex-systems-archeology
            seats:
              - seat: lead-archeology
                role: flex:systems:lead:archeology
                identity_id: r_self
              - seat: specialist-workstreams
                role: flex:systems:specialist:workstreams
                identity_id: r_peer
""".lstrip(),
        encoding="utf-8",
    )
    (current / "roles.md").write_text(
        """
# Flex Current Roles

## Systems

### flex:systems:lead:archeology

Lead archeology note.

### flex:systems:specialist:workstreams

Workstreams specialist note.
""".lstrip(),
        encoding="utf-8",
    )


def test_agent_map_includes_self_and_same_fleet_colleagues(aura_state):
    from lib import agent_map, holding, registry

    _write_desks_org(aura_state)
    registry.upsert_agent({
        "name": "lead-archeology",
        "fleet": "flex-systems-archeology",
        "runtime": "codex",
        "registered": True,
        "pane_ref": "tmux:flex-systems-archeology:%1",
        "identity_provider": "desks",
        "identity_id": "r_self",
        "desks_identity_id": "r_self",
        "runtime_session_id": "session-self",
        "runtime_session_source": "argv:codex-resume",
    })
    registry.upsert_agent({
        "name": "specialist-workstreams",
        "fleet": "flex-systems-archeology",
        "runtime": "codex",
        "registered": True,
        "registered_via": "adopt",
        "managed_state": "adopted_unbound",
        "pane_ref": "tmux:flex-systems-archeology:%2",
        "identity_provider": "desks",
        "identity_id": "r_peer",
        "desks_identity_id": "r_peer",
        "runtime_session_binding": "unbound",
    })
    registry.upsert_agent({
        "name": "outside",
        "fleet": "other-fleet",
        "runtime": "codex",
        "registered": True,
    })
    holding.create_from_candidate({
        "source": "tmux",
        "pane_ref": "tmux:flex-systems-archeology:%99",
        "tmux_session": "flex-systems-archeology",
        "window_name": "unmanaged",
        "pane_id": "%99",
    })

    result = agent_map.build_agent_map("flex-systems-archeology:lead-archeology", terminal=FakeTerminal)

    assert result["ok"] is True
    assert result["self"]["target"] == "flex-systems-archeology:lead-archeology"
    assert result["self"]["identity"]["current"]["position"] == "flex:systems:lead:archeology"
    assert [row["target"] for row in result["fleet"]] == ["flex-systems-archeology:specialist-workstreams"]
    assert result["fleet"][0]["managed_state"] == "adopted_unbound"
    assert result["fleet"][0]["runtime_session_binding"] == "unbound"
    assert result["unit"] == {"product": "flex", "unit": "systems", "programs": ["archeology"]}
    assert result["position_notes"]["flex:systems:lead:archeology"] == "Lead archeology note."
    assert result["position_notes"]["flex:systems:specialist:workstreams"] == "Workstreams specialist note."
    assert "outside" not in result["packet"]
    assert "unmanaged" not in result["packet"]
    assert "session-self" not in result["packet"]


def test_agent_map_command_returns_packet(aura_state, monkeypatch):
    from commands import agent_map as agent_map_cmd
    from lib import terminal
    from lib import registry

    monkeypatch.setattr(terminal, "configure_session", FakeTerminal.configure_session)
    monkeypatch.setattr(terminal, "target_exists", FakeTerminal.target_exists)

    registry.upsert_agent({
        "name": "lead",
        "fleet": "flex-systems-archeology",
        "runtime": "codex",
        "registered": True,
        "pane_ref": "tmux:flex-systems-archeology:%1",
    })

    result = agent_map_cmd.run(argparse.Namespace(target="flex-systems-archeology:lead"))

    assert result["ok"] is True
    assert result["schema"] == "aura.agent_map.v1"
    assert result["packet"].startswith("[AURA AGENT MAP]")
    assert result["text"] == result["packet"]


def test_agent_map_excludes_missing_pane_colleagues(aura_state):
    from lib import agent_map, registry

    registry.upsert_agent({
        "name": "lead",
        "fleet": "flex-systems-archeology",
        "runtime": "codex",
        "registered": True,
        "pane_ref": "tmux:flex-systems-archeology:%1",
    })
    registry.upsert_agent({
        "name": "gone",
        "fleet": "flex-systems-archeology",
        "runtime": "codex",
        "registered": True,
        "pane_ref": "tmux:flex-systems-archeology:%404",
    })

    result = agent_map.build_agent_map("flex-systems-archeology:lead", terminal=FakeTerminal)

    assert result["ok"] is True
    assert result["fleet"] == []
    assert "gone" not in result["packet"]


def test_agent_map_rejects_missing_target(aura_state):
    from lib import agent_map, registry

    registry.upsert_agent({
        "name": "gone",
        "fleet": "flex-systems-archeology",
        "runtime": "codex",
        "registered": True,
        "pane_ref": "tmux:flex-systems-archeology:%404",
    })

    result = agent_map.build_agent_map("flex-systems-archeology:gone", terminal=FakeTerminal, require_routable=True)

    assert result["ok"] is False
    assert result["error"] == "seat-not-routable"
    assert result["managed_state"] == "missing_pane"
