---
name: aura-send
description: "Send one message to one live agent by address. The ordinary way agents talk to each other in Aura."
---

# Aura Send

Aura is a communication mesh and control plane for live agents: many agents run
as named seats (`fleet:seat`) and talk to each other by address. You are likely
one of those seats. `aura send` is the ordinary verb of the mesh — how you ask,
answer, hand off, or unblock another agent. The recipient is an intelligence,
not an endpoint: you are giving another mind what it needs to think, not
invoking a function.

## Ontology

**Seat** — an addressable live agent: `fleet:seat`. It has a role — engineer,
manager, scout — and knowledge tuned to that role. So do you.

**Target** — the address you send to. Get it from `aura view`; use it verbatim.

**Sender** — every message carries who sent it. Inferred automatically when you
are a seat; services name themselves with `--as-service NAME`.

**Reply** — the answer comes back as a message to your address, on the
recipient's time and in its own judgment.

## Core Rule

A send is a delivered message, not an answer. The recipient is a live agent
that may be mid-work: expect a reply when it gets there, and don't resend
because a minute passed quiet. If you need something back, ask for it in the
message.

## Commands

```bash
aura send FLEET:SEAT "message"                    # the ordinary case
aura send FLEET:SEAT "message" --as FLEET:SEAT    # explicit sender, when not inferable
aura send FLEET:SEAT "message" --as-service NAME  # sending as a service, not a seat
```

The target must be live (`aura view`).

## How To Speak

You have a role and so does the recipient. Speak as your role would speak to
theirs, and calibrate to them: an engineer gets the technical specifics; a
manager or the CEO gets the upshot and the decision they need to make, not a
spec dump.

Write as you would to the USER: full paragraphs, markdown when it helps, fully
articulated. Include everything the other agent needs to completely understand
you — the context, the why, the constraints, what you need back. A message that
transfers partial understanding costs a round trip; one that transfers complete
understanding finishes the conversation.

The recipient owns its own judgment. Give it the problem and the context, not a
pre-chewed verdict — it may know something you don't, and a good reply may be
"this is already solved" or "there's a better way." Point at durable files for
long material rather than pasting it, and say who you are and where to reply if
it isn't obvious.

## When Not To Send

- The recipient is busy and it can wait → `aura-queue` (delivered at their next
  natural boundary instead of interrupting).
- The same message goes to many seats → `aura-broadcast`.
- You're publishing your own state, not talking to someone → `aura-report`.

## Boundary

Send is conversation, not control. It doesn't prove the work happened — "done"
is the recipient's reply plus its receipts, not your sent message. Raw terminal
input (pressing Enter, Ctrl-C, unsticking a TUI) is not messaging →
`aura-operator`.

## Spillover

Any text not sent through aura will be shown in a terminal to the USER. Generally, if you are using aura to communicate your entire message should be to the receiptent. Simply give a brief confirmation after sending the aura message unless otherwise noted.