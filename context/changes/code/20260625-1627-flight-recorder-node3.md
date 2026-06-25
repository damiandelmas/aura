# Code Receipt — Flight Recorder Node 3 (`aura restore`)

## What changed
- NEW `cli/commands/restore.py` — reconnect the fleet from the flight timeline.
  - `_normalize_at(at)` — canonical UTC iso matching the recorder's format (None→now, naive→UTC,
    date-only ok) so reconstruct's lexicographic `ts <= at` compare is chronological.
  - `_frame_to_restore_row(fs)` — frame tuple → the row `restore_plan_from_rows` consumes;
    `runtime_session_binding="bound"` + `session_id`/`runtime_session_id` straight from the frame.
  - `_plan(at)` — reconstruct → rows → `session_ledger.restore_plan_from_rows(..., runtimes.capability_map())`
    → `sessions._add_restore_reconciliation` (placements/events/subscriptions) + reconstructed_at/source.
  - `_live_targets()` / `_run_command()` — IO seams (monkeypatchable).
  - `run(args)` — dry-run by default; `--execute` runs each ready row's spawn-resume command, SKIPPING
    targets already live (idempotent: only resurrect the dead) and not-ready rows.
- EDIT `cli/aura` — import `restore as restore_cmd`, `restore` subparser (`--at`, `--from-snapshot`,
  `--execute`), dispatch elif.
- NEW `tests/test_restore.py` — 8 tests.

## The bug this closes
The original incident resumed 10/28 seats from stale observe-ledger sessions. `restore` reads
`session_id` straight from the recorded frame — the born-bound authoritative value — so the resume
command always carries the session the seat actually had. Guarded by
`test_restore_command_carries_session_id_from_the_frame`.

## Verification
`cd cli && python -m pytest ../tests/test_restore.py -q` → **8 passed**.
Real end-to-end dry-run: `aura restore` reconstructed the live 30-seat fleet from the snapshot →
**30/30 restore_ready** spawn-resume commands with correct cwds, plus reconciliation
(2 placements, 5 event jobs to rewire). This is exactly the by-hand recovery from the start of the
session, now one deterministic command.

## --execute safety
Only the dead are resurrected: targets currently live are skipped, `aura spawn` fails closed on a
live-name collision, AND a session id is resumed at most once per run (`duplicate-session-id` skip) so
two seats can never fork one mind — the original incident class in a different shape.

## Critic gate (FAIL → fixes folded)
- **Session-id dedupe** added to `--execute` (fork prevention). Tested.
- **`_normalize_at` robustness**: date-only / naive / µs=0 `--at` inputs all expand to the recorder's
  canonical fixed-width form, so reconstruct's lexicographic `ts<=at` stays chronological. Tested with
  messy inputs (the planned in-suite test used already-canonical ts and would have missed this).
- **Keeper filter**: confirmed `restore_status`→`is_keeper_thread_id(sid, keeper_ids=None)` self-loads
  keeper ids, so keeper-worker sessions are filtered without passing keeper_ids. No change needed.
- Crux (synthetic frame row reads as bound+ready) confirmed sound by the critic and empirically (30/30).

## Known limitation (documented + tested)
The Node 1 frame schema carries no `agent_package_*` fields, so a **package-native** seat currently
restores via plain `aura spawn ... --resume-session` rather than `aura agent spawn <pkg> ...` — it would
lose package-body/identity attachment. Asserted in `test_package_seats_degrade_to_plain_spawn_documented`.
Harmless today (the live fleet is all non-package); FOLLOW-UP: extend the frame schema + recorder to
carry the package ref when present. Filed for a future node.

## Scope
NEW restore.py + test file; EDIT cli/aura (3 edits). Reuses `session_ledger` /
`sessions._add_restore_reconciliation` (documented coupling). Nodes 1–2 untouched.

## Next
Node 4 — timeline API (`/api/timeline`) + scrubber animation over the org-forest canvas, playing
`reconstruct(T)` across a sweep.
