# IMEM sql-first Architecture (Target)

## Purpose

IMEM is a knowledge compiler for AI agent memories. The system transforms agent coding session artifacts (markdown changelogs, conversations, git metadata) into queryable knowledge with normalized structure, explicit relationships, and optional vector embeddings.

**SQLite is THE store.** All metadata and content lives in SQLite. Vector search (HNSW) is an optional modality added later. Qdrant is REMOVED from active code.

**Path**: `worktrees/sql-first/imem/src/imem/`

## Four Domains

**COMPILE** - Structural transformation of documents into searchable chunks. Parses markdown, extracts sections, normalizes phase/section_type metadata, stores via VectorStore protocol. ONE code path.

**MANAGE** - Project registration and entity normalization. Tracks project-to-path mappings, provides schema discovery for AI onboarding, normalizes entity variations (JWT → jwt).

**STORAGE** - SQLite backend via VectorStore protocol. Future: HNSW for vector similarity. Protocol contains only operations SQLite can implement.

**COMPOSE** - Query orchestration via processor chains. Builds retrieval pipelines from declarative config. SearchProcessor → RankingProcessor. Discovery via direct SQL queries.

## Data Flow

### Ingestion (Single Path)

```
.context/{phase}/*.md
        │
        ▼
   MarkdownParser
   (frontmatter, sections, chunk IDs)
        │
        ▼
   CompileResolver
   (phase normalization, section_type mapping)
        │
        ▼
   SQLiteVectorStore.upsert()
        │
        ▼
   SQLite DB
   ├── chunks table
   ├── resolution tables
   └── [future: HNSW vectors]

ONE path. ONE store. No backend selection.
```

### Retrieval

```
Query Config (JSON)
        │
        ▼
   Orchestrator.compose()
        │
        ▼
   Chain.build([processors])
        │
        ▼
   SearchProcessor
   ├── Metadata mode: SQL WHERE clauses
   └── Semantic mode: HNSW similarity [future]
        │
        ▼
   RankingProcessor
   (multi-phase progressive refinement)
        │
        ▼
   SearchResult[]
```

### Discovery (Direct SQL)

```
When relationship queries needed:
        │
        ▼
   Direct SQL query
   "SELECT * FROM chunks WHERE file_path = ?"
   "SELECT * FROM chunks WHERE session_id = ?"
   "SELECT * FROM chunks WHERE timestamp BETWEEN ? AND ?"
        │
        ▼
   Results

No protocol wrapper. Query directly. YAGNI.
```

## Key Components

**VectorStore Protocol** - Interface defining `upsert()`, `search()`, `get_stats()`, `get_by_ids()`. Implemented by SQLiteVectorStore. Pure, minimal interface.

**Processor Chain** - Vespa-inspired pattern for composable retrieval. Each processor transforms a RetrievalContext. Chain executes sequentially. Enables A/B testing of ranking strategies.

**CompileResolver** - Resolution tables mapping variations to canonical forms. "planning" → "design", "Key Decisions" → "Decision". SQL tables with confidence scores.

**MarkdownParser** - Pure Python markdown parsing. Extracts frontmatter, detects phase from path patterns, splits by H2/H3 headers, generates deterministic chunk IDs.

**Namespace Isolation** - Git branch detection determines storage namespace. Database paths include namespace. Enables v2/v3/feature branches to coexist.

**Legacy Reference** (`legacy/v2/`) - Quarantined Qdrant-coupled code preserved as specification. Documents v2 capabilities (field detection, hybrid scoring, discovery patterns). **NOT imported by active code.**

## Storage Architecture

```
~/.imem/namespaces/{branch}/
├── projects/{hash}/
│   └── metadata.db          # SQLite: ALL data
│       ├── chunks           # id, content, phase, section_type, timestamp, ...
│       ├── phase_variations # resolution tables
│       ├── entity_variations
│       └── [future: vectors] # HNSW index
└── registry.json            # Project → path mappings
```

**SQLite Schema**: chunks table with phase, section_type, timestamp, content, file_path, session_id. Resolution tables for phase/section/entity normalization with confidence and usage tracking.

**No Qdrant.** No external service. No Docker dependency.

## Integration Points

**SQLite** - Embedded database for ALL queries. WAL mode, memory-mapped I/O. Resolution tables enable structural normalization.

**HNSW** (future) - Embedded vector index in SQLite via sqlite-vss or similar. Stores chunk_id + vector only. Joins to chunks table for metadata.

**SentenceTransformers** (future) - nomic-embed-v1.5 (768D, 8k tokens) for embedding generation. Lazy-loaded, batch encoding for performance.

**File System** - Reads from `.context/{design,designate,develop,document}/` structure. Claude Code conversations from `~/.claude/projects/`.

## Patterns

**SQL-First Philosophy** - ALL queries are SQL. Metadata filters via WHERE clauses. Semantic search (when added) returns chunk_ids that join to SQL.

**Single Backend** - No "backend selection". SQLite is THE store. Simplicity over flexibility.

**Processor Chain** - Declarative pipelines from config. Cheap operations (metadata filter) before expensive (ranking). Enables experimentation without code changes.

**Resolution Tables** - Normalization via SQL with confidence scores. Tracks usage for learning. Separate tables for structure (compile-time) vs entities (query-time).

**Namespace Isolation** - Git-aware storage paths. Each branch/worktree gets isolated namespace. Prevents development collision.

**YAGNI Discovery** - No protocol wrapper for discovery queries. Write SQL directly. Abstract only when 2-3 patterns prove need. Legacy reference documents proven patterns.

## What's Removed

- ❌ `storage/qdrant_backend.py` - DELETE
- ❌ `QdrantVectorStore` exports - DELETE
- ❌ Qdrant config vars - DELETE
- ❌ `--backend` flags - DELETE
- ❌ Duplicate commands (`index` vs `index-metadata`) - UNIFY
- ❌ External Qdrant service - NOT NEEDED

## What's Preserved (Reference Only)

```
legacy/v2/
├── ingest.py      # Parsing patterns to port
├── enhanced.py    # Scoring formulas to port
├── search.py      # Filter composition patterns
├── discovery.py   # Query patterns (not as wrappers)
└── README.md      # What v2 could do
```

Use for porting logic. Do NOT import.
