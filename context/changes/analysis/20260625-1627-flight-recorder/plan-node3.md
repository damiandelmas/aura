# Plan — Node 3: `aura restore` (--from-snapshot / --at)

## Goal
The verb that would have made the whole incident one command: reconstruct the live fleet at a
point in time from the flight store and reconnect each seat to the session it ACTUALLY had then —
reading session_id from the frame (born-bound authoritative), not the weak observe-ledger.

## Reuse (verified seams)
- `flight.reconstruct(at)` → {ts, seats:[frame tuple]}.
- `session_ledger.restore_plan_from_rows(rows, capabilities)` → plan with per-row `restore_command`
  (`aura spawn <seat> --runtime <rt> --fleet <f> --cwd <cwd> --resume-session <sid> --as-pane --wait`,
  or `aura agent spawn` for package rows). `restore_status` needs `runtime_session_binding=="bound"`
  + a session id + `capability.supports_resume` (claude-code/codex both True).
- `runtimes.capability_map()` → capabilities.
- `sessions._add_restore_reconciliation(plan)` → annotate rows with placements/events/subscriptions.

## Module `cli/commands/restore.py`
```
_frame_to_restore_row(fs) -> {seat, fleet, runtime, session_id, runtime_session_id,
    runtime_session_binding ("bound" if session_id else "unbound"), cwd, seat_instance_id, terminal:target}
_normalize_at(at|None) -> canonical UTC iso  (None -> now; naive -> assume UTC; bad -> ValueError)
_plan(at) -> reconstruct -> rows -> restore_plan_from_rows(...) -> + reconstructed_at/source
             -> sessions._add_restore_reconciliation(plan)
_live_targets() -> {alive fleet:seat}      # IO; monkeypatchable
_run_command(cmd) -> (ok, stdout_tail)     # subprocess wrapper; monkeypatchable
run(args):
    at = _normalize_at(args.at)
    plan = _plan(at)
    if not args.execute: return plan                      # dry-run DEFAULT
    live = _live_targets()
    for row in plan.rows:
        target = f"{fleet}:{seat}"
        if not row.restore_ready or not row.restore_command: skip(reason)
        elif target in live: skip("already-live")          # idempotent: only resurrect the dead
        else: ok = _run_command(row.restore_command)
    return {ok, reconstructed_at, executed, skipped, results:[...]}
```

## CLI `cli/aura`
subparser `restore`: `--at TS` (point in time; default now), `--execute` (default dry-run),
`--from-snapshot` (documented no-op alias = the default now-snapshot). Dispatch elif.

## Tests `tests/test_restore.py`
1. `_frame_to_restore_row` — bound ⇒ binding "bound" + session; unbound ⇒ no session, "unbound".
2. `_plan` over a recorded snapshot — N bound claude seats ⇒ N restore_ready rows; restore_command
   present and a spawn-resume.
3. **session-id-from-frame (bug guard)** — seats with session ids X,Y ⇒ their restore_command carry
   exactly X,Y (proves restore reads the frame, never a reconstructed/ledger session).
4. `--at` time travel — snapshot t1 (A), t2 (A,B); `restore --at t1` rows=={A}; default(now)=={A,B}.
5. `--execute` — monkeypatch `_live_targets` (B alive) + `_run_command`; executes only dead+ready (A),
   skips B ("already-live"), skips not-ready; returns counts.
6. dry-run is default — no `--execute` ⇒ returns the plan, `_run_command` never called.

## Risks / mitigations
- Execute against a partially-live fleet → `_live_targets` skip + `aura spawn` fails closed on a live
  name collision. Only the dead get resurrected.
- `--at` lexicographic compare in reconstruct → `_normalize_at` emits the SAME canonical format the
  recorder writes, so string order == chronological.
- Reuse of private `sessions._add_restore_reconciliation` → acceptable coupling; documented.
- Empty store / no snapshot at T → plan total 0; restore no-op.

## Scope
NEW `cli/commands/restore.py`, `tests/test_restore.py`; EDIT `cli/aura` (import + subparser + elif).
