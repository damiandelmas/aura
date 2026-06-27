---
name: aura-profile
description: "List, inspect, and safely create Aura runtime profiles for launch-time capability and runtime-home templates."
---

# Aura Profile

Use runtime profiles to make Aura launches repeatable. A profile is a logical capability ref like `codex/dev` or `codex/aura-operator`, not a filesystem path. It can seed runtime guidance, skills, hooks, config, model policy, and runtime-home template material at spawn time. A profile is a reusable seed, not an agent — it shapes a launch, it does not own the resulting seat.

## Commands

```bash
aura profile list --include-future
aura profile inspect codex/aura-operator
aura profile create codex/aura-operator --from codex/default --preset aura-operator
aura profile create claude-code/dev --from claude-code/default
```

Profile refs are runtime-keyed: `<runtime>/<name>`. `create` is supported for Aura-owned boxed **Codex** and **Claude Code** templates. A Codex profile templates `.codex` (config/hooks/skills); a Claude Code profile templates `.claude` (`settings.json`, skills) — its `claude-home-template/` is copied into the seat's box at spawn, with the statusline + lifecycle hooks layered on top. `--from REF` clones from an existing same-runtime profile; it rejects path-like refs, missing source profiles, live runtime homes, and existing destinations. `--preset aura-operator` seeds the destination from the fixed operator skill allowlist.

Hermes profiles are Hermes-native (`~/.hermes/profiles/`); Aura references them with `--profile NAME` at spawn but does not create or template them. Gajae-Code does not use Aura runtime profiles; for fresh Gajae seats use `aura quick gajae-code`.

## Profile Contract

Profiles describe launch capability:

```text
runtime family
config and hooks
skills or prompts available at launch
runtime-home template files (boxed Codex / Claude Code)
model/runtime policy
safety notes
```

Profiles do not prove work completion and do not replace project context. Prepare the working directory and assignment clearly before spawn. Reusable templates reject auth files, sessions, histories, caches, logs, sqlite/db files, symlinks, and unsafe path segments; mutable runtime state belongs in the per-seat box, not the template.

## Verification

```bash
aura profile inspect codex/aura-operator
aura spawn test-aura-operator --fleet scratch --runtime codex --runtime-profile codex/aura-operator --cwd /path/to/project --as-pane --wait
aura inspect scratch:test-aura-operator --lines 80
```
