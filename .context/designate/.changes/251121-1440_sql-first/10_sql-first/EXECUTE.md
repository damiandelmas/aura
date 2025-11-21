# Execute: SQLite-First Architecture Refactor

## Mission

Refactor IMEM from broken dual-storage (Qdrant + SQLite competing) to coherent SQLite-first architecture with optional Qdrant enhancement.

## Current State

- 3 parallel systems: `imem index` → Qdrant, `imem index-metadata` → SQLite, no sync
- 283 files in corpus, only 8 indexed to Qdrant (slow), all 283 in SQLite (fast)
- `cli.py` = 1800 LOC (should be 200)
- Hardcoded pipeline in `compose.py` (should be processor chain)

## Target State

- SQLite = primary (metadata + content, always)
- Qdrant = derived (vectors + ID reference, optional via `--vectorize`)
- Two-layer resolution: COMPILE (structure) + MANAGE (entities)
- Processor chain architecture (declarative, testable)
- Domain separation: compile/ manage/ storage/ compose/ + thin CLI
- CLI composition root (shared DB/embedder initialization)

## Implementation Plan

**Read these documents in order:**

1. **00_overview.md** - Current broken state, vision, what gets fixed
2. **01_architecture.md** - Target domain structure, storage topology, resolution layers, processor chains
3. **02_plan.md** - 3-phase implementation (19 hours total):
   - Phase 1: SQLite-first + COMPILE resolution (5-6h)
   - Phase 2: Processor chain + async patterns + ranking (5-7h)
   - Phase 3: Domain separation + CLI composition root + MANAGE resolution (8-10h)
4. **03_optional_enhancements.md** - HNSW backend, entity consolidation patterns (do after core)
5. **04_patterns_applied.md** - What patterns added from 5-system review, what avoided, why

## Key Architectural Decisions

**Resolution (Two Layers):**
- COMPILE: Structure normalization at parse time (phase variations → canonical 4-phase, header variations → section types)
- MANAGE: Entity normalization at query time (project-scoped, "jwt"/"JWT" → canonical)

**Processor Chain:**
- Declarative composition via `Chain([SearchProcessor(), SiblingDiscovery(), FilterProcessor()])`
- Backend polymorphism via `StorageProtocol`
- Bounded concurrency via `semaphore_gather()` (Graphiti pattern)
- Multi-phase ranking (Vespa pattern): 1000s → 100s → 20s → 10 final

**Storage:**
- SQLite stores canonical phase/section_type (resolved at parse), raw content (for entity expansion at query)
- Qdrant stores vectors + minimal payload (chunk_id reference to SQLite)

## Success Criteria

- ✅ `imem index` populates SQLite (always), Qdrant optional with `--vectorize`
- ✅ Discovery primitives work on all 283 files (not just 8)
- ✅ `cli.py` < 250 LOC (logic in domains)
- ✅ Reindex 283 files in <10 seconds (was 15 min)
- ✅ Processor chain testable independently
- ✅ Backward compatible (same CLI commands)

## Start Here

Implement **Phase 1** first (02_plan.md lines 3-154). Ask questions if architecture unclear.
