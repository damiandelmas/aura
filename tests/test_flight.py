"""Tests for the flight recorder core (cli/lib/flight.py).

AURA_STATE_DIR is repointed to a per-test tmpdir by the autouse conftest fixture,
so every artifact lands under <tmp>/.aura/flight and the live store is never touched.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from lib import flight


# --------------------------------------------------------------------------- helpers

def _seat(target, *, session_id="s-1", cwd="/p", si="si-1", binding="bound", pane="tmux:f:%1", report=None):
    fleet, _, seat = target.partition(":")
    return {
        "target": target,
        "fleet": fleet,
        "seat": seat,
        "runtime": "claude-code",
        "session_id": session_id,
        "cwd": cwd,
        "seat_instance_id": si,
        "launch_id": "L1",
        "pane_ref": pane,
        "binding": binding,
        "report_state": report,
    }


def _t(base, secs):
    return (base + timedelta(seconds=secs)).isoformat()


def _state_map(reconstructed):
    return {s["target"]: s for s in reconstructed["seats"]}


# --------------------------------------------------------------------------- diff

def test_diff_appear_vanish_update_noop():
    a = _seat("f:a")
    assert flight.diff_frames({}, {"f:a": a}) == [{"op": "appear", "seat": a}]
    assert flight.diff_frames({"f:a": a}, {}) == [{"op": "vanish", "target": "f:a"}]
    assert flight.diff_frames({"f:a": a}, {"f:a": a}) == []

    moved = _seat("f:a", cwd="/q")
    changes = flight.diff_frames({"f:a": a}, {"f:a": moved})
    assert changes == [{"op": "update", "target": "f:a", "fields": {"cwd": "/q"}}]

    rebound = _seat("f:a", session_id="s-2")
    changes = flight.diff_frames({"f:a": a}, {"f:a": rebound})
    assert changes == [{"op": "update", "target": "f:a", "fields": {"session_id": "s-2"}}]


def test_diff_rename_by_seat_instance():
    old = _seat("f:old", si="si-X")
    new = _seat("f:new", si="si-X")
    changes = flight.diff_frames({"f:old": old}, {"f:new": new})
    assert changes == [{"op": "rename", "from": "f:old", "to": "f:new", "seat": new}]


def test_diff_null_si_is_not_a_rename():
    # Two unrelated seats with no seat_instance_id must NOT be mislabeled a rename.
    old = _seat("f:old", si=None)
    new = _seat("f:new", si=None)
    changes = flight.diff_frames({"f:old": old}, {"f:new": new})
    ops = sorted(c["op"] for c in changes)
    assert ops == ["appear", "vanish"]


# --------------------------------------------------------------------------- projection

def test_frame_seat_maps_seat_status_row_keys():
    row = {
        "target": "f:a", "fleet": "f", "seat": "a", "runtime": "claude-code",
        "runtime_session_binding": "bound", "runtime_session_id": "S",
        "cwd": "/p", "seat_instance_id": "si", "aura_launch_id": "L",
        "pane_ref": "tmux:f:%1", "latest_report": {"state": "working"},
    }
    fs = flight.frame_seat(row)
    assert fs["session_id"] == "S"
    assert fs["launch_id"] == "L"
    assert fs["binding"] == "bound"
    assert fs["report_state"] == "working"


def test_frame_seat_unbound_records_no_session_id():
    row = {
        "target": "f:a", "fleet": "f", "seat": "a", "runtime": "claude-code",
        "runtime_session_binding": "unbound", "runtime_session_id": "leaked",
    }
    assert flight.frame_seat(row)["session_id"] is None


# --------------------------------------------------------------------------- record / reconstruct

def test_first_tick_forces_keyframe_and_empty_store_reconstructs_empty():
    base = datetime(2026, 6, 25, 12, 0, tzinfo=timezone.utc)
    # empty store
    assert flight.reconstruct(_t(base, 0)) == {"ts": None, "seats": []}
    res = flight.record_tick([_seat("f:a")], now=_t(base, 0))
    assert res["wrote_keyframe"] is True
    assert flight.keyframes_dir().exists()
    got = _state_map(flight.reconstruct(_t(base, 0)))
    assert set(got) == {"f:a"}


def test_ts_must_strictly_increase():
    base = datetime(2026, 6, 25, 12, 0, tzinfo=timezone.utc)
    flight.record_tick([_seat("f:a")], now=_t(base, 10))
    with pytest.raises(ValueError):
        flight.record_tick([_seat("f:a")], now=_t(base, 10))
    with pytest.raises(ValueError):
        flight.record_tick([_seat("f:a")], now=_t(base, 5))


def test_quiet_tick_writes_nothing():
    base = datetime(2026, 6, 25, 12, 0, tzinfo=timezone.utc)
    flight.record_tick([_seat("f:a")], now=_t(base, 0), keyframe_interval_s=300)
    size0 = flight.frames_path().stat().st_size if flight.frames_path().exists() else 0
    kf0 = len(list(flight.keyframes_dir().glob("*.json")))
    # identical set, well within the keyframe interval -> no write at all
    res = flight.record_tick([_seat("f:a")], now=_t(base, 10), keyframe_interval_s=300)
    assert res == {"wrote_delta": False, "wrote_keyframe": False, "changes": 0}
    size1 = flight.frames_path().stat().st_size if flight.frames_path().exists() else 0
    kf1 = len(list(flight.keyframes_dir().glob("*.json")))
    assert size1 == size0 and kf1 == kf0


def test_property_keyframe_plus_delta_equals_full_snapshot():
    base = datetime(2026, 6, 25, 12, 0, tzinfo=timezone.utc)
    # scripted history: spawns, rebind, cwd move, rename, death. spacing 10s,
    # keyframe interval 25s -> keyframes fall mid-sequence, exercising the boundary.
    states = [
        [_seat("f:a")],
        [_seat("f:a"), _seat("f:b", si="si-b")],
        [_seat("f:a", session_id="s-2"), _seat("f:b", si="si-b")],          # rebind a
        [_seat("f:a", session_id="s-2", cwd="/q"), _seat("f:b", si="si-b")],  # move a
        [_seat("f:a", session_id="s-2", cwd="/q"), _seat("f:renamed", si="si-b")],  # rename b
        [_seat("f:renamed", si="si-b")],                                      # a dies
    ]
    times = []
    for i, st in enumerate(states):
        ts = _t(base, i * 10)
        times.append(ts)
        flight.record_tick(st, now=ts, keyframe_interval_s=25)

    for ts, st in zip(times, states):
        got = _state_map(flight.reconstruct(ts))
        expected = {s["target"]: s for s in st}
        assert got == expected, f"reconstruct({ts}) mismatch"

    # at least one keyframe AND one delta-only tick existed (boundary really exercised)
    assert len(list(flight.keyframes_dir().glob("*.json"))) >= 2
    assert flight.frames_path().stat().st_size > 0


# --------------------------------------------------------------------------- compaction

def test_compact_retention_boundary_is_exact():
    now = datetime(2026, 6, 25, 12, 0, tzinfo=timezone.utc)
    # 6-hourly ticks across 9 days, keyframe every 5th tick (every 30h) — deliberately
    # MISALIGNED with the 24h full-res cutoff so the cutoff lands mid-gap, with a delta
    # strictly between the covering keyframe and the cutoff. That delta is exactly what a
    # naive "drop all deltas <24h" compaction would lose; this test guards against it.
    t = now - timedelta(days=9)
    i = 0
    while t <= now:
        seat = _seat("f:a", cwd=f"/p{i % 2}", si="si-a")
        flight.record_tick(
            [seat], now=t.isoformat(), keyframe_interval_s=10**9,
            force_keyframe=(i % 5 == 0),
        )
        t += timedelta(hours=6)
        i += 1

    full_res_cutoff = (now - timedelta(seconds=flight.DEFAULT_FULL_RES_WINDOW_S)).isoformat()
    index = flight._read_json(flight.index_path(), {"keyframes": []})
    drop_below = None
    for ts in index["keyframes"]:
        if ts <= full_res_cutoff:
            drop_below = ts
        else:
            break
    assert drop_below is not None and drop_below < full_res_cutoff, "need a keyframe strictly below the cutoff"

    # there must be at least one delta strictly inside (drop_below, cutoff] — the guard window
    gap_delta_ts = None
    with flight.frames_path().open() as fh:
        for line in fh:
            import json as _j
            d_ts = _j.loads(line)["ts"]
            if drop_below < d_ts <= full_res_cutoff:
                gap_delta_ts = d_ts
                break
    assert gap_delta_ts is not None, "test did not produce a delta in the guard window"

    # snapshots BEFORE compaction, including a probe INSIDE the guard window
    probe_recent = (now - timedelta(seconds=flight.DEFAULT_FULL_RES_WINDOW_S) + timedelta(seconds=1)).isoformat()
    before = {
        ts: _state_map(flight.reconstruct(ts))
        for ts in (drop_below, gap_delta_ts, full_res_cutoff, probe_recent, now.isoformat())
    }

    res = flight.compact(now=now.isoformat())
    assert res["dropped_deltas"] > 0
    assert res["bytes_after"] < res["bytes_before"]

    # exactness preserved for every probe at/after the surviving keyframe boundary
    for ts, snap in before.items():
        assert _state_map(flight.reconstruct(ts)) == snap, f"reconstruct({ts}) drifted after compact"


def test_compact_drops_beyond_ttl():
    now = datetime(2026, 6, 25, 12, 0, tzinfo=timezone.utc)
    old = (now - timedelta(days=9)).isoformat()
    recent = (now - timedelta(hours=1)).isoformat()
    flight.record_tick([_seat("f:a")], now=old, force_keyframe=True)
    flight.record_tick([_seat("f:a"), _seat("f:b", si="si-b")], now=recent, force_keyframe=True)
    res = flight.compact(now=now.isoformat())
    assert res["dropped_keyframes"] >= 1
    # the surviving recent keyframe still reconstructs the latest set
    got = _state_map(flight.reconstruct(now.isoformat()))
    assert set(got) == {"f:a", "f:b"}


# --------------------------------------------------------------------------- isolation

def test_artifacts_are_under_state_dir():
    base = datetime(2026, 6, 25, 12, 0, tzinfo=timezone.utc)
    flight.record_tick([_seat("f:a")], now=_t(base, 0))
    root = flight.flight_root()
    assert str(root).endswith("/.aura/flight")
    assert (root / "keyframes").exists()
    assert (root / "head.json").exists()
