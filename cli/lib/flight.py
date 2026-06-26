"""Flight Recorder — a delta-encoded, keyframed timeline of the computed live fleet.

The live set is computed from tmux and evaporates on a host/tmux death. This module
persists that computed `seat_status` over time so a full shutdown is recoverable
deterministically and the fleet's history can be reconstructed at any instant T
(which also feeds a timeline animation).

It is a READ MODEL over time, not an authority: frames record what was live; restore
(a separate verb) replays through Aura's own gated spawn/bind path. This module is pure
in the sense that it never reads tmux or /proc and never writes the registry — the caller
(the recorder loop) supplies the already-enriched live seat list, and all time is an
injected `now`. That keeps it deterministic and testable with no tmux.

Storage (under state_root()/flight, honoring AURA_STATE_DIR):
    frames.jsonl      append-only delta lines   {schema, ts, prev_ts, changes:[...]}
    keyframes/<ts>.json  full snapshots          {schema, ts, seats:[...]}
    index.json        {keyframes:[ts,...], updated_at}
    head.json         recorder cache             {seats:[...], last_keyframe_ts, last_ts}

Reconstruct(at) = nearest keyframe with ts <= at, then replay delta lines with
kf_ts < ts <= at. The same-ts delta written beside a keyframe is excluded by the strict
lower bound, so there is no double-apply.
"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable

from lib.state import state_root

KEYFRAME_SCHEMA = "aura.flight.keyframe.v1"
DELTA_SCHEMA = "aura.flight.delta.v1"

# The one canonical timestamp format for the whole flight subsystem: fixed-width, aware-UTC,
# always 6-digit microseconds + literal +00:00. record_tick, the keyframe index sort, and
# reconstruct all compare ts as STRINGS, so every producer (recorder ticks, restore --at,
# the reconstruct/timeline verbs) MUST normalize through here or lexicographic order would
# diverge from chronological order.
_TS_FMT = "%Y-%m-%dT%H:%M:%S.%f+00:00"


def normalize_ts(value=None) -> str:
    """Canonicalize a timestamp to the flight format. Accepts None (->now), a datetime, or an
    iso string (date-only / naive / sub-second all expand to fixed width; naive assumes UTC)."""
    from datetime import datetime, timezone

    if value is None or (isinstance(value, str) and not value.strip()):
        dt = datetime.now(timezone.utc)
    elif isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(str(value).strip())
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime(_TS_FMT)

DEFAULT_KEYFRAME_INTERVAL_S = 300       # full snapshot at least every 5 min
DEFAULT_FULL_RES_WINDOW_S = 86_400      # keep fine deltas for 24h
DEFAULT_TTL_S = 604_800                 # drop everything older than 7d

# Fields copied verbatim from a cwd-enriched seat_status row into the frame tuple.
_PASSTHROUGH = ("target", "fleet", "seat", "runtime", "cwd", "seat_instance_id", "pane_ref")
# Fields whose change between ticks is recorded as an "update" op.
_UPDATE_FIELDS = ("session_id", "cwd", "pane_ref", "seat_instance_id", "binding", "report_state")


# ---------------------------------------------------------------------------
# Store paths
# ---------------------------------------------------------------------------

def flight_root() -> Path:
    return state_root() / "flight"


def frames_path() -> Path:
    return flight_root() / "frames.jsonl"


def keyframes_dir() -> Path:
    return flight_root() / "keyframes"


def index_path() -> Path:
    return flight_root() / "index.json"


def head_path() -> Path:
    return flight_root() / "head.json"


def _lock_path() -> Path:
    return flight_root() / ".lock"


@contextmanager
def _write_lock():
    """Single-writer flock around mutating writes. Reads are lock-free by design."""
    flight_root().mkdir(parents=True, exist_ok=True)
    fd = os.open(str(_lock_path()), os.O_WRONLY | os.O_CREAT, 0o644)
    try:
        try:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_EX)
        except (ImportError, OSError):
            pass  # best-effort; single recorder process is the contract
        yield
    finally:
        os.close(fd)


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# Projection
# ---------------------------------------------------------------------------

def frame_seat(row: dict[str, Any]) -> dict[str, Any]:
    """Project a (cwd-enriched) seat_status row into the stable frame tuple.

    session_id is the bound runtime session id ONLY — the authoritative, born-bound
    value; an unbound seat records session_id=None (never a reconstructed guess).
    """
    binding = row.get("runtime_session_binding") or row.get("binding")
    session_id = row.get("runtime_session_id") if binding == "bound" else None
    if session_id is None and binding == "bound":
        session_id = row.get("session_id")
    latest_report = row.get("latest_report") or {}
    seat = {
        "target": row.get("target"),
        "fleet": row.get("fleet"),
        "seat": row.get("seat") or row.get("name"),
        "runtime": row.get("runtime"),
        "session_id": session_id,
        "cwd": row.get("cwd"),
        "seat_instance_id": row.get("seat_instance_id"),
        "launch_id": row.get("aura_launch_id") or row.get("launch_id"),
        "pane_ref": row.get("pane_ref"),
        "binding": binding,
        "report_state": latest_report.get("state") if isinstance(latest_report, dict) else None,
    }
    return seat


def _as_map(seats: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for seat in seats:
        target = seat.get("target")
        if target:
            out[target] = seat
    return out


# ---------------------------------------------------------------------------
# Diff
# ---------------------------------------------------------------------------

def diff_frames(prev: dict[str, dict[str, Any]], curr: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Ordered change list turning `prev` into `curr`. Empty list == no change.

    Rename (target changed, same incarnation) is detected by a 1:1 non-null
    seat_instance_id match across the vanished/appeared sets; unmatched seats fall
    back to plain vanish+appear.
    """
    appeared = [t for t in curr if t not in prev]
    vanished = [t for t in prev if t not in curr]

    # rename detection: match appeared<->vanished by non-null si (1:1).
    vanished_by_si: dict[str, str] = {}
    for t in vanished:
        si = prev[t].get("seat_instance_id")
        if si:
            vanished_by_si.setdefault(si, t)  # first wins; a collision stays unmatched
    renamed_from: set[str] = set()
    renamed_to: set[str] = set()
    renames: list[dict[str, Any]] = []
    for t in appeared:
        si = curr[t].get("seat_instance_id")
        old = vanished_by_si.get(si) if si else None
        if old and old not in renamed_from:
            renames.append({"op": "rename", "from": old, "to": t, "seat": curr[t]})
            renamed_from.add(old)
            renamed_to.add(t)

    changes: list[dict[str, Any]] = []
    for t in vanished:
        if t not in renamed_from:
            changes.append({"op": "vanish", "target": t})
    for t in appeared:
        if t not in renamed_to:
            changes.append({"op": "appear", "seat": curr[t]})
    changes.extend(renames)

    # updates on seats present in both (and on rename targets — fields may shift too).
    for t in curr:
        old = prev.get(t)
        if old is None:
            continue
        fields = {k: curr[t].get(k) for k in _UPDATE_FIELDS if curr[t].get(k) != old.get(k)}
        if fields:
            changes.append({"op": "update", "target": t, "fields": fields})
    return changes


