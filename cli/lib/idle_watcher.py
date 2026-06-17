"""Idle-edge watcher — the sensed-completion seam.

Watches a placement of pool seats, fuses the cheap snapshot-delta posture signal
(``terminal_posture``) with the marker-based busy detector (``terminal_submit``),
debounces, and emits an ``aura report`` on the working -> idle falling edge.

Voiceless module: clock-in, report-out. It holds only a tiny per-seat gate so each
idle episode emits exactly once. Completion is *sensed, not signed* — a quiet pane
is a free seat. No hook, no anchor, no token.

The fusion is deliberately conservative about the dangerous direction. A false
*idle* (declaring a still-working seat free) lets the pool clobber live work, so a
seat reads idle ONLY when the diff is stable AND no busy/queued marker is present,
AND that has held for ``debounce`` consecutive samples. A false *busy* (an animated
idle screen that never settles) merely under-utilizes a seat — the safe failure,
tuned live per runtime.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable

from lib import placements, registry, reports, result_anchor, state, terminal_posture, terminal_submit


WATCHER_STATE_DIRNAME = "idle-watcher"
IDLE_SOURCE = "idle-watcher"
DEFAULT_DEBOUNCE = 2
DEFAULT_LINES = 80


def watcher_state_path() -> Path:
    return state.state_root() / WATCHER_STATE_DIRNAME / "state.json"


def read_state() -> dict[str, Any]:
    path = watcher_state_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def write_state(data: dict[str, Any]) -> None:
    path = watcher_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".state-", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
            f.write("\n")
        Path(tmp).replace(path)
    finally:
        try:
            Path(tmp).unlink()
        except FileNotFoundError:
            pass


def hash_capture(lines) -> str:
    text = terminal_posture.strip_ansi(terminal_posture.output_to_text(lines))
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()


def classify(previous_hash: str | None, lines: list[str]) -> dict[str, Any]:
    """Fuse the snapshot-delta (diff) and marker (busy) signals into idle/working.

    idle  := diff says the capture did not change since last sample
             AND no busy/queued marker is present.
    Anything else is working. The first sample (no previous_hash) is "unknown" to
    the diff and therefore reads working — we never declare idle without evidence.
    """
    output_hash = hash_capture(lines)
    delta = terminal_posture.classify_delta(previous_hash=previous_hash, output_hash=output_hash)
    blocker = terminal_submit.delivery_blocker(lines)
    diff_idle = delta["state"] == "idle"
    marker_busy = blocker is not None
    state_value = "idle" if (diff_idle and not marker_busy) else "working"
    return {
        "state": state_value,
        "output_hash": output_hash,
        "diff_state": delta["state"],
        "blocker": blocker,
    }


def decide(prev: dict[str, Any] | None, classification: dict[str, Any], *, debounce: int) -> tuple[dict[str, Any], bool]:
    """Advance the per-seat gate. Returns (new_state, emit?).

    ``emit`` fires once on the debounced working -> idle edge and re-arms only after
    the seat is seen working again, so one idle episode yields exactly one report.
    """
    prev = prev or {}
    state_value = classification["state"]
    idle_ticks = int(prev.get("idle_ticks", 0)) + 1 if state_value == "idle" else 0
    confirmed_idle = idle_ticks >= max(1, int(debounce))
    emitted = bool(prev.get("emitted", False))

    emit = False
    if confirmed_idle and not emitted:
        emit = True
        emitted = True
    if state_value == "working":
        emitted = False  # re-arm for the next idle episode

    new_state = {
        "last_state": "idle" if confirmed_idle else "working",
        "idle_ticks": idle_ticks,
        "emitted": emitted,
        "output_hash": classification["output_hash"],
    }
    return new_state, emit


def live_members(placement_name: str) -> list[dict[str, Any]]:
    record = placements.get_placement(placement_name)
    if not record:
        return []
    members: list[dict[str, Any]] = []
    for member in record.get("members", []):
        ref = member.get("seat_ref")
        if not ref:
            continue
        row = registry.resolve_live(ref)
        if not row:
            continue
        members.append({
            "seat_ref": ref,
            "fleet": row.get("fleet"),
            "seat": row.get("seat") or row.get("name"),
            "row": row,
        })
    return members


def _capture(seat_ref: str, lines: int) -> tuple[bool, list[str]]:
    import argparse

    from commands import check  # lazy: commands import lib

    ns = argparse.Namespace(name=seat_ref, output=True, lines=lines, format="text")
    try:
        result = check.run(ns)
    except Exception:
        return False, []
    if not isinstance(result, dict) or result.get("terminal") != "alive":
        return False, []
    out = result.get("output")
    return True, [str(x) for x in out] if isinstance(out, list) else []


def _resolve_anchor(member: dict[str, Any]) -> dict[str, Any] | None:
    """Best-effort latest-assistant anchor for a member (post-flush, from outside)."""
    try:
        return result_anchor.latest_assistant_anchor(member.get("row"), member.get("seat_ref"))
    except Exception:
        return None


def _emit_idle(member: dict[str, Any], idle_ticks: int, anchor: dict[str, Any] | None = None) -> dict[str, Any]:
    record = {
        "state": "idle",
        "seat": member.get("seat"),
        "fleet": member.get("fleet"),
        "seat_ref": member.get("seat_ref"),
        "source": IDLE_SOURCE,
        "work": f"{member.get('seat_ref')} went idle",
        "idle_ticks": idle_ticks,
    }
    if anchor and anchor.get("anchor"):
        # Demoted citation pointer — a reference to what the seat last produced, NOT a
        # success claim. The consumer resolves it; the report still only asserts idle.
        # flex_chunk_id is `session_<line>` — a Flex chunk id, resolvable via the index.
        record["anchor"] = anchor["anchor"]
        record["flex_chunk_id"] = anchor.get("flex_chunk_id")
        record["result_position"] = anchor.get("position")
        record["result_sha256"] = anchor.get("sha256")
    return reports.append_report(record)


def tick(
    placement_name: str,
    *,
    debounce: int = DEFAULT_DEBOUNCE,
    lines: int = DEFAULT_LINES,
    with_anchor: bool = False,
    capture_fn: Callable[[str, int], tuple[bool, list[str]]] | None = None,
    emit_fn: Callable[..., dict[str, Any]] | None = None,
    members_fn: Callable[[str], list[dict[str, Any]]] | None = None,
    anchor_fn: Callable[[dict[str, Any]], dict[str, Any] | None] | None = None,
) -> dict[str, Any]:
    """One watch pass over a placement. I/O hooks are injectable for tests.

    ``with_anchor`` opportunistically stamps a result anchor on each idle-edge report
    (post-flush, resolved from outside the seat) so a result pointer rides the bus.
    """
    capture_fn = capture_fn or _capture
    emit_fn = emit_fn or _emit_idle
    members_fn = members_fn or live_members
    anchor_fn = anchor_fn or _resolve_anchor

    state_data = read_state()
    members = members_fn(placement_name)
    emitted: list[str] = []
    for member in members:
        ref = member["seat_ref"]
        alive, capture = capture_fn(ref, lines)
        if not alive:
            continue
        prev = state_data.get(ref)
        prev_hash = (prev or {}).get("output_hash")
        classification = classify(prev_hash, capture)
        new_state, emit = decide(prev, classification, debounce=debounce)
        state_data[ref] = new_state
        if emit:
            anchor = anchor_fn(member) if with_anchor else None
            emit_fn(member, new_state["idle_ticks"], anchor)
            emitted.append(ref)
    write_state(state_data)
    return {"ok": True, "placement": placement_name, "members": len(members), "emitted_idle": emitted}
