# Code Receipt — Flight Recorder Node 2 (`aura recorder` + service)

## What changed
- NEW `cli/commands/recorder.py` — the recorder loop over `lib.flight`.
  - `pane_id_from_ref` via `pane_handle.PaneHandle.from_ref` (the single owner of the ref format).
  - `frames_from_rows(rows, pane_cwd)` — filters `liveness=="alive"`, projects via `flight.frame_seat`,
    enriches cwd from the tmux mirror's `pane_current_path` (reliable for a live pane even when the
    registry row lacks cwd), falls back to the row cwd.
  - `collect_live_frames()` — returns `None` (a "no observation" sentinel) when the tmux mirror is
    unavailable, so a blip never gets recorded as a mass-vanish.
  - `record_once` — skips on `None` (mirror down) and on a total wipe (empty-now while prev non-empty:
    a hiccup, or a real shutdown best preserved as the last good frame); a genuine partial change records.
  - `_next_ts` — canonical fixed-width aware-UTC ISO (always microseconds + `+00:00`) so lexicographic
    order == chronological; strictly increasing across same-µs ticks and process restarts.
  - `_run_loop` — single-instance `flock(LOCK_EX|LOCK_NB)`; per-tick try/except so a tmux blip can't
    crash-loop the unit; `--ticks` bound; numeric flags defaulted only on None (a real `--every 0` is honored).
  - `run(args)` dispatch: `run | once | status | compact` (default `status`).
- EDIT `cli/aura` — import `recorder as recorder_cmd`, `recorder` subparser (action + `--every/
  --keyframe-every/--compact-every/--ticks`), and the dispatch elif.
- NEW `services/aura-recorder.service` — systemd --user unit: `aura recorder run --every 10
  --keyframe-every 300 --compact-every 3600`, Restart=always, pinned AURA_STATE_DIR.
- NEW `tests/test_recorder.py` — 11 tests.

## Critic gate (FAIL → fixes folded)
Critic FAILed the Node 2 plan. Folded: (1) **QA-fatal** mirror-unavailable mass-vanish → `None`
sentinel + skip; (2) `pane_handle` reuse instead of a hand-rolled split; (3) per-tick try/except +
`LOCK_NB`; (4) canonical fixed-width `_next_ts`; (5) suspicious-total-wipe skip. Self-QA additionally
found and fixed the `or`-default numeric-zero bug (`--every 0` silently became 10s; surfaced as a 20s
test) and a def-time-bound default collector that defeated monkeypatching.

## Verification
`cd cli && python -m pytest ../tests/test_recorder.py ../tests/test_flight.py -q` → **23 passed in 0.05s**.
Real end-to-end: `aura recorder once` captured **30 live seats** with bound session ids + correct
cwds (e.g. `aura-engine:developer` → `/home/axp/projects/aura/main`, a cwd the registry row lacked);
`reconstruct(now)` returns all 30. This started the live store at `~/.aura/flight/`.

## Scope
NEW recorder.py, service unit, test file; EDIT cli/aura (3 surgical edits). Node 1's flight.py
untouched. Unrelated untracked WIP left alone.

## Next
Node 3 — `aura restore --from-snapshot | --at T`: reconstruct → rows → `session_ledger.restore_plan_from_rows`
+ reconciliation; `--execute` runs gated spawn-resume; reads session_id from the frame (fixes the
original stale-ledger bug).
