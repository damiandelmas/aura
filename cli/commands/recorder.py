"""`aura recorder` — the flight recorder loop.

Samples the computed live fleet (`seat_status.list_seat_statuses`), enriches each LIVE
seat's cwd from the tmux mirror's `pane_current_path`, and persists it through
`flight.record_tick`. Delta-encoded, so a quiet tick costs ~0 bytes; a keyframe lands on
the first tick and every interval. `compact` is run on a slower cadence for retention.

The data source and store are owned by `lib.flight` (pure); this command owns the IO
(tmux read) and the loop. All persistence-shaping logic stays in flight so it stays testable.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from lib import flight, pane_handle, seat_status, tmux_mirror


# --------------------------------------------------------------------------- pure helpers

def pane_id_from_ref(pane_ref: str | None) -> str | None:
    """`tmux:fleet:%N` -> `%N`, via the single owner of the ref format (pane_handle),
    so legacy/bare forms parse the same way the rest of Aura parses them."""
    handle = pane_handle.PaneHandle.from_ref(pane_ref)
    return handle.pane_id if handle else None


def frames_from_rows(rows: list[dict[str, Any]], pane_cwd: dict[str, str]) -> list[dict[str, Any]]:
    """Project the LIVE seat_status rows into flight frame tuples, enriching cwd from the
    pane map (tmux's own pane_current_path), which is reliably present for a live pane even
    when the registry row lacks cwd."""
    frames: list[dict[str, Any]] = []
    for row in rows:
        if row.get("liveness") != "alive":
            continue
        fs = flight.frame_seat(row)
        pid = pane_id_from_ref(row.get("pane_ref"))
        cwd = pane_cwd.get(pid) if pid else None
        if cwd:
            fs["cwd"] = cwd
        frames.append(fs)
    return frames


def _read_head() -> dict[str, Any] | None:
    try:
        return json.loads(flight.head_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


# Canonical, fixed-width, aware-UTC ISO so lexicographic order == chronological order
# (record_tick, the keyframe index sort, and reconstruct all compare ts as strings).
# datetime.isoformat() drops the fractional part when microsecond==0, which would mix
# widths across ticks — so format microseconds explicitly, always.
_TS_FMT = "%Y-%m-%dT%H:%M:%S.%f+00:00"


def _canonical(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime(_TS_FMT)


def _next_ts(last_ts: str | None) -> str:
    """A strictly-increasing canonical UTC iso timestamp. Guards against same-microsecond
    ticks and a clock that did not advance since the persisted head (which record_tick rejects)."""
    now = datetime.now(timezone.utc)
    if last_ts:
        try:
            prev = datetime.fromisoformat(last_ts)
            if now <= prev:
                now = prev + timedelta(microseconds=1)
        except ValueError:
            pass
    return _canonical(now)


# --------------------------------------------------------------------------- IO collectors

def collect_live_frames() -> list[dict[str, Any]] | None:
    """The LIVE fleet as flight frame tuples, or None when the tmux mirror is unavailable.

    None is a deliberate "no observation" sentinel: when the mirror can't be read (a tmux
    blip, a WSL resume), `list_seat_statuses` would mark every seat liveness=="unknown" and
    a naive recorder would write a full mass-vanish — the exact false "everyone died" the
    recorder exists to prevent. Returning None makes the caller SKIP the tick instead.
    """
    mirror = tmux_mirror.list_physical_panes()
    if not mirror.get("ok"):
        return None
    pane_cwd: dict[str, str] = {}
    for pane in mirror.get("panes", []):
        pid = pane.get("pane_id")
        cwd = pane.get("pane_current_path")
        if pid and cwd:
            pane_cwd[str(pid)] = str(cwd)
    rows = seat_status.list_seat_statuses(include_hidden=False)
    return frames_from_rows(rows, pane_cwd)


# --------------------------------------------------------------------------- orchestration

def record_once(
    *,
    collect: Callable[[], list[dict[str, Any]] | None] | None = None,
    keyframe_interval_s: float = 300.0,
) -> dict[str, Any]:
    # Resolve the collector at call time (module global) so a monkeypatched
    # collect_live_frames is honored and the default isn't frozen at def-time.
    frames = (collect or collect_live_frames)()
    if frames is None:
        return {"ok": True, "skipped": "mirror-unavailable", "live": None}

    head = _read_head()
    prev_had_seats = bool(head and head.get("seats"))
    # A total wipe (empty now, non-empty before) is almost always a mirror hiccup, not a
    # real mass-death — and even a real full shutdown is better preserved as the last good
    # frame than overwritten by an empty one. Skip it; a genuine partial change still records.
    if not frames and prev_had_seats:
        return {"ok": True, "skipped": "suspicious-empty-fleet", "live": 0}

    now = _next_ts(head.get("last_ts") if head else None)
    res = flight.record_tick(frames, now=now, keyframe_interval_s=int(keyframe_interval_s))
    return {"ok": True, **res, "live": len(frames), "ts": now}


def _status() -> dict[str, Any]:
    head = None
    try:
        head = json.loads(flight.head_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass
    index = {"keyframes": []}
    try:
        index = json.loads(flight.index_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass
    frames_bytes = flight.frames_path().stat().st_size if flight.frames_path().exists() else 0
    return {
        "ok": True,
        "live": len(head.get("seats", [])) if head else 0,
        "last_ts": head.get("last_ts") if head else None,
        "last_keyframe_ts": head.get("last_keyframe_ts") if head else None,
        "keyframes": len(index.get("keyframes", [])),
        "frames_bytes": frames_bytes,
    }


def _recorder_lock_path() -> str:
    return str(flight.flight_root() / ".recorder.lock")


def _run_loop(args) -> dict[str, Any]:
    """Single-instance sampling loop. Bounded by --ticks when provided (tests)."""
    flight.flight_root().mkdir(parents=True, exist_ok=True)
    fd = os.open(_recorder_lock_path(), os.O_WRONLY | os.O_CREAT, 0o644)
    try:
        import fcntl

        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return {"ok": False, "error": "recorder-already-running"}
    except ImportError:
        pass

    # NB: default only when the attr is missing/None — never via `or`, which would turn a
    # legitimate 0 (e.g. --every 0) into the default.
    def _num(name, default):
        val = getattr(args, name, None)
        return default if val is None else float(val)

    every = _num("every", 10.0)
    keyframe_every = _num("keyframe_every", 300.0)
    compact_every = _num("compact_every", 3600.0)
    max_ticks = getattr(args, "ticks", None)

    every = max(every, 0.0)
    ticks = 0
    last_compact = time.monotonic()
    try:
        while True:
            # A tmux blip must not crash-loop the unit: a failed tick is skipped, not fatal.
            try:
                record_once(keyframe_interval_s=keyframe_every)
                if compact_every > 0 and time.monotonic() - last_compact >= compact_every:
                    flight.compact(now=_next_ts(_head_last_ts()))
                    last_compact = time.monotonic()
            except Exception:  # noqa: BLE001 — recorder must survive a transient error
                pass
            ticks += 1
            if max_ticks is not None and ticks >= max_ticks:
                break
            if every > 0:
                time.sleep(every)
    finally:
        os.close(fd)
    return {"ok": True, "ticks": ticks}


def _head_last_ts() -> str | None:
    head = _read_head()
    return head.get("last_ts") if head else None


def run(args):
    action = getattr(args, "recorder_action", None) or "status"
    if action == "run":
        return _run_loop(args)
    if action == "once":
        kf = getattr(args, "keyframe_every", None)
        return record_once(keyframe_interval_s=300.0 if kf is None else float(kf))
    if action == "compact":
        return {"ok": True, **flight.compact(now=_next_ts(_head_last_ts()))}
    return _status()
