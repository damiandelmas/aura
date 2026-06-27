---
name: aura-society
description: "Name a resolvable container above fleets — durable member fleets, a config pointer-map, and one opaque ref — that stores and resolves, and nothing else."
---

# Aura Society

Aura groups agents into fleets, and fleets sometimes belong together — one
product, one tenant, one world that owns several fleets and carries config for
all of them. A society is that container: a named record above fleet and
placement that points at member fleets, a config pointer-map, and one opaque
`resolves_to`. It stores and resolves; it moves and applies nothing.

Store: `~/.aura/societies/registry.json`, schema `aura.society.v1`.

## The Package

```text
society = { members: [fleet-id://…], config: {K: pointer}, resolves_to: <opaque> }
```

**members** — durable `fleet-id://` pointers. You author by name or glob; they
pin to `fleet_id`s at write time and resolve to CURRENT names on read, so a
fleet rename never adds or drops one. A dead id reads `stale`, never silently
gone.

**config** — a K→pointer map. **resolves_to** — opaque; Aura stores and returns
it, never interprets it.

## The Resolver Seam

A config value is a pointer resolved through a pure scheme→resolver registry:

```text
scheme://path   → registry[scheme](path)     dispatch
bare value      → literal
unknown scheme  → passthrough, RAW (never errors)
```

One resolver exists today: `fleet-id` (durable id → current name, `live` |
`stale`). `op://`, `placement:`, `runway://` pass through raw — deref is a
later registration, not a break.

## Commands

```bash
aura society list
aura society get NAME                # members resolved to current names + config + resolves_to
aura society of FLEET                # reverse: which society owns this fleet
aura society resolve NAME -k KEY     # a config pointer's value (raw today)
aura society set NAME --member 'glob-*'   # resolves the glob, pins durable fleet_ids
aura society remove-member NAME FLEET_ID
```

## Core Rule

Society stores and resolves, full stop. It does NOT apply config to seat env,
does NOT deref secrets (`op://` returns raw), does NOT reach into Runway or
desks. Bind to durable ids, not labels.

## Boundary

- The container vs. the change: `society` is the record; **membership** is the
  event one level below (member set changed). Subscribe to it via `aura-event`,
  don't conflate it with the container.
- Grouping live seats across fleets without a container → `aura-placement`.
- Applying config to how a seat runs → out of scope; society only holds the
  pointer.
