---
name: aura-queue
description: "Queue a message for a live agent, delivered at its next natural boundary instead of interrupting it."
---

# Aura Queue

Aura is a communication mesh for live agents: many agents run as named seats
(`fleet:seat`) and talk by address. You are likely one of those seats.
`aura queue` is the considerate send — the recipient is a mind that may be deep
in work, and a queued message waits and arrives at its next natural pause
instead of landing mid-thought. Same conversation as `aura-send`, different
timing.

## Ontology

**Seat** — an addressable live agent: `fleet:seat`.

**Boundary** — the recipient's next natural pause: the moment it writes its
next report. Queued messages release there, through the normal send path, with
your sender identity intact.

**Queued message** — a held message: `pending` until the boundary, then
`released`.

## Core Rule

Queue when it can wait; send when it can't. A queued message releases only
when the recipient reaches a boundary — a seat that never reports never gets
there, so if the message must land regardless, use `aura-send`.

## Commands

```bash
aura queue FLEET:SEAT "message"      # held until the seat's next report
aura queue --list                    # what's pending/released
```

## How To Speak

Exactly as in `aura-send`: role to role, full paragraphs, complete
understanding — the recipient reads it later without you there, so it must
stand alone even more than a live message. Write it so the agent picks it up
cold and knows the context, the why, and what you need back.

## When To Queue

- Follow-up work for an agent that's mid-task ("after you finish X, do Y").
- Next-phase assignments, non-urgent questions, "when you get a chance."

## When To Send Instead

- Anything urgent: an interrupt, a correction, an unblock, a launch nudge.
- The recipient doesn't write reports — there is no boundary to release at.

## Boundary

Queue is held conversation, not scheduling — for "do this at 3pm" or recurring
wakeups, use `aura-event`. Released delivery proves the message landed, not
that the work happened: that's the recipient's reply and receipts.
