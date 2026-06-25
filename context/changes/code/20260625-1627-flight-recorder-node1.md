# Code Receipt — Flight Recorder Node 1 (flight.py core)

## What changed
- NEW `cli/lib/flight.py` — delta-encoded, keyframed timeline of the computed live fleet.
  Pure (no tmux/proc reads, no registry writes); caller injects the enriched live seat list
  and `now`. Storage under `state_root()/flight/` (honors `AURA_STATE_DIR`):
  `frames.jsonl` (delta lines), `keyframes/<ts>.json`, `index.json`, `head.json`.
  - `frame_seat(row)` — projects a seat_status row → stable tuple; `session_id` is the
    bound `runtime_session_id` ONLY (authoritative, born-bound) — unbound ⇒ None.
  - `diff_frames(prev, curr)` — appear/vanish/update/rename ops; rename matched by non-null
    `seat_instance_id` (null si ⇒ vanish+appear, never a false rename).
  - `record_tick(curr, *, now, keyframe_interval_s, force_keyframe)` — appends a delta only
    on change; keyframe on first-ever tick and every interval; strictly-increasing `ts`
    enforced (`ValueError` on regression); single-writer flock; quiet tick writes nothing.
  - `reconstruct(at)` — nearest keyframe ≤ at, replay deltas in `(kf_ts, at]`. Empty store ⇒
    `{ts:None, seats:[]}`.
  - `compact(*, now, full_res_window_s=86400, ttl_s=604800)` — drops fine deltas older than the
    full-res window **anchored to the keyframe boundary** (`drop_below = greatest keyframe ≤
    cutoff`; deltas with `ts ≤ drop_below` dropped), drops keyframes/deltas past the TTL.
    Atomic (`.tmp` + `os.replace`). Reconstruct stays exact for any T at/after the surviving
    keyframe boundary.
- NEW `tests/test_flight.py` — 12 tests (below).

## Why
Restore after a full WSL/tmux death was reconstructed from the weak observe-ledger tier, which
picked 10/28 stale sessions and surfaced a manager/memory swap. The recorder persists Aura's
own authoritative live state (born-bound session ids) on a cadence so restore is deterministic;
the same timeline feeds a future animation. This node is the data core only.

## Verification
`cd cli && python -m pytest ../tests/test_flight.py -q` → **12 passed**.
The retention-boundary test was proven to FAIL against a naive "drop all deltas <24h"
compaction (reconstruct drift on a dropped gap delta) and PASS against the keyframe-anchored
implementation — so it genuinely guards the critic's boundary fix.

## Critic gate
Plan failed the first critic pass (6 fixes); all folded into Plan v2 and implemented:
retention boundary, empty-store/first-tick, ts monotonicity+filename collision, null-si rename,
atomic compact, projection key mapping (`aura_launch_id`/`latest_report.state`/`runtime_session_binding`).

## Scope / boundary
Additive: one new lib module + one new test file + receipts. No existing file touched. Unrelated
untracked WIP (`autoresearch/`, `spike/`, `compact_recovery*`, `.gjc/`) left alone.

## Next
Node 2 (`aura recorder` loop+service: list_seat_statuses → filter LIVE → enrich cwd from /proc →
record_tick; schedule compact). Node 3 (`aura restore --from-snapshot/--at`). Node 4 (timeline + animation).
