# Plan — Node 4: timeline API + scrubber animation

## Split (ui/ is a SEPARATE git repo)
- **main/ (this branch, tested+committed):** expose the timeline as read-only `aura recorder` verbs.
  The animation is a thin client over these — same discipline as `ui/server.py` (a CLI bridge).
- **ui/ (separate repo, surfaced not committed here):** `/api/timeline*` routes + a scrubber page.

## main/ — `aura recorder` read verbs (extend cli/commands/recorder.py)
```
reconstruct --at T   -> flight.reconstruct(at)                     # {ts, seats:[...]} at an instant
timeline [--from T --to T]  -> {keyframes:[ts...], first, last, count, frames_bytes}
```
- `reconstruct`: `_normalize_at` (reuse the canonical-iso normalizer; lift the shared helper so
  recorder and restore use ONE) → `flight.reconstruct`.
- `timeline`: read `flight.index_path()` keyframes (optionally filtered to [from,to]) + bounds — the
  scrubber's tick marks and range. Pure read; no tmux.
- Add `reconstruct`/`timeline` to the `recorder` subparser choices + `--at/--from/--to` args.

### Shared normalizer
`_normalize_at` currently lives in restore.py; recorder needs it too. Lift to `lib/flight.py`
(`flight.normalize_ts`) so both call one impl and the recorder's `_next_ts`/`_canonical` and restore's
`_normalize_at` agree byte-for-byte. (Small refactor; keep behavior identical, re-run all suites.)

## main/ tests (extend tests/test_recorder.py)
- `recorder reconstruct --at T` returns the seats live at T (record two snapshots, query each).
- `recorder timeline` returns the keyframe ts list + correct first/last/count; `--from/--to` filters.
- `flight.normalize_ts` parity: date-only/naive/µs=0 → canonical fixed width (move the messy-input
  assertions here; restore keeps using the shared impl).

## ui/ — `/api/timeline` + scrubber (separate repo)
- `server.py`: `/api/timeline` → `_run_aura("recorder","timeline")`; `/api/timeline/at?ts=T` →
  `_run_aura("recorder","reconstruct","--at",ts)`. Thin, like the existing `/api/*` routes.
- `static/timeline.html`: a scrubber over [first,last]; on tick, fetch `/api/timeline/at?ts=T`, render
  seats as nodes grouped by fleet; play across the range so seats appear/vanish/move (births & deaths
  as visual events). Reuse the org-forest canvas style if cheap; otherwise a minimal standalone d3/SVG.
- Run it locally to confirm it animates the real recorded store; SURFACE to the user before committing
  to the ui/ repo (separate repo with its own WIP — not my branch to commit).

## Acceptance
- `aura recorder reconstruct --at T` and `aura recorder timeline` return correct JSON (tested).
- The ui scrubber loads the real flight store and plays the fleet timeline (manual, demoed).

## Risks
- ui/ is a different repo with dirty WIP → I do not commit there; I add files + run + surface.
- Shared-normalizer refactor must not change recorder/restore behavior → re-run all 35 tests.

## Scope (main/ commit)
EDIT cli/commands/recorder.py (+2 read verbs), cli/lib/flight.py (+normalize_ts), cli/aura (subparser
choices+args), cli/commands/restore.py (use flight.normalize_ts), tests/test_recorder.py. ui/ files
built + demoed separately.
