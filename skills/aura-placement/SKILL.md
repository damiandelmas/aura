---
name: aura-placement
description: "Group live Aura seats into named cohorts — workstreams, dashboards, cross-fleet operations — without moving anything."
---

# Aura Placement

Aura runs agents as named seats (`fleet:seat`) grouped into fleets. Sometimes
an operation spans fleets — a workstream, a dashboard, a tenant wave — and
needs its own roster. A placement is that roster: a named grouping over seats
that moves nothing and changes nothing about how they run.

## Ontology

**Placement** — a named grouping record over `fleet:seat` refs.

**Member** — a seat in the placement, with an optional role (`control`,
`floor`, `unblocker`, `reviewer`, `conductor-<slug>`, `worker-<slice>`),
kind, and label.

## Core Rule

Placement is grouping only. It does not move panes, rename seats, select
profiles, or replace `fleet:seat` routing — adding a member records
participation, removing one edits only the record. Routing stays `fleet:seat`;
movement stays lifecycle.

## Commands

```bash
aura placement add PLACEMENT FLEET:SEAT --role ROLE --kind workstream --label "Name"
aura placement remove PLACEMENT FLEET:SEAT
aura placement list
aura placement show PLACEMENT       # the stored record
aura view placement PLACEMENT       # the live view of its members
```

Pick roles that explain responsibility to the next agent reading the
placement. Verify with `show` or the live view before calling it done.

## Boundary

- Following a placement's reports → `aura-event` (subscribe `--placement`)
- Moving or renaming a seat → `aura-operator`
- Draining queued work to a placement's idle members (a work pool) →
  `aura-operator` (`work dispatch-start --placement`, `idle-watch --placement`).
  The placement names *who* is in the pool; the dispatcher flows work to whoever
  is free. Add a member, then restart `idle-watch` so it's sensed.
- Workstream truth (boards, receipts) lives outside Aura — a placement points
  at participants, it doesn't store the work.
