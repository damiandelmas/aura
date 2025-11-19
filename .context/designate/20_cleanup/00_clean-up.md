# How Extraction Enables End-State Architecture

**A conceptual map from current → extraction → ideal**

---

## The Transformation

### Current Flow (Tangled)

```
User Command
    ↓
CLI routes to controller
    ↓
    ├─→ Legacy Path (Qdrant hardcoded)
    │   └─→ EnhancedModularIngest
    │       └─→ QdrantClient(host="localhost")
    │           └─→ Direct API calls
    │
    └─→ Protocol Path (SQLite only)
        └─→ VectorStore interface
            └─→ SQLiteVectorStore
                └─→ SQL queries

= Two separate architectures coexisting
= Can't choose backend at runtime
= Core logic tied to Qdrant
```

### After Extraction

```
User Command
    ↓
CLI routes to controller
    ↓
Controller uses VectorStore protocol
    ↓
    ┌─────────────────────┐
    │  VectorStore        │ ← Single interface
    │  (abstraction)      │
    └─────────────────────┘
              ↓
    ┌─────────┴─────────┐
    ↓                   ↓
SQLiteVectorStore   QdrantVectorStore
    ↓                   ↓
  SQL DB          External Service

= Single architecture
= Backend choice via config/factory
= Core logic independent
```

---

## Component Evolution

### Phase 1: After Isolation

**File Structure:**
```
imem/
├── src/imem/
│   ├── legacy/v2/          ← REFERENCE (not imported)
│   │   ├── ingest.py       (how Qdrant indexing worked)
│   │   ├── search.py       (rich filtering patterns)
│   │   ├── enhanced.py     (scoring formulas)
│   │   └── README.md       (what capabilities existed)
│   │
│   ├── compile/            ← NEEDS FIXING
│   │   └── indexer.py      (still calls legacy - TODO marker)
│   │
│   ├── storage/            ← CLEAN
│   │   ├── protocol.py     (interface definition)
│   │   ├── factory.py      (backend selection)
│   │   ├── sqlite_backend.py   (works ✓)
│   │   └── qdrant_backend.py   (partial ✓)
│   │
│   ├── compose/            ← NEEDS WIRING
│   │   └── orchestrator.py (discovery stubbed)
│   │
│   └── cli/                ← CLEAN
│       └── commands.py     (uses factory ✓)
```

**Dataflow Clarity:**
```
Legacy code → isolated → documented → preserved as spec
Active code → marked where broken → clear TODO list
Working path → metadata queries → proves protocol works
```

---

### Phase 2: After Protocol Adoption

**Component Relationships:**

```
┌─────────────────────────────────────────────┐
│           COMPILE Domain                    │
│                                             │
│  MarkdownParser → chunks[]                  │
│         ↓                                   │
│  CompileResolver → normalize metadata       │
│         ↓                                   │
│  DocumentIndexer → store.upsert(chunks)     │ ← Uses protocol
│                                             │
└─────────────────┬───────────────────────────┘
                  ↓
         VectorStore Protocol
                  ↓
    ┌─────────────┴──────────────┐
    ↓                            ↓
┌──────────────┐         ┌──────────────┐
│   SQLite     │         │   Qdrant     │
│   Backend    │         │   Backend    │
│              │         │              │
│ • Metadata   │         │ • Vectors    │
│ • Relations  │         │ • Semantic   │
│ • Discovery  │         │ • Discovery  │
└──────────────┘         └──────────────┘
```

**What Changes:**
- `compile/indexer.py` → rewrites to use `self.store.upsert()`
- `storage/qdrant_backend.py` → adds discovery methods
- `compose/orchestrator.py` → enables discovery processors

**What Stays:**
- Parser logic (markdown → chunks)
- Resolution logic (normalization)
- CLI interface
- Factory pattern

---

### Phase 3: Full Protocol Compliance

**Data Flow Through System:**

```
INPUT (markdown files, conversations)
    ↓
COMPILE
    ├─→ Parse (MarkdownParser)
    │   └─→ chunks with content + metadata
    │
    ├─→ Resolve (CompileResolver)
    │   └─→ "planning" → "design"
    │   └─→ "Decisions" → "Decision"
    │
    └─→ Store (via protocol)
        └─→ VectorStore.upsert(chunks)
            ↓
    ┌───────┴────────┐
    ↓                ↓
  SQLite          Qdrant
    │                │
    ├─→ chunks table │
    ├─→ relationships│ (future)
    └─→ indexes      └─→ collections + vectors

STORAGE (abstracted, swappable)
    ↓
RETRIEVE/COMPOSE
    ├─→ SearchProcessor
    │   └─→ VectorStore.search(filters, use_vector)
    │
    ├─→ DiscoveryProcessor (future)
    │   └─→ VectorStore.get_siblings()
    │   └─→ VectorStore.get_temporal()
    │
    └─→ RankingProcessor
        └─→ Sort by recency, relevance, etc.
    ↓
OUTPUT (SearchResult[])
```

