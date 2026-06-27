# Agent Map

An Aura agent is a join across a few surfaces.

```text
organization.json  -> where the agent belongs
index.json         -> package id or alias to package root
manifest.json      -> how the agent starts
aura.json          -> where the agent has run
.codex/.claude/.gjc -> what the runtime stores
registry/ledger    -> Aura authority for live/history state
fleet:seat         -> current live execution address
```

## Topology

```text
Runway position
  -> identity id
  -> Aura package index row
  -> Aura package root
  -> manifest.json
  -> live Aura fleet:seat
  -> registry/session-ledger rows
  -> generated aura.json
```

## Paths

```text
ORG POSITION
  /home/axp/.runway/<product>/organization.json

IDENTITY PACKAGE
  /home/axp/.aura/agents/i_<id>/

PACKAGE INDEX
  /home/axp/.aura/agents/index.json

SPAWN RECIPE
  /home/axp/.aura/agents/i_<id>/manifest.json

AURA HISTORY
  /home/axp/.aura/agents/i_<id>/aura.json

RUNTIME STATE
  /home/axp/.aura/agents/i_<id>/.codex/
  /home/axp/.aura/agents/i_<id>/.claude/
  /home/axp/.aura/agents/i_<id>/.gjc/

LIVE EXECUTION
  Aura registry/session-ledger
  Aura fleet:seat
```

## Example

```text
organization.json
  flexgraph / chatbot / operations / chief-of-staff
    -> i_d40ca383d29d

package root
  /home/axp/.aura/agents/i_d40ca383d29d/

manifest.json
  runtime: codex
  cwd: /home/axp/projects/flexgraph/chatbot
  fleet: flexgraph-operations
  seat: chief-of-staff
  resume: latest

aura.json
  current:
    ref: flexgraph-operations:chief-of-staff
    session_id: 019e2d0a-03c6-7462-87fe-f1227118a1c5

.codex/
  Codex-native config, sessions, hooks, state
```
