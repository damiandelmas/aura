import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


def test_cut_force_marks_fleet_qualified_missing_terminal_dead(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))

    from commands import cut
    from lib import mesh
    from lib import registry, terminal

    registry.upsert_agent({
        "name": "manager",
        "fleet": "fleet",
        "runtime": "codex",
        "pane_ref": "tmux:fleet:%1",
        "status": "starting",
    })

    monkeypatch.setattr(terminal, "configure_session", lambda fleet: fleet)
    monkeypatch.setattr(terminal, "target_exists", lambda target: False)

    monkeypatch.setattr(mesh, "unregister", lambda name: {"ok": True, "name": name})

    result = cut.run(argparse.Namespace(name="fleet:manager", force=True))

    assert result["ok"] is True
    assert registry.get_agent("manager", fleet="fleet")["status"] == "dead"
