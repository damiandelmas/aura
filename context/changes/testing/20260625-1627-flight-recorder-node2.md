# Testing Receipt — Flight Recorder Node 2

Command: `cd cli && python -m pytest ../tests/test_recorder.py ../tests/test_flight.py -q`
→ **23 passed in 0.05s** (11 recorder + 12 flight).

## test_recorder.py → coverage
- `test_pane_id_from_ref` — ref parse via pane_handle (valid/legacy/None)
- `test_frames_from_rows_filters_and_enriches_cwd` — drops non-alive; cwd from pane map; row fallback
- `test_frames_from_rows_unbound_has_no_session` — unbound ⇒ session_id None
- `test_next_ts_strictly_increasing` — monotonic across calls
- `test_record_once_writes_and_status_reflects` — record + status round-trip
- `test_run_once_and_compact_dispatch` — `run once` / `run compact` dispatch (monkeypatched collect)
- `test_run_loop_bounded_ticks_no_collision` — `run --ticks 3 --every 0` → 3 distinct ts, no ValueError
- `test_skip_when_mirror_unavailable` — collect()→None ⇒ tick skipped, nothing written (critic-fix, QA-fatal)
- `test_skip_suspicious_total_wipe_but_record_partial` — empty-while-prev-nonempty skipped; partial records (critic-fix)
- `test_next_ts_is_canonical_fixed_width` — fixed-width µs + `+00:00`, lexicographic==chronological (critic-fix)
- `test_default_action_is_status` — bare `recorder` ⇒ status

## Regressions caught by tests during the node
- `--every 0` silently became 10s via an `or`-default → surfaced as a 20.01s test; fixed (None-only default).
- Def-time-bound default collector defeated monkeypatch → record_once now resolves the collector at call time.

## Real end-to-end (manual)
`aura recorder once` → `{ok, wrote_keyframe, changes:30, live:30}`; `aura recorder status` →
`{live:30, keyframes:1, frames_bytes:12086}`; `flight.reconstruct(now)` → 30 seats with bound
session ids and correct cwds. Live store initialized at `~/.aura/flight/`.
