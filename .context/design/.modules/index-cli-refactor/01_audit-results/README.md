# IMEM CLI Architecture Audit - Complete Documentation

**Audit Date:** 2025-10-29  
**Project:** /home/axp/projects/fleet/hangar/code/aura/main  
**Target:** imem/src/imem/cli.py (1167 lines)

---

## Documents in This Folder

### 1. **cli-audit.md** (669 lines) - COMPLETE DETAILED AUDIT
Start here for comprehensive analysis.

**Contains:**
- Full command structure overview with all signatures
- Every decorator (@click.group, @click.command) mapped
- All 23+ commands with locations and line numbers
- Complete metadata structures (what's stored in Qdrant)
- Phase and conversation indexing flows (with diagrams)
- Helper function inventory
- All 9 identified inconsistencies explained
- Summary table with file:line references
- Implementation roadmap with estimated hours
- Success criteria and testing checklist

**Use when:** You need complete reference or detailed understanding

---

### 2. **cli-summary.md** (308 lines) - QUICK REFERENCE
Start here for quick lookups.

**Contains:**
- Problem statement + solution overview
- Command patterns comparison table
- Key commands at a glance
- Metadata structures (Python format)
- Collection architecture (current vs target)
- Helper functions quick reference
- Phase/conversation indexing flows
- Click decorator groups
- Refactor target (new command tree)
- Files to modify
- Testing checklist
- Implementation phases

**Use when:** You need quick reference or want overview before deep dive

---

### 3. **cli-visual.txt** (352 lines) - ASCII ART REFERENCE
Start here for visual understanding.

**Contains:**
- ASCII command tree (current state)
- Visual command pattern comparison
- Formatted metadata structures with boxes
- Collection architecture diagrams
- Key indexing entry points
- Helper functions at a glance
- Top issues ranked by severity
- Refactor target (visual tree)
- Implementation roadmap
- Testing checklist

**Use when:** You prefer visual/graphical representation

---

### 4. **251029-1437.md** (426 lines) - DESIGN DECISION DOCUMENT
Context for why this refactor was designed.

**Contains:**
- Current state (what's built in FlexGraph Phase 6.5)
- The problem (inconsistent CLI + conversation indexing blocked)
- Decisions made (verb-noun CLI structure + collection architecture)
- Implementation plan (Phase 1, 2, 3)
- Architecture references (links to other docs)
- Quick start for next agent
- Success criteria for each phase

**Use when:** You need context or design rationale

---

## Key Findings Summary

### Root Problem
**Conversation indexing is completely broken** due to:
- Hardcoded `institutional_memory` collection (cli.py:879, 1011)
- Global collection (no project isolation)
- Never created with E5-Large-v2 schema
- Not tracked in registry

### Secondary Issues
1. **Three incompatible CLI patterns** (noun-verb groups + verb-first + verb-noun-hyphenated)
2. **Registry only tracks 1 collection** per project (should track 2)
3. **Duplicated search logic** (3 separate entry points)
4. **Design phase excluded by default** (no explanation)
5. **Phase filter mismatch** (CLI supports designate but doesn't index it)

---

## Commands Currently in CLI

### Search (3 entry points)
```
imem develop search <query>           [noun-verb, limited]
imem conversations search <query>     [noun-verb, limited]
imem search <query>                   [verb-first, most features]
```

### Index (4 entry points)
```
imem init                             [verb-first, phases only]
imem index-conversation <id>          [verb-noun, broken]
imem index-all-conversations          [verb-noun, broken]
imem update                           [verb-first, delegates]
```

### Other
```
imem service start|stop|status        [verb-first subgroup]
imem compose '<config>'               [verb-first, complex]
imem dedupe [--dry-run]               [verb-first]
imem status                           [verb-first]
```

---

## Refactor Target

```
imem
├─ index
│  ├─ develop [--force]
│  ├─ design [--force]
│  ├─ document [--force]
│  ├─ conversations [--limit] [--recent]
│  └─ context [--force] [--include-design]
├─ search <query> [--in develop|design|document|conversations|context]
├─ service [start|stop|status]
├─ compose '<config>'
├─ update
├─ dedupe
└─ status
```

**Benefits:**
- Consistent verb-noun everywhere
- Discoverable: `imem index` lists all phases
- Per-project collections (separate changelog + conversation)
- Intuitive English word order

---

## Files to Modify

### Primary: imem/src/imem/cli.py (1167 lines)
- Extract `_index_phase()` helper
- Refactor to verb-noun pattern
- Fix collection naming (add _changelog suffix)
- Merge noun-verb groups into verb commands
- Remove old index-conversation, index-all-conversations

### Secondary: imem/src/imem/registry.py (75 lines)
- Track multiple collections per project
- Support backward compatibility

### Minor: imem/src/imem/ingest.py (1076 lines)
- No changes (already flexible)

---

## Implementation Plan

### Phase 1: Foundation (2-3 hours)
1. Extract `_index_phase()` helper (~30 min)
2. Refactor CLI to verb-noun (~1 hour)
3. Fix collection architecture (~30 min)
4. Test conversation indexing (~30 min)

### Phase 2: Graph Intelligence (3-4 hours, NEXT SESSION)
1. Build graph from chunks (topology detection)
2. Enrich metadata (position, confidence)
3. Adapt templates by topology

### Phase 3: BRAIN Persistence (MONTHS LATER)
Requires 3-6 months usage data first

---

## How to Use These Documents

### Quick orientation (5 minutes)
1. Read this README
2. Skim **cli-summary.md** "Problem Statement" section

### Understand the problem (15 minutes)
1. Read **cli-visual.txt** sections 1-4
2. Look at command tree
3. Review "Top Issues" section

### Deep dive for implementation (30+ minutes)
1. Read **cli-audit.md** in full
2. Reference **cli-summary.md** tables while coding
3. Keep **cli-visual.txt** open for quick lookups

### Decision context (10 minutes)
1. Read **251029-1437.md** "The Problem" section
2. Review "Decisions Made" section
3. Read "Implementation Plan" for rationale

---

## Key Insights

> "The current CLI has three incompatible patterns at root level:
> noun-verb groups, verb-first, and verb-noun-hyphenated.
> This blocks intuitive discoverability and makes extension painful.
>
> Verb-noun throughout fixes this + enables per-project conversation
> isolation. Graph reveals how chunks relate → how to serve them →
> structure aids AI comprehension."

---

## Navigation Across Documents

**To find X, check:**

| Looking for | Document | Section |
|---|---|---|
| All commands | cli-audit.md | Section 3 |
| Specific command signature | cli-audit.md | Section 3 |
| Line numbers | cli-audit.md | Section 11 |
| Quick command list | cli-summary.md | "Key Commands at a Glance" |
| Metadata structure | cli-audit.md | Section 3 OR cli-summary.md | "Metadata & Filtering" |
| Collection architecture | cli-audit.md | Section 4 OR cli-visual.txt | Section 4 |
| Helper functions | cli-audit.md | Section 7 OR cli-summary.md | "Helper Functions" |
| Issues ranked | cli-visual.txt | Section 7 |
| Refactor design | 251029-1437.md | "Decisions Made" |
| Implementation steps | cli-audit.md | Section 13 OR 251029-1437.md | "Implementation Plan" |

---

## Next Steps

1. **Orientation:** Read this README and skim cli-summary.md
2. **Analysis:** Review cli-visual.txt command tree
3. **Deep Dive:** Read cli-audit.md sections 1-4
4. **Decision Context:** Skim 251029-1437.md for rationale
5. **Implementation:** Use cli-summary.md + cli-visual.txt as reference while coding
6. **Testing:** Follow checklist in cli-audit.md Section 12

---

## Quick Stats

- **Total lines analyzed:** 1,167 (cli.py) + 1,076 (ingest.py) + 75 (registry.py) = 2,318
- **Total commands found:** 23+ (including groups)
- **Inconsistencies identified:** 9
- **Files to modify:** 2 (cli.py primary, registry.py secondary)
- **Estimated effort Phase 1:** 2-3 hours
- **Documentation generated:** 1,329 lines across 3 audit docs

---

## References

**Design:** 251029-1437.md (full design decision doc)  
**Architecture:** /home/axp/projects/fleet/hangar/code/aura/main/.context/document/architecture_imem-i2.md  
**FlexGraph:** /home/axp/projects/fleet/hangar/code/aura/main/.context/design/.modules/flex-graph/02_current/

---

Generated: 2025-10-29  
Project: /home/axp/projects/fleet/hangar/code/aura/main
