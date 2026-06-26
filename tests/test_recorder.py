"""Tests for `aura recorder` (cli/commands/recorder.py).

AURA_STATE_DIR is isolated per-test by the autouse conftest fixture.
"""

from __future__ import annotations

import types

import pytest

from commands import recorder
from lib import flight


# --------------------------------------------------------------------------- helpers

def _row(target, *, liveness="alive", pane="tmux:f:%1", binding="bound", session="s-1", cwd=None):
    fleet, _, seat = target.partition(":")
    return {
        "target": target, "fleet": fleet, "seat": seat, "runtime": "claude-code",
        "liveness": liveness, "pane_ref": pane,
        "runtime_session_binding": binding, "runtime_session_id": session,
        "cwd": cwd, "seat_instance_id": "si-" + seat, "aura_launch_id": "L",
    }


def _args(**kw):
    return types.SimpleNamespace(**kw)


# --------------------------------------------------------------------------- pure helpers

def test_pane_id_from_ref():
    assert recorder.pane_id_from_ref("tmux:recall:%26") == "%26"
    assert recorder.pane_id_from_ref("tmux:flex-engine:%7") == "%7"
    assert recorder.pane_id_from_ref("recall:manager") is None  # no %N tail
    assert recorder.pane_id_from_ref(None) is None


def test_frames_from_rows_filters_and_enriches_cwd():
    rows = [
        _row("f:a", pane="tmux:f:%1", cwd=None),       # alive, cwd from pane map
        _row("f:b", liveness="missing"),                # dropped
        _row("f:c", pane="tmux:f:%9", cwd="/fallback"), # alive, no pane entry -> row cwd
    ]
    pane_cwd = {"%1": "/home/axp/projects/aura"}
    frames = recorder.frames_from_rows(rows, pane_cwd)
    by_t = {f["target"]: f for f in frames}
    assert set(by_t) == {"f:a", "f:c"}              # missing dropped
    assert by_t["f:a"]["cwd"] == "/home/axp/projects/aura"  # enriched from mirror
    assert by_t["f:c"]["cwd"] == "/fallback"        # fell back to row cwd


def test_frames_from_rows_unbound_has_no_session():
    rows = [_row("f:a", binding="unbound", session="leaked")]
    frames = recorder.frames_from_rows(rows, {})
    assert frames[0]["session_id"] is None


def test_next_ts_strictly_increasing():
    # same-ts collision guard: next ts after a given last_ts is strictly greater
    last = "2030-01-01T00:00:00+00:00"  # far future -> real now is behind it
    nxt = recorder._next_ts(last)
    assert nxt > last
    assert recorder._next_ts(nxt) > nxt


# --------------------------------------------------------------------------- orchestration

def test_record_once_writes_and_status_reflects():
    frames_a = [flight.frame_seat(_row("f:a"))]
    frames_b = [flight.frame_seat(_row("f:a")), flight.frame_seat(_row("f:b"))]

    r1 = recorder.record_once(collect=lambda: frames_a)
    assert r1["ok"] and r1["wrote_keyframe"] and r1["live"] == 1

    r2 = recorder.record_once(collect=lambda: frames_b)
    assert r2["live"] == 2 and r2["wrote_delta"] and r2["ts"] > r1["ts"]

    st = recorder.run(_args(recorder_action="status"))
    assert st["live"] == 2 and st["keyframes"] >= 1 and st["last_ts"] == r2["ts"]


def test_run_once_and_compact_dispatch(monkeypatch):
    monkeypatch.setattr(recorder, "collect_live_frames", lambda: [flight.frame_seat(_row("f:a"))])
    once = recorder.run(_args(recorder_action="once", keyframe_every=300.0))
    assert once["ok"] and once["live"] == 1
    comp = recorder.run(_args(recorder_action="compact"))
    assert comp["ok"] and "dropped_deltas" in comp


def test_run_loop_bounded_ticks_no_collision(monkeypatch):
    # 3 ticks, no sleep; each must produce a strictly-increasing ts with no ValueError
    seq = iter([
        [flight.frame_seat(_row("f:a"))],
        [flight.frame_seat(_row("f:a", cwd="/x"))],
        [flight.frame_seat(_row("f:a", cwd="/y"))],
    ])
    monkeypatch.setattr(recorder, "collect_live_frames", lambda: next(seq))
    res = recorder.run(_args(recorder_action="run", every=0, keyframe_every=10**9,
                             compact_every=0, ticks=3))
    assert res == {"ok": True, "ticks": 3}
    st = recorder.run(_args(recorder_action="status"))
    assert st["live"] == 1  # last set


