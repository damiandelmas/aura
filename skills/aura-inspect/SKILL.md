---
name: aura-inspect
description: "Read one seat's raw evidence — mechanical status and terminal excerpt. Heavy; a last resort after reports and replies."
---

# Aura Inspect

`aura inspect` reads one seat's raw evidence: its mechanical status and,
optionally, its actual terminal text. It is heavy and noisy — a pane dump
loads a lot of context — so it is a last resort, not a status tool. To know
what an agent is doing, read its reports or ask it (`aura-status`); reach for
inspect only when you genuinely need to *see* the terminal.

## Commands

```bash
aura inspect FLEET:SEAT                  # compact mechanical status
aura inspect FLEET:SEAT --raw --lines 80  # the actual terminal text
```

One seat at a time. Never sweep a fleet with inspect.

## Boundary

- Who is live → `aura-view`
- What a seat is doing → `aura-status` (reports, or just ask)
- Watch loops, semantic sense, terminal surgery, binding repair → `aura-operator`
