---
name: aura-crew
description: "Run a managed group of Aura seats toward one outcome — assign, watch, verify, integrate, close. Pick a workflow gear: lite or maxx."
---

# Aura Crew

Aura is a communication mesh and control plane for live agents: many agents run
as named seats (`fleet:seat`) and talk by address. You are likely one of those
seats — and sometimes one agent leads several others toward one outcome. That
is a crew: a lead who assigns, watches, verifies, and integrates, over workers
who produce. Each worker is an intelligence, not a function — give it a
mission and context, and own the verification of what comes back.

## Ontology

**Crew** — one lead plus the seats it manages for one bounded outcome.

**Lead** — the seat that decomposes, assigns, reduces reports, verifies
receipts, and integrates. The lead owns acceptance.

**Worker** — a seat with a mission, a write scope, and a report expectation.

**Receipt** — the artifact that proves work: a diff, a test run, a file. A
worker's "done" is a claim; the receipt plus the lead's verification is the
acceptance.

## Core Rule

Worker reports are evidence, not acceptance. The lead reads the receipts,
inspects the diffs, reruns verification where it matters — and only then
integrates. Never promote a claim because the pane looked busy or a message
was delivered.

## The Loop

```text
define the outcome and the seats   (objective, ownership, write scopes, stop gates)
  -> spawn or message the workers  (aura-spawn / aura-send; full context, role to role)
  -> follow progress               (replies and reports; queue non-urgent follow-ups)
  -> verify receipts               (read them; rerun checks that matter)
  -> integrate and close           (park or cut seats; name evidence and gaps)
```

Queue by default for a busy worker (`aura-queue`); send immediately only to
launch, unblock, or correct (`aura-send`).

## Workflows

Pick the lightest gear that preserves the work; the library grows as crew
shapes are proven.

```text
references/workflows/lite.md   one lead, a few seats, one session, light machinery
references/workflows/maxx.md   board + worker packets + subscriptions + closeout ledger,
                               for long-running or high-stakes crews
```

Templates: `references/onboard-packet.md`, `references/worker-packet.md`,
`references/crew-ledger.md`, `references/coordinator-posture.md`.

## Boundary

Crew work is coordination over the routine verbs. Workers don't repair seats,
edit the registry, or do terminal surgery — they report symptoms, and the lead
routes lifecycle or repair to `aura-operator`. A single message or a single
direct action doesn't need a crew.
