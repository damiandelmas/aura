# IMEM sql-first Architecture

## Purpose

IMEM is a knowledge compiler for AI agent memories. The system transforms agent coding session artifacts (markdown changelogs, conversations, git metadata) into queryable knowledge with normalized structure and explicit relationships.

**SQLite is THE store.** Most queries are structural ("show develop phase from last week") not semantic ("find things about authentication"). Metadata-first search with optional vectors (future: sqlite-vss).

**Path**: `worktrees/sql-first/imem/src/imem/`

## Four Domains

**COMPILE** - Structural transformation of documents into searchable chunks. Parses markdown, extracts sections, normalizes phase/section_type metadata, stores via VectorStore protocol.

**MANAGE** - Project registration and introspection. Tracks project-to-path mappings, provides schema discovery for AI onboarding.

**STORAGE** - SQLite backend via VectorStore protocol. Single backend, no selection. Future: HNSW vectors via sqlite-vss extension.

**COMPOSE** - Query orchestration via processor chains. Builds retrieval pipelines from declarative config. SearchProcessor → RankingProcessor. Cheap operations first, expensive last.

## Data Flow

### Ingestion

```
.context/{phase}/*.md
        │
        ▼
   compile/parser.py
   (frontmatter, sections, phase detection)
        │
        ▼
   Flat chunk dict
   (top-level indexed fields + metadata blob)
        │
        ▼
   SQLiteVectorStore.upsert()
        │
        ▼
   SQLite DB
   (chunks table with indexes)
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
   (SQL WHERE clauses)
        │
        ▼
   [Optional] MultiPhaseRanker
   (recency, metadata, authority)
        │
        ▼
   SearchResult[]
```

### Discovery

```
Relationship queries needed?
        │
        ▼
   Direct SQL query
   "SELECT * FROM chunks WHERE file_path = ?"
   "SELECT * FROM chunks WHERE session_id = ?"
   "SELECT * FROM chunks WHERE timestamp > ?"
        │
        ▼
   Results

No protocol wrapper. Query directly. YAGNI.
```

## Key Components

**VectorStore Protocol** - Backend-agnostic interface defining `upsert()`, `search()`, `get_stats()`, `get_by_ids()`. SQLiteVectorStore implements this protocol.

**Processor Chain** - Vespa-inspired pattern for composable retrieval. Each processor transforms a RetrievalContext. Chain executes sequentially. Enables A/B testing of ranking strategies.

**MarkdownParser** - Lightweight custom parser (no ML deps). Extracts frontmatter, detects phase from path patterns, splits by H2/H3 headers, generates deterministic chunk IDs.

**Namespace Isolation** - Git branch detection determines storage namespace. Database paths include namespace. Enables branches to coexist without collision.

## Storage Architecture

```
~/.imem/namespaces/{branch}/
├── projects/{hash}/
│   └── metadata.db          # SQLite: ALL data
└── registry.json            # Project → path mappings
```

**SQLite Schema**: chunks table with indexed columns (phase, section_type, file_path, timestamp, session_id) plus JSON metadata blob for extras.

**No external services.** No Docker. No Qdrant.

## Integration Points

**SQLite** - Embedded database for ALL queries. WAL mode for concurrent access. Indexed columns for fast filtering.

**File System** - Reads from `.context/{design,designate,develop,document}/` structure. Claude Code conversations from `~/.claude/projects/`.

**No ML Dependencies** - Custom regex-based parsing. No LlamaIndex, no transformers, no heavy deps.

## Patterns

**SQL-First Philosophy** - ALL queries are metadata filters. SQLite handles "show me develop phase decisions" directly. No vectors required for structural queries.

**Single Backend** - No "backend selection". SQLite is THE store. Simplicity over flexibility.

**Processor Chain** - Declarative pipelines from config. Cheap operations (metadata filter) before expensive (ranking). Enables experimentation without code changes.

**YAGNI Discovery** - No protocol wrapper for relationship queries. Write SQL directly. Abstract only when 2-3 patterns prove need.

**Namespace Isolation** - Git-aware storage paths. Each branch/worktree gets isolated namespace. Prevents development collision.

**Metadata Predicates ARE the Graph** - No edge tables. file_path = siblings, session_id = genealogy, timestamp = temporal. Query SQLite directly.

## Lifecycle Phases (Causal Graph)

```
designate → design → develop → document
(explore)   (decide) (build)   (ship)
```

Each phase constrains the next. Enables temporal validation: did implementation match design?

## Not Implemented (Future EPICs)

- **CompileResolver** - Normalize unstructured logs from any agentic workflow
- **EntityResolver** - Query-time entity normalization (JWT → jwt)
- **HNSW vectors** - sqlite-vss for semantic similarity
- **Git validation** - Temporal truth via commits
