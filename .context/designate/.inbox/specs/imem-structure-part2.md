## Component Functions

### manage/nexus/
- **registry.py** - Tier 1: Cross-project source facts
- **qualification.py** - Tier 2: Per-project context
- **access.py** - Access event logging

### manage/mind/
- **schema_evolution.py** - Canonical type discovery
- **entity_resolution.py** - Keyword normalization
- **graph_runtime.py** - On-demand graph materialization
- **introspection.py** - System schema exposure
- **temporal_cortex.py** - Git diff validation

### use/modalities/
- **vector.py** - Semantic chunk retrieval
- **trace.py** - Linear conversation parsing
- **graph.py** - Topology queries
- **temporal.py** - Git timeline validation

### Entry Points
- **cli.py** - `imem compose`, `imem trace`, `imem introspect`
- **ingest.py** - Filesystem/git watcher, indexes artifacts

## Data Storage

```
.imem/
├── index/
│   ├── chunks.jsonl
│   ├── embeddings.db
│   └── metadata.jsonl
│
├── nexus/
│   ├── access.jsonl
│   ├── registry.jsonl
│   ├── qualification.jsonl
│   └── timeline.jsonl
│
├── mind/
│   ├── schema/
│   ├── entities/
│   ├── graphs/
│   └── validation/
│
└── trace/
    ├── sessions.jsonl
    └── conversations/
```

## Flow

```
ARTIFACT EXISTS
    ↓
ingest.py
    ↓
manage/nexus (wrap)
    ↓
manage/mind (enrich)
    ↓
use/modalities (query)
    ↓
SERVE
```
