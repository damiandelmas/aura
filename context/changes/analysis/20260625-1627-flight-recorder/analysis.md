# Analysis — Flight Recorder (Node 1: flight.py core)

## Node
Persist the computed `seat_status` timeline so a full tmux/host death is recoverable
deterministically, and so the fleet's history can be reconstructed at any T (and later
animated). Node 1 is the data core: `cli/lib/flight.py` + `tests/test_flight.py`.

## Why (incident origin)
After a WSL shutdown there is no durable snapshot of "what was live + each seat's session".
Liveness is computed from tmux and evaporates on death. Reconstructing from the
`session-ledger.jsonl` event stream is heuristic — `restore-plan --from-ledger --latest-per-seat`
picked stale/older sessions for 10/28 seats and surfaced a manager/memory swap. The fix is a
flight recorder that copies Aura's **own authoritative** live state on a cadence.

## What was read (seams this depends on)
- `cli/lib/seat_status.py`
  - `list_seat_statuses(fleet=None, *, include_hidden=False, include_ledger=True)` → list of rows;
    does ONE tmux-mirror snapshot for all seats (O(1)). This is the recorder's data source.
  - `build_from_record(...)` output keys we use:
    `target, fleet, seat, seat_instance_id, pane_ref, runtime, liveness,
     runtime_session_id (set ONLY when binding=="bound"), runtime_session_binding,
     cwd (= runtime_session_cwd or cwd or workdir — OFTEN ABSENT on the record)`.
  - `aura_launch_id` is on the underlying record (not always echoed) — pull from registry row.
  - liveness enum: `"alive" | "missing" | "unknown"`. LIVE := `liveness == "alive"`.
- `cli/lib/state.py` → `state_root()` (honors `AURA_STATE_DIR`). Store goes at `state_root()/"flight"`.
- `cli/lib/registry.py` → `read_registry()` for `aura_launch_id` / raw row fields when needed.
- `cli/lib/session_ledger.py` → `restore_plan_from_rows(rows, capability_map)` consumes rows keyed
  by `cwd, session_id|runtime_session_id, runtime, fleet, seat`. A frame seat tuple maps directly in.
  (Node 3 reuses this; Node 1 only needs to emit a compatible tuple.)
- `cli/lib/pane_resolver.py` / `runtime_session._read_process_environ(pid)` — pane→pid→/proc.
  cwd enrichment for a live pane reads `/proc/<pid>/cwd`.

## What matters / constraints
- **Authoritative session id**: read `runtime_session_id` from the bound row (born-bound for
  claude-code). NEVER reconstruct from the observe-ledger — that is the original bug.
- **cwd gap**: registry rows frequently lack cwd. Recorder must enrich each LIVE seat with its
  process cwd from `/proc` at record time. flight.py exposes the enrichment hook; the recorder
  (Node 2) supplies the live pid→cwd. flight.py itself stays pure/testable (no tmux/proc calls).
- **Delta encoding**: a quiet tick must cost ~0 bytes. Diff current LIVE set vs last recorded set;
  emit only changes (appear/vanish/rebind/move/rename). Keyframe every ~5 min bounds replay.
- **Determinism**: `reconstruct(T)` = latest keyframe ≤ T, apply deltas with keyframe.ts < ts ≤ T.
  Must equal a full snapshot taken at T (property test).
- **Read model, not authority**: frames record computed liveness; restore replays through the
  existing gated spawn/bind path. flight.py never writes the registry.
- **Bounded storage**: 7-day TTL; compaction drops fine deltas >24h, keeps keyframes; drops >7d.
- **Purity for test**: flight.py takes the live seat list as an argument (injected), so tests run
  with no tmux. Store paths honor `AURA_STATE_DIR` (tests point it at a tmpdir).

## Code/test surfaces implicated (Node 1)
- NEW `cli/lib/flight.py`: schema constants, store paths, `frame_seat()` projection,
  `diff_frames()`, `write_keyframe()/append_delta()`, `record_tick()` (the orchestrator entry,
  injected seat list), `reconstruct(T)`, `compact()`.
- NEW `tests/test_flight.py`: diff correctness; keyframe+delta == full snapshot (property);
  reconstruct at arbitrary T; quiet tick writes nothing; compaction bounds; AURA_STATE_DIR isolation.

## Out of scope for Node 1
Recorder loop/service (Node 2), `aura restore` verb (Node 3), timeline API + animation (Node 4).
