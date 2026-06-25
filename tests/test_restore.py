"""Tests for `aura restore` (cli/commands/restore.py).

AURA_STATE_DIR isolated per-test by the autouse conftest fixture.
"""

from __future__ import annotations

import types

from commands import restore
from lib import flight


def _frame(target, *, session="s-1", cwd="/p", runtime="claude-code", binding="bound", si="si-1"):
    fleet, _, seat = target.partition(":")
    return {
        "target": target, "fleet": fleet, "seat": seat, "runtime": runtime,
        "session_id": session if binding == "bound" else None,
        "cwd": cwd, "seat_instance_id": si, "launch_id": "L",
        "pane_ref": "tmux:%s:%%1" % fleet, "binding": binding, "report_state": None,
    }


def _args(**kw):
    kw.setdefault("execute", False)
    kw.setdefault("at", None)
    return types.SimpleNamespace(**kw)


def _record(seats, *, ts):
    flight.record_tick(seats, now=ts, keyframe_interval_s=10**9, force_keyframe=True)


# --------------------------------------------------------------------------- mapping

def test_frame_to_restore_row_bound_and_unbound():
    bound = restore._frame_to_restore_row(_frame("f:a"))
    assert bound["runtime_session_binding"] == "bound"
    assert bound["session_id"] == "s-1" and bound["runtime_session_id"] == "s-1"

    unbound = restore._frame_to_restore_row(_frame("f:b", binding="unbound"))
    assert unbound["runtime_session_binding"] == "unbound"
    assert unbound["session_id"] is None


def test_normalize_at_canonical_and_now():
    assert restore._normalize_at("2026-06-25T12:00:00+00:00").endswith("+00:00")
    # naive -> assumed UTC; date-only accepted
    assert restore._normalize_at("2026-06-25").startswith("2026-06-25T00:00:00")
    assert restore._normalize_at(None)  # now, no raise


# --------------------------------------------------------------------------- plan

def test_plan_marks_bound_claude_seats_restore_ready():
    ts = "2026-06-25T12:00:00.000000+00:00"
    _record([_frame("f:a"), _frame("f:b", session="s-2")], ts=ts)
    plan = restore._plan(ts)
    assert plan["total"] == 2 and plan["restore_ready"] == 2
    for row in plan["rows"]:
        assert row["restore_ready"]
        assert row["restore_command"] and "--resume-session" in row["restore_command"]


def test_restore_command_carries_session_id_from_the_frame():
    # The bug guard: the resume command must use the session id RECORDED IN THE FRAME.
    ts = "2026-06-25T12:00:00.000000+00:00"
    _record([_frame("recall:manager", session="AAA111"), _frame("recall:memory", session="BBB222")], ts=ts)
    plan = restore._plan(ts)
    cmds = {row["seat"]: row["restore_command"] for row in plan["rows"]}
    assert "--resume-session AAA111" in cmds["manager"]
    assert "--resume-session BBB222" in cmds["memory"]


def test_plan_includes_reconciliation_and_reconstructed_at():
    ts = "2026-06-25T12:00:00.000000+00:00"
    _record([_frame("f:a")], ts=ts)
    plan = restore._plan(ts)
    assert plan["reconstructed_at"] == ts
    assert plan["source"] == "flight-snapshot"
    assert "reconciliation" in plan  # added by sessions._add_restore_reconciliation


# --------------------------------------------------------------------------- time travel

def test_at_reconstructs_historical_fleet():
    t1 = "2026-06-25T12:00:00.000000+00:00"
    t2 = "2026-06-25T12:05:00.000000+00:00"
    _record([_frame("f:a")], ts=t1)
    _record([_frame("f:a"), _frame("f:b", si="si-b")], ts=t2)

    at_t1 = restore.run(_args(at=t1))
    assert {r["seat"] for r in at_t1["rows"]} == {"a"}

    at_t2 = restore.run(_args(at=t2))
    assert {r["seat"] for r in at_t2["rows"]} == {"a", "b"}


# --------------------------------------------------------------------------- execute

