---
name: aura-view
description: "Discover live Aura topology: who you are, which seats are live, and the exact fleet:seat to message or report to."
---

# Aura View

Aura is the control plane for live agent runtimes: it runs many agents (Codex,
Claude Code, Hermes, ...) as named seats in tmux, and lets them be viewed,
messaged, and managed by address. You are likely one of those seats — a live
agent at an address like `fleet:seat` — working alongside others. `aura view`
is how you discover that topology: who you are, who else is live, and the
exact addresses to use.

## Ontology

**Aura** — the live control plane for managed agent runtimes.

**Seat** — an addressable live runtime. Its address is `fleet:seat`.

**Fleet** — a live group of seats. The fleet label maps to a tmux session, but
the fleet is the Aura-managed group, not the session itself.

**Target** — the full live address `fleet:seat`. Use the returned `target`
verbatim when you message or report.

## Core Rule

`aura view` is the source of truth for live topology. If `aura view` doesn't
return it, it isn't live. If docs disagree with `aura view`, the docs are stale.

## Commands

```bash
aura view self                  # who am I — my fleet:seat
aura view fleet                 # my current fleet
aura view fleet FLEET           # a named fleet
aura view fleets                # all live fleets
aura view placement PLACEMENT   # live seats grouped by placement
```

## How To Read It

- Use the returned `target` exactly as the seat address.
- It says it can't reach tmux → treat that as **unknown**, not "nothing is live."

## What To Say

```text
I am FLEET:SEAT.

FLEET has N live managed seats:
- FLEET:seat-a
- FLEET:seat-b

I don't see live managed seats for FLEET.
```

Speak in the first person — "I" / "this seat," not "your fleet" — unless the
user named a different target.

## Boundary

Discovery only. Don't read panes, repair seats, or debug runtime behavior here.

- What a seat is *doing* → its reports (`aura-report` / `aura-status`)
- Roster, historical registry, physical pane↔row repair → `aura-operator`
