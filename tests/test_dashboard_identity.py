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
    monkeypatch.setenv("AURA_FLEET", "runway-engineering")
    return tmp_path


class FakeTerminal:
    SESSION_NAME = "runway-engineering"

    @staticmethod
    def configure_session(fleet):
        return fleet

    @staticmethod
    def target_exists(target):
        return target == "tmux:runway-engineering:%7"

    @staticmethod
    def capture_output(_target, _lines=20):
        return ["ready"]


def _write_desks(root: Path):
    identity_dir = root / ".desks" / "identities" / "r_dash001"
    identity_dir.mkdir(parents=True)
    (identity_dir / "identity.json").write_text(
        json.dumps({
            "schema": "desks.identity.v1",
            "identity_id": "r_dash001",
            "current_name": "flex:systems:lead:engineering",
            "aliases": [],
        }),
        encoding="utf-8",
    )
    org_dir = root / ".desks" / "organizations" / "flex" / "current"
    org_dir.mkdir(parents=True)
    (org_dir / "organization.yaml").write_text(
        """
product: flex
units:
  - unit: systems
    programs:
      - program: aura
        fleets:
          - fleet/project: runway-engineering
            seats:
              - seat: lead-engineer
                role: flex:systems:lead:engineering
                identity_id: r_dash001
""".lstrip(),
        encoding="utf-8",
    )


def test_dashboard_identity_uses_canonical_status_and_desks_position(aura_state):
    from lib import dashboard_identity, registry

    _write_desks(aura_state)
    registry.upsert_agent({
        "name": "lead-engineer",
        "fleet": "runway-engineering",
        "runtime": "codex",
        "registered": True,
        "seat_instance_id": "si_dash001",
        "pane_ref": "tmux:runway-engineering:%7",
        "runtime_session_id": "019dd797-1169-7931-b2f7-17824b3b7134",
        "runtime_session_source": "argv:codex-resume",
        "identity_provider": "desks",
        "identity_id": "r_dash001",
        "desks_identity_id": "r_dash001",
        "desks_product": "flex",
    })

    result = dashboard_identity.build_dashboard_identity("runway-engineering:lead-engineer", terminal=FakeTerminal)

    assert result["ok"] is True
    assert result["target"] == "runway-engineering:lead-engineer"
    assert result["seat_instance_id"] == "si_dash001"
    assert result["runtime_session_binding"] == "bound"
    assert result["identity"]["name"] == "flex:systems:lead:engineering"
    assert result["identity"]["current"]["position"] == "flex:systems:lead:engineering"
    assert result["compact"] == "runway-engineering:lead-engineer | si_dash001 | codex bound | flex:systems:lead:engineering"
    assert "Aura: runway-engineering:lead-engineer" in result["text"]
    assert "Identity: flex:systems:lead:engineering / flex:systems:lead:engineering" in result["text"]


def test_dash_identity_command_returns_surface(aura_state):
    from commands import dash
    from lib import registry

    registry.upsert_agent({
        "name": "lead",
        "fleet": "runway-engineering",
        "runtime": "codex",
        "registered": True,
        "seat_instance_id": "si_dash002",
    })

    result = dash.run(argparse.Namespace(dash_action="identity", target="runway-engineering:lead"))

    assert result["ok"] is True
    assert result["schema"] == "aura.dashboard_identity.v1"
    assert result["compact"] == "runway-engineering:lead | si_dash002 | codex unbound"


def test_dashboard_identity_updates_after_rename(aura_state):
    from lib import dashboard_identity, registry

    registry.upsert_agent({
        "name": "old-name",
        "fleet": "runway-engineering",
        "runtime": "codex",
        "registered": True,
        "seat_instance_id": "si_dash003",
    })
    registry.rename_agent("runway-engineering:old-name", new_name="new-name")

    result = dashboard_identity.build_dashboard_identity("runway-engineering:new-name")

    assert result["ok"] is True
    assert result["target"] == "runway-engineering:new-name"
    assert "Aura: runway-engineering:new-name" in result["text"]
