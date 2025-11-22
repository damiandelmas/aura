# IMEM sql-first Architecture (Current State)

## System Overview

IMEM (Institutional Memory) is a knowledge compiler for AI agent memories. It processes markdown documents through a 4-phase taxonomy (design, designate, develop, document) and conversation logs, storing chunks in either SQLite (fast metadata queries) or Qdrant (semantic vector search). The sql-first branch emphasizes metadata-based retrieval with optional vector similarity, enabling sub-10ms queries without requiring vector operations.

**Current State:** 74% clean architecture - VectorStore protocol exists but legacy Qdrant code still entangled at entry points.

## Codebase Shape

```
imem/src/imem/
│
├── __init__.py              # EXPORTS LEGACY CLASSES (problem)
├── config.py                # Centralized config with namespace isolation
├── registry.py              # Project registration and collection naming
├── introspect.py            # Schema discovery (misplaced - should be in manage/)
│
├── cli/                     # COMMAND INTERFACE (clean)
│   ├── main.py              # Composition root - dependency injection
│   └── commands.py          # Click commands - thin wrappers
│
├── compile/                 # COMPILE DOMAIN
│   ├── indexer.py           # DocumentIndexer - CALLS LEGACY ingest.py
│   └── resolver.py          # Structural normalization
│
├── compose/                 # COMPOSE DOMAIN (clean)
│   ├── orchestrator.py      # Chain builder + compose() entry
│   └── processors/
│       ├── search.py        # SearchProcessor - metadata or semantic
│       └── ranking.py       # MultiPhaseRanker
│
├── core/                    # CHAIN ABSTRACTION (clean)
│   └── chain.py             # Processor protocol + Chain executor
│
├── manage/                  # MANAGE DOMAIN
│   └── resolver.py          # EntityResolver
│
├── parse/                   # PARSING (clean)
│   └── markdown.py          # MarkdownParser - pure Python
│
├── primitives/              # DISCOVERY (Qdrant-coupled)
│   └── discovery.py         # get_siblings, genealogy, temporal
│
├── storage/                 # BACKEND ABSTRACTION (clean)
│   ├── protocol.py          # VectorStore protocol + SearchResult
│   ├── factory.py           # create_store() backend selector
│   ├── sqlite.py            # SQLiteStore - raw implementation
│   ├── sqlite_backend.py    # SQLiteVectorStore - protocol wrapper
│   └── qdrant_backend.py    # QdrantVectorStore - protocol wrapper
│
├── legacy/v2/               # EXISTS BUT EMPTY
│
└── [LEGACY - Root Level]    # SHOULD BE IN legacy/v2/
    ├── ingest.py            # EnhancedModularIngest (738 LOC)
    ├── search.py            # ModularSearch (587 LOC)
    ├── enhanced.py          # EnhancedQdrantSearch (445 LOC)
    └── qdrant_service.py    # Docker management
```

## Core Components

| Component | Location | Status | Purpose |
|-----------|----------|--------|---------|
| VectorStore Protocol | `storage/protocol.py` | Clean | Backend-agnostic interface |
| Chain Abstraction | `core/chain.py` | Clean | Composable retrieval pipelines |
| DocumentIndexer | `compile/indexer.py` | **Coupled** | Calls legacy EnhancedModularIngest |
| CompileResolver | `compile/resolver.py` | Clean | Phase/section normalization |
| MarkdownParser | `parse/markdown.py` | Clean | Pure Python section splitting |
| Orchestrator | `compose/orchestrator.py` | Clean | Builds chains from config |
| Discovery Primitives | `primitives/discovery.py` | **Coupled** | Hardcoded Qdrant client |

## Domain Separation

