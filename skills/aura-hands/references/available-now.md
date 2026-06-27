# Aura Hands Reference: What Works Now

This reference describes the **manual operating surface** that exists before Aura Hands has a complete `aura hands` CLI. It is not the product spec and not a promise that every workflow is automated. It is a practical bridge: use agents, `aura skills`, Printing Press cells, SQLite queries, and careful file edits to get useful Aura Hands outcomes today.

## Purpose

Aura Hands is about managing an agent runtime's useful capability surface as data. For Codex, that surface includes skills, agents, hooks, config, rules, prompts, support scripts, and eventually MCP settings. The current implementation only automates package-local skills, but the Printing Press cell proves we can inventory and reason over the wider `.codex` surface now.

## When to Use This Reference

Use this when the user asks what Aura Hands can already do, wants to inspect or compare `.codex` homes, wants a migration plan before automation exists, or wants a safe hand-rolled operation. Load this file for functional guidance, then use the current repo, sandbox, or cell artifacts as evidence. If a task touches hooks, MCP, or runtime config, produce a plan and risk boundary before changing files.

## Operating Rule

Follow this sequence for every manual Aura Hands operation:

```text
scan/source evidence
→ classify capability surfaces
→ plan the desired state
→ dry-run or show diff
→ backup before mutation
→ apply only low-risk changes
→ rebuild/re-query
→ emit receipt
```

Do not skip verification. A change is not complete until the resulting skill inventory, control cell, or filesystem state proves the target state exists.

## Inputs

Common inputs are a `.codex` root, an Aura agent package, an existing Printing Press cell, or a canonical skill/library root. Useful paths include:

```text
/home/axp/.codex
/home/axp/.aura/agents/i_<id>/.codex
/home/axp/.codex/skills
/home/axp/projects/aura/sandbox/transient/2026-05-22-1856-pp-binary/
```

## Outputs

A successful manual workflow should produce one or more concrete artifacts: an inventory report, a SQLite cell, a diff report, a mutation plan, a backup path, a library manifest draft, or a verification receipt. Prefer files over chat-only conclusions when the output may be reused by another agent. Always include enough paths and commands for replay.

## Functional Workflows

### Build a Codex Control Cell

Run the Printing Press-backed builder against a `.codex` root to produce a source-pack, projection JSON, SQLite/FTS cell, validation report, and receipt. This turns a runtime config folder into a queryable control surface. Use this before broad reasoning about skills, hooks, config, rules, prompts, or agents.

### Query a Capability Surface

Open the generated SQLite cell and answer focused questions from `files`, `surfaces`, `chunks`, and FTS tables. Good questions include which skills exist, which hooks are installed, which files define model behavior, and which support files belong to a skill. Cite the cell path, table, and surface kind used.

### Diff Two Codex Homes

Build one cell per `.codex` root, then compare `files` and `surfaces` by path, kind, name, hash, and payload. This gives a hand-rolled version of future `aura hands diff --cell A --cell B`. Use it to find missing capabilities, divergent skill copies, hook/config drift, or prompt/rule mismatches.

### Generate a Mutation Plan

Use the inventory or cell to write a dry-run plan for adding, removing, or updating a skill, prompt, rule, hook, agent profile, or config entry. The plan must include target files, expected diff, risk class, backup path, validation command, and rollback path. Hooks, MCP settings, and global config should normally stop at the plan stage unless the user explicitly asks for implementation.

### Apply Low-Risk Changes

Prompts, rules, agent TOMLs, and symlinked skills can usually be changed manually with backups and verification. Make one small change at a time, preserve the old file or symlink target, then rebuild the cell or rerun `aura skills inventory` / `aura skills doctor`. Avoid bundling many behavior-changing edits into one unreviewable operation.

### Draft a Capability Library

Read an existing `.codex` root or package and draft a reusable manifest such as `capabilities.lock.json`. The draft should identify source paths, projection mode, target runtime surface, ownership assumptions, and validation checks. Mark it as a draft until canonical sources and rollout policy are chosen.

### Normalize Skill Duplicates

Use `aura skills duplicates`, `aura skills diff NAME`, and existing inventory artifacts to identify canonical skill copies. Produce a cleanup plan first; do not delete divergent copies just because names match. Treat archives, raw transcripts, and sandbox evidence as historical unless the task explicitly includes archive cleanup.

### Spawn Workers Per Root

Use Aura to spawn one worker per `.codex` root or agent package when a fleet-wide map is needed. Each worker should build or inspect in its own sandbox and return a receipt path. This manually approximates future parallel `aura hands cell build --fleet ...` behavior.

## Risk Classes

- **Low risk:** read-only inventory, SQLite queries, duplicate reports, manifest drafts, symlink inspection.
- **Medium risk:** prompt/rule edits, agent profile edits, package-local skill symlink/copy changes with backup.
- **High risk:** hooks, MCP servers, global runtime config, environment-affecting scripts, anything that changes command execution.

High-risk work should normally produce a plan and stop unless the user has clearly requested implementation.

## Verification Checklist

Before reporting completion, verify at least one concrete claim with fresh evidence:

```bash
aura skills inventory
aura skills duplicates
aura skills diff NAME
aura skills doctor --agent AGENT
sqlite3 path/to/codex-config-cell.sqlite '.tables'
```

For cell-based workflows, confirm the validation report passes and the cell contains populated `files` and `surfaces` tables. For mutation workflows, show the backup path, the changed path, and the post-change inventory/cell evidence.
