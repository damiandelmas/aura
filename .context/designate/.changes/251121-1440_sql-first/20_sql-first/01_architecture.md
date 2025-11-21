# Target Architecture

## Storage Topology

```
┌──────────────────────────────────────┐
│  Git Repository (source of truth)    │
│  - .context/**/*.md                  │
│  - .claude/.convs/*.jsonl            │
│  - git commits                       │
└────────────┬─────────────────────────┘
             │
    ┌────────▼────────┐
    │ compile/Parser  │ ← Template-based extraction
    │ (pluggable)     │
    └────────┬────────┘
             │
    ┌────────▼────────────────────┐
    │ Canonical Chunks            │
    │ {id, phase, section_type,   │
    │  content, timestamp, ...}   │
    └────────┬────────────────────┘
             │
    ┌────────▼────────────┐
    │ storage/SQLite      │ ← PRIMARY (always)
    │ .imem/corpus.db     │
    │ - metadata + content│
    │ - indexed queries   │
    └────────┬────────────┘
             │
             ├──→ retrieve/ (SQL queries, graph ops)
             │
             └──→ storage/Qdrant (OPTIONAL)
                  - vectors only
                  - references SQLite IDs
                  - no payload duplication
```

## Domain Structure (Current + Planned)

```
imem/
├── core/                  ✅ Phase 2
│   ├── chain.py          # Processor chain abstraction
│   ├── context.py        # RetrievalContext dataclass
│   └── async_helpers.py  # Bounded concurrency (semaphore_gather)
│
├── compile/              ✅ Phase 3
│   ├── indexer.py        # Document indexing orchestration
│   ├── parser.py         # Template-based extraction
│   ├── templates/        # Domain parsers (changelog, conversation)
│   └── resolver.py       # Schema evolution (phase/section normalization)
│
├── manage/               ✅ Phase 3 (partial)
│   ├── resolver.py       # Entity normalization ✅
│   ├── registry.py       # Project tracking ✅
│   ├── analyzer.py       # Semantic relationship detection ⏳ Phase 5
│   └── temporal.py       # Git validation ⏳ Phase 6
│
├── storage/              ✅ Phase 1 | ⏳ Phase 4 (protocol split)
│   ├── protocol.py       # VectorSearch + GraphStore protocols ⏳
│   ├── sqlite.py         # Implements both protocols ✅
│   ├── qdrant_backend.py # VectorSearch only ⏳
│   └── factory.py        # Backend creation ✅
│
├── compose/              ✅ Phase 2-3
│   ├── orchestrator.py   # Chain builder + executor ✅
│   └── processors/
│       ├── search.py     # SearchProcessor ✅
│       ├── ranking.py    # MultiPhaseRanker ✅
│       ├── discovery.py  # Siblings/Temporal (stubbed) ⏳ Phase 4
│       └── graph.py      # Relationship traversal ⏳ Phase 5
│
└── cli/                  ✅ Phase 3
    ├── main.py           # IMEMCLI composition root ✅
    └── commands.py       # Command definitions ✅
```

**Legend:** ✅ Shipped | ⏳ Planned

## Processor Chain Pattern

**Current (hardcoded):**
```python
# compose.py - 500+ LOC of procedural logic
results = await _execute_search(...)
if discovery_config:
    results = await _enrich_with_discovery(...)
results = _enrich_metadata(results)
results = _filter_results(results)
```

**Target (declarative):**
```python
# Chain configured via YAML/code
chain = Chain([
    SearchProcessor(store, mode='metadata'),
    SiblingDiscovery(),
    TemporalDiscovery(),
    FilterProcessor()
])

result = chain.execute(RetrievalContext(query, config))
```

**Benefits:**
- Reorder stages via config
- Skip optional stages conditionally
- Test processors independently
- A/B test implementations
- Backend polymorphism via StorageProtocol

## Storage Protocol (Revised - Phase 4)

**Current Issue:** VectorStore mixes vector search + graph operations. Qdrant can't do graph ops (no file_path indexing), creates false abstraction.

**Solution:** Split into two protocols:

