# Plan

**Total Estimate:** 2 hours

---

## Phase 1: Quarantine Legacy (1h)

- [ ] **1.1** Move files to `legacy/v2/`
  - `ingest.py`
  - `search.py`
  - `enhanced.py`
  - `qdrant_service.py`
  - `primitives/discovery.py`

- [ ] **1.2** Update import in `compile/indexer.py`
  - FROM: `from ..ingest import EnhancedModularIngest`
  - TO: `from ..legacy.v2.ingest import EnhancedModularIngest`

- [ ] **1.3** Update import in `cli/commands.py` (service command)
  - FROM: `from ..service import QdrantService`
  - TO: `from ..legacy.v2.qdrant_service import QdrantService`

- [ ] **1.4** Clean `__init__.py` exports
  - REMOVE: `EnhancedQdrantSearch`, `ModularSearch`, `SearchConfig`, `EnhancedModularIngest`

- [ ] **1.5** Create `legacy/v2/README.md`

- [ ] **1.6** Validate Phase 1
  - `ls legacy/v2/` shows 5 files + README
  - `imem index-metadata develop --limit 5` works
  - `imem query-metadata --phase develop` works

---

## Phase 2: Delete Confused Wrappers (1h)

- [ ] **2.1** Remove from `storage/protocol.py`
  - DELETE: `get_siblings()`, `get_genealogy()`, `get_temporal()`

- [ ] **2.2** Delete from `storage/sqlite.py`
  - DELETE: `get_siblings()`, `get_genealogy()`, `get_temporal()`

- [ ] **2.3** Delete from `storage/sqlite_backend.py`
  - DELETE: `get_siblings()`, `get_genealogy()`, `get_temporal()`

- [ ] **2.4** Delete from `storage/qdrant_backend.py`
  - DELETE: `get_siblings()`, `get_genealogy()`, `get_temporal()`

- [ ] **2.5** Clean `compose/orchestrator.py`
  - REPLACE: NotImplementedError stubs
  - WITH: Comment "Discovery: Query SQL directly when needed"

- [ ] **2.6** Validate Phase 2
  - `grep "get_siblings\|get_genealogy\|get_temporal" storage/*.py` returns nothing
  - `imem query-metadata --phase develop` still works

---

## Validation Checklist

- [ ] No legacy imports except via `legacy.v2` prefix
- [ ] `__init__.py` exports only protocol classes
- [ ] Protocol has no discovery methods
- [ ] All backends have no discovery methods
- [ ] Orchestrator has no NotImplementedError stubs
- [ ] SQLite path commands work end-to-end
