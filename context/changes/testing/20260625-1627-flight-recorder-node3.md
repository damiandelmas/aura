# Testing Receipt — Flight Recorder Node 3 (`aura restore`)

Command: `cd cli && python -m pytest ../tests/test_restore.py ../tests/test_recorder.py ../tests/test_flight.py -q`
→ **35 passed in 0.09s** (12 restore + 11 recorder + 12 flight).

## test_restore.py → coverage
- `test_frame_to_restore_row_bound_and_unbound` — mapping; bound vs unbound
- `test_normalize_at_canonical_and_now` — canonical / date-only / None
- `test_normalize_at_messy_inputs_are_fixed_width` — date-only/naive/µs=0 → fixed width (critic-fix)
- `test_plan_marks_bound_claude_seats_restore_ready` — the crux: frame row reads as bound+ready
- `test_restore_command_carries_session_id_from_the_frame` — **bug guard**: resume sid comes from the frame
- `test_plan_includes_reconciliation_and_reconstructed_at` — reconciliation + reconstructed_at
- `test_at_reconstructs_historical_fleet` — time travel t1 vs t2
- `test_at_messy_input_selects_correct_keyframe` — naive `--at` selects right keyframe; date-only→empty (critic-fix)
- `test_package_seats_degrade_to_plain_spawn_documented` — known limit asserted (critic-fix)
- `test_dry_run_is_default_and_runs_no_commands` — default dry-run, no execution
- `test_execute_dedupes_shared_session` — shared session id → one resume only (critic-fix, fork guard)
- `test_execute_resurrects_dead_skips_live_and_not_ready` — execute skips live + not-ready, runs dead

## Real end-to-end (manual)
`aura restore` (dry-run) reconstructed the live 30-seat fleet from the snapshot →
**30/30 restore_ready** spawn-resume commands with correct cwds + reconciliation
(2 placements, 5 event jobs). One deterministic command replaces the by-hand recovery.
