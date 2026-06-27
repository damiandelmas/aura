# Aura

A local control plane for live agent runtimes. Its center is the **seat** — a named runtime process that can be launched, viewed, messaged, inspected, reported from, grouped, restarted, or cut.

```
Owns:    liveness · routing · launch records · delivery evidence · grouping · observability
Refuses: runtime memory · workstream truth · organization identity · prompt compilation
```

Live address is `fleet:seat`. Live backend is tmux. Truth is the registry joined to physical pane proof.

---

## Install

```bash
# global entry point
ln -s /home/axp/projects/aura/main/cli/aura ~/.local/bin/aura

# smoke check (clean env)
env -i HOME=$HOME USER=$USER LOGNAME=$USER PATH=/usr/bin:/bin aura view
```

Dependencies: Python standard library + tmux. Discord listener requires `discord.py`. Local sense requires a reachable Ollama endpoint.

---

## Core Model

### The seat

```
seat             fleet:seat           live addressable runtime process
seat_instance_id si_<id>              current process incarnation; changes on restart/rollover
package          ~/.aura/agents/i_<id>/  durable runnable body: manifest.json + runtime home + memories/
fleet            fleet_id + name      group of seats; name maps to a tmux session
placement        named logical group  cross-fleet grouping overlay; not routing, not movement
```

A `fleet:seat` address is not a liveness guarantee — it is a routing address. **LIVE** means the tmux pane is reachable and joined to a registry row. **HISTORICAL** means the row exists but the pane is gone.

### The two laws

```
READ   liveness is computed every read from the tmux mirror + registry join.
       reads never mutate the registry. state is binary: LIVE | HISTORICAL.

WRITE  operations key off the globally-unique pane id %N (or =exact name)
       with a fleet-identity assertion. fail closed on staleness. dead %N → no-op.
```

### Registry

Control-plane authority at `~/.aura/registry/`:

```
seats.json          routing + topology rows
fleets.json         fleet identity and aliases
placements.json     grouping membership
seat-aliases.json   historical lineage breadcrumbs (one-way; never a live router)
session-ledger.jsonl  append-only evidence of lifecycle events
deliveries.jsonl    append-only evidence of attempted deliveries
```

---

## Runtimes

Each runtime is reached through an adapter declaring its capabilities (prompt argv, resume, fork, session binding). Aura adapts to the runtime; it does not re-model it.

| Runtime | State home | Prompt argv | Resume | Fork | Notes |
|---------|-----------|-------------|--------|------|-------|
| `codex` | `CODEX_HOME=.codex/` | ✓ | ✓ | ✓ | Reference adapter; hook auto-bind |
| `claude-code` | `CLAUDE_CONFIG_DIR=.claude/` | ✓ | ✓ | — | Born-bound by allocation (Aura mints session UUID at launch) |
| `hermes` | `~/.hermes/profiles/<name>/` | — | native | — | Profile-first; 4 animation modes |
| `shell` | — | — | — | — | `bash` seat; test/debug |
| `gajae-code` | `GJC_CONFIG_DIR=.gjc/` | — | — | — | Package-native; minor |

### Hermes animation modes

```
terminal seat    aura spawn --runtime hermes ...   ordinary tmux pane, visible as an Aura seat
live_gateway     hermes -p <profile> gateway run   owns an external channel (Discord, etc.)
warm_node        entry in ~/.hermes/nodes.json      fast local Q&A; kept ready by hermes-node-host
HTTP ingress     POST 127.0.0.1:7135/v1/messages    routes to warm_node or live_gateway
```

---

## External Surfaces

### Discord

```
~/.aura/discord/channel-bindings.json  (the switch)

  binding → hermes:*   →  hermes-discord-router.service  →  warm node / live gateway
  binding → fleet:seat →  aura-discord-listener.service  →  aura send

Native Hermes gateway profiles also own channels directly.
```

The channel tree is a live projection of the society config × fleet roster — a reconciler writes it idempotently. A fleet with no live seats gets a 💤 dormant marker; it is never deleted.

