"""Tests for the tmux pane -> runtime session resolver and guarded bind."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


def _pane(pane_id="%5", session="flt", pid="1234", cmd="codex", cwd="/repo", window="scout"):
    return {
        "pane_id": pane_id,
        "tmux_session": session,
        "physical_fleet": session,
        "pane_pid": pid,
        "pane_current_command": cmd,
        "pane_current_path": cwd,
        "window_id": "@1",
        "window_name": window,
        "pane_ref": f"tmux:{session}:{pane_id}",
        "terminal_ref": f"tmux:{session}:{window}",
    }


def _install_mirror(monkeypatch, panes):
    from lib import tmux_mirror

    monkeypatch.setattr(tmux_mirror, "list_physical_panes", lambda **kw: {"ok": True, "panes": panes})


def _install_env(monkeypatch, env):
    from lib import pane_resolver

    monkeypatch.setattr(pane_resolver, "_pane_env", lambda pid: dict(env))


def _install_discover(monkeypatch, disc):
    from lib import runtime_session

    monkeypatch.setattr(runtime_session, "discover_from_pane_pid", lambda *a, **k: dict(disc))


def _args(**kw):
    base = {"pane": None, "current": False, "target": None, "repair": False}
    base.update(kw)
    return type("Args", (), base)()


# ---------------------------------------------------------------- resolve-pane


def test_resolve_pane_uses_registry_binding(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from lib import registry, pane_resolver

    registry.upsert_agent({
        "name": "scout",
        "fleet": "flt",
        "runtime": "codex",
        "registered": True,
        "pane_ref": "tmux:flt:%5",
        "seat_instance_id": "si_scout",
        "runtime_session_id": "sid-registry",
        "runtime_session_binding": "bound",
        "runtime_session_source": "codex-hook:session-start",
    })
    _install_mirror(monkeypatch, [_pane()])
    _install_env(monkeypatch, {})

    res = pane_resolver.resolve_pane(pane="%5")

    assert res["ok"] is True
    assert res["managed_state"] == "managed"
    assert res["runtime_session_id"] == "sid-registry"
    assert res["runtime_session_source"] == "tmux-pane:registry"
    assert res["runtime_session_confidence"] == "exact"


def test_resolve_pane_aura_env_is_exact(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from lib import pane_resolver

    _install_mirror(monkeypatch, [_pane()])
    _install_env(monkeypatch, {"AURA_RUNTIME_SESSION_ID": "sid-env"})

    res = pane_resolver.resolve_pane(pane="%5")

    assert res["runtime_session_id"] == "sid-env"
    assert res["runtime_session_source"] == "tmux-pane:env"
    assert res["runtime_session_confidence"] == "exact"
    assert res["managed_state"] == "unmanaged"


def test_resolve_pane_codex_resume_argv_is_exact(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from lib import pane_resolver

    _install_mirror(monkeypatch, [_pane()])
    _install_env(monkeypatch, {})
    _install_discover(monkeypatch, {
        "runtime_session_id": "sid-argv",
        "runtime_session_source": "argv:codex-resume",
    })

    res = pane_resolver.resolve_pane(pane="%5")

    assert res["runtime_session_id"] == "sid-argv"
    assert res["runtime_session_source"] == "tmux-pane:argv"
    assert res["runtime_session_confidence"] == "exact"


def test_resolve_pane_reports_candidates_without_binding(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from lib import pane_resolver

    _install_mirror(monkeypatch, [_pane()])
    _install_env(monkeypatch, {})
    _install_discover(monkeypatch, {
        "runtime_session_possible_matches": [
            {"runtime_session_id": "maybe-a", "source": "codex-state:cwd-start"},
            {"runtime_session_id": "maybe-b", "source": "codex-state:cwd-start"},
        ],
    })

    res = pane_resolver.resolve_pane(pane="%5")

    assert res["runtime_session_id"] is None
    assert res["runtime_session_confidence"] == "candidates"
    assert len(res["candidates"]) == 2


def test_resolve_pane_pane_not_found(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from lib import pane_resolver

    _install_mirror(monkeypatch, [_pane(pane_id="%9")])
    _install_env(monkeypatch, {})

    res = pane_resolver.resolve_pane(pane="%5")

    assert res["ok"] is False
    assert res["error"] == "pane-not-found"


def test_resolve_pane_finds_transcript_under_codex_home(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from lib import pane_resolver

    home = tmp_path / "pkg" / ".codex"
    sessions_dir = home / "sessions" / "2026" / "06"
    sessions_dir.mkdir(parents=True)
    transcript = sessions_dir / "rollout-sid-tx.jsonl"
    transcript.write_text("{}\n", encoding="utf-8")

    _install_mirror(monkeypatch, [_pane()])
    _install_env(monkeypatch, {"AURA_RUNTIME_SESSION_ID": "sid-tx", "CODEX_HOME": str(home)})

    res = pane_resolver.resolve_pane(pane="%5")

    assert res["runtime_session_id"] == "sid-tx"
    assert res["transcript_path"] == str(transcript)


# ------------------------------------------------------------------- bind-pane


def _seed_unbound(registry, **extra):
    registry.upsert_agent({
        "name": "scout",
        "fleet": "flt",
        "runtime": "codex",
        "registered": True,
        "pane_ref": "tmux:flt:%5",
        "seat_instance_id": "si_scout",
        "runtime_session_binding": "unbound",
        **extra,
    })


def test_bind_pane_binds_on_exact_env(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from lib import registry, runtime_session
    from commands import sessions

    _seed_unbound(registry)
    _install_mirror(monkeypatch, [_pane()])
    _install_env(monkeypatch, {"AURA_RUNTIME_SESSION_ID": "sid-env", "AURA_SEAT_INSTANCE_ID": "si_scout"})

    result = sessions._bind_pane(_args(pane="%5"))

    assert result["ok"] is True
    assert result["runtime_session_id"] == "sid-env"
    assert result["runtime_session_source"] == "tmux-pane:env"
    assert result["runtime_session_bind_method"] == "tmux-pane"

    row = registry.get_agent("scout", fleet="flt")
    assert row["runtime_session_id"] == "sid-env"
    assert runtime_session.is_bound_session(row) is True


def test_bind_pane_refuses_package_env_mismatch(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from lib import registry
    from commands import sessions

    _seed_unbound(registry, agent_package_id="i_pkg", agent_package_root="/pkg/right")
    _install_mirror(monkeypatch, [_pane()])
    _install_env(monkeypatch, {
        "AURA_RUNTIME_SESSION_ID": "sid-env",
        "AURA_AGENT_PACKAGE_ROOT": "/pkg/right",
        "CODEX_HOME": "/pkg/WRONG/.codex",
    })

    result = sessions._bind_pane(_args(pane="%5"))

    assert result["ok"] is False
    assert result["error"] == "package-env-mismatch"
    assert registry.get_agent("scout", fleet="flt").get("runtime_session_id") is None


def test_bind_pane_refuses_seat_instance_mismatch(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from lib import registry
    from commands import sessions

    _seed_unbound(registry)
    _install_mirror(monkeypatch, [_pane()])
    _install_env(monkeypatch, {"AURA_RUNTIME_SESSION_ID": "sid-env", "AURA_SEAT_INSTANCE_ID": "si_other"})

    result = sessions._bind_pane(_args(pane="%5"))

    assert result["ok"] is False
    assert result["error"] == "seat-instance-mismatch"


def test_bind_pane_refuses_low_confidence_candidates(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from lib import registry
    from commands import sessions

    _seed_unbound(registry)
    _install_mirror(monkeypatch, [_pane()])
    _install_env(monkeypatch, {})
    _install_discover(monkeypatch, {
        "runtime_session_possible_matches": [{"runtime_session_id": "maybe", "source": "codex-state:cwd-start"}],
    })

    result = sessions._bind_pane(_args(pane="%5"))

    assert result["ok"] is False
    assert result["error"] == "multiple-candidates"


def test_bind_pane_refuses_no_exact_evidence(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from lib import registry
    from commands import sessions

    _seed_unbound(registry)
    _install_mirror(monkeypatch, [_pane()])
    _install_env(monkeypatch, {})
    _install_discover(monkeypatch, {})

    result = sessions._bind_pane(_args(pane="%5"))

    assert result["ok"] is False
    assert result["error"] == "no-exact-evidence"


def test_bind_pane_refuses_unmanaged_without_target(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from commands import sessions

    _install_mirror(monkeypatch, [_pane()])
    _install_env(monkeypatch, {"AURA_RUNTIME_SESSION_ID": "sid-env"})

    result = sessions._bind_pane(_args(pane="%5"))

    assert result["ok"] is False
    assert result["error"] == "no-target"


# ------------------------------------------------------- classify_physical (live graph)


def _install_env_map(monkeypatch, env_by_pid):
    from lib import pane_resolver

    monkeypatch.setattr(pane_resolver, "_pane_env", lambda pid: dict(env_by_pid.get(int(pid), {})))


def _seed_graph(registry):
    registry.upsert_agent({"name": "boundseat", "fleet": "flt", "runtime": "codex", "registered": True,
        "pane_ref": "tmux:flt:%1", "runtime_session_id": "sid-X",
        "runtime_session_binding": "bound", "runtime_session_source": "codex-hook:session-start"})
    registry.upsert_agent({"name": "unbseat", "fleet": "flt", "runtime": "codex", "registered": True,
        "pane_ref": "tmux:flt:%2", "runtime_session_binding": "unbound"})
    registry.upsert_agent({"name": "badseat", "fleet": "flt", "runtime": "codex", "registered": True,
        "pane_ref": "tmux:flt:%3", "agent_package_id": "i_p", "agent_package_root": "/pkg",
        "runtime_session_binding": "unbound"})
    registry.upsert_agent({"name": "ghostseat", "fleet": "flt", "runtime": "codex", "registered": True,
        "pane_ref": "tmux:flt:%9", "runtime_session_id": "sid-G",
        "runtime_session_binding": "bound", "runtime_session_source": "codex-hook:session-start"})


def _graph_panes():
    return [
        _pane(pane_id="%1", pid="101", window="boundseat"),
        _pane(pane_id="%2", pid="102", window="unbseat"),
        _pane(pane_id="%3", pid="103", window="badseat"),
        _pane(pane_id="%5", pid="105", window="randomshell"),  # unmanaged
    ]


def test_classify_physical_cheap_four_states(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from lib import registry, pane_resolver

    _seed_graph(registry)
    _install_mirror(monkeypatch, _graph_panes())

    out = pane_resolver.classify_physical(resolve=False)

    assert out["ok"] is True and out["resolved"] is False
    states = {p["pane_id"]: p["physical_state"] for p in out["panes"]}
    assert states == {"%1": "managed-bound", "%2": "managed-unbound", "%3": "managed-unbound", "%5": "unmanaged"}
    assert out["counts"]["stale"] == 1 and out["stale"][0]["physical_state"] == "stale"
    assert out["counts"]["mismatch"] == 0  # cheap mode cannot detect contamination


def test_classify_physical_resolve_flags_mismatch(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from lib import registry, runtime_session, pane_resolver

    _seed_graph(registry)
    _install_mirror(monkeypatch, _graph_panes())
    # %3 advertises a real session id but its CODEX_HOME contradicts the package root.
    _install_env_map(monkeypatch, {
        103: {"AURA_RUNTIME_SESSION_ID": "sid-bad", "AURA_AGENT_PACKAGE_ROOT": "/pkg", "CODEX_HOME": "/WRONG/.codex"},
    })
    monkeypatch.setattr(runtime_session, "discover_from_pane_pid", lambda *a, **k: {})

    out = pane_resolver.classify_physical(resolve=True)

    assert out["resolved"] is True
    states = {p["pane_id"]: p["physical_state"] for p in out["panes"]}
    assert states["%1"] == "managed-bound"      # registry-bound, clean body
    assert states["%2"] == "managed-unbound"    # no session yet, not contamination
    assert states["%3"] == "mismatch"           # real session id, wrong body -> refused class
    assert states["%5"] == "unmanaged"
    assert out["counts"]["stale"] == 1
    bad = next(p for p in out["panes"] if p["pane_id"] == "%3")
    assert any(m["check"] == "codex_home" for m in bad["mismatches"])
    assert bad["agent_package_id"] == "i_p"  # registry body, for the org join


def test_classify_physical_deghost_keeps_count_drops_list(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from lib import registry, pane_resolver

    _seed_graph(registry)
    _install_mirror(monkeypatch, _graph_panes())

    out = pane_resolver.classify_physical(resolve=False, include_stale=False)

    assert out["counts"]["stale"] == 1  # ghost count is preserved
    assert out["stale"] == []           # but the 585-row firehose is dropped
