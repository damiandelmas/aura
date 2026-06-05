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


def test_cut_stale_pane_ref_does_not_fall_back_to_name(monkeypatch, tmp_path):
    """Core safety regression: a dead pane_ref must NOT cause a name-based kill.

    The old behavior fell back from stale %N to terminal_ref/backend_ref name
    targets, which tmux resolved by prefix-match and could kill the WRONG fleet.
    The new behavior: if pane_ref exists but is dead, treat seat as already gone
    and proceed to registry cleanup with NO kill issued.
    """
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))

    from commands import cut
    from lib import mesh
    from lib import registry, terminal

    registry.upsert_agent({
        "name": "manager",
        "fleet": "fleet",
        "runtime": "codex",
        "pane_ref": "tmux:fleet:%stale",
        "terminal_ref": "tmux:fleet:manager",
        "backend_ref": "tmux:fleet:manager",
        "status": "idle",
    })

    killed = []
    monkeypatch.setattr(terminal, "configure_session", lambda fleet: fleet)
    # The pane_ref is dead; the name target would resolve to something live
    # — but we must never reach it.
    monkeypatch.setattr(terminal, "target_exists", lambda target: False)
    monkeypatch.setattr(terminal, "kill_window", lambda target: killed.append(target) or {"ok": True})
    monkeypatch.setattr(mesh, "unregister", lambda name: {"ok": True, "name": name})

    result = cut.run(argparse.Namespace(name="fleet:manager", force=True))

    assert result["ok"] is True
    # No kill must have been issued — the pane was already gone.
    assert killed == [], f"Expected no kill calls but got: {killed}"
    assert result.get("note") == "pane already gone"
    # Seat must be marked dead.
    assert registry.get_agent("manager", fleet="fleet")["status"] == "dead"
    # pane_ref must be cleared.
    assert registry.get_agent("manager", fleet="fleet").get("pane_ref") is None


def test_cut_prefix_collision_regression(monkeypatch, tmp_path):
    """Headline regression: cut X:engineer (pane_ref dead) must not kill anything in X-v2.

    Simulates: session 'X' does not exist / its engineer pane is dead, but
    session 'X-v2' with window 'engineer' is live. The old code would name-fall-
    back to 'X:engineer', tmux prefix-matched to 'X-v2:engineer', and killed it.
    """
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))

    from commands import cut
    from lib import mesh
    from lib import registry, terminal

    registry.upsert_agent({
        "name": "engineer",
        "fleet": "X",
        "runtime": "codex",
        "pane_ref": "tmux:X:%dead99",
        "terminal_ref": "tmux:X:engineer",
        "backend_ref": "tmux:X:engineer",
        "status": "idle",
    })

    killed = []

    def fake_target_exists(target):
        # X-v2:engineer is live; X:%dead99 is not; X:engineer is not.
        if "X-v2" in str(target):
            return True
        return False

    monkeypatch.setattr(terminal, "configure_session", lambda fleet: fleet)
    monkeypatch.setattr(terminal, "target_exists", fake_target_exists)
    monkeypatch.setattr(terminal, "kill_window", lambda target: killed.append(target) or {"ok": True})
    monkeypatch.setattr(mesh, "unregister", lambda name: {"ok": True, "name": name})

    result = cut.run(argparse.Namespace(name="X:engineer", force=False))

    assert result["ok"] is True
    # Absolutely no kill must reach X-v2 or anything else.
    assert killed == [], f"Expected no kill calls but got: {killed}"
    # pane_ref must be cleared so future ops see no stale pointer.
    assert registry.get_agent("engineer", fleet="X").get("pane_ref") is None


def test_cut_live_pane_ref_kills_pane_and_clears_pane_ref(monkeypatch, tmp_path):
    """When pane_ref is alive, it is the sole kill target and pane_ref is cleared."""
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))

    from commands import cut
    from lib import mesh
    from lib import registry, terminal

    registry.upsert_agent({
        "name": "worker",
        "fleet": "myfleet",
        "runtime": "codex",
        "pane_ref": "tmux:myfleet:%7",
        "terminal_ref": "tmux:myfleet:worker",
        "backend_ref": "tmux:myfleet:worker",
        "status": "idle",
    })

    killed = []
    monkeypatch.setattr(terminal, "configure_session", lambda fleet: fleet)
    monkeypatch.setattr(terminal, "target_exists", lambda target: target == "tmux:myfleet:%7")
    monkeypatch.setattr(terminal, "kill_window", lambda target: killed.append(target) or {"ok": True})
    monkeypatch.setattr(terminal, "send_text", lambda *a, **kw: {"ok": True})
    monkeypatch.setattr(mesh, "unregister", lambda name: {"ok": True, "name": name})

    result = cut.run(argparse.Namespace(name="myfleet:worker", force=False))

    assert result["ok"] is True
    assert result["terminal"] == "killed"
    assert killed == ["tmux:myfleet:%7"]
    assert result["terminal_target"] == "tmux:myfleet:%7"
    assert registry.get_agent("worker", fleet="myfleet")["status"] == "dead"
    assert registry.get_agent("worker", fleet="myfleet").get("pane_ref") is None


def test_cut_no_pane_ref_falls_back_to_name_target(monkeypatch, tmp_path):
    """When no pane_ref exists, name-based targets are still tried (exact-matched)."""
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))

    from commands import cut
    from lib import mesh
    from lib import registry, terminal

    registry.upsert_agent({
        "name": "legacy",
        "fleet": "oldfleet",
        "runtime": "codex",
        # No pane_ref
        "terminal_ref": "tmux:oldfleet:legacy",
        "backend_ref": "tmux:oldfleet:legacy",
        "status": "idle",
    })

    killed = []
    monkeypatch.setattr(terminal, "configure_session", lambda fleet: fleet)
    monkeypatch.setattr(terminal, "target_exists", lambda target: "legacy" in str(target))
    monkeypatch.setattr(terminal, "kill_window", lambda target: killed.append(target) or {"ok": True})
    monkeypatch.setattr(terminal, "send_text", lambda *a, **kw: {"ok": True})
    monkeypatch.setattr(mesh, "unregister", lambda name: {"ok": True, "name": name})

    result = cut.run(argparse.Namespace(name="oldfleet:legacy", force=False))

    assert result["ok"] is True
    assert result["terminal"] == "killed"
    assert len(killed) == 1
    assert "legacy" in killed[0]
