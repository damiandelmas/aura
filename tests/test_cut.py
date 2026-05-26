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


def test_cut_falls_back_from_stale_pane_ref_to_live_terminal_ref(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))

    from commands import cut
    from lib import mesh
    from lib import registry, terminal

    registry.upsert_agent({
        "name": "manager",
        "fleet": "fleet",
        "runtime": "codex",
        "pane_ref": "tmux:fleet:%stale",
        "terminal_ref": "tmux:fleet:%live",
        "status": "idle",
    })

    killed = []
    monkeypatch.setattr(terminal, "configure_session", lambda fleet: fleet)
    monkeypatch.setattr(terminal, "target_exists", lambda target: target == "tmux:fleet:%live")
    monkeypatch.setattr(terminal, "kill_window", lambda target: killed.append(target) or {"ok": True})
    monkeypatch.setattr(mesh, "unregister", lambda name: {"ok": True, "name": name})

    result = cut.run(argparse.Namespace(name="fleet:manager", force=True))

    assert result["ok"] is True
    assert result["terminal"] == "killed"
    assert result["terminal_target"] == "tmux:fleet:%live"
    assert killed == ["tmux:fleet:%live"]
    assert result["terminal_target_checks"] == [
        {"target": "tmux:fleet:%stale", "exists": False},
        {"target": "tmux:fleet:%live", "exists": True},
    ]
