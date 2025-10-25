---
type: "design"
timestamp: "2025-10-11T04:00:00-0700"
---

# Multi-Dimensional Conversation Manager (AUI)

## Question
> "Can we vectorize a SQLite database where 3 agents write to the same file with different verbosity levels? Or should we have parallel agents create different dimensions of the same changelog?"

**Evolved into:** Design system for ONE conversation thread enabling PARALLEL design work (schemas, business logic, architecture) with real-time validation, all sharing the same ground truth conversation.

## Key Insights

### 1. Three Distinct Phases (Taxonomy)
- **DESIGN**: R&D, ideation, spec creation → `.context/design/`
- **DEVELOP**: Actual coding, git commits → `.context/develop/`
- **DOCUMENT**: Maintained codebase state → `.context/document/`

**Critical:** AUI operates in DESIGN phase. PULSE/PRUNE operate in DEVELOP→DOCUMENT phase.

### 2. Conversation as Ground Truth
- ONE JSONL thread = source of truth
- Multiple watchers (floating UI, validation brothers) tail same JSONL
- `--resume SESSION_ID` = instant context inheritance
- Brothers spawn via subprocess, inherit ALL context

### 3. Spec = Codebase for AI
In AI development, complete spec (schemas + business logic + architecture) IS the codebase. With perfect specs, AI agents can reliably implement. **Goal: Create complete codebase spec in ONE conversation.**

### 4. Validation Gates
Schema Brother, Business Logic Brother, Architecture Brother = validation gates preventing noise from polluting ground truth documents. User confirms all changes.

## Explored Ideas

### SQLite Multi-Verbosity (Changelog Context)
**Original question:** 3 brothers write different verbosity levels (concise/standard/detailed) to same SQLite .db file.

**Outcome:** Valid for DEVELOP changelogs (post-conversation extraction). NOT the focus for AUI (DESIGN phase, real-time).

### Post-Conversation vs Real-Time Extraction
**Post-conversation (DEVELOP):**
- User types `/log:develop`
- Spawn 6 brothers (changelog verbosity, vision, schema, business logic, architecture, constraints)
- All write to `.context/develop/.changes/bookmark.db`
- PULSE aggregates across conversations

