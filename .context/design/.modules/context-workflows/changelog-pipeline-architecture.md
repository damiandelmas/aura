# Changelog Pipeline Architecture

## Overview

Built a 5-stage agentic pipeline that converts session chronicles into dual-layer changelogs: v3 (project-specific) + conceptual (language-agnostic).

## Architecture

```
/log:develop:workflow
    ↓
OrchestratorAgent (spawned via async.sh)
    ↓
[a] a_capture (sonnet)              → Create changelog from template
[b] b_metadata-and-rename (haiku)   → Clean frontmatter, rename file
[c] c_content-converter-v3 (haiku)  → Convert to v3 structure
[d] d_quality-assurance (haiku)     → Validate compliance
[e] e_conceptual-layer-mirror (haiku) → Create language-agnostic mirror
    ↓
Output: v3.md + conceptual.md
```

## The Prism Concept

**Dual-layer changelogs** enable cross-project learning without code pollution:

- **v3 layer:** Project-specific, actual code, framework names
- **Conceptual layer:** Language-agnostic, pseudocode, pure patterns

Query conceptual layers across ALL projects to find patterns without seeing implementation code from other languages/stacks.

## Key Files

### Commands
- `/home/axp/.claude/commands/log/develop/workflow.md` - Triggers full pipeline

### Agents
- `a_capture.md` - Reads chronicle + template, creates initial changelog (sonnet)
- `b_metadata-and-rename.md` - Cleans metadata, proper filename (haiku)
- `c_content-converter-v3.md` - Converts to v3 structure (haiku)
- `d_quality-assurance.md` - Validates v3 compliance (haiku)
- `e_conceptual-layer-mirror.md` - Creates language-agnostic mirror (haiku)

### Templates
- `/home/axp/projects/fleet/hangar/code/aura/main/assets/changelogs/develop/template/00_TEMPLATE.md` - v3 structure
- `/home/axp/projects/fleet/hangar/code/aura/main/assets/changelogs/develop/template/01_FIELD_GUIDE.md` - Field variations
- `/home/axp/projects/fleet/hangar/code/aura/main/assets/changelogs/develop/template/02_EXAMPLE_SPECTRUM.md` - Real examples

## What's Built

✅ All 5 agents created and configured
✅ Pipeline command `/log:develop:workflow` created
✅ Proof of concept: Created first conceptual layer manually
✅ Agent [e] removes all language specifics via ~20% edits

## What's Next

### 1. Test the Pipeline
Run `/log:develop:workflow` on a real session to validate orchestration

### 2. Refine Orchestrator Prompt
May need to adjust how agents are invoked via Task tool

### 3. Batch Convert Existing Changelogs
Run existing changelogs through stages [b][c][d][e] to create conceptual layers

### 4. Build SQL/Vector Index
Index conceptual layers separately for cross-project pattern queries

## Usage

```bash
# Full pipeline (creates v3 + conceptual)
/log:develop:workflow

# Current simple version (creates v3 only)
/log:develop
```

## The Innovation

**Pattern mining across tech stacks** - Every changelog becomes queryable in two forms:
1. Detailed implementation (for working in project)
2. Abstract pattern (for learning across projects)

A Python project can learn from Bash discoveries without seeing Bash code.
