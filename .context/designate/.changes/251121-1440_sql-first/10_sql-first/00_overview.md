# SQLite-First Architecture: Overview

## Current State (BROKEN)

**Three parallel systems doing the same thing:**
1. `imem index develop` → Qdrant (vectors + metadata payload)
2. `imem index-metadata` → SQLite (metadata only)
3. No synchronization between them

**Result:** Confusion, duplication, orphaned data

**Metrics:**
- 283 markdown files in corpus
- Only 8 indexed to Qdrant (slow, requires embeddings)
- All 283 indexed to SQLite (fast, metadata-only)
- `cli.py` = 1800+ LOC (should be ~200)
- `compose.py` = hardcoded procedural pipeline (should be processor chain)

## The Vision (CORRECT)

**From `.context/designate/overview.md` lines 199-217:**

```
Git repository = source of truth
SQLite = compiled output (always)
Qdrant = vector embeddings (optional)

Parse once. Storage choice = which queries you need.
```

**SQLite enables:**
- Instant reindexing (2 sec vs 15 min)
- Schema experimentation (ALTER TABLE)
- Graph queries (recursive CTEs, JOINs)
- Pattern mining (GROUP BY, analytics)
- **THEN** selective vectorization (10% of chunks that need semantic search)

## The Unlock

Vector embeddings are **expensive** and **slow** and **inflexible**.

SQLite is **cheap** and **instant** and **queryable**.

Once you have canonical chunks in SQLite:
1. Test 10 parsing strategies in 10 minutes
2. Mine patterns with SQL (co-occurrence, temporal trends)
3. Build graph operations (decision → implementation lineage)
4. Implement manage/Temporal (git validation via JOINs)
5. Implement manage/Resolver (entity normalization via GROUP BY)
6. **Only then** vectorize high-value chunks

## What Gets Fixed

**Architecture:**
- SQLite = primary storage (metadata + content)
- Qdrant = derived index (vectors only, references SQLite IDs)
- Single source of truth

**CLI:**
- Extract 1600 LOC of business logic from `cli.py`
- Move to 5 domains: compile/ manage/ storage/ compose/ (+ cli.py router)
- `cli.py` becomes thin argument parser (~200 LOC)

**Compose:**
- Replace hardcoded pipeline with processor chain
- Config-driven stage composition
- Independent processor testing
- Backend polymorphism (SQLite/Qdrant via StorageProtocol)

## The Plan

**Phase 1:** SQLite-first indexing + COMPILE resolution (5-6 hours)
**Phase 2:** Processor chain + async patterns + multi-phase ranking (5-7 hours)
**Phase 3:** Domain separation + CLI composition root + MANAGE resolution (8-10 hours)

**Optional (P1):** HNSW backend (8 hours - replaces Qdrant with local vectors)

**New additions from 5-system review:**
- Bounded concurrency (Graphiti pattern) - prevents SQLite write contention
- Multi-phase ranking (Vespa pattern) - 25x faster graph operations

Total core: ~19 hours | With HNSW: ~27 hours
