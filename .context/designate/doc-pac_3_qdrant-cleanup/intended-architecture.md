# IMEM sql-first Architecture (Target)

## Purpose

IMEM is a knowledge compiler for AI agent memories. The system transforms agent coding session artifacts (markdown changelogs, conversations, git metadata) into queryable knowledge with normalized structure, explicit relationships, and optional vector embeddings.

The sql-first branch prioritizes SQLite for fast metadata queries (<10ms) with Qdrant as optional semantic search modality. Most queries are structural ("show develop phase from last week") not semantic ("find things about authentication").

**Path**: `worktrees/sql-first/imem/src/imem/`

## Four Domains

**COMPILE** - Structural transformation of documents into searchable chunks. Parses markdown, extracts sections, normalizes phase/section_type metadata, stores via VectorStore protocol. Single code path for all backends.

**MANAGE** - Project registration and entity normalization. Tracks project-to-collection mappings, provides schema discovery for AI onboarding, normalizes entity variations (JWT → jwt).

**STORAGE** - Backend abstraction via VectorStore protocol. SQLite for metadata-rich queries, Qdrant for semantic similarity. Factory pattern enables runtime backend selection. Protocol contains only shared operations.

**COMPOSE** - Query orchestration via processor chains. Builds retrieval pipelines from declarative config. SearchProcessor → RankingProcessor. Discovery via direct SQL queries when needed.

## Data Flow

### Ingestion (Unified)

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
   VectorStore.upsert()
        │
    ┌───┴───┐
    ▼       ▼
 SQLite   Qdrant
(metadata) (vectors)

One path. Backend selected via factory.
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
   (VectorStore.search with filters)
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
        │
        ▼
   Results

No protocol wrapper. Query directly when patterns emerge.
```

## Key Components

**VectorStore Protocol** - Backend-agnostic interface defining `upsert()`, `search()`, `get_stats()`, `get_by_ids()`. Pure interface - no discovery methods. Both backends implement identically.

**Processor Chain** - Vespa-inspired pattern for composable retrieval. Each processor transforms a RetrievalContext. Chain executes sequentially. Enables A/B testing of ranking strategies.

**CompileResolver** - Resolution tables mapping variations to canonical forms. "planning" → "design", "Key Decisions" → "Decision". SQL tables with confidence scores enable evolution tracking.

**MarkdownParser** - Pure Python markdown parsing. Extracts frontmatter, detects phase from path patterns, splits by H2/H3 headers, generates deterministic chunk IDs.

**Namespace Isolation** - Git branch detection determines storage namespace. Collections prefixed with namespace. Enables v2/v3/feature branches to coexist without collision.

**Legacy Reference** (`legacy/v2/`) - Quarantined Qdrant-coupled code preserved as specification. Documents v2 capabilities (field detection, hybrid scoring, discovery patterns). Not imported by active code.

## Storage Architecture

```
~/.imem/namespaces/{branch}/
├── projects/{hash}/
│   └── metadata.db          # SQLite: chunks, resolution tables
└── registry.json            # Project → collection mappings

Qdrant Collections:
├── {namespace}_imem_{hash}_context
└── {namespace}_imem_{hash}_conversation
```

**SQLite Schema**: chunks table with phase, section_type, timestamp, content. Resolution tables for phase/section/entity normalization with confidence and usage tracking.

**Qdrant Collections**: Named vectors (nomic-embed-v1.5, 768D). Rich metadata payloads mirror SQLite schema for hybrid queries.

## Integration Points

**Qdrant** (localhost:6334) - External vector database in Docker. Named vectors for multi-model support. HNSW indexing for sub-100ms similarity search.

**SQLite** - Embedded database for metadata queries. WAL mode, memory-mapped I/O. Resolution tables enable structural normalization.

**SentenceTransformers** - nomic-embed-v1.5 (768D, 8k tokens) for embedding generation. Lazy-loaded, batch encoding for performance.

**File System** - Reads from `.context/{design,designate,develop,document}/` structure. Claude Code conversations from `~/.claude/projects/`.

## Patterns

**SQL-First Philosophy** - Most queries are metadata filters, not semantic search. SQLite handles "show me develop phase decisions" without vectors. Qdrant adds semantic modality when needed.

**Protocol Abstraction** - VectorStore interface enables backend swapping without code changes. Factory pattern selects backend at runtime. Protocol contains only operations both backends can implement honestly.

**Processor Chain** - Declarative pipelines from config. Cheap operations (metadata filter) before expensive (ranking). Enables experimentation without code changes.

**Resolution Tables** - Normalization via SQL with confidence scores. Tracks usage for learning. Separate tables for structure (compile-time) vs entities (query-time).

**Namespace Isolation** - Git-aware storage paths. Each branch/worktree gets isolated namespace. Prevents development collision.

**YAGNI Discovery** - No protocol wrapper for discovery queries. When you need "chunks in same file", write SQL directly. Abstract only when 2-3 patterns prove need. Legacy reference documents proven patterns.