**Rule:** a Discord message id is sink evidence, not a seat id. Sidecars correlate; they never substitute.

### HTTP in-jack (`services/aura_ingress.py`)

One-way inbound door. External `POST /in` → `aura send / broadcast / work submit`.

```
POST /in          native envelope (bearer token)
POST /in/<source> foreign webhook (Linear, etc.) — per-source adapter normalizes + verifies HMAC

target: seat:<fleet>:<seat>  → aura send
        fleet:<name>         → aura broadcast
        placement:<name>     → aura work submit
```

Runs as a systemd service behind a Cloudflare named tunnel. Dedup ledger at `~/.aura/ingress/seen.jsonl`.

### Clawhip

Sidecar adapter for external delivery systems. `aura clawhip status / verify-bindings / emit / deliver`.

---

## Flows

### Lifecycle

```
aura spawn        fresh live seat
aura quick        canonical quick package body (varies cwd/prompt/fleet/seat/model)
aura agent create  create a durable package body
aura agent spawn   launch or resume a package-native agent

seat restart      replace process, keep session
seat rollover     replace process, fresh session (explicit freshen; not a repair reflex)
seat rename       relabel within the same fleet
fleets rename     relabel the tmux session; readdress live rows; record lineage
seat adopt        promote an unmanaged pane into a managed seat

seat cut          retire → HISTORICAL
seat gc --ttl N   TTL auto-archival of cruft rows
agent archive     lineage-preserving body retirement → ~/.aura/_archive/agents/
```

Cross-fleet seat movement is **spawn-verify-cut** — never a registry edit.

### Delivery

```
send       immediate semantic message to one live seat (with provenance)
queue      hold until the target's next report boundary
broadcast  fan out over live seats in a fleet or placement
write      raw terminal control (operator-only; no provenance)
deferred   time-based recovery worker
```

Every semantic envelope resolves a sender: `--as fleet:seat` (managed) or `--as-service NAME` (service). Unprovenanced traffic is refused.

`state=attempted` in the delivery ledger proves the backend accepted keystrokes — not that the recipient understood or completed the work. Acceptance is a reply, report, or workstream receipt.

### Continuity (session binding)

Every bind flows through one writer — `_bind_registry_session` — which runs the body-integrity veto:

```
bind_guard.body_gates:
  native_state_ref ⊂ package_root   (runtime-agnostic)
  seat_instance_id matches
  package env agrees (or record-internal only when env=None)

→ refused (body-gate-refused) or written
```

Repair ladder: `bind-current → bind-nonce → resolve-pane → bind-pane → heal → restore-plan`

Native session transcripts under `.codex/sessions/` are never deleted — resume depends on them.

### Reporting

```
aura report STATE --work TEXT [--receipt | --next | --blocker | --done | --ack]
```

Writing a report is the boundary event that releases queued messages and fires subscriptions. A report is the seat's own account of its state; `view` and `inspect` are external evidence.

---

## Nine Domains

| Domain | Concern | Skill | Key code |
|--------|---------|-------|----------|
| identity | who/where | `aura-agent` | `cli/lib/agent_packages.py` |
| lifecycle | born → change → end | `aura-spawn` / `aura-rollover` | `cli/commands/spawn.py`, `seat.py` |
| delivery | intent → seat | `aura-send` / `aura-queue` / `aura-broadcast` | `cli/commands/send.py`, `cli/lib/delivery.py` |
| reporting | self-state | `aura-report` / `aura-status` | `cli/lib/reports.py` |
| observation | what is live | `aura-view` / `aura-inspect` | `cli/lib/live_topology.py` |
| continuity | session survives process | `aura-self-bind` | `cli/lib/bind_guard.py`, `registry.py` |
| grouping | which seats = one operation | `aura-placement` | `cli/lib/placements.py` |
| capability | what a runtime knows | `aura-profile` / `aura-hands` | `cli/lib/runtime_profiles.py` |
| sidecars | external channels | `aura-bridge` | `cli/commands/discord_bridge.py`, `services/aura_ingress.py` |