def _apply(seats: dict[str, dict[str, Any]], change: dict[str, Any]) -> None:
    op = change.get("op")
    if op == "appear":
        seat = change["seat"]
        seats[seat["target"]] = dict(seat)
    elif op == "vanish":
        seats.pop(change["target"], None)
    elif op == "rename":
        seats.pop(change["from"], None)
        seat = change["seat"]
        seats[seat["target"]] = dict(seat)
    elif op == "update":
        target = change["target"]
        if target in seats:
            seats[target] = {**seats[target], **change["fields"]}


# ---------------------------------------------------------------------------
# Record
# ---------------------------------------------------------------------------

def _iso(now: Any) -> str:
    if isinstance(now, str):
        return now
    return now.isoformat()


def record_tick(
    curr_seats: Iterable[dict[str, Any]],
    *,
    now: Any,
    keyframe_interval_s: int = DEFAULT_KEYFRAME_INTERVAL_S,
    force_keyframe: bool = False,
) -> dict[str, Any]:
    """Persist one observation. `curr_seats` is the already-enriched LIVE frame tuples.

    A quiet tick (no diff, keyframe not yet due) writes nothing. The first tick ever
    (no head) forces a keyframe so reconstruct always has an anchor.
    """
    ts = _iso(now)
    curr_map = _as_map(frame_seat(s) if "binding" not in s else s for s in curr_seats)

    with _write_lock():
        head = _read_json(head_path(), None)
        prev_map = _as_map(head.get("seats", [])) if head else {}
        last_ts = head.get("last_ts") if head else None
        last_keyframe_ts = head.get("last_keyframe_ts") if head else None

        if last_ts is not None and ts <= last_ts:
            raise ValueError(f"flight ts must strictly increase: {ts!r} <= {last_ts!r}")

        changes = diff_frames(prev_map, curr_map)

        # keyframe decision: first ever tick always; else interval elapsed.
        if last_keyframe_ts is None:
            keyframe_due = True
        else:
            keyframe_due = force_keyframe or _seconds_between(last_keyframe_ts, ts) >= keyframe_interval_s

        wrote_delta = False
        if changes:
            line = json.dumps(
                {"schema": DELTA_SCHEMA, "ts": ts, "prev_ts": last_ts, "changes": changes},
                ensure_ascii=False,
            )
            with frames_path().open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
            wrote_delta = True

        wrote_keyframe = False
        if keyframe_due:
            _write_keyframe(ts, list(curr_map.values()))
            last_keyframe_ts = ts
            wrote_keyframe = True

        _atomic_write_json(
            head_path(),
            {"seats": list(curr_map.values()), "last_keyframe_ts": last_keyframe_ts, "last_ts": ts},
        )

    return {"wrote_delta": wrote_delta, "wrote_keyframe": wrote_keyframe, "changes": len(changes)}