**Real-time (DESIGN - what we're building):**
- Floating UI watches active JSONL
- Extracts dimensions as we talk
- Validation brothers confirm before writing
- Writes to `.context/design/modules/{project}/`

### --resume Behavior (Critical Research)
**Findings:**
- Normal `--resume`: Reads existing JSONL, appends to same file, same session ID
- SDK `forkSession: true`: Creates NEW JSONL, NEW session ID (clean branches)
- JSONL editing: NOT officially supported (risky, undefined behavior)
- File location: `~/.claude/projects/[ENCODED-PATH]/[UUID].jsonl`

**Implication:** Use `--resume` for context inheritance, SDK forking for drill-down branches.

### One .db vs Multiple Files
**Decision:** NOT one .db per conversation. Design is per-module/project:
- `.context/design/modules/llm-pipeline/schemas/`
- `.context/design/modules/payment-system/business-logic/`

Modular structure, not conversation-centric for design outputs.

## Architecture Design

### System Shape

```
Main Conversation (ONE JSONL thread)
    ↓ Real-time tail -f
Floating UI (AUI)
    ├─ Watches JSONL stream
    ├─ Extracts dimensions (schema, logic, arch)
    ├─ Prompts user validation
    └─ Spawns brothers on-demand
        │
        ▼
Validation Brothers (Persistent Watchers)
    ├─ Schema Brother (--resume MAIN_SESSION)
    │   └─ Validates all schema changes
    ├─ Business Logic Brother
    │   └─ Validates all workflow rules
    └─ Architecture Brother
        └─ Validates all design decisions
            │
            ▼
Output: .context/design/modules/{project}/
    ├── schemas/Payment.schema.json
    ├── business-logic/payment-flow.md
    └── architecture/event-driven.md
```

### Core Features

**1. Main Thread Maintenance**
- User + AI discuss R&D freely
- Floating UI extracts structured info
- Can splice/edit JSONL (risky but needed for long conversations)
- Brothers reference cleaned documents, not raw JSONL noise

**2. Deep Dive Forks**
- User clicks "Schema Deep Dive" in UI
- Spawns new pane with Schema Brother
- Brother inherits via `--resume MAIN_SESSION`
- 15 messages to perfect schema
- Writes to `.context/design/.../schema.json`
- Main conversation references completed file

**3. Validation Gates**
- Schema changes ONLY happen via Schema Brother
- Brother watches main conversation
- Notification: "Main convo mentioned Payment.declined. Add?" [y/n]
- User confirms before schema mutation

**4. Cross-Conversation (Future)**
- 5 conversations about payment system this week
- All feed same `.context/design/modules/payment-system/`
- Aggregation/deduplication (semantic similarity? LLM-based?)

## Outcomes

### Immediate Decision: What to Build
**Three options presented:**

**A.** Floating UI watcher (real-time JSONL tail -f)
**B.** Validation brothers (subprocess spawning via --resume)
**C.** Complete NPTA inventory system first (stay focused)

**User triggered /log:design before answering** - capturing design conversation before implementation choice.

### Technical Feasibility
**Validated:**
- ✅ `--resume` reads entire JSONL (instant context inheritance)
- ✅ Concurrent brother spawning (ConcurrentWorkflow)
- ✅ SQLite WAL for concurrent writes (if needed for DEVELOP phase)
- ✅ JSONL structure parseable in real-time

**Needs Experimentation:**
- ⚠️ JSONL editing safety (truncate from END probably safe)
- ⚠️ Cross-conversation deduplication strategy
- ⚠️ Floating UI framework choice

### Design Principles Established

1. **Conversations are ephemeral inputs, documents are persistent Omega**
2. **DESIGN phase creates specs, DEVELOP phase creates code**
3. **Validation gates prevent inference noise from corrupting ground truth**
4. **One conversation CAN create complete codebase spec (via parallel extraction)**
5. **Brothers inherit context instantly (no onboarding needed)**

## References

### Related Design Docs
- AURA System Architecture: `/home/axp/projects/aura-retrieval-qdrant/aura/projects/imem-suite/main/.context/design/modules/complete-system/04_document-package/E_01_SYSTEM_ARCHITECTURE.md`
- Agent Protocols: `E_02_AGENT_PROTOCOLS.md`
- Section Chunking Strategy: `/home/axp/projects/aura-retrieval-qdrant/aura/projects/imem-suite/main/assets/changelogs/.context/.document/section-chunking-strategy.md`

### Claude Code Research
- `--resume` behavior validated via docs + GitHub issues + local file inspection
- Session forking via SDK (`forkSession: true`)
- JSONL location: `~/.claude/projects/[ENCODED-PATH]/[SESSION-UUID].jsonl`

### Parallel Work
- NPTA inventory system (provider abstraction for ACE, ISSA, multi-provider support)
- Hybrid architecture complete (Days 1-2 done)
- User working on both systems concurrently

---

## Next Steps (Unresolved)

**User needs to decide:**
1. Build AUI floating UI watcher (DESIGN system)
2. Build validation brothers (subprocess orchestration)
3. Complete NPTA inventory first, defer AUI

**For AUI (if proceeding):**
- Define floating UI framework (Electron? Web-based? Terminal TUI?)
- Prototype JSONL tail -f watcher
- Build Schema Brother validation gate
- Test --resume context inheritance with real brothers
- Validate JSONL editing strategy (safe splice points)

**For NPTA (if proceeding):**
- Complete provider abstraction (already in progress, see file modifications)
- Load provider configs (ACE, ISSA JSON files)
- Test multi-provider key assignment
- Phase 2: CSV key importer
