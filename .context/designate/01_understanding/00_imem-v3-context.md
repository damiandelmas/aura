# IMEM v3: Context for Future Sessions

**For:** Claude agents resuming this project
**Assumes:** You understand RAG, compilers, software architecture
**Purpose:** Prevent scope creep, vocabulary confusion, and overengineering

---

## What IMEM Is

**Knowledge compiler for AI agent memories.**

- **Input:** Agent coding workflows (`.context/` markdown, conversations, git metadata)
- **Compile:** Resolve unstructured agent output → structured knowledge (design/designate/develop/document phases)
- **Store:** Metadata-rich chunks in SQLite (+ optional vector embeddings)
- **Retrieve:** Query compiled knowledge via metadata filters, relationships, semantic search

**Not (yet):** General knowledge compiler for human documentation (that's i4 wrapper, future iteration)

---

## Critical Distinctions (Read This First)

### IMEM vs i4 Knowledge Compiler

**IMEM (now):** Foundation for agent memory compilation
- Scope: Agent workflows → phase-structured knowledge
- Output: Queryable chunks with metadata

**i4 Compiler (future):** Wraps IMEM for broader knowledge
- Scope: Any documentation → multi-tier knowledge graph
- Output: ATOMIC/RELATIONAL/SEMANTIC tiers

**Do NOT conflate these.** Building IMEM foundation ≠ building full i4 system.

### "Compile" Has Multiple Meanings

**COMPILE domain (IMEM):** Structural normalization
- Parse markdown → extract chunks
- Resolve phase variations (`planning` → `design`)
- Resolve section types (`Decisions` → `Decision`)
- Store with normalized metadata

**Compilation (i4):** Multi-stage knowledge transformation
- Tier 1: Atomic extraction
- Tier 2: Relational linking
- Tier 3: Semantic enrichment

**Context matters.** When we say "compile" in IMEM, we mean domain 1.

### Metadata vs Knowledge Graph

**Metadata (now):** Structural attributes on chunks
- `phase`, `section_type`, `file_path`, `timestamp`
- Stored as columns in SQLite
- Used for filtering/grouping

**Knowledge Graph (phase 2):** Explicit relationships between chunks
- `relationships` table: `(source_id, target_id, relationship_type)`
- Types: `spatial_proximity`, `conversation_continues`, `decision_implements`
- Used for discovery/traversal

**Don't mix:** Metadata = chunk properties. Relationships = graph edges.

---

## Current State (Post-Phase 3)

### What Works (70% Complete)

**Storage:**
- ✅ VectorStore protocol (abstraction)
- ✅ SQLiteVectorStore (metadata-only backend)
- ✅ QdrantVectorStore (semantic search backend)
- ✅ Factory pattern (`create_store(backend, **kwargs)`)

**Compile:**
- ✅ MarkdownParser (frontmatter + sections)
- ✅ CompileResolver (phase/section normalization, 50+ variations)
- ✅ DocumentIndexer (orchestrates parsing → resolution → storage)

**Retrieve/Compose:**
- ✅ Processor chain abstraction (`Chain`, `Processor` protocol)
- ✅ SearchProcessor (metadata/semantic modes)
- ✅ MultiPhaseRanker (progressive refinement)
- ✅ Orchestrator (config-driven pipeline builder)

**Manage:**
- ✅ EntityResolver (infrastructure exists, not populated yet)
- ✅ Introspection functions (corpus stats)

**CLI:**
- ✅ Composition root (IMEMCLI class, shared DB/embedder)
- ✅ 9 commands functional
- ✅ 506 LOC (down from 1772, 72% reduction)

### What's Broken/Incomplete

**Legacy Confusion:**
- ⚠️ `compile/indexer.py:89` calls `EnhancedModularIngest()` (hardcoded Qdrant)
- ⚠️ Two indexing paths: `index` (legacy) vs `index-metadata` (new, SQLite-only)
- ⚠️ Legacy code still active: `ingest.py` (738 LOC), `search.py` (587 LOC), `enhanced.py` (445 LOC)

**Not Wired:**
- ❌ Discovery processors exist (`primitives/discovery.py` - 343 LOC) but not integrated into orchestrator
- ❌ Relationship schema doesn't exist (metadata only, no explicit graph)
- ❌ HNSW backend not implemented (only Qdrant for vectors)

**Vocabulary Confusion:**
- ⚠️ "Siblings" used to mean "chunks in same document" (should be `spatial_proximity` relationship)
- ⚠️ CLI exposes implementation (`--metadata` flag) instead of intent (`--mode` flag)

---

## Architecture Vision (Where We're Going)

### Domain Structure

```
compile/          - Structural normalization
├── indexer.py    - Orchestrates parse → resolve → store
├── resolver.py   - Phase/section normalization (COMPILE resolution)
└── relationship_builder.py  - Detect relationships from metadata

manage/           - Entity/concept normalization
├── resolver.py   - Entity normalization (MANAGE resolution)
└── introspect.py - Corpus analysis

storage/          - Backend abstraction
├── protocol.py   - VectorStore interface
├── factory.py    - Backend selection
├── sqlite_backend.py     - Metadata + optional HNSW
├── qdrant_backend.py     - External vector service
└── relationships.py      - Graph schema

retrieve/compose/ - Query pipeline
├── orchestrator.py       - Config-driven chain builder
└── processors/
    ├── search.py         - Metadata/semantic search
    ├── ranking.py        - Multi-phase ranking
    └── discovery.py      - Graph traversal

cli/              - User interface
├── main.py       - Composition root (IMEMCLI)
└── commands.py   - Command definitions
```

### Clean Entry Points (Goal)

**Indexing:**
```bash
imem index <phase> --backend sqlite|qdrant|hnsw --limit N
```
- Single command, backend-agnostic
- DocumentIndexer uses factory (not hardcoded Qdrant)
- Builds relationships during indexing

**Querying:**
```bash
imem compose '{
  "search": {"mode": "metadata", "filters": {...}},
  "discovery": {"relationships": ["spatial_proximity"]},
  "ranking": {"phases": [{"name": "recency"}]}
}'
```
- Config-driven (not hardcoded paths)
- Uses explicit relationship graph
- Backend determines if vectors available

---

## Common Pitfalls (For Future You)

### 1. Scope Creep: "Let's Build Everything"

**Symptom:** Reading architecture docs → assuming all features must be built now

**Example:** Seeing `metadata_tiers.md` (3-tier enrichment) → wanting to implement Tier 1/2/3 before shipping basic retrieval

**Correction:** IMEM foundation (metadata + relationships + retrieval) ≠ full i4 system. Build foundation first.

### 2. Premature Unification: "Let's Fix All The Things"

**Symptom:** Finding legacy confusion → proposing 13-hour refactor touching 5 domains

**Example:** "We need to extract Qdrant, build relationships schema, unify indexing, rewrite discovery, and add HNSW" (all at once)

**Correction:** **Isolate first, then build incrementally.** Move Qdrant to `legacy/v2/`, THEN see what's actually broken, THEN fix one vertical slice.

### 3. Vocabulary Drift: "Siblings = Related Chunks"

**Symptom:** Using v2 terminology without questioning the abstraction

**Example:** "Siblings" = chunks in same document. But that's just spatial proximity, not a sibling relationship in knowledge graph terms.

**Correction:** Use precise relationship types: `spatial_proximity`, `conversation_continues`, `decision_implements`. Words matter for architecture clarity.

### 4. Over-Abstraction: "We Need a Framework"

**Symptom:** Seeing pattern → building abstraction before proving need

**Example:** "Let's create a DiscoveryProcessor base class with plugin system" before shipping ONE working discovery type

**Correction:** **Walking skeleton first.** Build spatial proximity discovery end-to-end (stub → schema → query → test). Then abstract when adding second type.

### 5. Mixing Concerns: "Indexing Should Also Discover Relationships And Rank And..."

**Symptom:** Adding multiple responsibilities to single component

**Example:** DocumentIndexer doing parsing AND resolution AND relationship building AND embedding AND validation

**Correction:** **Single responsibility.** DocumentIndexer = orchestrate (delegate to Parser, Resolver, RelationshipBuilder, Store). Each does one thing.

---

## Decision Rationale (Why We Did Things)

### Why SQL-First?

**v2 Problem:** Qdrant-first meant metadata was second-class
- Filtering = vector search with metadata post-filter (slow, limited)
- No rich querying (can't JOIN, GROUP BY, aggregate)
- Relationships implicit from vector similarity (not explicit)

**v3 Solution:** SQLite primary, vectors optional
- Metadata filtering = SQL WHERE clauses (fast, expressive)
- Relationships = explicit table with JOINs (queryable graph)
- Vectors = modality that can be added/removed (not required)

### Why Processor Chain?

**v2 Problem:** Hardcoded retrieval pipeline
- Search → rank → filter → return (fixed sequence)
- No experimentation with different ranking strategies
- No A/B testing of discovery approaches

**v3 Solution:** Declarative config-driven chain
- Build pipeline from config: `[SearchProcessor, DiscoveryProcessor, MultiPhaseRanker]`
- Swap components without code changes
- Test different compositions easily

### Why Domain Separation?

**v2 Problem:** 1772 LOC CLI with everything mixed
- Commands had business logic
- No separation of concerns
- Hard to test, hard to reuse

**v3 Solution:** 4 domains + thin CLI (506 LOC)
- `compile/` = structural normalization (reusable)
- `manage/` = entity normalization (reusable)
- `storage/` = backend abstraction (swappable)
- `retrieve/compose/` = query orchestration (configurable)
- `cli/` = thin wrapper (just routing)

### Why Composition Root?

**v2 Problem:** Every command initialized DB/embedder separately
- 2-3s overhead per command (loading embedder)
- Pragmas applied multiple times
- No shared connection pool

**v3 Solution:** IMEMCLI class with lazy initialization
- Load embedder once, reuse across commands
- Single DB connection with pragmas
- Shared state management

---

## Next Steps (Immediate)

### Phase 1: Isolate Qdrant (4h)

**Goal:** Quarantine legacy without touching working code

**Actions:**
1. Move to `legacy/v2/`:
   - `ingest.py`, `search.py`, `enhanced.py`, `qdrant_service.py`

2. Document `legacy/v2/README.md`:
   - What v2 did (feature list)
   - Why isolated (Qdrant-hardcoded)
   - Use as spec, not code

3. Fix `compile/indexer.py:89`:
   - Remove `EnhancedModularIngest()` call
   - Add TODO: "Use DocumentIndexer with factory"
   - Mark `index` command as temporarily broken

4. Keep working path:
   - `index-metadata` still works (SQLite path)
   - Other commands unaffected

**Deliverable:** Clear boundary between legacy and new architecture

### After Isolation: Walking Skeletons

**Phase 2:** Inventory what works/broken (2h, documentation only)

**Phase 3:** Stub out component interfaces (4h, no implementation)

**Phase 4:** Build ONE relationship type end-to-end (6h)
- Pick simplest: `spatial_proximity` (chunks in same document)
- Schema → detection → storage → discovery → test
- Prove clean architecture works

**Phase 5+:** Add remaining components one by one
- HNSW backend
- Temporal relationships
- Unified indexing path
- Discovery processors

---

## Red Flags (Stop If You See These)

1. **"Let's refactor everything first"**
   - Isolate, don't refactor
   - Build new alongside old
   - Strangler pattern, not rewrite

2. **"This 13-hour plan touches 5 domains"**
   - Too much at once
   - Break into vertical slices
   - One domain + one feature = one phase

3. **"I'm implementing features from i4/metadata_tiers/knowledge_compiler docs"**
   - Wrong scope
   - IMEM foundation ≠ full i4 system
   - Check if it's needed for agent memory compilation

4. **"I need to build the abstraction before the concrete implementation"**
   - Backwards
   - Build ONE concrete example
   - Abstract when adding second

5. **"The user said 'siblings' so I'll use that terminology"**
   - Question vocabulary
   - Use precise relationship types
   - Align with graph/SQL semantics

---

## Key Phrases (Trigger Understanding)

**When user says:** "We need to clean up the refactor"
**They mean:** Legacy is tangled with new, isolate first

**When user says:** "Don't mix concerns"
**They mean:** You're trying to do too much in one phase, break it down

**When user says:** "We're building towards i4"
**They mean:** IMEM is foundation, not the full vision yet

**When user says:** "Walking skeleton"
**They mean:** One vertical slice working cleanly, then iterate

**When user says:** "We're SQL-first now"
**They mean:** Relationships are explicit (table + JOINs), not inferred from vectors

---

## Success Criteria

**You understand the context when you can:**
- Distinguish IMEM (agent memory compiler) from i4 (general knowledge compiler)
- Explain why we're isolating Qdrant before refactoring
- Identify when a proposal mixes too many concerns
- Describe the relationship model (explicit graph, not metadata inference)
- Propose incremental changes (one vertical slice at a time)

**You're ready to code when you:**
- Know which domain a change belongs to
- Can explain why we're NOT doing something yet
- Resist the urge to "fix everything" before validating one thing works
- Use precise vocabulary (spatial_proximity vs siblings)

---

## Questions to Ask (If Uncertain)

1. "Is this feature part of IMEM foundation or i4 wrapper?"
2. "Can I prove this works with ONE example before abstracting?"
3. "Am I touching multiple domains in this phase?" (red flag)
4. "Does this change require breaking working code?" (avoid)
5. "What's the simplest vertical slice that demonstrates this?"

---

**Last Updated:** 2025-11-18
**Session:** 082b2e2a (14.5h Phase 1-3 implementation + strategic pivot)
**Status:** Post-Phase 3, pre-cleanup (architecture exists, half-wired to legacy)
