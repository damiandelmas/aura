# Aura

Aura exists because many agents running in parallel need a floor: a shared address book, a way to talk to each other, and a guarantee that process death doesn't erase identity. Each agent runs as a named **seat** at `fleet:seat` in tmux. Aura gives it an address, a roster of peers, a delivery layer, and a durable body that survives restarts.

The skill library is how agents learn to operate that floor. Each `aura-*` skill teaches one domain verb — start with `aura-onboard` for the full mental model, then reach for the specific skill when you need it. An agent with the right skills can view the fleet, message a peer, report its state, spawn a worker, and manage its own session binding without any operator help.

```
Owns:    liveness · routing · launch records · delivery evidence · grouping · observability
Refuses: runtime memory · workstream truth · organization identity · prompt compilation
```

Live address is `fleet:seat`. Live backend is tmux. Truth is the registry joined to physical pane proof.

## Install

One symlink exposes the CLI globally. The smoke check runs in a clean environment so you can confirm Aura resolves tmux correctly before doing anything real.

```bash
# global entry point
ln -s /home/axp/projects/aura/main/cli/aura ~/.local/bin/aura

# smoke check (clean env)
env -i HOME=$HOME USER=$USER LOGNAME=$USER PATH=/usr/bin:/bin aura view
```

Dependencies: Python standard library + tmux. Discord listener requires `discord.py`. Local sense requires a reachable Ollama endpoint.

---

## Core Model

`seat_instance_id` (`si_<id>`) tracks the current process incarnation and changes on every restart or rollover. A `fleet:seat` address is a routing address, not a liveness guarantee — **LIVE** means a real tmux pane joined to a registry row; **HISTORICAL** means the row exists but the pane is gone.

### Registry

The registry is the only source of seat identity and routing — never inferred from tmux or process state alone. Every read joins these files to live tmux to compute the LIVE/HISTORICAL split; writes are gated on exact pane evidence. Control-plane authority at `~/.aura/registry/`:

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

Hermes is not just a seat runtime — it can run as a channel-owning gateway, a kept-warm fast-answer node, or a local HTTP router. Pick the mode that matches whether you need a persistent Aura seat, an always-on channel owner, or a quick in-process answer surface.

```
terminal seat    aura spawn --runtime hermes ...   ordinary tmux pane, visible as an Aura seat
live_gateway     hermes -p <profile> gateway run   owns an external channel (Discord, etc.)
warm_node        entry in ~/.hermes/nodes.json      fast local Q&A; kept ready by hermes-node-host
HTTP ingress     POST 127.0.0.1:7135/v1/messages    routes to warm_node or live_gateway
```

---

## External Surfaces

### Discord

Each Discord channel is bound to either a Hermes node (for fast, profile-driven replies) or an Aura fleet seat (for full agent conversation). The bindings file is the live switch — machine-authored and re-read hot, so a newly bound channel is watched with no restart.

```
~/.aura/discord/channel-bindings.json  (the switch)

  binding → hermes:*   →  hermes-discord-router.service  →  warm node / live gateway
  binding → fleet:seat →  aura-discord-listener.service  →  aura send

Native Hermes gateway profiles also own channels directly.
```

The channel tree is a live projection of the society config × fleet roster — a reconciler writes it idempotently. A fleet with no live seats gets a 💤 dormant marker; it is never deleted.

**Rule:** a Discord message id is sink evidence, not a seat id. Sidecars correlate; they never substitute.

### HTTP in-jack (`services/aura_ingress.py`)

One-way inbound door — external automation, SaaS webhooks, and hosted buttons POST work into the mesh without needing a seat of their own.

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

These are the verbs that change a seat's state — from born to renamed to retired. The key distinction is between `restart` (keep the session, replace the process) and `rollover` (fresh session, different mind). Everything else — cross-fleet moves, adoption of unmanaged panes, archiving old bodies — follows from those primitives.

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

Every message carries sender provenance and lands in the delivery ledger as evidence. The key distinction is between semantic delivery (send/queue/broadcast — conversations between minds, with provenance) and raw terminal control (write — operator-only, no provenance, no receipt).

```
send       immediate semantic message to one live seat (with provenance)
queue      hold until the target's next report boundary
broadcast  fan out over live seats in a fleet or placement
write      raw terminal control (operator-only; no provenance)
deferred   time-based recovery worker
```

