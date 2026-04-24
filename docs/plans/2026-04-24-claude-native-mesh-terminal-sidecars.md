# Claude-Native Mesh With Terminal Sidecars Implementation Plan

> For Hermes: implement directly in small verified steps. Keep the mesh Claude-first; make Hermes/Codex controllable sidecars, not fully indexed runtimes.

Goal: Make Aura's new terminal-backed runtimes show up as registered fleet participants, add fleet broadcast, and keep Flex/session observability as a Claude Code capability rather than pretending Hermes/Codex are fully mesh-native.

Architecture: Add a small local terminal-agent registry under `/tmp/aura` for spawned tmux runtimes. Merge that registry with the existing mesh daemon discovery and tmux window discovery in `list`, `check`, and `resolve`. Add a `broadcast` command that enumerates a fleet and sends through the existing tmux delivery path. Do not build Hermes/Codex Flex cells in this slice.

Tech stack: Python CLI, tmux backend, existing Aura mesh socket client, JSON registry file, existing delivery ledger.

---

### Task 1: Add a local registry for terminal-backed agents

Objective: Persist runtime/fleet/terminal metadata when `aura spawn --runtime ...` creates a tmux agent.

Files:
- Create: `cli/lib/registry.py`
- Modify: `cli/commands/spawn.py`

Behavior:
- `registry.upsert_agent(record)` writes `/tmp/aura/agents.json` atomically.
- Records are keyed by `fleet:name`.
- Record fields: `name`, `fleet`, `runtime`, `profile`, `command`, `workdir`, `terminal_ref`, `transport`, `status`, `delivery_mode`, `registered`, `created_at`, `last_seen`, `trace_cell`.
- `trace_cell` is `claude_code` for `claude-code`/`claude`, else `None` for now.

Verification:
- Spawn with `--runtime claude-code` and confirm `/tmp/aura/agents.json` has the record.

### Task 2: Merge registry into list/check/resolve

Objective: Make terminal runtimes display as registered without requiring the legacy mesh socket registration path.

Files:
- Modify: `cli/commands/list.py`
- Modify: `cli/commands/check.py`
- Modify: `cli/commands/resolve.py`

Behavior:
- `aura list` merges existing mesh agents + registry agents + tmux windows.
- Registry agents show `registered: true`, `runtime`, `fleet`, `terminal_ref`, `trace_cell`.
- Plain tmux windows with no registry still show `registered: false`.
- `aura check NAME` reports registry metadata when present.
- `aura resolve FLEET` includes terminal-only records; if no `session_id`, include record anyway with `session_id: null` and `terminal_ref`, so tools can fall back to tmux instead of dropping agents.

Verification:
- `AURA_FLEET=triad python3 cli/aura list` shows `claude1/hermes1/codex1 registered: true` after respawn or manual registry update.

### Task 3: Add fleet broadcast

Objective: Broadcast one message to every agent in a fleet using existing `send` delivery.

Files:
- Create: `cli/commands/broadcast.py`
- Modify: `cli/aura`

CLI:
- `aura broadcast --fleet triad "message"`
- `aura broadcast triad "message"` optional positional fleet form if simple to support.
- Options: `--as`, `--transport`, `--dedupe-key`, `--force`, `--include-shell`.

Behavior:
- Enumerate registry agents for fleet plus tmux windows.
- Default excludes tmux window named `bash` and unregistered shell-only windows.
- Sends via `send.run()` to each target.
- Returns JSON: `ok`, `fleet`, `count`, `results`.

Verification:
- Broadcast to triad returns delivered result per agent.

### Task 4: Add coarse terminal status inference

Objective: Give sidecars useful statuses without runtime-specific APIs.

Files:
- Modify: `cli/lib/registry.py` or create helper in `cli/lib/status.py`
- Modify: `list.py` / `check.py`

Behavior:
- If terminal missing: `dead`.
- If pane contains obvious prompt/waiting marker near tail: `idle`.
- If pane contains permission/trust prompt: `waiting`.
- Else registered terminal alive: previous status or `alive`.

Verification:
- `check claude1/hermes1/codex1` reports not `unknown` when panes are live.

### Task 5: Smoke-test and commit

Commands:
- `python3 -m py_compile cli/aura cli/commands/*.py cli/lib/*.py`
- create a small test fleet with `--command "python3 -i"` if real model runtimes are expensive
- `aura broadcast --fleet <fleet> "ping"`
- `aura list`
- `aura check <agent>`
- `git status --short`
- `git add -A && git commit -m "feat: register terminal runtimes in aura mesh"`

Non-goals:
- No Hermes/Codex Flex cells.
- No full runtime transcript indexing.
- No PM autonomous task planner yet.
- No daemon-side persistent mesh rewrite.
