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

## Domain Structure

```
imem/
├── core/
│   ├── chain.py          # Processor chain abstraction
│   ├── context.py        # RetrievalContext dataclass
│   └── storage.py        # StorageProtocol interface
│
├── compile/              # Domain 1: Parsing
│   ├── parser.py         # Template-based extraction
│   ├── templates/        # Domain parsers (changelog, conversation)
│   └── resolver.py       # Schema evolution
│
├── manage/               # Domains 2+3: Intelligence
│   ├── temporal.py       # Git validation (JOINs with commits)
│   ├── resolver.py       # Entity normalization
│   └── registry.py       # Project tracking
│
├── storage/              # Domain 4: Backends
│   ├── protocol.py       # StorageProtocol (ABC)
│   ├── sqlite.py         # SQLite implementation
│   └── qdrant.py         # Qdrant implementation
│
├── compose/              # Domain 5: Retrieval
│   ├── orchestrator.py   # Chain builder + executor
│   └── processors/
│       ├── search.py     # SearchProcessor
│       ├── discovery.py  # Siblings/Temporal/Genealogy
│       ├── graph.py      # GraphOperations
│       └── filter.py     # FilterProcessor
│
└── cli.py                # Thin router (~200 LOC)
```

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

## Storage Protocol

```python
class StorageProtocol(Protocol):
    """Backend interface (SQLite or Qdrant)"""
    def query(self, filters: dict, mode: str) -> List[Dict]: ...
    def get_siblings(self, chunk_id: str, **kwargs) -> List[Dict]: ...
    def get_temporal(self, chunk_id: str, **kwargs) -> List[Dict]: ...
    def get_genealogy(self, chunk_id: str, **kwargs) -> List[Dict]: ...

# Both backends implement same interface
store = SQLiteStore(project_root)  # or QdrantStore(project_root)

# Processors are backend-agnostic
processor = SiblingDiscovery(store)
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