Every semantic envelope resolves a sender: `--as fleet:seat` (managed) or `--as-service NAME` (service). Unprovenanced traffic is refused. `state=attempted` in the delivery ledger proves the backend accepted keystrokes — acceptance is a reply, report, or workstream receipt.

### Continuity (session binding)

Every bind flows through one writer — `_bind_registry_session` — which runs the body-integrity veto:

```
bind_guard.body_gates:
  native_state_ref ⊂ package_root   (runtime-agnostic)
  seat_instance_id matches
  package env agrees (or record-internal only when env=None)

→ refused (body-gate-refused) or written
```

When binding fails or drifts, escalate through the repair ladder in order — each step requires more evidence than the last, and the self-heal sweep backstops most cases automatically before you need to intervene manually.

Repair ladder: `bind-current → bind-nonce → resolve-pane → bind-pane → heal → restore-plan`

Native session transcripts under `.codex/sessions/` are never deleted — resume depends on them.

**Self-heal sweep:** `aura-event-supervisor.timer` drives a `no_agent` event (`heal-sweep`) that runs `reconcile-orphans --all` then `heal --all` every 60 seconds — rebuilding registry rows for Aura-born panes whose row was dropped on crash, then rebinding them. An orphan self-recovers within a tick; supervise the daemon or the sweep can die and stay dead.

### Work pool

A thin claim-queue that flows tasks to free seats without Aura holding any work truth. Submit tasks to a named queue, point the dispatcher at a placement, and `idle-watch` senses which members are available. Aura moves the task; the seat owns the result.

```
aura work submit QUEUE "task body"               enqueue one task
aura work dispatch-start QUEUE --placement POOL  drain to idle members of a placement (or --fleet)
aura idle-watch start --placement POOL --every 6 sense which members are free
```

`idle` means released, not done. The placement names who is in the pool; the dispatcher flows work to whoever is free. Add a member, then restart `idle-watch` so it is sensed.

### Reporting

Reporting is how a seat makes its state legible to the rest of the mesh — without it, the only way to know what an agent is doing is to ask or inspect its terminal. A receipt anchors a `complete` claim to durable evidence; without one, it's just a claim.

```
aura report STATE --work TEXT [--receipt | --next | --blocker | --done | --ack]
```

Writing a report is the boundary event that releases queued messages and fires subscriptions. A report is the seat's own account of its state; `view` and `inspect` are external evidence.

---

## Nine Domains

The same system carved by concern rather than by skill. Use this table to find the right code path for a domain-level change, or to understand which skill owns a given area. Orchestration, scheduling, querying, and repair compose across domains and are listed separately below.

| Domain | Concern | Skill | Key code |
|--------|---------|-------|----------|
| identity | who/where | `aura-agent` | `cli/lib/agent_packages.py` |
| lifecycle | born → change → end | `aura-spawn` / `aura-rollover` | `cli/commands/spawn.py`, `seat.py` |
| delivery | intent → seat | `aura-send` / `aura-queue` / `aura-broadcast` | `cli/commands/send.py`, `cli/lib/delivery.py` |
| reporting | self-state | `aura-report` / `aura-status` | `cli/lib/reports.py` |
| observation | what is live | `aura-view` / `aura-inspect` | `cli/lib/live_topology.py` |
| continuity | session survives process | `aura-self-bind` | `cli/lib/bind_guard.py`, `registry.py` |
| grouping | which seats = one operation | `aura-placement` | `cli/lib/placements.py` |
| container | fleet ownership + config | `aura-society` | `cli/lib/societies.py` |
| capability | what a runtime knows | `aura-profile` / `aura-hands` | `cli/lib/runtime_profiles.py` |
| sidecars | external channels | `aura-bridge` | `cli/commands/discord_bridge.py`, `services/aura_ingress.py` |

Orchestration (`aura-crew`), scheduling (`aura-event`), query (`aura-flex`), and repair (`aura-operator`) compose domains — they are not domains themselves.

### Routine vs operator

Routine work is what a seat does day-to-day; operator work is what manages the floor itself — registry edits, raw terminal control, session repair. The line matters because operator verbs have blast radius: a routine skill reaching for them is a mistake, not a shortcut.