def test_dry_run_is_default_and_runs_no_commands(monkeypatch):
    ts = "2026-06-25T12:00:00.000000+00:00"
    _record([_frame("f:a")], ts=ts)
    called = []
    monkeypatch.setattr(restore, "_run_command", lambda c: called.append(c) or (True, ""))
    plan = restore.run(_args(at=ts))  # no execute
    assert plan["schema"] == "aura.restore_plan.v1"
    assert called == []  # nothing executed


def test_normalize_at_messy_inputs_are_fixed_width():
    # date-only, naive, and µs=0 inputs must all expand to the recorder's canonical width
    for raw in ("2026-06-25", "2026-06-25T12:00:00", "2026-06-25T12:00:00+00:00"):
        out = restore._normalize_at(raw)
        assert out.endswith("+00:00")
        frac = out.split(".")[1]
        assert frac == "000000+00:00", (raw, out)


def test_at_messy_input_selects_correct_keyframe():
    # recorder writes canonical ts; a naive --at at the same instant must still select it
    t1 = "2026-06-25T12:00:00.000000+00:00"
    t2 = "2026-06-25T12:05:00.000000+00:00"
    _record([_frame("f:a")], ts=t1)
    _record([_frame("f:a"), _frame("f:b", si="si-b")], ts=t2)
    # naive form of t2 (no offset) — would mis-sort without normalization
    res = restore.run(_args(at="2026-06-25T12:05:00"))
    assert {r["seat"] for r in res["rows"]} == {"a", "b"}
    # date-only before any record -> empty fleet (nothing was live at midnight)
    res0 = restore.run(_args(at="2026-06-25"))
    assert res0["rows"] == []


def test_package_seats_degrade_to_plain_spawn_documented():
    # KNOWN LIMITATION: the frame schema carries no agent_package_* fields, so a package-
    # native seat restores via plain `aura spawn` (not `aura agent spawn <pkg>`). Asserted so
    # the degrade is explicit and tested, pending a frame-schema extension.
    ts = "2026-06-25T12:00:00.000000+00:00"
    _record([_frame("f:a")], ts=ts)
    plan = restore._plan(ts)
    cmd = plan["rows"][0]["restore_command"]
    assert cmd.startswith("aura spawn ") and "agent spawn" not in cmd


def test_execute_dedupes_shared_session(monkeypatch):
    # two dead seats sharing one session id -> only ONE resume runs (never fork a mind)
    ts = "2026-06-25T12:00:00.000000+00:00"
    _record([_frame("f:one", session="SHARED"), _frame("f:two", session="SHARED")], ts=ts)
    ran = []
    monkeypatch.setattr(restore, "_live_targets", lambda: set())
    monkeypatch.setattr(restore, "_run_command", lambda c: ran.append(c) or (True, ""))
    res = restore.run(_args(at=ts, execute=True))
    assert res["executed"] == 1
    skips = [r for r in res["results"] if r.get("skipped") == "duplicate-session-id"]
    assert len(skips) == 1 and len(ran) == 1


def test_execute_resurrects_dead_skips_live_and_not_ready(monkeypatch):
    ts = "2026-06-25T12:00:00.000000+00:00"
    _record([
        _frame("f:dead", session="D"),
        _frame("f:alive", session="A"),
        _frame("f:nosess", binding="unbound"),  # not restore-ready
    ], ts=ts)

    ran = []
    monkeypatch.setattr(restore, "_live_targets", lambda: {"f:alive"})
    monkeypatch.setattr(restore, "_run_command", lambda c: ran.append(c) or (True, "ok"))

    res = restore.run(_args(at=ts, execute=True))
    assert res["executed"] == 1 and res["failed"] == 0
    by_target = {r["target"]: r for r in res["results"]}
    assert by_target["f:dead"].get("ok") is True
    assert by_target["f:alive"]["skipped"] == "already-live"
    assert "skipped" in by_target["f:nosess"]
    # exactly one command ran, and it was the dead seat's resume
    assert len(ran) == 1 and "--resume-session D" in ran[0]
