---
name: aura-status
description: "Answer 'what is X doing?' for a seat, fleet, or placement — from live topology, any reports, or by asking the seat."
---

# Aura Status

Aura is a communication mesh and control plane for live agents: many agents run
as named seats (`fleet:seat`) and can message each other by address. You are
likely one of those seats. "What is X doing?" is answered the same way it is
with a colleague — see who's around, check anything they've published, and
otherwise just ask them. This is a workflow over existing verbs, not a CLI
command.

## Ontology

**Seat** — an addressable live agent: `fleet:seat`.

**Report** — a seat's optionally published state (`working`, `blocked`,
`complete`, ...) with receipts. Opt-in — many seats never report, and that's
normal.

**Status** — the synthesis: who is live, plus what's known or said about what
they're doing.

## Core Rule

Status comes from the seat, not its terminal. Check what it published; if
nothing's there, ask it. Never scrape a pane for status you can get by asking.

## Workflow

```bash
aura view fleet FLEET                      # 1. who is live
aura report list --fleet FLEET --limit 20  # 2. anything published? (opt-in; often empty)
aura send FLEET:SEAT "Quick status check — what are you working on, any blockers?"
                                           # 3. the normal path: just ask
```

An empty report list means nothing — it's opt-in. Asking is not a fallback;
it's the ordinary way. Expect the answer as a reply, not instantly.

**Last resort:** if a seat doesn't answer and you genuinely need evidence of
what it's doing right now, `aura inspect FLEET:SEAT` reads its raw terminal
pane — heavy and noisy. One seat at a time, never a default sweep.

## What To Say

One seat:

```text
FLEET:SEAT — working on <work> (their reply / report, <age>).
```

A fleet:

```text
FLEET — N live seats:
- FLEET:seat-a   working   <summary>
- FLEET:seat-b   blocked   <blocker>     ← attention
- FLEET:seat-c   asked, awaiting reply

Attention: seat-b blocked on <blocker>.
```

Mark blocked/failed seats as attention. Distinguish "said" (reply/report) from
"observed" — don't present silence as a problem or a guess as a fact.

## Boundary

Status is asking and reading, not managing. Don't repair or assign work here.

- Liveness/topology only → `aura-view`
- Publishing your own state → `aura-report`
- Non-urgent follow-up to a busy seat → `aura-queue`
- Binding, recovery, registry archaeology → `aura-operator`