```
ROUTINE   view · inspect · status · send · queue · broadcast · report · event
          spawn · self-bind · placement · quick
OPERATOR  above + registry/session repair · package work · raw terminal · fleet closeout · gc/archive
```

Enforced by `tests/fixtures/public_surface_contract.json` — operator verbs are kept out of routine skills by test, not convention.

---

## Skills

Agent-facing skills live in `skills/`. Each is a `SKILL.md` (+ optional `agents/` subdir) that teaches the *how-to* for one domain verb. The conceptual *what/why* is in `context/`. Skills are symlinked from `~/.claude/skills/` so they are version-controlled here and consumed live from there.

### aura-agent

Package bodies are the durable identity behind a seat — they survive process death and provide the recipe to relaunch the agent exactly as it was. A body is `manifest.json` plus the runtime's isolated home and `memories/`. Use this to create, inspect, audit (census), and archive the relaunchable shapes that back your most important seats.

### aura-bridge

The external edge of the mesh: how Discord channels, Clawhip events, and Hermes HTTP ingress map to live seats. Channel bindings route incoming messages to the right `fleet:seat`; correlation work keeps sink ids (Discord message ids) distinct from seat identities. Use this when wiring external channels to the mesh or debugging delivery discrepancies between a surface and Aura state.

### aura-broadcast

When the same message genuinely applies to every seat in a fleet or runtime, broadcast fans it out in one command — reaching only live, managed, routable seats and skipping everything else, including the sender. The discipline is restraint: if different seats need different instructions, send separately. A broadcast that needs per-seat caveats is several sends wearing a disguise.

### aura-crew

The coordination layer for multi-seat work — one lead decomposes a goal, assigns workers with full context, watches receipts, and integrates only after verification. Workers are intelligences with missions, not functions with inputs; "done" is their reply plus the diffs and test results, not a delivered message. The skill library has two gears: `lite` for light single-session crews and `maxx` for long-running or high-stakes work with boards, packets, and closeout ledgers.

### aura-event

Control machinery that causes work to happen at the right time: wakeup ticks on an interval, subscriptions that fire when report rows match a filter, and the external HTTP in-jack for inbound webhooks. An event is a trigger, not a reasoning agent — it knocks, the seat does the thinking. Jobs have a lifecycle (active → paused → retired) and are never silently deleted; retire what you no longer want so intent stays legible.

### aura-flex

Joins Aura's live topology view with Flex's indexed session transcripts — `aura view fleet` gives you `session_id`s, then you query the appropriate Flex cell (`codex` or `claude_code`) with SQL to read what agents actually did. This is the normal path for "what did your fleet do recently?" Use direct Flex SQL over the session ids; the helper scripts are secondary.

### aura-hands

Materializes canonical skills into agent package bodies — projecting skill directories via symlink (edit-once-update-everywhere) or copy (frozen snapshot) and recording ownership in `skills.lock.json`. The lockfile is provenance, not canonical content; sources stay in their roots and packages receive projections. Always inventory, diff, and dry-run before mutating; run `doctor` to verify after.

### aura-inspect

Reads one seat's raw terminal pane — mechanical status or actual terminal text. Heavy and noisy, so it is a last resort after reading reports or simply asking the seat. Never sweep a fleet with inspect; use `aura-status` first, and reach for inspect only when you genuinely need to see what is on the screen.

### aura-onboard

The system orientation: what Aura is, the mental model, and the full skill map organized by purpose. Start here to understand the system before reaching for any specific skill. Your first three commands are `aura view self`, `aura view fleet`, `aura send`.

### aura-operator

The operator stance for managing the control plane itself — lifecycle ops (spawn, restart, rollover, cut, rename, adopt), session binding and repair, registry hygiene, and the work pool. Each op is one command; the system validates and fails closed, so run it and read the refusal reason if one comes back. Everything routine belongs to routine verbs; you are here only when managing the floor itself.

### aura-placement

A named grouping record over `fleet:seat` refs — moves nothing, changes nothing about how seats run, but names a cohort for one operation or workstream. Placement is also the target for the work pool dispatcher: add members, restart `idle-watch`, and free seats receive dispatched work. Verify membership with `aura view placement` before calling it done.

### aura-profile

