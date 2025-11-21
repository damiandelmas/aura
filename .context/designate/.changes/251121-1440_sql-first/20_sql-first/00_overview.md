# SQLite-First Architecture: Overview

## Current State (Phase 1-3 Complete)

**Shipped (Phases 1-3):**
- ✅ SQLite-first storage with VectorStore abstraction
- ✅ Processor chain pattern for declarative retrieval
- ✅ Domain separation (cli/, compile/, manage/, compose/)
- ✅ Two-layer resolution (structural + entity normalization)
- ✅ CLI composition root (shared resources, 72% LOC reduction)

**Production Metrics:**
- 40 chunks indexed (5 markdown files from .context/develop)
- SQLite metadata queries: <10ms (vs 15min Qdrant upload)
- CLI: 1772 LOC → 501 LOC (cli_new.py + cli/main.py + cli/commands.py)
- All Phase 3 smoke tests passing

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

## What's Missing (Gap Analysis)

**Phase 4: Complete Core Architecture (~4h)**
1. Split VectorStore → VectorSearch + GraphStore (1h)
2. Extract Qdrant to vector-only role (30min)
3. Implement Discovery processors (2h)
4. Add relationships table schema (30min)

**Phase 5: Semantic Layer (~3h)**
1. Build manage/analyzer.py for semantic detection (2h)
2. Add `imem analyze` command (30min)
3. Implement get_implementations() (30min)

**Phase 6: Git Integration (~3h)**
1. Parse git commits → chunks (1h)
2. Temporal validation (manage/temporal.py) (2h)

**Completed:** ~19 hours (Phases 1-3)
**Remaining:** ~10 hours (Phases 4-6) to complete original vision
