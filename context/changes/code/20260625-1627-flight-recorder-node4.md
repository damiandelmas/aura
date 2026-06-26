# Code Receipt — Flight Recorder Node 4 (timeline data API)

Node 4 splits: the timeline DATA API lands in main/ (here, tested+committed); the scrubber
ANIMATION lives in `ui/` (a separate git repo) — built + demoed, surfaced not committed here.

## What changed (main/)
- NEW `flight.normalize_ts(value)` (cli/lib/flight.py) — the ONE canonical timestamp normalizer
  for the whole subsystem (None→now, datetime, or iso str; date-only/naive/sub-second expand to
  fixed width; naive→UTC via replace, never local). Lifted from the duplicate `_TS_FMT`/normalizers.
- `cli/commands/recorder.py` — two read-only verbs:
  - `reconstruct --at T` → `flight.reconstruct` (the fleet at an instant).
  - `timeline [--from --to]` → `{keyframes, events, first, last, count, frames_bytes}`. `last` is
    `head.last_ts` (newest activity, not the last keyframe), and `events` surfaces the DELTA
    timestamps (with op kinds) so the scrubber can mark/snap to actual births & deaths between
    keyframes. `--from/--to` run through `normalize_ts` before the lexicographic window filter.
  - `_next_ts` now formats via `flight.normalize_ts` (keeps its +1µs monotonic bump).
- `cli/commands/restore.py` — `_normalize_at` delegates to `flight.normalize_ts` (one impl).
- `cli/aura` — `reconstruct`/`timeline` added to `recorder_action` choices; `--at/--from/--to` args.

## Critic gate (FAIL → fixes folded)
- **timeline `last` from head, not last keyframe** — a post-keyframe delta birth/death must fall
  inside `[first,last]`. (Built this way; now guarded by a test using a delta after the last keyframe.)
- **surface delta `events`** — keyframes (~5min) miss changes between them; `events` gives the
  scrubber real change moments. Added.
- **normalize `--from/--to`** — raw lexicographic bounds mis-fire (date-only prefix excludes a day).
  Run through `normalize_ts`. (Built this way; covered.)
- Refactor confirmed behavior-preserving: all prior tests stayed green.

## Verification
`cd cli && python -m pytest ../tests/test_flight.py ../tests/test_recorder.py ../tests/test_restore.py -q`
→ **38 passed**.
Real smoke: `aura recorder timeline` → 2 keyframes, `last` = the newest delta ts (later than the last
keyframe); `aura recorder reconstruct --at <now>` → 30 seats. `--at "2026-06-25T12:05:00"` (naive)
selects the right keyframe.

## Scope
EDIT recorder.py, restore.py, flight.py, cli/aura, tests/test_recorder.py. The `ui/` scrubber is
a separate repo — built and run locally, surfaced to the user before any commit there.