Orchestration (`aura-crew`), scheduling (`aura-event`), query (`aura-flex`), and repair (`aura-operator`) compose domains — they are not domains themselves.

### Routine vs operator

```
ROUTINE   view · inspect · status · send · queue · broadcast · report · event
          spawn · self-bind · placement · quick
OPERATOR  above + registry/session repair · package work · raw terminal · fleet closeout · gc/archive
```

Enforced by `tests/fixtures/public_surface_contract.json` — operator verbs are kept out of routine skills by test, not convention.

---

## Skills

Agent-facing skills live in `skills/`. Each is a `SKILL.md` (+ optional `agents/` subdir) that teaches the *how-to* for one domain verb. The conceptual *what/why* is in `context/`.

Skills are symlinked from `~/.claude/skills/` into this repo so they are version-controlled here and consumed live from there.

```
skills/
  aura-agent       package bodies: create / spawn / clone / archive / history
  aura-bridge      external surfaces: discord bind, clawhip
  aura-broadcast   fan a message over a fleet or placement
  aura-crew        multi-seat workflow orchestration
  aura-event       wakeups, report + membership subscriptions
  aura-flex        scope a Flex session search to live Aura topology
  aura-hands       skill materialization into a package body
  aura-inspect     one-seat evidence: mechanical status + terminal excerpt
  aura-onboard     seat self-onboarding
  aura-operator    substrate and repair: lifecycle, registry/session, raw terminal
  aura-placement   named grouping over logical fleet:seat refs
  aura-profile     runtime profile templates
  aura-queue       message held until the target's next report boundary
  aura-quick       launch from current dir using a canonical quick package
  aura-report      write this seat's self-state
  aura-rollover    replace a seat's process with a fresh session
  aura-self-bind   bind this process to its seat row
  aura-send        immediate message to one live seat
  aura-society     container config: members + config + resolves_to
  aura-spawn       create a new live seat
  aura-status      surface a seat's current status
  aura-view        live topology: self / fleet / placement
```

---

## Services

```
~/.local/bin/aura                        CLI entry (wrapper/aura.py)
aura-discord-listener.service            Discord → fleet:seat
hermes-discord-router.service            Discord → hermes:node
hermes-http-ingress.service              127.0.0.1:7135  (Hermes local mesh router)
hermes-node-host.service                 127.0.0.1:7136  (warm node host)
aura-ingress.service                     external POST door (→ Cloudflare tunnel)
aura-agents-autocommit.service           inotifywait → git commit on ~/.aura/agents/
```

---

## Durable State

```
~/.aura/
  registry/                  control-plane authority
  agents/                    durable bodies (git repo; autocommit watcher)
    index.json               package id → root
    i_<id>/manifest.json     spawn/resume recipe
  discord/channel-bindings.json
  runtime-bases/             clean Aura-owned defaults
  runtime-profiles/          reusable boxed runtime profile templates
  reports/ events/ queue/ deferred/ holding/  live coordination
  ingress/secrets.json + ingress.env + seen.jsonl
  workspaces/                per-cwd launch breadcrumbs
  _archive/agents/           retired bodies (sessions preserved)

~/.hermes/
  profiles/<name>/           Hermes profile homes
  nodes.json                 warm node registry
  mailbox/ gateway/inject/   bridge plumbing
```

---

## Key Boundaries

- `package ≠ workstream` — a body is a small runnable thing; boards/receipts/decisions live outside
- `placement ≠ routing` — grouping only; routing stays `fleet:seat`; movement stays lifecycle
- `sink id ≠ seat id` — Discord message ids are channel evidence; sidecars correlate, never substitute
- `profile ≠ agent` — a reusable capability seed, not the owner of a session
- `native delegation ≠ Aura worker creation` — a runtime's own subagent (Codex native child) is not an Aura seat; `aura spawn` from inside a native subagent is refused

Conceptual depth: `context/current/2026-06-04-2022/`