Launch-time capability templates (`<runtime>/<name>`) that seed a seat at spawn with config, hooks, skills, and runtime-home files. A profile is a reusable seed, not an agent — it shapes a launch, not a session. Codex profiles template `.codex/`; Claude Code profiles template `.claude/` and are copied into the seat's isolated box at spawn with lifecycle hooks layered on top.

### aura-queue

The considerate send — a message held until the recipient writes its next report, landing at a natural pause rather than mid-thought. Queue when the message can wait; send when it can't. A seat that never reports never reaches a boundary, so if delivery must happen regardless, use `aura-send` instead.

### aura-quick

Fastest path to a working live seat — launches from the canonical quick body for a runtime, born-bound, boxed in its own isolated home, with no package ceremony. Reach for it when you want a throwaway seat to think or work in. For a seat that should survive and be revivable later, make a package with `aura-agent` instead.

### aura-report

How a seat publishes its own state to the mesh — `working`, `blocked`, `complete`, and more — with receipts that prove the claim. Writing a report is the boundary event that releases any queued messages and fires subscriptions watching this seat. Report when state is worth knowing; use `aura-send` when you are answering someone directly.

### aura-rollover

Replaces a seat's process and starts a fresh runtime session while keeping its name — the same chair, a fresh mind. Use it only when explicitly asked to freshen a seat; it permanently discards recoverable session context, so it is not a repair reflex. For a stuck or confused seat, diagnose first with `aura-operator`.

### aura-self-bind

Ties this process's native runtime session to its Aura seat row — the binding that makes the session resumable. Normally automatic via the SessionStart hook; reach for this only when `aura view self` shows the seat unbound and the hook didn't fire. Binding another seat is operator work.

### aura-send

The ordinary verb of the mesh — how you ask, answer, hand off, or unblock another agent by address. The recipient is an intelligence, not an endpoint: write role-to-role with full context and what you need back, because a message that transfers complete understanding finishes the conversation in one round. A delivered message proves mechanics, not acceptance; acceptance is the reply plus receipts.

### aura-society

A named container above fleets — durable `fleet-id://` member pins, a config pointer-map, and one opaque `resolves_to` — that stores and resolves, never applies. Member pins survive fleet renames because they key off `fleet_id`; a dead id reads `stale`, never silently gone. Use it to bind a product or tenant's fleet constellation together with shared config pointers.

### aura-spawn

Creates one new live seat in a fleet — validates cwd, runtime, and env before creating the pane, then carries the first assignment into the runtime's own launch so it lands before spawn returns. The new seat is an intelligence waking up cold: give it an objective, a scope, expected receipts, and a stop condition. `--wait` means the seat launched, not that the task finished.

### aura-status

Answers "what is X doing?" by working through a workflow: check `aura view` for liveness, `aura report list` for anything published, then just ask the seat directly. Reports are opt-in — an empty list is normal, not a problem. `aura inspect` is the last resort when a seat doesn't answer and you genuinely need to see the terminal.

### aura-view

The source of truth for live topology — who you are, who's in your fleet, and the exact addresses to use. If `aura view` doesn't return a seat, it isn't live; if docs disagree with `aura view`, the docs are stale. Use the returned `target` verbatim when messaging or reporting.

---

## Services

These processes are what makes Aura always-on. The Discord listener and Hermes router watch external channels 24/7 so messages reach seats while no human is present. The in-jack is a permanently open door for external automation — SaaS webhooks, hosted buttons, cron on another box — to post work into the mesh without needing a seat of their own. The autocommit watcher and event supervisor run silent maintenance so the fleet stays healthy and package bodies stay versioned without manual intervention.

```
~/.local/bin/aura                        CLI entry (wrapper/aura.py)
aura-discord-listener.service            Discord → fleet:seat
hermes-discord-router.service            Discord → hermes:node
hermes-http-ingress.service              127.0.0.1:7135  (Hermes local mesh router)
hermes-node-host.service                 127.0.0.1:7136  (warm node host)
aura-ingress.service                     external POST door (→ Cloudflare tunnel)
aura-agents-autocommit.service           inotifywait → git commit on ~/.aura/agents/
aura-event-supervisor.timer              drives ensure-daemons → heal-sweep cadence
```

---

## Durable State

