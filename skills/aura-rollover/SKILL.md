---
name: aura-rollover
description: "Give a live seat a fresh runtime session while keeping its name. Explicit freshen on request — not a repair tool."
---

# Aura Rollover

Aura runs agents as named seats (`fleet:seat`); each seat's mind carries a
runtime session — its conversation and context. `aura rollover` replaces the
process *and* starts a fresh session while keeping the seat's name: the same
chair, a fresh mind. Use it when the user explicitly asks to freshen, rotate,
or re-up a seat.

## Core Rule

Rollover is an explicit request, not a repair reflex. It permanently discards
the seat's recoverable session context — so never reach for it to "fix" a
confused or stuck seat. A stuck seat is a diagnosis problem
(`aura-operator`); a known-good seat the user wants fresh is a rollover.

```text
restart  = new process, KEEP the session
rollover = new process, FRESH session
cut      = retire the seat
```

## Command

```bash
aura seat rollover FLEET:SEAT --reason "why"
```

For a whole fleet, get the seat list from `aura view fleet FLEET` and roll
each. Add `--force` only when the user wants it now and there's no safe
report boundary to wait for.

## Verify And Report

`aura view fleet FLEET` after rolling. Report compactly: seats rolled,
old/new instance ids, whether the panes are alive, and any
`session_observation_pending` caveat. Rollover born-binds — the relaunch
carries the new `seat_instance_id`, so the SessionStart hook's occupant
check matches and the fresh session binds via the hook without manual heal.
The pending caveat is just the hook firing asynchronously: the born-bind
hook resolves it within moments and the self-heal sweep backstops it —
report it as transient, not a risk.

## Boundary

- Keep the names. Don't cut and respawn under a new name for a rollover request.
- Don't send work prompts to the fresh seats unless explicitly asked.
- A durable package's seat → `aura-operator` (the body stays attached).
