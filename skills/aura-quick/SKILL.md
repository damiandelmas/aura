---
name: aura-quick
description: "Spawn the fastest possible live seat from a canonical quick body — no package, no naming, no ceremony."
---

# Aura Quick

`aura quick` is the shortest path to a working live seat. It launches a ready
agent from the **canonical quick body** for a runtime — born-bound, boxed in its
own runtime home — with none of the package ceremony. Reach for it when you want
a fast, throwaway seat to think or work in, not a durable named colleague.

## Runtimes

```bash
aura quick codex
aura quick claude-code
aura quick gajae-code
```

Each spawns from that runtime's canonical quick body. The claude-code path is
boxed via `CLAUDE_CONFIG_DIR` (its config + transcripts live under the seat, not
`~/.claude`) and launches unattended — no theme/login/trust/permission prompts.

## Options

- `--new` — fresh box, nothing inherited.
- `--profile <runtime>/<name>` — launch from a boxed template (see `aura-profile`).
- `--default` — the runtime's default profile.
- `--runtime-profile` — same boxed-template launch, named to match `aura spawn`.

## When To Reach For Quick

- **`aura quick`** — a fast canonical seat to use and discard. No durable body.
- **`aura spawn`** — an ad-hoc live agent you name and assign now (`aura-spawn`).
- **`aura agent create`** — a durable, named package body that persists (`aura-agent`).
- **`aura profile`** — the template a quick or spawn can launch *from* (`aura-profile`).

## Boundary

- Want it to survive and be revivable later → make a package (`aura-agent`), not a quick seat.
- Messaging the seat afterwards → `aura-send` / `aura-queue`.
- Building the template it launches from → `aura-profile`.