Everything Aura knows that survives process death. The registry is the control plane's authority — it is joined to live tmux state on every read, never trusted in isolation. `agents/` is a git-versioned store of package bodies, autocommitted by a watcher. The coordination dirs (`reports/`, `queue/`, `events/`, `holding/`) are the live surfaces where the mesh does its work between seat processes.

```
~/.aura/
  registry/                  control-plane authority
  agents/                    durable bodies (git repo; autocommit watcher)
    index.json               package id → root
    i_<id>/manifest.json     spawn/resume recipe
  societies/registry.json    named containers above fleets (schema aura.society.v1)
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
- `society ≠ placement` — society is a durable named container with config above fleets; placement is a live cross-fleet grouping for one operation
- `placement ≠ routing` — grouping only; routing stays `fleet:seat`; movement stays lifecycle
- `sink id ≠ seat id` — Discord message ids are channel evidence; sidecars correlate, never substitute
- `profile ≠ agent` — a reusable capability seed, not the owner of a session
- `native delegation ≠ Aura worker creation` — a runtime's own subagent (Codex native child) is not an Aura seat; `aura spawn` from inside a native subagent is refused

Conceptual depth: `context/current/2026-06-04-2022/`

---

## Topology

```text
PRIMITIVE STACK
  society          named container above fleets   ~/.aura/societies/registry.json
    └── fleet      live group of seats            tmux session, durable fleet_id
          └── seat  runtime at fleet:seat         tmux pane, bound to a session
                └── runtime  one live mind        codex | claude-code | hermes | gajae-code | shell
                      └── session  native UUID    continuity anchor — survives rename/restart/move

  placement        cross-fleet roster             no movement, grouping only

  package          durable body                   ~/.aura/agents/i_<id>/
    manifest.json  spawn/resume recipe
    .codex/ | .claude/  runtime home (isolated)
    memories/
    skills.lock.json    aura-hands ownership

  profile          launch-time template           <runtime>/<name>
  registry         control-plane truth            ~/.aura/registry/

SKILL MAP
  TALK
    aura-send        one message → one seat, now
    aura-queue       same, held until recipient's next report boundary
    aura-broadcast   one message → many seats (fleet, scope, runtime)
    aura-report      publish own state (working/blocked/complete) + receipts; releases queued messages

  ORIENT
    aura-view        live topology source of truth — if it isn't here, it isn't live
    aura-status      workflow: view → reports → ask  ("what is X doing?")
    aura-inspect     raw terminal pane read — heavy, one seat, last resort

  WORK
    aura-spawn       create one new live seat in a fleet with a first assignment
    aura-crew        lead/assign/verify/integrate across multiple seats (lite | maxx workflow)
    aura-placement   named cross-fleet grouping; also a work pool target
    aura-society     named container above fleets: member pins + config pointer-map + resolves_to
    aura-event       wakeups · report/membership subscriptions · external HTTP in-jack

  SELF
    aura-self-bind   bind this process to its seat (rare — SessionStart hook does it automatically)
    aura-rollover    fresh session for a known-good seat (explicit, not repair)

  SUBSTRATE
    aura-operator    lifecycle, repair, hygiene, work pool — one op per job; fails closed
    aura-agent       durable package bodies: create, inspect, census, hooks, history, archive
    aura-profile     launch-time capability templates
    aura-hands       materialize skills into a package (symlink/copy, lockfile ownership)
    aura-quick       fastest throwaway seat from a canonical quick body

  EDGES
    aura-bridge      Discord channel-bindings · Clawhip · Hermes HTTP ingress (127.0.0.1:7135)
    aura-flex        Aura view → session_ids → Flex SQL over runtime transcripts

EXTERNAL SURFACES
  Discord           channel-bindings.json → fleet:manager default | @seat aliases
  Clawhip           delivery sidecar
  Hermes ingress    HTTP POST :7135 → hermes:<node> or aura:<fleet:seat>
  In-jack           services/aura_ingress.py  external POST (webhook/button/cron)
                      → token/signature proof → dedup → send | broadcast | work submit

TWO HARD LAWS
  READ   live = tmux pane + registry row, computed on every call.
         a row alone is HISTORICAL. state is binary: LIVE | HISTORICAL.
  WRITE  operations key off exact pane id %N. fail closed on staleness. dead %N → no-op.

STANDING INVARIANT
  delivered ≠ accepted — sent proves mechanics; acceptance is reply + receipts
```
