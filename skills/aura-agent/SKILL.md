---
name: aura-agent
description: "Maintain durable Aura agent packages: bodies, manifests, history, hooks, and their live bindings."
---

# Aura Agent

Aura runs agents as live seats (`fleet:seat`), but a seat's process can die.
A **package** is the durable body that survives it: a small directory holding
the recipe to relaunch the agent and the runtime's own state. This skill is
package maintenance — what a durable agent is, where its body lives, how it
starts, and whether its live binding matches its package state.

## Ontology

**Package** — a durable body at `~/.aura/agents/i_<id>/`: `manifest.json`
(the spawn/resume recipe) + the runtime's own home (`.codex/`, `.claude/`,
`.gjc/`) + `memories/` + optional generated `aura.json` (rebuildable history,
never authority). The home is isolated by a runtime env root the manifest sets
(`CODEX_HOME=.codex`, `CLAUDE_CONFIG_DIR=.claude`).

**Clean body** — before first spawn, a package is `manifest.json` only.

**Alias** — a human name for a package id in the index.

## Core Rule

Census before acting: `aura agent census` classifies every body (bound,
unbound, ghost, broken) — audit first, then touch only what's safe. And for a
new role, **create, don't clone**: clone copies the source's memories,
identity, and bindings — the old agent under a new address. Clone only when
that inheritance is the point.

## Commands

```bash
aura agent census                      # audit all bodies first
aura agent inspect REF                 # one body: manifest + state + bindings
aura agent create ADDRESS --runtime codex --cwd PATH --alias NAME   # new clean body (codex | claude-code | gajae-code)
aura agent history REF [--write]       # the body's Aura history projection
aura agent hooks REF [--repair]        # hook shape audit/repair
aura agent adopt-root /path/to/i_<id> --address A --alias N   # index an existing body
aura agent promote-seat FLEET:SEAT --address A --alias N      # snapshot a live seat to a body
aura agent archive REF                 # retire a body, lineage preserved
```

Direct file reads for the package-local surfaces:

```bash
python3 -m json.tool ~/.aura/agents/i_<id>/manifest.json
python3 -m json.tool ~/.aura/agents/i_<id>/aura.json
```

## Package Capability

Package-local skills are reusable capability, not product memory: keep them
small and role-shaped (scout, maker, auditor, manager). Tenant facts, prospect
lists, and audit results stay in the owning workstream and are passed in as
inputs. Audit order: `census → hooks → aura skills list → aura skills doctor`
(→ `aura-hands` for materialization). A new capability is package-grade only
when a fresh package-backed spawn can run it from the package materials alone.

## References

`references/map.md` · `references/surfaces.md` · `references/maintenance.md`

Architecture: `/home/axp/.runway/runway/places/aura/.context/current/2026-06-04-2022/bodies/package.md`

## Boundary

- Making a body live → `aura-operator` (`agent spawn --resume-session latest`)
- Materializing skills into a body → `aura-hands`
- Org policy, workstream truth, runtime transcripts — not package material.
