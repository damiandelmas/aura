# Testing Receipt — Flight Recorder Node 1

Command: `cd cli && python -m pytest ../tests/test_flight.py -q` → **12 passed in 0.05s**

## Coverage map (test → acceptance check)
- `test_diff_appear_vanish_update_noop` — diff ops + no-op (AC1)
- `test_diff_rename_by_seat_instance` — rename matched by si (AC1 / critic-fix 4)
- `test_diff_null_si_is_not_a_rename` — null si ⇒ vanish+appear, not a false rename (critic-fix 4)
- `test_frame_seat_maps_seat_status_row_keys` — projection key mapping (critic-fix 6)
- `test_frame_seat_unbound_records_no_session_id` — session_id None when unbound (AC4)
- `test_first_tick_forces_keyframe_and_empty_store_reconstructs_empty` — empty store + first tick (critic-fix 2)
- `test_ts_must_strictly_increase` — monotonic ts / ValueError (critic-fix 3)
- `test_quiet_tick_writes_nothing` — quiet tick = 0 bytes (AC3)
- `test_property_keyframe_plus_delta_equals_full_snapshot` — reconstruct(t_i)==state_i across a
  keyframe boundary, scripted spawn/rebind/move/rename/death (AC2)
- `test_compact_retention_boundary_is_exact` — exactness at the 24h boundary, misaligned keyframes
  so the cutoff lands mid-gap with a delta in the guard window (AC5 / critic-fix 1)
- `test_compact_drops_beyond_ttl` — keyframes past 7d dropped, latest still reconstructs (AC5)
- `test_artifacts_are_under_state_dir` — AURA_STATE_DIR isolation (AC6)

## Mutation proof
The boundary test was run against a naive compaction (drop every delta with ts < cutoff). It
FAILED with `reconstruct(2026-06-24T06:00:00+00:00) drifted after compact` (cwd /p0 vs /p1 — a
dropped gap delta), confirming the test is a real regression guard, not a tautology. Against the
shipped keyframe-anchored compaction it passes.
