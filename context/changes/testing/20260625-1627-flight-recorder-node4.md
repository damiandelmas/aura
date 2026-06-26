# Testing Receipt — Flight Recorder Node 4 (timeline data API)

Command: `cd cli && python -m pytest ../tests/test_flight.py ../tests/test_recorder.py ../tests/test_restore.py -q`
→ **38 passed** (12 flight + 14 recorder + 12 restore).

## New / changed coverage
- `test_reconstruct_verb_returns_fleet_at_instant` — `recorder reconstruct --at T` (canonical + naive)
- `test_timeline_verb_lists_keyframes_and_bounds` — keyframes + bounds; **last tracks a post-keyframe
  delta** (head-derived, critic-fix); `events` surfaces the delta with op="appear" (critic-fix);
  normalized `--from` window filter
- `test_flight_normalize_ts_messy_inputs_fixed_width` — shared normalizer: date-only/naive/datetime → fixed width
- Refactor (lift `_normalize_at`/`_canonical` → `flight.normalize_ts`) kept all prior flight/recorder/
  restore tests green.

## Real smoke
`aura recorder timeline` → 2 keyframes, `last` = newest delta ts (> last keyframe), `events` listed.
`aura recorder reconstruct --at <now>` → 30 seats.
