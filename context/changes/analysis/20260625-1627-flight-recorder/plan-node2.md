# Plan — Node 2: `aura recorder` command + service

## Key finding
cwd enrichment needs NO /proc walk: `tmux_mirror.list_physical_panes()` already returns each pane
with `pane_current_path` (from `tmux list-panes -F '#{pane_current_path}'`). The recorder builds a
`pane_id → cwd` map from the same mirror snapshot `list_seat_statuses` already polled.

## Module `cli/commands/recorder.py`

Pure/testable (no IO):
```
pane_id_from_ref("tmux:fleet:%N") -> "%N" | None
frames_from_rows(rows, pane_cwd) -> [frame tuple]   # filter liveness=="alive";
    flight.frame_seat(row); cwd <- pane_cwd.get(pane_id) or frame_seat cwd
_next_ts(last_ts) -> iso   # max(real utc now, last_ts + 1µs) — strictly increasing, clock-safe
```

IO:
```
pane_cwd_from_mirror() -> {pane_id: pane_current_path}     # tmux_mirror.list_physical_panes()
collect_live_frames()  -> frames_from_rows(seat_status.list_seat_statuses(), pane_cwd_from_mirror())
record_once(*, collect=collect_live_frames, keyframe_interval_s=300) -> summary
    # now = _next_ts(head.last_ts); flight.record_tick(collect(), now=now, ...)
```

Dispatch `run(args)` on `args.recorder_action` (default `status`):
- `once`    -> record_once(); {ok, wrote_delta, wrote_keyframe, changes, live:N}
- `run`     -> single-instance flock; loop: record_once every `--every`s; compact every
              `--compact-every`s; bound by optional `--ticks N`; `--every 0` ⇒ no sleep (tests).
- `status`  -> read flight head/index: {ok, live, last_ts, last_keyframe_ts, keyframes, frames_bytes}
- `compact` -> flight.compact(now=_next_ts(None)); pass-through result.

## Wiring `cli/aura`
`from commands import ... recorder as recorder_cmd`; subparser `recorder` with positional
`recorder_action` choices [run, once, status, compact], `--every` (float, default 10),
`--keyframe-every` (float, 300), `--compact-every` (float, 3600), `--ticks` (int).
Dispatch: `elif args.command == "recorder": result = recorder_cmd.run(args)`.

## Service `services/aura-recorder.service`
systemd --user, Type=simple, `ExecStart=%h/.local/bin/aura recorder run --every 10 --compact-every 3600`,
Restart=always, Environment=AURA_STATE_DIR=%h/.aura. Mirrors the autocommit/heal-sweep daemons.

## Tests `tests/test_recorder.py`
1. `pane_id_from_ref` parsing (valid / malformed / None).
2. `frames_from_rows`: drops liveness!="alive"; enriches cwd from pane map; falls back to row cwd
   when pane absent; unbound seat ⇒ session_id None (delegates to frame_seat).
3. `record_once` with injected `collect` returns canned frames → a keyframe is written;
   second call with a changed set appends a delta; `_next_ts` keeps ts strictly increasing.
4. `run(args)` dispatch: `once` then `status` (status reflects live count + last_ts);
   `compact` returns a dict. Use a fake args namespace + monkeypatched `collect_live_frames`.
5. `run` loop with `--ticks 3 --every 0` and a monkeypatched collect emits exactly 3 records
   (3 distinct ts; no ValueError from same-microsecond collisions).

## Risks
- Same-microsecond ticks → handled by `_next_ts` (bump to last+1µs).
- `run` infinite loop in tests → bounded by `--ticks`.
- Single-instance: flock on `flight_root()/.recorder.lock`; second `run` exits cleanly.

## Scope
NEW `cli/commands/recorder.py`, `services/aura-recorder.service`, `tests/test_recorder.py`;
EDIT `cli/aura` (import + subparser + one dispatch elif). Nothing else.
