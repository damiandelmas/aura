# Codebase Lineage Map

**Generated:** 2025-11-17
**Session:** 4a9c53da-df78-40c7-86c5-0cf144f36b47

## System Overview

**Collections:**
- **Context Docs:** 3,608 chunks (3,409 implementation, 199 patterns)
- **Conversations:** 1,357 chunks across 10 sessions
- **Phases Indexed:** design, develop, document

## Architecture Lineage

### Core Documents
```
architecture_aura.md          → Ecosystem overview
architecture_imem-i2.md       → IMEM detailed architecture
architecture_trace-i2.md      → TRACE conversation archaeology
```

### FlexGraph Evolution
```
.context/design/.modules/flex-graph/02_current/
  ├── Methodology, architecture, roadmap
  ├── .conversations/251029-1401.md → Endstate vision (graph-informed intelligence)
  └── the-brain/251029-1425.md → BRAIN architecture (separate persistence)
```

### Recent Architectural Shifts
```
251028-2151_flexgraph-composition-narrative-reconstruction.md
  → Compositional flexibility insights

251028-1234_soft-graph-consolidation.md
  → Documentation consolidation
```

## Decision Lineage (Top 15)

| Phase   | Timestamp | Decision |
|---------|-----------|----------|
| develop | 2025-10-20 | Archive Python ORCA (Don't Delete) |
| develop | 2025-10-30 | Keep search.py Despite Appearing Dead |
| develop | 2025-10-18 | Remove ORCA Output Parsing |
| develop | 2025-11-15 | Path Reconstruction Over Substring Match |
| develop | 2025-11-15 | Remove Validation Set Generator |
| develop | 2025-10-18 | Create Unified `aura` CLI Entry Point |
| develop | 2025-10-29 | Auto-Create Collections |
| develop | 2025-10-23 | Cross-project session access in claude-r |
| develop | 2025-10-20 | Replace with Error Message, Not Complete Removal |
| develop | 2025-10-20 | User-Level Hook Over Project-Level Hooks |
| develop | 2025-10-29 | Temporal Position Detection Algorithm |
| develop | 2025-10-30 | Remove All Legacy Command Groups |
| develop | 2025-10-20 | Individual YAML Files Over Monolithic |
| develop | 2025-10-20 | Add PULSE Brother to Workflow |
| develop | 2025-10-11 | Full Context Availability for Spawned Agents |

## Pattern Lineage (Top 15)

| Phase   | Timestamp | Pattern |
|---------|-----------|---------|
| develop | 2025-10-29 | Source as First-Class Concept |
| develop | 2025-10-20 | User-Level Hook with Project Detection |
| develop | 2025-10-29 | Backward Compatible Schema Evolution |
| develop | 2025-10-20 | Archive Don't Delete |
| develop | 2025-11-15 | Collection Existence Checks Before Query |
| develop | 2025-11-15 | Self-Documenting Systems via Live Introspection |
| develop | 2025-10-20 | Graceful Deprecation |
| develop | 2025-10-20 | Registry-First Architecture |
| develop | 2025-10-23 | Deprecation with Guidance Pattern |
| develop | 2025-10-20 | Microservice for Process Management |
| develop | 2025-10-20 | Brother Chaining via Output Variables |
| develop | 2025-10-20 | Graceful Deprecation |
| develop | 2025-10-29 | Progressive Collection Creation |
| develop | 2025-10-20 | Progressive Architecture Evolution |
| develop | 2025-10-29 | aiUX: Structure as Comprehension |

## Architecture Evolution

### From Monolith to Modular
```
TRACE-TALK (250920)
  From: 553-line monolithic CLI with enterprise intelligence
  To:   Clean modular architecture with separated layers
  Tools: Parallel agent spawning, Task tool, Click CLI
```

### Integration Over Microservices
```
Pulse V4 Integration (250115)
  From: Fragmented tools with duplicated state
  To:   Unified ecosystem with shared infrastructure
  Impact: 472-line script perfectly sized for integration
```

### Search Architecture
```
Local-First Global Fallback Pattern:
  1. Fast path: Search local/primary location first
  2. Fallback: Search globally if not found
  Benefits: Optimal common case + reliable edge cases
```

## Cross-Phase Discovery

**Design → Develop Trail:**
- FlexGraph design docs → Implementation in develop/
- Architecture principles → Concrete implementations
- Decision records → Pattern emergence

**Conversation → Context:**
- 10 indexed sessions
- 1,357 conversation chunks
- Linked to 6 unique sessions in context docs

## Key Architectural Insights

### Compositional Flexibility
- Multi-source routing with clean JSON output
- Granular chunking with compose routing
- Discovery primitives: siblings, genealogy, temporal, cross_phase

### Progressive Evolution
- Graceful deprecation patterns
- Backward compatible schema evolution
- Archive don't delete philosophy

### Self-Documenting Systems
- Live introspection capabilities
- Registry-first architecture
- Structure as comprehension (aiUX)

## Metadata Fields Available

### Context Docs
- `source`, `phase`, `section_type`, `section_name`
- `header_path`, `category`, `subtype`, `timestamp`
- `session_id`, `file_path`, `word_count`, `char_count`
- Boolean flags: `has_context`, `has_solution`, `has_rationale`, etc.

### Conversations
- `source`, `session_id`, `section_type`, `header_path`
- `chunk_type` (message/thinking/tools/patch)
- `role` (user/assistant)
- `start_time`, `duration_minutes`, `message_count`
- `has_changelog`, `changelog_path`

## Discovery Primitives

### Siblings
Find related sections from same document:
```bash
"siblings": {"limit": 3, "section_types": ["Decisions", "Patterns"]}
```

### Genealogy
Trace parent/child relationships:
```bash
"genealogy": {"direction": "ancestors", "limit": 5}
```

### Temporal
Find chunks before/after in git timeline:
```bash
"temporal": {"direction": "both", "limit": 3}
```

### Cross-Phase
Connect design to implementation:
```bash
"cross_phase": true
```

## Quality Hierarchy

1. **Best:** develop/design docs with `--section Decisions|Patterns|Implementation`
2. **Good:** Code patches from conversations
3. **Bad:** User messages (hit or miss)
4. **Useless:** Thinking chunks

## Next Actions

- Use `imem introspect --map` for full concept topology
- Query specific decision lineage with genealogy discovery
- Trace implementation from design with cross_phase
- Build decision/pattern taxonomy from metadata queries