def _write_keyframe(ts: str, seats: list[dict[str, Any]]) -> None:
    keyframes_dir().mkdir(parents=True, exist_ok=True)
    path = keyframes_dir() / f"{_safe_ts(ts)}.json"
    if path.exists():
        raise ValueError(f"keyframe collision for ts {ts!r}")
    _atomic_write_json(path, {"schema": KEYFRAME_SCHEMA, "ts": ts, "seats": seats})
    index = _read_json(index_path(), {"keyframes": []})
    keyframes = index.get("keyframes", [])
    keyframes.append(ts)
    keyframes.sort()
    _atomic_write_json(index_path(), {"keyframes": keyframes, "updated_at": ts})


def _safe_ts(ts: str) -> str:
    return ts.replace(":", "").replace("+", "_").replace(".", "_")


def _seconds_between(a_iso: str, b_iso: str) -> float:
    from datetime import datetime

    return (datetime.fromisoformat(b_iso) - datetime.fromisoformat(a_iso)).total_seconds()


# ---------------------------------------------------------------------------
# Reconstruct
# ---------------------------------------------------------------------------

def reconstruct(at: Any) -> dict[str, Any]:
    """Fleet state at time `at`, from keyframes+frames alone (the source of truth)."""
    at_ts = _iso(at)
    index = _read_json(index_path(), {"keyframes": []})
    kf_ts = None
    for ts in index.get("keyframes", []):
        if ts <= at_ts:
            kf_ts = ts
        else:
            break
    if kf_ts is None:
        return {"ts": None, "seats": []}

    kf = _read_json(keyframes_dir() / f"{_safe_ts(kf_ts)}.json", {"seats": []})
    seats = _as_map(kf.get("seats", []))

    path = frames_path()
    if path.exists():
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    delta = json.loads(line)
                except json.JSONDecodeError:
                    continue
                d_ts = delta.get("ts")
                if d_ts is None or d_ts <= kf_ts:
                    continue
                if d_ts > at_ts:
                    break
                for change in delta.get("changes", []):
                    _apply(seats, change)

    return {"ts": at_ts, "seats": sorted(seats.values(), key=lambda s: s.get("target") or "")}


# ---------------------------------------------------------------------------
# Compaction / retention
# ---------------------------------------------------------------------------

def compact(
    *,
    now: Any,
    full_res_window_s: int = DEFAULT_FULL_RES_WINDOW_S,
    ttl_s: int = DEFAULT_TTL_S,
) -> dict[str, Any]:
    """Drop fine deltas older than the full-res window (anchored to a keyframe boundary)
    and drop everything older than the TTL. Reconstruct stays exact for any T at or after
    the surviving keyframe boundary; older T degrades to keyframe granularity.
    """
    now_ts = _iso(now)
    from datetime import datetime, timedelta

    now_dt = datetime.fromisoformat(now_ts)
    full_res_cutoff = (now_dt - timedelta(seconds=full_res_window_s)).isoformat()
    ttl_cutoff = (now_dt - timedelta(seconds=ttl_s)).isoformat()

    with _write_lock():
        index = _read_json(index_path(), {"keyframes": []})
        keyframes = sorted(index.get("keyframes", []))

        # delta drop anchor: the greatest keyframe ts <= full_res_cutoff. Never drop a
        # delta newer than the keyframe that covers the cutoff, or reconstruct just above
        # the cutoff would be inexact.
        drop_below = None
        for ts in keyframes:
            if ts <= full_res_cutoff:
                drop_below = ts
            else:
                break

        path = frames_path()
        bytes_before = path.stat().st_size if path.exists() else 0
        dropped_deltas = 0
        kept_lines: list[str] = []
        if path.exists():
            with path.open(encoding="utf-8") as fh:
                for line in fh:
                    s = line.strip()
                    if not s:
                        continue
                    try:
                        d_ts = json.loads(s).get("ts")
                    except json.JSONDecodeError:
                        continue
                    drop = d_ts is not None and (
                        d_ts < ttl_cutoff or (drop_below is not None and d_ts <= drop_below)
                    )
                    if drop:
                        dropped_deltas += 1
                    else:
                        kept_lines.append(s)
            tmp = path.with_suffix(".jsonl.tmp")
            tmp.write_text("".join(l + "\n" for l in kept_lines), encoding="utf-8")
            os.replace(tmp, path)
        bytes_after = path.stat().st_size if path.exists() else 0

        # drop keyframes older than the TTL.
        dropped_keyframes = 0
        surviving: list[str] = []
        for ts in keyframes:
            if ts < ttl_cutoff:
                kf_file = keyframes_dir() / f"{_safe_ts(ts)}.json"
                try:
                    kf_file.unlink()
                except OSError:
                    pass
                dropped_keyframes += 1
            else:
                surviving.append(ts)
        _atomic_write_json(index_path(), {"keyframes": surviving, "updated_at": now_ts})

    return {
        "dropped_deltas": dropped_deltas,
        "dropped_keyframes": dropped_keyframes,
        "bytes_before": bytes_before,
        "bytes_after": bytes_after,
    }
