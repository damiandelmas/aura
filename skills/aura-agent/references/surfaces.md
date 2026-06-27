# Agent Surfaces

An Aura agent is a join across package, organization, runtime, and live
execution surfaces. No single file is the whole agent.

## Organization Position

```text
/home/axp/.runway/<product>/organization.json
```

The organization file maps product, line, unit, team, and position to a durable
identity id. It answers where the agent belongs. It does not carry live Aura
fleet, seat, cwd, runtime, or session data.

Example:

```text
flexgraph / chatbot / operations / chief-of-staff -> i_d40ca383d29d
```

## Identity Package

```text
/home/axp/.aura/agents/i_<id>/
```

The package root is the durable Aura identity body. It contains the spawn
recipe, generated Aura history, and runtime-native package homes. It is the
thing Aura can inspect, spawn, clone, migrate, and assign to an organization
position.

## Spawn Recipe

```text
/home/axp/.aura/agents/i_<id>/manifest.json
```

The manifest says how to start the package. It usually carries runtime, cwd,
argv, env, profile, resume defaults, fleet, and seat. It is not the runtime
history and it is not the organization map.

## Aura History Projection

```text
/home/axp/.aura/agents/i_<id>/aura.json
```

`aura.json` is a generated package-local projection. It summarizes where the
identity has run using Aura registry and session-ledger evidence. The registry
and session ledger remain the authority.

## Runtime State

```text
/home/axp/.aura/agents/i_<id>/.codex/
  /home/axp/.aura/agents/i_<id>/.claude/
  /home/axp/.aura/agents/i_<id>/.gjc/
```

Runtime-native state stays in runtime-native shape. Codex and Gajae-Code may store
sessions, logs, hooks, local config, prompts, skills, and runtime-specific
state under their own homes. Agent maintenance can preserve or locate these
roots, but should not pretend they are organization truth.

## Live Execution

```text
Aura registry
Aura session ledger
Aura fleet:seat
tmux session/window when terminal-backed
```

Live execution is the current runtime address and process state. A live Aura
seat may animate an organization position, but it is not the organization
position itself. A package can have no live seat, one live seat, or historical
seats across many fleets.
