---
name: aura-spawn
description: "Create one new persistent live agent in an Aura fleet."
---

# Aura Spawn

Aura is the control plane for live agent runtimes: agents run as named seats
(`fleet:seat`) in tmux and talk by address. You are likely one of those seats —
and `aura spawn` is how a new colleague comes into existence: a fresh live
agent, in a fleet, at a name, with its first assignment.

## Ontology

**Seat** — the new agent's live address: `fleet:seat`.

**Runtime** — the mind that occupies it: `claude-code` (default), `codex`,
`hermes`, `gajae-code`, `shell`.

**Prompt** — the first assignment, carried into the runtime's own launch
command so it has landed by the time spawn returns.

## Core Rule

Spawn validates before it creates — cwd, runtime, env — and refuses bad input
with a structured reason rather than leaving a half-made pane. `--wait` means
the seat launched, not that the task finished.

## Command

```bash
aura spawn NAME \
  --fleet FLEET \
  --runtime codex \
  --cwd /path/to/project \
  --prompt "The assignment." \
  --as-pane --wait
```

Use `--work /path/to/packet.md` instead of `--prompt` only when a work packet
file already exists — don't create a file just to use the flag.

Add `--runtime-profile <runtime>/<name>` to launch the seat from a boxed
template (claude-code or codex) — see `aura-profile` for the templates.

## The First Assignment

The new seat is an intelligence waking up cold. Give it what a colleague would
need on day one: the objective, the files or scope it owns, what evidence or
report you expect back, and when to stop. Don't paste broad history — durable
context belongs in the cwd, the work packet, or the project docs it can read
itself.

## After Spawn

Give it a few seconds. If you need proof the task started, look once
(`aura inspect FLEET:NAME`); if it's sitting idle at the composer, send one
concise launch nudge with `aura-send`. If it's working — leave it alone.

## Boundary

- Reviving a durable agent package → `aura-operator` (package resume keeps the
  body attached; don't reconstruct its cwd/runtime by hand)
- Resume/fork of an existing session, adoption, repair → `aura-operator`
- Messaging the new seat afterwards → `aura-send` / `aura-queue`
