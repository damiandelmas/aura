# Aura Testing

Aura uses two kinds of checks:

- Unit and command tests that run in pytest without launching real agent TUIs.
- Optional live smoke tests that launch real runtimes in tmux and verify durable Aura evidence.

## Baseline

Run this before treating control-plane changes as ready:

```bash
python3 scripts/aura-test-gates.py --gate baseline
```

The baseline expands to:

```bash
PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/test_seat_contract.py tests/test_registry_and_broadcast.py tests/test_state_paths.py
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile cli/aura cli/commands/*.py cli/lib/*.py
git diff --check
```

The baseline covers seat contracts, registry and broadcast behavior, state path isolation, Python syntax across command and library modules, and diff whitespace hygiene.

For a broader local readiness pass, run the full non-live suite:

```bash
python3 scripts/aura-test-gates.py --gate confidence
```

The confidence gate expands to the full non-live suite, Python compilation, diff whitespace hygiene, and focused Codex-hook/runtime-plumbing slices. To inspect the commands without running them:

```bash
python3 scripts/aura-test-gates.py --gate confidence --dry-run
```

To keep a durable JSON evidence packet for the full confidence proof:

```bash
python3 scripts/aura-test-gates.py --gate confidence --include-live --fail-fast --save
python3 scripts/aura-test-gates.py --gate confidence --include-live --fail-fast --output /tmp/aura-confidence.json
```

`--save` writes to `.aura/test-gates/<timestamp>-<gate>.json`; `--output` writes to an explicit path.

To verify a saved evidence packet later:

```bash
python3 scripts/aura-test-gates.py --verify-latest --latest-gate confidence --require-live
python3 scripts/aura-test-gates.py --verify .aura/test-gates/<timestamp>-confidence.json --require-live
```

Verification fails for failed, timed-out, skipped, or dry-run steps. Use `--require-live` when the receipt must prove live Codex smoke coverage; it requires an executed passing `codex-hook-live` pytest step with a positive pass count. Use `--allow-dry-run` only when intentionally validating a dry-run command-selection receipt.

Each gate step has a timeout and records timeout failures in the JSON evidence. Override the per-step timeout only when a slow machine or live runtime needs more room:

```bash
python3 scripts/aura-test-gates.py --gate confidence --timeout 900
```

To stop after the first failure and record the remaining steps as skipped:

```bash
python3 scripts/aura-test-gates.py --gate confidence --include-live --fail-fast --output /tmp/aura-confidence.json
```

For pytest steps, the JSON evidence includes `summary_line` and `counts` so automation can read pass, skip, warning, and failure totals without scraping the output tail. The top-level `aggregate` object sums step outcomes and pytest counts across the whole gate run; dry-run steps are counted under `aggregate.steps.dry_run`, not `passed`.

The full non-live suite by itself is:

```bash
PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider
```

Expected intentional skips:

- `tests/test_codex_hook_smoke_live.py` is skipped unless `AURA_RUN_LIVE_CODEX_SMOKE=1`.
- symlink-specific runtime profile/box tests skip on platforms without `os.symlink`.

## Codex Hook Smoke

Run the live boxed Codex hook smoke when changing Codex boxes, runtime profiles, prompt delivery, session binding, reports, compact continuity, or hook trust:

```bash
scripts/codex-hook-smoke.py --timeout 180
```

This launches a disposable boxed Codex seat in an isolated Aura state directory and verifies:

- profile command hooks are pretrusted and do not block on the Codex hook review UI
- `SessionStart` and `UserPromptSubmit` hooks run
- hook context is injected and observed by the assistant
- the Codex session is bound back to the Aura seat
- `Stop` publishes an Aura report
- `/compact` triggers `PreCompact` and `PostCompact`
- the next prompt after compact receives hook context again

To exercise terminal prompt delivery instead of Codex's native initial-prompt argv path:

```bash
scripts/codex-hook-smoke.py \
  --command 'codex --dangerously-bypass-approvals-and-sandbox --no-alt-screen' \
  --skip-compact \
  --timeout 180
```

Use this after changing spawn prompt retry behavior or tmux paste/submit handling.

The same live gates are available through opt-in pytest tests:

```bash
python3 scripts/aura-test-gates.py --gate live-codex
AURA_RUN_LIVE_CODEX_SMOKE=1 PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/test_codex_hook_smoke_live.py
```

These tests are skipped unless `AURA_RUN_LIVE_CODEX_SMOKE=1` is set because they launch real Codex processes in tmux and require local Codex auth.

To run the default confidence gate and then the live Codex smoke:

```bash
python3 scripts/aura-test-gates.py --gate confidence --include-live
```

## Smoke Output

A passing smoke prints JSON with `ok: true`, artifact paths, report id, runtime session id, and named checks.

A failing smoke exits nonzero and still prints JSON. Key fields:

- `phase`: the operation or wait that failed
- `state_dir`: isolated Aura state directory for the run
- `hook_log`: hook event JSONL path, when materialized
- `hook_event_names`: hook events seen before failure
- `spawn.prompt_delivery`: prompt submit and retry diagnostics
- `inspect`: Aura runtime-session binding state
- `terminal_tail`: last captured terminal lines
- `latest_report`: report lookup result

Use those fields first. They are more reliable than reading tmux scrollback by eye.

## Focused Hook Slice

For the current Codex hook path, this slice is a good non-live preflight:

```bash
PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider \
  tests/test_codex_hook_smoke.py \
  tests/test_runtime_boxes.py \
  tests/test_seat_contract.py \
  tests/test_sessions_command.py \
  tests/test_runtime_session_identity.py
```

It covers hook profile materialization, boxed hook trust, prompt retry regressions, session discovery, and the smoke harness diagnostic contract.

## Focused Runtime Slices

Use focused slices when changing adjacent runtime plumbing:

```bash
PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider \
  tests/test_omx_adapter.py \
  tests/test_runtime_boxes.py
```

This covers boxed runtime materialization, OMX hook wrapping, OMX root fallback behavior, and boxed Codex hook trust.

```bash
PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider \
  tests/test_profile_command.py \
  tests/test_quick_command.py \
  tests/test_seat_contract.py
```

This covers runtime command construction, spawn contract behavior, quick launch behavior, CLI command exposure, and Hermes native default/profile handling.

```bash
PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/test_terminal_posture.py
```

This covers the terminal posture snapshot-delta classifier and persisted posture records.
