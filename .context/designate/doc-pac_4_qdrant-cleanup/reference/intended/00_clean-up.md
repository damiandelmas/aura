# Target Architecture: SQLite-First, Qdrant-Free

**The transformation from Qdrant-coupled to SQLite-primary**

---

## The Decision

**Qdrant is REMOVED from active code.**

- SQLite = PRIMARY store for ALL metadata AND content
- HNSW = embedded vector search (future, replaces Qdrant)
- Qdrant = reference only in `legacy/v2/`

**No "backend choice".** No "Qdrant option". ONE path.

---

## Before (Tangled)

```
User Command
    ↓
CLI routes to controller
    ↓
    ├─→ Legacy Path (Qdrant hardcoded)
    │   └─→ EnhancedModularIngest
    │       └─→ QdrantClient(host="localhost")
    │           └─→ Direct API calls
    │           └─→ Metadata duplicated in payloads
    │
    └─→ Protocol Path (SQLite only)
        └─→ VectorStore interface
            └─→ SQLiteVectorStore
                └─→ SQL queries

= Two architectures coexisting
= Duplicate commands (index vs index-metadata)
= Metadata in two places
= Can't reason about system
```

---

## After (Clean)

```
User Command
    ↓
CLI routes to controller
    ↓
Controller uses VectorStore protocol
    ↓
    ┌─────────────────────┐
    │  SQLiteVectorStore  │ ← THE store
    │  (metadata + content)│
    └─────────────────────┘
              ↓
    ┌─────────┴─────────┐
    ↓                   ↓
  SQL queries      HNSW vectors
  (metadata)       (semantic search)
                   [future]

= ONE architecture
= ONE index command
= Metadata in ONE place (SQLite)
= Clear, testable, simple
```

---

## Data Flow

### Indexing (Single Path)

```
.context/{phase}/*.md
        │
        ▼
   MarkdownParser
   (parse/markdown.py)
        │
        ▼
   CompileResolver
   (compile/resolver.py)
        │
        ▼
   SQLiteVectorStore.upsert()
        │
        ▼
   SQLite DB
   ├── chunks table
   ├── resolution tables
   └── [future: HNSW vectors]
```

### Retrieval

```
Query
    │
    ▼
Orchestrator.compose()
    │
    ▼
Chain.build([processors])
    │
    ▼
SearchProcessor
    │
    ├─→ Metadata mode: SQL WHERE clauses
    └─→ Semantic mode: HNSW similarity [future]
    │
    ▼
RankingProcessor
    │
    ▼
SearchResult[]
```

---

## What Gets Deleted

### From Active Code

```
storage/qdrant_backend.py     → DELETE
introspect.py (QdrantClient)  → REWRITE
compile/indexer.py (legacy)   → REWRITE
cli/main.py (qdrant methods)  → DELETE
config.py (qdrant settings)   → DELETE
```

### Commands

```
BEFORE:
  imem index           → Qdrant
  imem index-metadata  → SQLite

AFTER:
  imem index           → SQLite (only option)
```

---

## What Stays (as Reference)

```
legacy/v2/
├── README.md        # What v2 could do
├── ingest.py        # Parsing patterns to port
├── enhanced.py      # Scoring formulas to port
├── search.py        # Filter composition patterns
└── discovery.py     # Query patterns (not wrappers)
```

**Use for:** Porting logic to SQLite implementations
**Do NOT:** Import from active code

---

## Storage Architecture

```
~/.imem/namespaces/{branch}/
├── projects/{hash}/
│   └── metadata.db          # SQLite: ALL data
│       ├── chunks           # id, content, phase, section_type, ...
│       ├── phase_variations # resolution tables
│       └── vectors          # [future: HNSW index]
└── registry.json            # Project → path mappings
```

**No Qdrant collections.** No external service. No Docker dependency.

---

## Why This Matters

### Enables

- **Fast queries**: SQL WHERE vs vector post-filter
- **Rich querying**: JOINs, GROUP BY, aggregations
- **No Docker**: Embedded SQLite, no external service
- **Testable**: No network, no containers
- **Portable**: Single file database

### Removes

- **Duplicate data**: Metadata was in SQLite AND Qdrant
- **Duplicate commands**: `index` vs `index-metadata`
- **External dependency**: Qdrant service
- **Confusion**: Which backend? What's the source of truth?

---

## Semantic Search (Future)

When we need vectors:

```
SQLite + HNSW (embedded)
├── chunks table: ALL metadata
└── vectors table: chunk_id + vector

Search flow:
1. HNSW.search(query_vector) → [chunk_ids]
2. SELECT * FROM chunks WHERE id IN (chunk_ids)
3. Return joined results
```

**Key:** Vectors are OPTIONAL modality. Metadata is always in SQLite.

---

## Migration Path

1. ✅ Quarantine legacy to `legacy/v2/`
2. ✅ Delete confused wrappers
3. ⬜ Rewrite indexer to use protocol
4. ⬜ Delete Qdrant backend
5. ⬜ Fix introspection
6. ⬜ Unify CLI commands
7. ⬜ [Future] Add HNSW for vectors

---

**The goal is simplicity.** ONE store, ONE path, ONE source of truth.