```
┌──────────────────────────────────────────────────────────────┐
│  COMPILE         │  Parse → Resolve → Store                  │
│                  │  indexer.py (COUPLED TO LEGACY)           │
├──────────────────────────────────────────────────────────────┤
│  MANAGE          │  Project registration, introspection      │
│                  │  registry.py, introspect.py               │
├──────────────────────────────────────────────────────────────┤
│  STORAGE         │  VectorStore protocol abstraction         │
│                  │  sqlite_backend.py ✓  qdrant_backend.py ✓ │
├──────────────────────────────────────────────────────────────┤
│  COMPOSE         │  Query orchestration via processor chain  │
│                  │  orchestrator.py ✓  SearchProcessor ✓     │
└──────────────────────────────────────────────────────────────┘
```

## Data Flow

### Ingestion (Two Paths - Problem)

```
PATH A: Legacy (Qdrant-coupled)
┌─────┐    ┌──────────────────────┐    ┌─────────────┐
│ .md │───>│ EnhancedModularIngest│───>│ QdrantClient│
│files│    │ (ingest.py)          │    │ (hardcoded) │
└─────┘    └──────────────────────┘    └─────────────┘
                     ↑
           compile/indexer.py calls this


PATH B: Protocol (Clean)
┌─────┐    ┌──────────────┐    ┌─────────────┐    ┌─────────────┐
│ .md │───>│MarkdownParser│───>│ VectorStore │───>│SQLite/Qdrant│
│files│    │(parse/)      │    │ .upsert()   │    │  backend    │
└─────┘    └──────────────┘    └─────────────┘    └─────────────┘
                                      ↑
                         index-metadata command uses this
```

### Retrieval (Clean)

```
┌───────┐    ┌────────────┐    ┌─────────────────────┐    ┌─────────┐
│ Query │───>│Orchestrator│───>│ Chain               │───>│ Results │
│ JSON  │    │ .compose() │    │ [Search → Rank]     │    │         │
└───────┘    └────────────┘    └─────────────────────┘    └─────────┘
                  │
                  ▼
         VectorStore.search()
                  │
        ┌─────────┴─────────┐
        ▼                   ▼
   SQLiteBackend      QdrantBackend
```

## Key Patterns

**VectorStore Protocol**
- Backend-agnostic interface: `upsert()`, `search()`, `get_stats()`
- Factory pattern: `create_store(backend='sqlite'|'qdrant')`
- Enables transparent backend switching

**Processor Chain**
- Declarative pipeline: `Chain.build([SearchProcessor, RankingProcessor])`
- Cheap operations first (metadata), expensive last (ranking)
- Config-driven assembly via Orchestrator

**Namespace Isolation**
- Git branch detection → `~/.imem/namespaces/{branch}/`
- Collections prefixed: `{namespace}_imem_{hash}_context`
- v2/v3/main can coexist without collision

**Resolution Tables**
- COMPILE: phase/section_type normalization
- MANAGE: entity normalization (project-specific)
- SQL tables with confidence scores

## Current Entanglements

| Location | Problem | Impact |
|----------|---------|--------|
| `__init__.py` | Exports legacy classes | Public API leaks Qdrant coupling |
| `compile/indexer.py:65` | Imports `EnhancedModularIngest` | Indexing bypasses protocol |
| `primitives/discovery.py` | Hardcoded `QdrantClient` | Discovery not protocol-based |
| Root level | `ingest.py`, `search.py`, `enhanced.py` | Should be in `legacy/v2/` |
| `storage/protocol.py` | Has `get_siblings/genealogy/temporal` | False abstraction (simple SQL queries) |

## Integration Points

```
┌─────────────────┬─────────────────────────────────────────┐
│ External        │ Purpose                                 │
├─────────────────┼─────────────────────────────────────────┤
│ Qdrant          │ Vector similarity search                │
│ localhost:6334  │ Named vectors (nomic-embed-v1.5)        │
├─────────────────┼─────────────────────────────────────────┤
│ SQLite          │ Fast metadata queries (<10ms)           │
│ ~/.imem/ns/{b}/ │ Chunks + resolution tables              │
├─────────────────┼─────────────────────────────────────────┤
│ File System     │ .context/{phase}/*.md source docs       │
├─────────────────┼─────────────────────────────────────────┤
│ SentenceTransf. │ nomic-embed-v1.5 (768-dim)              │
└─────────────────┴─────────────────────────────────────────┘
```
