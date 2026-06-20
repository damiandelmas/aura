"""H3 — membership event source: emit, schedule, pending-flag, subscriptions."""

import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


@pytest.fixture
def mem(tmp_path, monkeypatch):
    from lib import membership as mod
    monkeypatch.setattr(mod, "_state_root", lambda: tmp_path)
    return mod


def test_pending_path_key_matches_hook_format(mem):
    # must match cli/hooks/claude_ambient_hook.py:_pending_key
    assert mem.pending_path("F:a").name == "F__a.json"


def test_set_ambient_pending_writes_and_skips_bad(mem):
    written = mem.set_ambient_pending(["F:a", "F:b", "garbage"], "join:fleet:F:newseat")
    assert set(written) == {"F:a", "F:b"}
    rec = json.loads(mem.pending_path("F:a").read_text(encoding="utf-8"))
    assert rec["schema"] == "aura.ambient_pending.v1"
    assert rec["reason"] == "join:fleet:F:newseat"
    assert not mem.pending_path("garbage").exists()


def test_schedule_flags_implicit_live_in_group(mem, monkeypatch):
    monkeypatch.setattr(mem, "_live_targets_in_group", lambda g: ["F:a", "F:b"])
    res = mem.schedule_membership_subscriptions("fleet:F", kind="join", member="F:newseat")
    assert set(res["flagged"]) == {"F:a", "F:b"}
    assert mem.pending_path("F:a").exists()


def test_explicit_subscription_fleet_and_placement(mem, monkeypatch):
    monkeypatch.setattr(mem, "_live_targets_in_group", lambda g: [])
    mem.create_subscription({"fleet": "F"}, "G:watch")
    mem.create_subscription({"placement": "ops"}, "G:dash")

    r1 = mem.schedule_membership_subscriptions("fleet:F", kind="join")
    assert "G:watch" in r1["delivered"] and "G:dash" not in r1["delivered"]
    assert mem.pending_path("G:watch").exists()

    r2 = mem.schedule_membership_subscriptions("placement:ops", kind="leave")
    assert "G:dash" in r2["delivered"]


def test_kind_filter(mem, monkeypatch):
    monkeypatch.setattr(mem, "_live_targets_in_group", lambda g: [])
    mem.create_subscription({"fleet": "F"}, "G:watch", kinds=["leave"])
    res = mem.schedule_membership_subscriptions("fleet:F", kind="join")
    assert "G:watch" not in res["delivered"]


def test_scope_matches(mem):
    assert mem._scope_matches({"fleet": "F"}, "fleet:F")
    assert mem._scope_matches({"placement": "ops"}, "placement:ops")
    assert not mem._scope_matches({"fleet": "F"}, "fleet:G")
    assert not mem._scope_matches({"fleet": "F"}, "placement:F")


def test_emit_invalid_kind_is_noop(mem, monkeypatch):
    called = []
    monkeypatch.setattr(mem, "schedule_membership_subscriptions",
                        lambda *a, **k: called.append(1))
    mem.emit_membership_change("fleet:F", "frobnicate", "F:x")
    assert called == []  # invalid kind never schedules


def test_reap_ambient_pending(mem):
    import os, time
    mem.set_ambient_pending(["F:old", "F:fresh"], "join:fleet:F:x")
    old = mem.pending_path("F:old")
    past = time.time() - 7200
    os.utime(old, (past, past))  # age the old flag 2h
    res = mem.reap_ambient_pending(ttl_seconds=3600)
    assert res["scanned"] == 2 and res["reaped"] == 1
    assert not old.exists() and mem.pending_path("F:fresh").exists()


def test_emit_non_fatal_on_error(mem, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("registry mid-write")
    monkeypatch.setattr(mem, "schedule_membership_subscriptions", boom)
    # must NOT raise — a membership emit can never break the originating write
    mem.emit_membership_change("fleet:F", "join", "F:x")


def test_subscribe_membership_verb_creates_record(mem, monkeypatch):
    """The CLI verb wires to the tested create_subscription API."""
    import argparse
    from commands import event as event_cmd
    monkeypatch.setattr("lib.membership._state_root", mem._state_root)

    args = argparse.Namespace(event_action="subscribe", subscribe_source="membership",
                              fleet="F", placement=None, to="G:watch",
                              kind=["leave"], sender="service:aura-membership")
    res = event_cmd.run(args)
    assert res["ok"] and res["subscription"]["scope"] == {"fleet": "F"}
    assert res["subscription"]["kinds"] == ["leave"]
    assert mem.list_subscriptions(status="active")[0]["to"] == "G:watch"