```python
class VectorSearch(Protocol):
    """Vector similarity + metadata filters (Qdrant, HNSW)"""
    def search(query: str, filters: Dict, limit: int) -> List[SearchResult]: ...
    def upsert(chunks: List[Dict]) -> bool: ...

class GraphStore(Protocol):
    """Metadata queries + relationship traversal (SQLite only)"""
    def get_siblings(chunk_id: str) -> List[SearchResult]: ...
    def get_temporal(chunk_id: str, window_days: int) -> List[SearchResult]: ...
    def get_implementations(chunk_id: str) -> List[SearchResult]: ...  # Semantic links
    def get_stats() -> Dict: ...

# SQLite implements BOTH
sqlite_store = SQLiteStore(project_root)  # VectorSearch + GraphStore

# Qdrant implements VectorSearch ONLY
qdrant_store = QdrantVectorSearch(collection='docs')  # No graph methods

# Processors use appropriate protocol
SearchProcessor(vector_search=qdrant_store)  # VectorSearch
DiscoveryProcessor(graph_store=sqlite_store)  # GraphStore
```

## Resolution Architecture (Two Layers)

### COMPILE Resolution (Structure - Indexing Time)

**Purpose:** Normalize document structure to canonical 4-phase + section types

```python
# imem/compile/resolver.py
class CompileResolver:
    def resolve_phase(self, raw: str) -> str:
        """Map phase variation → canonical 4-phase"""
        # 'planning' → 'design'
        # 'spec' → 'designate'
        # 'implementation' → 'develop'
        # 'docs' → 'document'

    def resolve_section_type(self, header: str) -> str:
        """Map header variation → canonical section type"""
        # 'Decisions' → 'Decision'
        # 'We Decided:' → 'Decision'
        # 'Best Practice' → 'Pattern'
```

**Schema:**
```sql
CREATE TABLE phase_resolution (
    variation TEXT PRIMARY KEY,
    canonical TEXT CHECK (canonical IN ('design', 'designate', 'develop', 'document')),
    confidence REAL DEFAULT 1.0
);

CREATE TABLE section_type_resolution (
    variation TEXT PRIMARY KEY,
    canonical TEXT,  -- Decision, Pattern, Implementation, etc.
    confidence REAL DEFAULT 1.0
);
```

**Seeded mappings:**
- Phase: 20-30 known variations per canonical phase
- Section types: 10-15 variations per canonical type
- Updated via observation (discover new variations, cluster to canonical)

### MANAGE Resolution (Entities - Query Time)

**Purpose:** Normalize entity references within project scope

```python
# imem/manage/resolver.py
class EntityResolver:
    def __init__(self, project_id: str):
        self.project_id = project_id

    def resolve_entity(self, term: str) -> str:
        """Map entity variation → canonical within project"""
        # 'jwt' / 'JWT' / 'json-web-tokens' → canonical 'jwt'

    def expand_query(self, canonical: str) -> List[str]:
        """Expand canonical → all variants for search"""
        # 'jwt' → ['jwt', 'JWT', 'json-web-tokens', 'jwt-auth']
```

**Schema:**
```sql
CREATE TABLE entity_resolution (
    project_id TEXT NOT NULL,
    variation TEXT NOT NULL,
    canonical TEXT NOT NULL,
    context TEXT,  -- Optional: domain hint
    confidence REAL DEFAULT 1.0,
    PRIMARY KEY (project_id, variation)
);
```

**Key differences:**
- COMPILE: Universal, pre-defined canonical taxonomy
- MANAGE: Project-scoped, emergent from corpus

## Key Principles

1. **SQLite = source of truth** (Qdrant = derived index)
2. **Parse once, query many ways** (storage choice = query needs)
3. **Two-layer resolution** (COMPILE = structure, MANAGE = entities)
4. **Processor chain = declarative composition** (not hardcoded pipeline)
5. **StorageProtocol = backend polymorphism** (swap via config)
6. **CLI = thin router** (logic lives in domains)

## What Changes

| Component | Before | After |
|-----------|--------|-------|
| **Indexing** | Qdrant-first, slow (15 min) | SQLite-first, fast (2 sec) |
| **Storage** | Duplicate metadata (SQLite + Qdrant) | Single source (SQLite), Qdrant derived |
| **Discovery** | Qdrant-only (8/283 files) | SQLite-based (283/283 files) |
| **Pipeline** | Hardcoded stages | Processor chain (configurable) |
| **Backend** | Coupled to compose logic | Polymorphic via StorageProtocol |
| **CLI** | 1800 LOC monolith | 200 LOC router + domains |
| **Testing** | Integration only | Unit test each processor |

## What Stays Same

- User-facing commands (same CLI interface)
- Discovery primitives (siblings, temporal, genealogy)
- Compose config format (backward compatible)
- Existing Qdrant data (migration path provided)
