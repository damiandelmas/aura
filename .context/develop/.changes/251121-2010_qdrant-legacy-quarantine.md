---
schema_version: "v3_adaptive"
type: "refactor.legacy-isolation"
status: "completed"
keywords: "qdrant legacy quarantine protocol cleanup yagni discovery"
timestamp: "2025-11-21T20:10:00-0700"
session_id: "f3dc6a97-33d9-4191-a55a-3531cdda76d0"
---

# Qdrant Legacy Quarantine and Discovery Cleanup

## Request
> "Read all documents. Execute plan.md"

## Overview
Executed 2-phase cleanup plan isolating Qdrant-hardcoded legacy code and removing confused discovery wrappers. Moved 5 files to `legacy/v2/`, updated imports to use legacy path, cleaned protocol of false abstractions (`get_siblings/genealogy/temporal`). Architecture now SQL-first with explicit YAGNI guidance for discovery queries.

## Decisions

### Quarantine Over Delete
- **Context**: Legacy files (`ingest.py`, `search.py`, `enhanced.py`) still have working import chain via `indexer.py`
- **Solution**: Move to `legacy/v2/` with updated imports rather than delete
- **Rationale**: Preserves v2 capabilities as specification; `compile/indexer.py` still needs `EnhancedModularIngest`

### Delete Discovery Wrappers
- **Context**: `get_siblings/genealogy/temporal` were 1-line SQL queries wrapped in confusing abstraction
- **Solution**: Delete from protocol and all backends, replace with YAGNI comment
- **Rationale**: Qdrant can't implement these honestly (fakes with semantic similarity). Query SQL directly when patterns emerge.

## Implementation

### File Moves
```
src/imem/
├── legacy/v2/           # NEW: quarantined
│   ├── ingest.py        # EnhancedModularIngest
│   ├── search.py        # ModularSearch
│   ├── enhanced.py      # EnhancedQdrantSearch
│   ├── qdrant_service.py
│   ├── discovery.py     # from primitives/
│   └── README.md        # v2 spec documentation
```

### Import Updates
```python
# compile/indexer.py
# TODO: Remove EnhancedModularIngest dependency - use self.store.upsert() via protocol
from ..legacy.v2.ingest import EnhancedModularIngest

# service/__init__.py
from ..legacy.v2.qdrant_service import QdrantService
```

### Protocol Cleanup
```python
# storage/protocol.py - REMOVED
# get_siblings(), get_genealogy(), get_temporal()

# REPLACED WITH:
# Discovery: Query SQL directly when needed. Don't wrap until usage patterns emerge.
# Examples:
#   SELECT * FROM chunks WHERE file_path = ?  -- same document
#   SELECT * FROM chunks WHERE session_id = ? -- same session
```

## Patterns

### YAGNI Discovery
- **Pattern**: Don't wrap simple queries until 2-3 usage patterns prove abstraction needed
- **When**: Building discovery/relationship queries
- **Approach**: Write explicit SQL, track patterns, abstract only when repetition emerges
- **Benefit**: Clear semantics, no confused naming inherited from wrong domain

## Audit

### Created
- `legacy/v2/__init__.py` - Package marker
- `legacy/__init__.py` - Package marker
- `legacy/v2/README.md` - v2 capabilities spec

### Modified
- `compile/indexer.py` - Import path to `legacy.v2.ingest`
- `service/__init__.py` - Import path to `legacy.v2.qdrant_service`
- `__init__.py` - Removed legacy exports, now exports only `SimpleRegistry`, `VectorStore`, `create_store`
- `storage/protocol.py` - Removed discovery methods
- `storage/sqlite.py` - Removed discovery methods (~200 LOC)
- `storage/sqlite_backend.py` - Removed discovery methods (~150 LOC)
- `storage/qdrant_backend.py` - Removed discovery methods (~140 LOC)
- `compose/orchestrator.py` - Removed NotImplementedError stubs

### Removed
- Discovery method implementations from all backends
- Legacy class exports from package `__init__.py`
