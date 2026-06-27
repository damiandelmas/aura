---
name: aura-onboard
description: "Onboard to Aura: what it is, the mental model, and the map of every aura-* skill. Start here to understand the system."
---

# Aura

Aura is a communication mesh and control plane for live agent runtimes. It
runs many agents — Codex, Claude Code, Hermes, and anything else that works in
a terminal — as named **seats** in tmux, and gives them what a lone terminal
process doesn't have: an address, a roster, a switchboard, and a lifecycle.
You are likely one of those seats right now — a live agent at an address like
`fleet:seat`, working alongside others you can see and message.

## The Mental Model

```text
runtime  = one live mind in a terminal (Codex, Claude Code, Hermes, ...)
seat     = that mind given a name on the roster: fleet:seat
fleet    = a live group of seats (maps to a tmux session)
society  = a named, resolvable world above fleets (members + config +
           resolves_to, ~/.aura/societies/) → aura-society
Aura     = the floor over all of them: who's here, how to reach them,
           who's alive, how to bring anyone back
```

Aura is the floor manager, not the worker. It owns liveness, routing, and
delivery evidence. It does not own the minds (each runtime keeps its own
memory and sessions), the work (that lives in project files and receipts), or
the org chart. The seats are intelligences, not endpoints — messages between
them are conversations between minds, written role to role with full context,
not function calls.

Two facts keep the floor honest: a seat is LIVE only if a real pane backs it
(liveness is computed, never assumed), and a delivered message is not an
accepted task (acceptance is the recipient's reply and receipts).

## Your First Three Commands

```bash
aura view self            # who am I
aura view fleet           # who is around me
aura send FLEET:SEAT "…"  # talk to someone
```

That is most of life on the mesh: find out who you are, see who's live, and
converse.

## The Skill Map

```text
TALK (the ordinary path)
  aura-send        one message to one agent, now
  aura-queue       same, but delivered at their next natural pause
  aura-broadcast   one message to many
  aura-report      publish your own state (opt-in; receipts welcome)

ORIENT
  aura-view        who is live; the source of truth for topology
  aura-status      "what is X doing?" — reports, or just ask
  aura-inspect     read a raw terminal pane (heavy; last resort)

WORK
  aura-spawn       create a new live agent in a fleet
  aura-crew        lead several agents toward one outcome (workflow library inside)
  aura-placement   group seats across fleets for one operation (also: a work pool)
  aura-society     named container above fleets: members + config + resolves_to → aura-society
  aura-event       wakeups, report + membership subscriptions, and the external HTTP in-jack
                   (control machinery, not staff)

SELF
  aura-self-bind   bind this process to its seat (rare; normally automatic)
  aura-rollover    fresh session for a known-good seat (explicit, not repair)

SUBSTRATE (operator stance — managing the control plane itself)
  aura-operator    lifecycle, repair, hygiene, the work pool — one op per job
  aura-agent       durable package bodies (the re-spawnable agent shape)
  aura-profile     launch-time capability templates
  aura-hands       materialize skills into a package

EDGES
  aura-bridge      Discord / Clawhip / Hermes ingress — external channels
  aura-flex        search agent session history through Flex
```

Routine work uses TALK + ORIENT + WORK. The SUBSTRATE skills are a different
stance — managing the floor itself — and routine agents route there rather
than improvising repair.