**Key Insight:** Each domain talks to abstraction, never concrete implementation.

---

## Codebase Shape Evolution

### Current Shape (Confused)

```
Active Code:
  compile/indexer.py        [SPLIT: half protocol, half legacy]
  storage/sqlite_backend.py [CLEAN: pure protocol]
  storage/qdrant_backend.py [PARTIAL: upsert works, discovery missing]
  compose/orchestrator.py   [STUBBED: discovery raises errors]

Legacy Code (active!):
  ingest.py                 [ACTIVE: called by indexer]
  enhanced.py               [DORMANT: not called but importable]
  search.py                 [DORMANT: parallel to SearchProcessor]
  primitives/discovery.py   [DORMANT: Qdrant-only, not protocol]
```

### After Extraction (Clear Boundaries)

```
Active Code (protocol-based):
  compile/
    ├── indexer.py          [REWRITTEN: uses store.upsert()]
    ├── resolver.py         [CLEAN: normalization logic]
    └── relationship_builder.py [NEW: detects graph edges]

  storage/
    ├── protocol.py         [STABLE: interface definition]
    ├── factory.py          [STABLE: backend selection]
    ├── sqlite_backend.py   [ENHANCED: relationships support]
    └── qdrant_backend.py   [COMPLETE: discovery implemented]

  compose/
    ├── orchestrator.py     [ENABLED: calls discovery processors]
    └── processors/
        ├── search.py       [STABLE]
        ├── ranking.py      [STABLE]
        └── discovery.py    [NEW: uses store methods]

  cli/
    └── commands.py         [STABLE: uses factory + protocol]

Reference Code (isolated):
  legacy/v2/
    ├── README.md           [SPEC: what v2 could do]
    ├── ingest.py           [REFERENCE: field detection patterns]
    ├── search.py           [REFERENCE: filter composition]
    ├── enhanced.py         [REFERENCE: scoring formulas]
    └── discovery.py        [REFERENCE: Qdrant query patterns]
```

---

## Domain Data Flow (End State)

### COMPILE Domain
```
Input:  Raw markdown files
Process:
  1. Parse → chunks with metadata
  2. Resolve → normalize structure
  3. Detect → find relationships
  4. Store → VectorStore.upsert()
Output: Indexed chunks in storage backend
```

**Files:**
- `compile/indexer.py` - orchestrates
- `parse/markdown.py` - extracts chunks
- `compile/resolver.py` - normalizes
- `compile/relationship_builder.py` - detects edges

**Dependencies:** Only VectorStore protocol, not backends

---

### STORAGE Domain
```
Input:  Protocol method calls (upsert, search, get_siblings)
Process:
  - SQLite backend → SQL queries
  - Qdrant backend → API calls
  - HNSW backend (future) → local vectors
Output: SearchResult[] objects
```

**Files:**
- `storage/protocol.py` - interface
- `storage/factory.py` - runtime selection
- `storage/sqlite_backend.py` - SQL implementation
- `storage/qdrant_backend.py` - Qdrant implementation

**Dependencies:** Backend-specific (isolated)

---

### RETRIEVE Domain
```
Input:  Query config (search + discovery + ranking)
Process:
  1. Build processor chain from config
  2. SearchProcessor → VectorStore.search()
  3. DiscoveryProcessor → VectorStore.get_siblings()
  4. RankingProcessor → sort/score
Output: Enriched SearchResult[]
```

**Files:**
- `compose/orchestrator.py` - builds chain
- `compose/processors/search.py` - metadata/semantic
- `compose/processors/discovery.py` - graph traversal
- `compose/processors/ranking.py` - scoring

**Dependencies:** Only VectorStore protocol

---

### MANAGE Domain
```
Input:  Indexed corpus
Process:
  1. Entity detection
  2. Concept clustering
  3. Resolution table population
Output: Normalized entity mappings
```

**Files:**
- `manage/resolver.py` - entity normalization
- `manage/introspect.py` - corpus analysis

