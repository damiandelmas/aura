"""Tests for the sensed-completion seam (idle_watcher) and the work-claim pool (work).

Covers the adversarial cases the design turns on: the watcher must NOT false-idle on
a mid-turn pause (busy marker overrides a stable diff), must emit exactly once per
idle episode and re-arm only after working, and must require the debounce. The pool
must assign pending->idle, free on an idle report dated after assignment, requeue on
lease expiry, and never double-assign a busy seat.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))

import argparse
import hashlib
import json

from lib import idle_watcher, result_anchor, work  # noqa: E402
from commands import anchor as anchor_cmd  # noqa: E402


# --------------------------------------------------------------------------
# idle_watcher.classify — the fused diff + marker signal
# --------------------------------------------------------------------------

IDLE_LINES = ["", "❯ ", ""]
BUSY_LINES = ["working (3s · esc to interrupt)", "running tool", ""]


def test_first_sample_reads_working_no_evidence():
    # No previous hash -> diff is "unknown" -> never declare idle without evidence.
    out = idle_watcher.classify(None, IDLE_LINES)
    assert out["state"] == "working"


def test_stable_quiet_pane_reads_idle():
    h = idle_watcher.hash_capture(IDLE_LINES)
    out = idle_watcher.classify(h, IDLE_LINES)
    assert out["state"] == "idle"


def test_changed_pane_reads_working():
    old = idle_watcher.hash_capture(["older"])
    out = idle_watcher.classify(old, IDLE_LINES)
    assert out["state"] == "working"


def test_mid_turn_pause_does_not_false_idle():
    # The dangerous case: output is momentarily stable (diff would say idle) but a
    # busy marker is present -> the marker must override and keep it working.
    h = idle_watcher.hash_capture(BUSY_LINES)
    out = idle_watcher.classify(h, BUSY_LINES)
    assert out["diff_state"] == "idle"      # diff alone would have been wrong
    assert out["blocker"] == "target-busy"
    assert out["state"] == "working"        # fused result is correct


# --------------------------------------------------------------------------
# idle_watcher.decide — debounce + emit-once edge
# --------------------------------------------------------------------------

def _idle(h="h"):
    return {"state": "idle", "output_hash": h, "diff_state": "idle", "blocker": None}


def _working(h="h"):
    return {"state": "working", "output_hash": h, "diff_state": "working", "blocker": None}


def test_debounce_requires_n_idle_samples():
    s1, e1 = idle_watcher.decide(None, _idle(), debounce=2)
    assert e1 is False and s1["idle_ticks"] == 1
    s2, e2 = idle_watcher.decide(s1, _idle(), debounce=2)
    assert e2 is True and s2["idle_ticks"] == 2  # edge fires on the 2nd idle


def test_emit_once_then_rearm_after_working():
    s1, _ = idle_watcher.decide(None, _idle(), debounce=1)
    assert s1["emitted"] is True
    s2, e2 = idle_watcher.decide(s1, _idle(), debounce=1)
    assert e2 is False                      # still idle -> no second emit
    s3, _ = idle_watcher.decide(s2, _working(), debounce=1)
    assert s3["emitted"] is False           # working re-arms the gate
    s4, e4 = idle_watcher.decide(s3, _idle(), debounce=1)
    assert e4 is True                       # next idle episode emits again


# --------------------------------------------------------------------------
# idle_watcher.tick — end to end with injected I/O
# --------------------------------------------------------------------------

def test_tick_emits_once_for_a_seat_that_goes_idle(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path))
    member = {"seat_ref": "pool:a", "fleet": "pool", "seat": "a"}
    emits = []

    def members_fn(_):
        return [member]

    def emit_fn(m, idle_ticks, anchor=None):
        emits.append((m["seat_ref"], idle_ticks))
        return {}

    # working, then idle, idle, idle  (debounce 2 -> emit once on the 2nd idle)
    captures = iter([["x"], ["❯ "], ["❯ "], ["❯ "]])

    def capture_fn(_ref, _lines):
        return True, next(captures)

    for _ in range(4):
        idle_watcher.tick("pool", debounce=2, capture_fn=capture_fn, emit_fn=emit_fn, members_fn=members_fn)

    assert emits == [("pool:a", 2)]  # exactly one emit, on the debounced edge


# --------------------------------------------------------------------------
# work.plan_dispatch — pure dispatch decisions
# --------------------------------------------------------------------------

def _task(tid, state, **over):
    base = {"task_id": tid, "state": state, "seat": None, "assigned_at": None,
            "lease_until": None, "created_at": tid, "body": "do"}
    base.update(over)
    return base


def test_assign_pending_to_idle_seat():
    tasks = {"t1": _task("t1", "pending")}
    plan = work.plan_dispatch(tasks, {"pool:a": "2026-06-01T00:00:00+00:00"}, now_epoch_value=1000.0)
    assert plan["assign"] == [("t1", "pool:a")]


def test_release_on_idle_report_after_assignment():
    # idle proves the seat is FREE (release), not that the task succeeded.
    tasks = {"t1": _task("t1", "assigned", seat="pool:a",
                          assigned_at="2026-06-01T00:00:00+00:00", lease_until=9e9)}
    plan = work.plan_dispatch(tasks, {"pool:a": "2026-06-02T00:00:00+00:00"}, now_epoch_value=1000.0)
    assert plan["release"] == ["t1"] and plan["assign"] == []


def test_no_release_when_idle_predates_assignment():
    # A pre-assignment idle (why we assigned) must NOT count as turn-end.
    tasks = {"t1": _task("t1", "assigned", seat="pool:a",
                          assigned_at="2026-06-02T00:00:00+00:00", lease_until=9e9)}
    plan = work.plan_dispatch(tasks, {"pool:a": "2026-06-01T00:00:00+00:00"}, now_epoch_value=1000.0)
    assert plan["release"] == [] and plan["requeue"] == []


def test_requeue_on_lease_expiry():
    tasks = {"t1": _task("t1", "assigned", seat="pool:a",
                          assigned_at="2026-06-01T00:00:00+00:00", lease_until=500.0)}
    plan = work.plan_dispatch(tasks, {}, now_epoch_value=1000.0)
    assert plan["requeue"] == ["t1"]


def test_busy_seat_not_double_assigned():
    tasks = {
        "t1": _task("t1", "assigned", seat="pool:a",
                    assigned_at="2026-06-02T00:00:00+00:00", lease_until=9e9),
        "t2": _task("t2", "pending"),
    }
    # pool:a is busy (no fresh idle); only pool:b is free.
    plan = work.plan_dispatch(tasks, {"pool:a": "2026-06-01T00:00:00+00:00", "pool:b": "2026-06-03T00:00:00+00:00"},
                              now_epoch_value=1000.0)
    assert plan["assign"] == [("t2", "pool:b")]


# --------------------------------------------------------------------------
# work store + dispatch_tick integration (temp state dir, injected send)
# --------------------------------------------------------------------------

def test_store_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path))
    work.submit("q", "alpha")
    work.submit("q", "beta")
    rows = work.list_tasks("q")
    assert [r["body"] for r in rows] == ["alpha", "beta"]
    assert all(r["state"] == "pending" for r in rows)


def test_dispatch_tick_assigns_then_releases(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path))
    sent = []

    def fake_send(seat, body):
        sent.append((seat, body))
        return {"ok": True}

    task = work.submit("q", "process A")
    # No placement record -> members empty -> idle map passes through unscoped.
    res = work.dispatch_tick("q", "pool", send_fn=fake_send,
                             idle_map={"pool:a": "2026-06-01T00:00:00+00:00"}, now_epoch_value=1000.0)
    assert res["assigned"] == [{"task": task["task_id"], "seat": "pool:a"}]
    assert sent == [("pool:a", "process A")]
    assigned = work.fold_tasks("q")[task["task_id"]]
    assert assigned["state"] == "assigned" and assigned["seat"] == "pool:a"

    # A fresh idle report dated after the assignment RELEASES it (free, not done).
    res2 = work.dispatch_tick("q", "pool", send_fn=fake_send,
                              idle_map={"pool:a": "2999-01-01T00:00:00+00:00"}, now_epoch_value=1001.0)
    assert res2["released"] == [task["task_id"]]
    # idle never infers success: released, NOT done.
    assert work.fold_tasks("q")[task["task_id"]]["state"] == "released"


# --------------------------------------------------------------------------
# result_anchor — the optional, demoted result pointer (citation, not done-signal)
# --------------------------------------------------------------------------

def test_latest_assistant_anchor_uses_flex_line_number(tmp_path):
    # The position must be the 1-based JSONL LINE number (Flex's chunk N), not a
    # count of text messages. Non-text lines (reasoning / events) are skipped for
    # content but still consume a line — so the last assistant lands on line 5
    # while being only the 2nd assistant *message*. Line-number minting => 5.
    transcript = tmp_path / "sess.jsonl"
    rows = [
        {"type": "response_item", "payload": {"type": "message", "role": "user",       # line 1
            "content": [{"type": "input_text", "text": "go"}]}},
        {"type": "response_item", "payload": {"type": "reasoning"}},                     # line 2 (no text)
        {"type": "response_item", "payload": {"type": "message", "role": "assistant",    # line 3
            "content": [{"type": "output_text", "text": "first"}]}},
        {"type": "event", "payload": {}},                                                # line 4 (no text)
        {"type": "response_item", "payload": {"type": "message", "role": "assistant",    # line 5
            "content": [{"type": "output_text", "text": "FINAL ANSWER"}]}},
    ]
    transcript.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    row = {"runtime_session_id": "sess", "seat_ref": "pool:a", "transcript_path": str(transcript)}

    anchor = result_anchor.latest_assistant_anchor(row)
    assert anchor is not None
    assert anchor["position"] == 5                       # LINE number, not message count (would be 3)
    assert anchor["flex_chunk_id"] == "sess_5"           # == Flex chunk id by construction
    assert anchor["sha256"] == hashlib.sha256(b"FINAL ANSWER").hexdigest()
    assert anchor["anchor"] == f"pool:a@sess#5 sha:{anchor['sha256'][:8]}"


def test_latest_assistant_anchor_missing_session_returns_none():
    assert result_anchor.latest_assistant_anchor({"seat_ref": "pool:a"}) is None


def test_to_chunk_id_parses_anchor_and_raw_id():
    # an anchor string -> the Flex chunk id; a raw chunk id passes through.
    assert result_anchor.to_chunk_id("pool:a@sess#5 sha:deadbeef") == "sess_5"
    assert result_anchor.to_chunk_id("pool:a@sess#5") == "sess_5"            # no sha suffix
    assert result_anchor.to_chunk_id("pool:a@sess#5 sha:whatever") == "sess_5"  # robust to any suffix
    assert result_anchor.to_chunk_id("sess_5") == "sess_5"
    assert result_anchor.to_chunk_id("nonsense with spaces!") is None


# --------------------------------------------------------------------------
# aura anchor — the canonical CLI (latest / enum) over a synthetic transcript
# --------------------------------------------------------------------------

def _anchor_transcript(tmp_path):
    transcript = tmp_path / "sess.jsonl"
    rows = [
        {"type": "response_item", "payload": {"type": "message", "role": "user",
            "content": [{"type": "input_text", "text": "go"}]}},                          # line 1
        {"type": "response_item", "payload": {"type": "reasoning"}},                        # line 2
        {"type": "response_item", "payload": {"type": "message", "role": "assistant",
            "content": [{"type": "output_text", "text": "the answer"}]}},                   # line 3
    ]
    transcript.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return str(transcript)


def test_anchor_latest_cli_mints_flex_chunk_id(tmp_path):
    args = argparse.Namespace(anchor_action="latest", target=None, session="sess",
                              seat_ref="pool:a", transcript=_anchor_transcript(tmp_path))
    out = anchor_cmd.run(args)
    assert out["ok"] is True
    assert out["position"] == 3 and out["flex_chunk_id"] == "sess_3"
    assert out["anchor"] == f"pool:a@sess#3 sha:{out['sha256'][:8]}"


def test_anchor_enum_cli_lists_canonical_positions(tmp_path):
    args = argparse.Namespace(anchor_action="enum", target=None, session="sess",
                              seat_ref="pool:a", transcript=_anchor_transcript(tmp_path), limit=None)
    out = anchor_cmd.run(args)
    assert out["ok"] is True
    # only content-bearing rows surface, tagged with their LINE number == Flex chunk N
    positions = {r["position"]: r["flex_chunk_id"] for r in out["rows"]}
    assert positions == {1: "sess_1", 3: "sess_3"}   # line 2 (reasoning, no text) omitted


def test_anchor_latest_cli_requires_a_session():
    out = anchor_cmd.run(argparse.Namespace(anchor_action="latest", target=None, session=None,
                                            seat_ref=None, transcript=None))
    assert out["ok"] is False


def test_tick_stamps_anchor_when_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path))
    member = {"seat_ref": "pool:a", "fleet": "pool", "seat": "a", "row": {}}
    captured = []

    def emit_fn(m, idle_ticks, anchor=None):
        captured.append(anchor)
        return {}

    fake_anchor = {"anchor": "pool:a@sess#3 sha:deadbeef", "position": 3, "sha256": "deadbeef..."}
    # working, changed, then stable -> idle edge fires on the 3rd pass (debounce 1).
    captures = iter([["x"], ["❯ "], ["❯ "]])

    for _ in range(3):
        idle_watcher.tick(
            "pool", debounce=1, with_anchor=True,
            capture_fn=lambda *_: (True, next(captures)),
            emit_fn=emit_fn,
            members_fn=lambda _: [member],
            anchor_fn=lambda _m: fake_anchor,
        )
    # the anchor is stamped on the idle-edge emit.
    assert fake_anchor in captured


def test_dispatch_tick_requeues_expired_lease(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path))
    task = work.submit("q", "slow one")
    work.update_task("q", task, state="assigned", seat="pool:a",
                     assigned_at="2026-06-01T00:00:00+00:00", lease_until=500.0)
    res = work.dispatch_tick("q", "pool", send_fn=lambda *_: {"ok": True},
                             idle_map={}, now_epoch_value=1000.0)
    assert res["requeued"] == [task["task_id"]]
    folded = work.fold_tasks("q")[task["task_id"]]
    assert folded["state"] == "pending" and folded["attempts"] == 1
