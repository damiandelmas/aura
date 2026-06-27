---
name: aura-event
description: "Wake a seat on a cadence, or subscribe a seat to others' reports. Control machinery — it triggers work, it isn't a worker."
---

# Aura Event

Aura runs agents as named seats (`fleet:seat`) that talk by address. Some
things should happen *later* or *on a signal*: a seat woken every N seconds, a
lead notified when a worker reports blocked, an external `POST` arriving from a
button or webhook. `aura event` is that machinery.
An event is a trigger, not a reasoning agent — it causes work to happen at the
right time; the seat it wakes does the thinking.

## Ontology

**Wakeup** — an interval tick delivered to one seat
(`tick → take one bounded step → return idle`).

**Subscription** — a rule turning matching report rows into normal messages to
one recipient seat.

**Membership** — a rule turning a group's member-set change (a seat joins/leaves/renames
within a fleet or placement) into messages; distinct from a report (a member's own
self-state).

**In-jack** — the external-push trigger: an HTTP `POST` from outside Aura,
turned into a normal `send` / `broadcast` / `work submit`. See
`references/in-jack.md`.

**Job** — the durable record behind a wakeup or subscription. Jobs have a
lifecycle — active, updated, retired — and are never silently deleted.

## Core Rule

Events are control machinery, not staff. A wakeup target should be durable
(respawnable by name) so the cadence survives a process death; a tick should
name what to read and when to stop. Never run sleep loops inside a runtime —
that's what events are for.

## Wakeups

```bash
aura event start --name ops-cadence \
  --target FLEET:SEAT \
  --as service:aura-event \
  --every 180 \
  --template "cadence tick {tick}: take one bounded operations step, then return idle."
```

`--ticks N` bounds the run. Wakeups target one seat; to drive a cohort, wake
its lead and let the lead message the placement.

## Subscriptions

```bash
aura event subscribe reports --name crew-checkins \
  --fleet FLEET --to FLEET:LEAD --as FLEET:LEAD

aura event subscribe reports --name crew-blockers \
  --fleet FLEET --state blocked --state needs_decision \
  --to FLEET:LEAD --as FLEET:LEAD

aura event subscribe membership --fleet F | --placement P \
  [--kind join,leave,rename] --to FLEET:SEAT
```

Source filter is `--fleet`, `--target`, or `--placement` (placement membership
is followed dynamically). Self-echo is suppressed; overlapping subscriptions
dedupe per report. `--as` is a managed seat, because releases are normal sends.

## External Triggers (the in-jack)

A trigger can also arrive from *outside* Aura. The HTTP in-jack
(`services/aura_ingress.py`) is the push-equivalent of a wakeup: an external
`POST` — a hosted button, a SaaS webhook, a cron on another box — is proven by a
token or per-source signature, deduped, then handed to the mesh as a normal
`send`, `broadcast`, or `work submit` against a scheme-prefixed target
(`seat:` / `fleet:` / `placement:`). Sources you control speak the native
envelope and need no code; foreign signers (Linear, GitHub) get a small
per-source adapter. You don't call it from a seat — an operator runs the door;
from the seat's side the work just arrives. Full contract + the adapter "SDK" in
`references/in-jack.md`.

## Manage The Jobs

```bash
aura event list / status NAME
aura event update NAME --target NEW-FLEET:SEAT --every 300   # mutate in place, keep the id
aura event pause / resume / run / stop NAME
aura event retire NAME                                       # done with it: retire, don't delete
aura event subscriptions / subscription show|pause|resume|remove NAME
```

After a seat rename or move, `update` the job's target — reorgs don't update
event targets by themselves. Retire jobs that are no longer wanted, so intent
stays legible.

## Boundary

- One held message for one seat → `aura-queue` (a report boundary, not a clock)
- The recipient of a wakeup does the work; the event only knocks.
- Standing up or supervising the in-jack door itself → `aura-operator` (it's
  edge infra, run as a service, not a seat op).