def test_skip_when_mirror_unavailable():
    # collect returns None (mirror down) -> tick is SKIPPED, nothing recorded
    res = recorder.record_once(collect=lambda: None)
    assert res == {"ok": True, "skipped": "mirror-unavailable", "live": None}
    assert not flight.head_path().exists()


def test_skip_suspicious_total_wipe_but_record_partial():
    # establish a non-empty fleet
    recorder.record_once(collect=lambda: [flight.frame_seat(_row("f:a")), flight.frame_seat(_row("f:b"))])
    # a total empty-while-prev-nonempty is treated as a hiccup and skipped
    wipe = recorder.record_once(collect=lambda: [])
    assert wipe == {"ok": True, "skipped": "suspicious-empty-fleet", "live": 0}
    assert recorder.run(_args(recorder_action="status"))["live"] == 2  # last good frame intact
    # but a genuine PARTIAL change still records
    part = recorder.record_once(collect=lambda: [flight.frame_seat(_row("f:a"))])
    assert part["live"] == 1 and part["wrote_delta"]
    assert recorder.run(_args(recorder_action="status"))["live"] == 1


def test_next_ts_is_canonical_fixed_width():
    ts = recorder._next_ts(None)
    # always microseconds + fixed +00:00 offset, so lexicographic == chronological
    assert ts.endswith("+00:00")
    assert "." in ts and len(ts.split(".")[1]) == len("000000+00:00")
    # round-trips and stays strictly increasing even off a µs=0 prior
    assert recorder._next_ts("2026-06-25T12:00:00+00:00") > "2026-06-25T12:00:00+00:00"


def test_default_action_is_status():
    st = recorder.run(_args(recorder_action=None))
    assert st["ok"] and st["live"] == 0  # nothing recorded yet


def test_reconstruct_verb_returns_fleet_at_instant():
    t1 = "2026-06-25T12:00:00.000000+00:00"
    t2 = "2026-06-25T12:05:00.000000+00:00"
    flight.record_tick([flight.frame_seat(_row("f:a"))], now=t1, force_keyframe=True)
    flight.record_tick([flight.frame_seat(_row("f:a")), flight.frame_seat(_row("f:b"))], now=t2, force_keyframe=True)
    at1 = recorder.run(_args(recorder_action="reconstruct", at=t1))
    assert {s["target"] for s in at1["seats"]} == {"f:a"}
    # naive --at at the t2 instant still selects t2 (shared normalizer)
    at2 = recorder.run(_args(recorder_action="reconstruct", at="2026-06-25T12:05:00"))
    assert {s["target"] for s in at2["seats"]} == {"f:a", "f:b"}


def test_timeline_verb_lists_keyframes_and_bounds():
    t1 = "2026-06-25T12:00:00.000000+00:00"
    t2 = "2026-06-25T12:05:00.000000+00:00"
    flight.record_tick([flight.frame_seat(_row("f:a"))], now=t1, force_keyframe=True)
    flight.record_tick([flight.frame_seat(_row("f:a")), flight.frame_seat(_row("f:b"))], now=t2, force_keyframe=True)
    # a birth recorded as a DELTA after the last keyframe (no new keyframe)
    t3 = "2026-06-25T12:06:00.000000+00:00"
    flight.record_tick(
        [flight.frame_seat(_row("f:a")), flight.frame_seat(_row("f:b")), flight.frame_seat(_row("f:c"))],
        now=t3, keyframe_interval_s=10**9,  # NOT due -> delta only
    )
    tl = recorder.run(_args(recorder_action="timeline", from_ts=None, to_ts=None))
    assert tl["count"] == 2 and tl["first"] == t1
    assert tl["last"] == t3, "last must track newest activity (the post-keyframe delta), not last keyframe"
    # the births/deaths are surfaced as events the scrubber can snap to
    ev_ts = {e["ts"] for e in tl["events"]}
    assert t3 in ev_ts and "appear" in next(e["ops"] for e in tl["events"] if e["ts"] == t3)
    # window filter (normalized; date-only bound)
    tl2 = recorder.run(_args(recorder_action="timeline", from_ts=t2, to_ts=None))
    assert tl2["keyframes"] == [t2]


def test_flight_normalize_ts_messy_inputs_fixed_width():
    for raw in ("2026-06-25", "2026-06-25T12:00:00", "2026-06-25T12:00:00+00:00"):
        out = flight.normalize_ts(raw)
        assert out.endswith("+00:00") and out.split(".")[1] == "000000+00:00"
    from datetime import datetime, timezone
    assert flight.normalize_ts(datetime(2026, 6, 25, tzinfo=timezone.utc)) == "2026-06-25T00:00:00.000000+00:00"
