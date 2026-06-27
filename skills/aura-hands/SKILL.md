---
name: aura-hands
description: "Operate Aura Hands: package-local skills today, with the same ownership model extending to MCP, runtime config, hooks, prompts, rules, and agent capability materialization."
user-invocable: true
---

# Aura Hands

Aura runs agents as live seats backed by durable packages (`~/.aura/agents/i_<id>/`)
— and a package's capabilities (its skills) are materialized into it from
canonical sources, not authored inside it. Aura Hands is that capability layer:
it projects skills into packages, records ownership in a lockfile, and repairs
drift. Today the implemented CLI is `aura skills`; the Hands ownership model is
intended to extend to MCP servers, config, hooks, prompts, and rules.

Core rule: evidence first — inventory, diff, dry-run, mutate only when safe,
then verify with doctor.

The current implemented package skill surface materializes runtime-native
skills into the package, deriving the runtime home from the package manifest —
`.codex/skills/` for codex packages, `.claude/skills/` for claude-code packages:

```text
~/.aura/agents/i_<id>/.codex/skills/<skill-directory>     # codex package
~/.aura/agents/i_<id>/.claude/skills/<skill-directory>    # claude-code package
```

Apply derives the home the same way — same verb, runtime-aware target:

```bash
# codex package → <body>/.codex/skills/
aura skills apply --agent <codex-pkg> --skill /home/axp/.codex/skills/aura-operator --mode symlink

# claude-code package → <body>/.claude/skills/
aura skills apply --agent <claude-pkg> --skill /home/axp/.claude/skills/aura-operator --mode symlink
```

Aura-owned package skill state is currently recorded in:

```text
~/.aura/agents/i_<id>/skills.lock.json
```

## Progressive References

Read these only when needed:

- `references/available-now.md` — manual Aura Hands workflows available before a polished `aura hands` CLI exists, including Printing Press control cells, Codex-home diffing, safe mutation plans, and fleet PP workers.

## Core Doctrine

Aura Hands owns package materialization, not semantic authorship. Canonical capability sources stay in their source locations, while agent packages receive symlink or copy projections. The lockfile is an ownership/provenance record, not the canonical content store.

- Canonical skills stay in source roots such as `context/current/skills/*` or another chosen library root.
- Agent packages receive projections by symlink or copy.
- Symlink is the edit-once/update-everywhere mode.
- Copy is the frozen snapshot mode.
- Inventory, duplicates, and diff are read-only.
- Adoption is dry-run unless `--write` is passed.
- Remove only deletes Aura-owned package targets recorded in `skills.lock.json`; it never deletes canonical sources.
- Do not use package skill commands to mutate global `~/.codex` or `~/.claude` homes.

## Current Command Surface

The current implemented CLI remains skill-specific:

```bash
aura skills inventory [--root PATH]... [--no-packages]
aura skills duplicates [--root PATH]... [--include-identical] [--no-packages]
aura skills diff NAME [--root PATH]... [--no-packages]

aura skills apply --agent AGENT --skill SKILL_DIR [--skill SKILL_DIR ...] \
  [--mode symlink|copy] [--replace] [--dry-run]
aura skills list --agent AGENT
aura skills doctor --agent AGENT
aura skills sync --agent AGENT [--dry-run] [--prune]
aura skills remove --agent AGENT SKILL_NAME [--dry-run]
aura skills adopt --agent AGENT [--write] [--replace-lock]
```

## Standard Operating Procedure

Start read-only, narrow the target, then mutate with dry-runs and verification. This keeps agent behavior changes observable and reversible. If the request touches hooks, MCP, runtime config, or global homes, treat it as higher-risk and prefer a written mutation plan first.

### Inventory

Use inventory to map skills, names, paths, hashes, symlink targets, and package projections.

```bash
aura skills inventory
```

For a narrow source root:

```bash
aura skills inventory --root /home/axp/.codex/skills --no-packages
```

### Duplicates and Diff

Use duplicates to find divergent skill names, then diff one skill identity before deciding which copy is canonical.

```bash
aura skills duplicates
aura skills duplicates --include-identical
aura skills diff SKILL_NAME
```

### Inspect One Agent Package

Use list and doctor before applying, adopting, syncing, or removing package skills.

```bash
aura skills list --agent AGENT
aura skills doctor --agent AGENT
```

### Adopt Existing Package Skills

Adoption records existing package-local skills into `skills.lock.json` without moving, copying, rewriting, or deleting skill directories.

```bash
aura skills adopt --agent AGENT
aura skills adopt --agent AGENT --write
```

Use `--replace-lock` only when intentionally replacing the existing lockfile entries with the current on-disk package skills.

### Apply Canonical Skills

Apply projects one or more canonical skill sources into one agent package. Prefer symlink mode for canonical Aura skills and dry-run first on real packages.

```bash
aura skills apply \
  --agent AGENT \
  --skill /home/axp/.codex/skills/aura-operator \
  --mode symlink \
  --dry-run

aura skills apply \
  --agent AGENT \
  --skill /home/axp/.codex/skills/aura-operator \
  --mode symlink
```

### Repair Drift

Run doctor first, preview sync, then repair only drift Aura can prove from lockfile ownership evidence.

```bash
aura skills doctor --agent AGENT
aura skills sync --agent AGENT --dry-run
aura skills sync --agent AGENT
```

Use prune cautiously and preview it first:

```bash
aura skills sync --agent AGENT --prune --dry-run
aura skills sync --agent AGENT --prune
```

### Remove Safely

Removal is ownership-bound. It removes package-local targets only when `skills.lock.json` says Aura owns them.

```bash
aura skills remove --agent AGENT SKILL_NAME --dry-run
aura skills remove --agent AGENT SKILL_NAME
```

## Canonical Workflows

### Make One Agent Use Current Aura Operator Skills

Use symlinks so edits to canonical skills under `/home/axp/.codex/skills` flow into the package.

```bash
aura skills apply \
  --agent AGENT \
  --skill /home/axp/.codex/skills/aura-operator \
  --skill /home/axp/.codex/skills/aura-profile \
  --mode symlink \
  --dry-run

aura skills apply \
  --agent AGENT \
  --skill /home/axp/.codex/skills/aura-operator \
  --skill /home/axp/.codex/skills/aura-profile \
  --mode symlink

aura skills doctor --agent AGENT
```

### Bring an Old Package Under Management

Use this when an existing package already has skills but no lockfile.

```bash
aura skills list --agent AGENT
aura skills doctor --agent AGENT
aura skills adopt --agent AGENT
aura skills adopt --agent AGENT --write
aura skills doctor --agent AGENT
```

### Investigate a Forked Skill

Use this when two agents or runtimes may be using different versions of the same skill.

```bash
aura skills inventory
aura skills duplicates
aura skills diff SKILL_NAME
```

## Verification

After meaningful package skill changes, collect evidence:

```bash
aura skills list --agent AGENT
aura skills doctor --agent AGENT
```

## Naming Note

Refer to the product/system as **Aura Hands**. The current CLI remains `aura skills` because the implemented verbs operate on skill directories specifically; future MCP/config/hook/prompt support should generalize into sibling Aura Hands surfaces rather than overloading skill terminology.