**Dependencies:** Only VectorStore protocol for queries

---

## Configuration Flow (End State)

### User Perspective
```bash
# Simple: Metadata-only (SQLite)
imem index develop --backend sqlite

# Advanced: Semantic search (Qdrant)
imem index develop --backend qdrant

# Future: Local vectors (HNSW)
imem index develop --backend hnsw
```

### System Perspective
```
Config/CLI flag
    ↓
Factory.create_store(backend='sqlite'|'qdrant'|'hnsw')
    ↓
Returns VectorStore implementation
    ↓
Injected into DocumentIndexer, SearchProcessor, etc.
    ↓
All code uses protocol methods
    ↓
Backend-specific behavior encapsulated
```

**Key:** User chooses capability, not implementation. Code doesn't know or care which backend.

---

## Relationship Model (End State)

### Schema
```sql
-- Chunks (metadata)
CREATE TABLE chunks (
    id TEXT PRIMARY KEY,
    content TEXT,
    phase TEXT,
    section_type TEXT,
    timestamp TEXT,
    ...
);

-- Relationships (graph edges)
CREATE TABLE relationships (
    source_id TEXT,
    target_id TEXT,
    type TEXT,  -- spatial_proximity, conversation_continues, etc.
    confidence REAL,
    metadata JSON,
    PRIMARY KEY (source_id, target_id, type)
);
```

### Discovery Flow
```
User: "Find related chunks"
    ↓
Orchestrator: build DiscoveryProcessor
    ↓
Processor: VectorStore.get_siblings(chunk_id)
    ↓
Backend:
  - SQLite → SELECT * FROM relationships WHERE source_id=?
  - Qdrant → query with file_path filter
    ↓
Results: SearchResult[] with explicit relationship metadata
```

**No implicit inference.** Relationships stored explicitly, queried directly.

---

## Enables vs Blocks

### What Extraction ENABLES

**1. Walking Skeletons**
```
Can now build:
  ├─→ spatial_proximity relationships (SQL-only)
  ├─→ temporal_cluster relationships (SQL-only)
  └─→ decision_implements (SQL + pattern matching)

Each isolated, testable, incremental.
```

**2. Backend Experimentation**
```
Can test:
  ├─→ SQLite performance (metadata queries)
  ├─→ HNSW integration (local vectors)
  └─→ Qdrant optimization (production scale)

Without rewriting core logic.
```

**3. Feature Parity Analysis**
```
Can compare:
  legacy/v2/search.py    ← What filtering existed?
  compose/processors/    ← What do we have now?
  
Preserve proven patterns without coupling.
```

**4. Clean Testing**
```
Can test:
  ├─→ Compile domain (mock VectorStore)
  ├─→ Storage backends (isolated)
  └─→ Retrieve domain (mock VectorStore)

No Docker, no external dependencies for unit tests.
```

### What Tangling BLOCKS

**Cannot do while tangled:**
- ✗ Test SQLite path independently (Qdrant imports leak)
- ✗ Add HNSW backend (which path would use it?)
- ✗ Build relationships table (unclear which code would populate)
- ✗ Validate protocol works (indexer bypasses it)
- ✗ Run without Docker (Qdrant hardcoded in indexer)

---

## Final State Vision

```
┌─────────────────────────────────────────────────┐
│  IMEM: Knowledge Compiler for Agent Memories    │
└─────────────────────────────────────────────────┘
                      ↓
        ┌─────────────┴─────────────┐
        ↓                           ↓
    COMPILE                     MANAGE
  (structure)                (concepts)
        ↓                           ↓
    ┌───────────────────────────────┴──┐
    │     STORAGE (protocol-based)     │
    │  ┌────────┬─────────┬─────────┐ │
    │  │ SQLite │ Qdrant  │  HNSW   │ │
    │  └────────┴─────────┴─────────┘ │
    └──────────────────────────────────┘
                      ↓
        ┌─────────────┴─────────────┐
        ↓                           ↓
   RETRIEVE                      CLI
  (compose)                   (interface)
        ↓
   SearchResult[]
```

**Characteristics:**
- **Domains separated** - single responsibility
- **Protocol abstraction** - swap backends
- **Explicit relationships** - graph edges in SQL
- **Config-driven** - runtime choice, not compile-time
- **Testable** - mock protocol, test domains
- **Incremental** - add features without refactor

---

**The extraction doesn't just move files.** It clarifies architecture, enables experimentation, prevents degradation, and makes the system reason-about-able.