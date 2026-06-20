"""Event-driven mirror cache: source dispatch, hook invalidation, TTL, shadow A/B."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))

from lib import tmux_mirror_cache as cache  # noqa: E402


def _result(pane_refs):
    panes = [{"pane_ref": r, "physical_fleet": r.split(":")[1]} for r in pane_refs]
    return {"ok": True, "schema": "aura.tmux_mirror.v1",
            "counts": {"sessions": 1, "panes": len(panes)},
            "sessions": ["f"], "panes": panes}


def _counter(refs):
    state = {"n": 0, "refs": refs}
    def poll():
        state["n"] += 1
        return _result(state["refs"])
    return state, poll


def test_poll_mode_always_polls(monkeypatch):
    monkeypatch.setenv("AURA_MIRROR_SOURCE", "poll")
    st, poll = _counter(["tmux:f:%1"])
    cache.serve(poll); cache.serve(poll)
    assert st["n"] == 2  # no caching in poll mode (default behavior preserved)


def test_cache_mode_serves_from_cache(monkeypatch):
    monkeypatch.setenv("AURA_MIRROR_SOURCE", "cache")
    monkeypatch.setenv("AURA_MIRROR_TTL", "60")
    st, poll = _counter(["tmux:f:%1"])
    r1 = cache.serve(poll)
    r2 = cache.serve(poll)
    assert st["n"] == 1            # second read served from cache, no poll
    assert r2 == r1
    assert {p["pane_ref"] for p in r2["panes"]} == {"tmux:f:%1"}


def test_hook_dirty_invalidates_cache(monkeypatch):
    monkeypatch.setenv("AURA_MIRROR_SOURCE", "cache")
    monkeypatch.setenv("AURA_MIRROR_TTL", "60")
    st, poll = _counter(["tmux:f:%1"])
    cache.serve(poll)                         # poll #1, writes cache
    # simulate a tmux lifecycle hook firing: dirty newer than the cache write
    cache.mark_dirty()
    os.utime(cache.dirty_path(), (cache._mtime(cache.cache_path()) + 5,) * 2)
    cache.serve(poll)                         # dirty -> must re-poll
    assert st["n"] == 2


def test_ttl_bounds_staleness(monkeypatch):
    monkeypatch.setenv("AURA_MIRROR_SOURCE", "cache")
    monkeypatch.setenv("AURA_MIRROR_TTL", "0")  # nothing is ever "fresh"
    st, poll = _counter(["tmux:f:%1"])
    cache.serve(poll); cache.serve(poll)
    assert st["n"] == 2  # TTL=0 forces a re-poll even with no hook event


def test_shadow_logs_divergence(monkeypatch):
    monkeypatch.setenv("AURA_MIRROR_TTL", "60")
    # 1) warm a fresh cache with pane set A via cache mode
    monkeypatch.setenv("AURA_MIRROR_SOURCE", "cache")
    _, poll_a = _counter(["tmux:f:%1", "tmux:f:%2"])
    cache.serve(poll_a)
    # 2) shadow read where the live poll returns a DIFFERENT set B
    monkeypatch.setenv("AURA_MIRROR_SOURCE", "shadow")
    _, poll_b = _counter(["tmux:f:%1", "tmux:f:%3"])
    result = cache.serve(poll_b)
    # poll is authoritative -> caller sees B
    assert {p["pane_ref"] for p in result["panes"]} == {"tmux:f:%1", "tmux:f:%3"}
    # divergence recorded
    rows = [json.loads(l) for l in cache.shadow_log_path().read_text().splitlines() if l.strip()]
    assert rows and rows[-1]["diverged"] is True
    assert "tmux:f:%3" in rows[-1]["missing"]   # live pane the cache lacked
    assert "tmux:f:%2" in rows[-1]["extra"]     # stale pane the cache still held


def test_shadow_no_divergence_when_in_sync(monkeypatch):
    monkeypatch.setenv("AURA_MIRROR_TTL", "60")
    monkeypatch.setenv("AURA_MIRROR_SOURCE", "cache")
    _, poll = _counter(["tmux:f:%1"])
    cache.serve(poll)
    monkeypatch.setenv("AURA_MIRROR_SOURCE", "shadow")
    _, poll2 = _counter(["tmux:f:%1"])
    cache.serve(poll2)
    rows = [json.loads(l) for l in cache.shadow_log_path().read_text().splitlines() if l.strip()]
    assert rows[-1]["diverged"] is False


def test_install_hooks_commands_cover_lifecycle():
    cmds = cache.install_hooks_commands("touch /tmp/x")
    events = {c[2] for c in cmds}
    assert "after-split-window" in events and "window-unlinked" in events
    assert all(c[0] == "set-hook" and c[1] == "-g" for c in cmds)
