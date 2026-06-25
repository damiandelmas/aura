# Plan — Node 1: cli/lib/flight.py + tests/test_flight.py

## Module API (`cli/lib/flight.py`, pure: no tmux/proc calls)

```
KEYFRAME_SCHEMA = "aura.flight.keyframe.v1"
DELTA_SCHEMA    = "aura.flight.delta.v1"

# store (honors AURA_STATE_DIR via state.state_root())
flight_root()    -> state_root()/"flight"
frames_path()    -> flight_root()/"frames.jsonl"      # append-only deltas
keyframes_dir()  -> flight_root()/"keyframes"         # <ts>.json full snapshots
index_path()     -> flight_root()/"index.json"        # {keyframes:[ts,...], updated_at}
head_path()      -> flight_root()/"head.json"         # recorder cache: {seats, last_keyframe_ts}

# projection — stable frame tuple from a seat_status row (already cwd-enriched by caller)
frame_seat(row) -> {
  target, fleet, seat, runtime,
  session_id,        # row.runtime_session_id IF binding=="bound" else None
  cwd, seat_instance_id, launch_id, pane_ref, binding, report_state }

# diff: ordered list of changes between two {target: frame_seat} maps
diff_frames(prev, curr) -> [
  {op:"appear", seat:{...}},
  {op:"vanish", target:"f:s"},
  {op:"rename", from:"f:old", to:"f:new", seat:{...}},     # matched by seat_instance_id
  {op:"update", target:"f:s", fields:{<changed subset of session_id,cwd,pane_ref,
                                       seat_instance_id,binding,report_state>}} ]

# record one tick (injected live set → persisted frames). now is an aware datetime/iso.
record_tick(curr_seats, *, now, keyframe_interval_s=300, force_keyframe=False) -> {
  wrote_delta:bool, wrote_keyframe:bool, changes:int }

# reconstruct fleet state at time T (source of truth = keyframes + frames)
reconstruct(at) -> {ts, seats:[frame_seat,...]}   # latest kf ≤ at, apply deltas kf.ts<ts≤at

# retention
compact(*, now, full_res_window_s=86400, ttl_s=604800) -> {dropped_deltas, dropped_keyframes, bytes_before, bytes_after}
```

### Semantics
- `record_tick`: read `head.json` (last recorded seats + last_keyframe_ts) → `diff_frames` →
  if changes, append one delta line `{schema,ts,prev_ts,changes}`; if
  `now - last_keyframe_ts ≥ interval` or `force_keyframe`, write `keyframes/<ts>.json` +
  push ts to index; always rewrite `head.json` to curr. Empty diff + no keyframe due ⇒ writes nothing.
- `reconstruct`: nearest keyframe with `ts ≤ at` (or empty if none), then replay frame lines with
  `kf_ts < ts ≤ at`. `appear`/`update`/`rename` mutate the map; `vanish` removes.
- `compact`: drop delta lines with `ts < now-full_res_window` (24h); drop keyframes + deltas with
  `ts < now-ttl` (7d). Rewrite `frames.jsonl`, prune `keyframes/` + index. Reconstruct of any
  T newer than 24h stays exact; older T degrades to ≤keyframe-interval granularity (by design).
- Single-writer: wrap frames/keyframe/head writes in a `flock` on `flight_root()/.lock` (cheap;
  mirrors registry discipline). Reads are lock-free.

## Files
- NEW `cli/lib/flight.py` (~220 lines)
- NEW `tests/test_flight.py` (~180 lines)

## Acceptance checks (proof the node closes)
1. `diff_frames` unit: appear, vanish, update(session_id), update(cwd), rename(by si) each emit the
   right op; no-op when identical.
2. **Property — keyframe+delta == full snapshot**: drive a scripted sequence of ticks (spawns,
   rebinds, cwd moves, renames, deaths) with monotonic injected `now`; assert `reconstruct(t_i).seats`
   equals the curr set passed at each tick `t_i`, for every i, across a keyframe boundary.
3. Quiet tick: identical curr set, before keyframe interval → `frames.jsonl` byte-length unchanged,
   no new keyframe.
4. `session_id` is `None` in the frame for an unbound seat; equals `runtime_session_id` for a bound one.
5. `compact`: after a 9-day scripted history, deltas <24h kept, deltas 24h–7d dropped, keyframes/deltas
   >7d dropped; `reconstruct(now)` still exact; `bytes_after < bytes_before`.
6. `AURA_STATE_DIR` isolation: with env pointed at a tmpdir, every artifact lands under `<tmp>/flight/`
   and nothing touches the real `~/.aura`.

## Test command
`cd cli && python -m pytest ../tests/test_flight.py -q`  (confirm import root in conftest first)

## Risks / mitigations
- Rename ambiguity if two seats swap si simultaneously → rename matches 1:1 by si; unmatched fall back
  to vanish+appear. Documented; acceptable for v1.
- frames.jsonl growth → bounded by compact() (Node 2 schedules it); reconstruct scans from last
  keyframe only, not genesis.
- Clock injection: all time is a passed-in `now` (prod recorder passes real `datetime.now(tz=utc)`);
  no `Date.now`-style nondeterminism inside flight.py beyond the injected value.

## Critic fixes incorporated (Plan v2 — gate returned FAIL, all folded in)
1. **Retention boundary (was inexact above 24h).** `compact` drops deltas only up to a keyframe
   boundary: `drop_below = greatest keyframe ts ≤ now-full_res_window`; delete delta lines with
   `ts ≤ drop_below` (never a delta newer than the keyframe that covers the cutoff). Reconstruct of
   any T ≥ `drop_below` stays exact. Add acceptance assertion at `T = cutoff + epsilon`, not just `now`.
2. **First tick / empty store.** No `head.json` ⇒ first `record_tick` FORCES a keyframe (guard the
   `now - last_keyframe_ts` arithmetic on None). `reconstruct` with no keyframe ≤ at returns
   `{ts: None, seats: []}`.
3. **ts monotonicity.** `ts` must be strictly increasing; `record_tick` rejects `now ≤ last_ts`
   (raises `ValueError`). Keyframe filename `<ts>.json` therefore cannot collide; assert it.
4. **Rename only on non-null si.** appear↔vanish rename match requires both `seat_instance_id`
   present and equal; None si is unmatchable → falls back to vanish+appear.
5. **Atomic compact.** Rewrite `frames.jsonl.tmp` then `os.replace`; prune keyframes/index after the
   swap. Reads stay lock-free and never see a torn file.
6. **Projection key mapping.** `frame_seat`: `launch_id ← row["aura_launch_id"]`,
   `report_state ← (row.get("latest_report") or {}).get("state")`,
   `binding ← row["runtime_session_binding"]`, `session_id ← runtime_session_id if binding=="bound"`.

## Dirty-worktree constraint
Only add NEW files (`cli/lib/flight.py`, `tests/test_flight.py`, receipts under `context/changes/`).
Do not touch the unrelated untracked WIP (`autoresearch/`, `spike/`, `compact_recovery*`).
