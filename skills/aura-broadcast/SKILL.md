---
name: aura-broadcast
description: "Send one message to many live agents at once — a fleet, all live seats, or all seats of one runtime."
---

# Aura Broadcast

Aura is a communication mesh for live agents: many agents run as named seats
(`fleet:seat`) and talk by address. You are likely one of those seats.
`aura broadcast` fans one message out to many of them at once — the
all-hands version of `aura-send`, with the same voice and the same provenance.

## Core Rule

Broadcast only when the same message genuinely applies to every target. If
different seats need different instructions, send separate messages — a
broadcast that needs per-seat caveats is several sends wearing a disguise.

## Commands

```bash
aura broadcast --fleet FLEET "message"                  # one fleet
aura broadcast --scope live "message"                   # all live managed seats
aura broadcast --scope live --runtime codex "message"   # all live seats of one runtime
```

Broadcast is live-first: it reaches live, managed, routable seats and skips
everything else (including you). Sender identity is inferred as with
`aura-send`; services use `--as-service NAME`.

## How To Speak

As in `aura-send` — but you're addressing many roles at once, so write the
shared core plainly: what's being asked, why, where the materials are, and
what response you expect from each.

## Boundary

- One target → `aura-send`
- Can wait for each seat's natural pause → `aura-queue` per seat
- Publishing your own state → `aura-report`
- Fewer seats reached than expected → check `aura view fleet` first; registry
  archaeology and shell-window inclusion are `aura-operator` work
