---
name: aura-report
description: "Publish this seat's own state — working, blocked, complete — with receipts, to Aura's report ledger."
---

# Aura Report

Aura is a communication mesh for live agents: many agents run as named seats
(`fleet:seat`) and talk by address. You are likely one of those seats.
`aura report` is how you publish your own state to the mesh — a durable
check-in anyone can read later, distinct from talking to someone
(`aura-send`). Reporting is opt-in: publish when your state is worth knowing,
with receipts.

## Ontology

**Report** — your published state: what you're doing, what's blocking, what's
done, with evidence.

**Receipt** — the path or artifact that proves the claim. A `complete` without
a receipt is just a claim.

**Boundary** — writing a report is your natural pause: it releases any
messages queued for you.

## Core Rule

Report is publishing, not replying. To answer, confirm, or ask a live seat,
use `aura-send`; report when the state itself should be on the record —
work started, a blocker hit, a handoff, a completion with receipts.

## Commands

```bash
aura report working  --work "Reviewing the skill surface" --next "patch current docs"
aura report blocked  --work "Launching worker" --blocker "missing cwd"
aura report complete --work "Added queue skill" --receipt "/abs/path/to/proof"

aura report latest
aura report list --limit 20
```

States: `working · blocked · needs_decision · handoff · complete · parked · failed`

Writing a report also releases any `aura queue` messages waiting for you —
expect held instructions to arrive right after you report.

## Handoff

Name the next actor and the next concrete action:

```bash
aura report handoff \
  --work "Completed slice X" \
  --receipt "/abs/path" \
  --next "Next actor: FLEET:SEAT should review /abs/path"
```

If it's state transfer only, say so — `state-only; no new work unless the
operator directs it` — and don't turn a handoff into a fresh assignment.

## Boundary

- Talking to a live seat → `aura-send`
- Being notified of others' reports → `aura-event` (subscriptions)
- A report is evidence, not acceptance — whoever integrates your work still
  verifies the receipts.
