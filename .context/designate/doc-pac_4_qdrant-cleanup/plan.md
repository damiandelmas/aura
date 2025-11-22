# Plan: Complete Qdrant Removal

**Total Estimate:** 6 hours

**Goal:** SQLite is THE store. HNSW for vectors. Qdrant REMOVED from active code.

---

## COMPLETED: Phase 1 & 2 (doc-pac_3)

- [x] **1.1-1.6** Quarantine legacy files to `legacy/v2/`
- [x] **2.1-2.6** Delete confused wrappers (`get_siblings/genealogy/temporal`)

**Result:** Legacy isolated, protocol cleaned. BUT indexer still uses Qdrant.

---

## Phase 3: Rip Out Indexer Coupling (2h)

- [ ] **3.1** Rewrite `compile/indexer.py`
  - DELETE: `from ..legacy.v2.ingest import EnhancedModularIngest`
  - DELETE: `from qdrant_client.models import Distance, VectorParams, HnswConfigDiff`
  - DELETE: `_ensure_collections_exist()` method (lines 216-256)
  - REWRITE: `index_phase()` to use `self.store.upsert()` directly
  - REWRITE: `index_conversations()` to use `self.store.upsert()` directly

- [ ] **3.2** Create `compile/parser.py` (extract from legacy)
  - Port markdown parsing logic from `legacy/v2/ingest.py`
  - Pure function: `parse_markdown(file_path) -> List[Chunk]`
  - No Qdrant imports, no storage coupling

- [ ] **3.3** Validate Phase 3
  - `grep "qdrant" compile/*.py` returns nothing
  - `imem index develop --limit 5` works with SQLite

---

## Phase 4: Remove Qdrant Backend (1h)

- [ ] **4.1** Delete `storage/qdrant_backend.py`

- [ ] **4.2** Clean `storage/factory.py`
  - REMOVE: Qdrant backend option
  - DEFAULT: SQLite (with optional HNSW)

- [ ] **4.3** Clean `storage/__init__.py`
  - REMOVE: `QdrantVectorStore` export

- [ ] **4.4** Clean `config.py`
  - REMOVE: `qdrant_host`, `qdrant_port`, `qdrant_timeout`

- [ ] **4.5** Validate Phase 4
  - `grep -r "qdrant" storage/*.py` returns nothing
  - `grep -r "QdrantVectorStore" src/imem/` returns nothing

---

## Phase 5: Fix Introspection (2h)

- [ ] **5.1** Rewrite `introspect.py`
  - REMOVE: `from qdrant_client import QdrantClient`
  - ACCEPT: `VectorStore` parameter instead of hardcoded client
  - All functions work with SQLite backend

- [ ] **5.2** Validate Phase 5
  - `grep "qdrant" introspect.py` returns nothing
  - `imem introspect` works with SQLite

---

## Phase 6: Unify CLI Commands (1h)

- [ ] **6.1** Delete duplicate commands
  - REMOVE: `index-metadata` command (merge into `index`)
  - KEEP: `index` command (now uses SQLite by default)

- [ ] **6.2** Clean `cli/main.py`
  - REMOVE: `get_qdrant_store()` method
  - REMOVE: `qdrant_store` from AppState
  - UPDATE: `get_compile_controller()` to use SQLite store

- [ ] **6.3** Deprecate service command
  - REMOVE or mark deprecated: `service` command (Qdrant Docker management)

- [ ] **6.4** Validate Phase 6
  - `imem --help` shows unified commands
  - `imem index develop` works (SQLite)
  - `imem query "text"` works (SQLite)

---

## Validation Checklist (Final)

- [ ] `grep -r "qdrant" src/imem/ | grep -v legacy` returns NOTHING
- [ ] `grep -r "QdrantClient" src/imem/ | grep -v legacy` returns NOTHING
- [ ] ONE `index` command (not `index` + `index-metadata`)
- [ ] `config.py` has no Qdrant settings
- [ ] `imem index develop --limit 5` works
- [ ] `imem query-metadata --phase develop` works
- [ ] `imem introspect` works

---

## Architecture After Cleanup

```
SQLite (PRIMARY - ALL data):
├── chunks table (id, content, phase, section_type, timestamp, ...)
├── resolution tables (phase_variations, entity_variations)
└── relationships table (future: graph edges)

HNSW (OPTIONAL - vectors only):
├── Embedded in SQLite via sqlite-vss or similar
└── Stores: chunk_id + vector (nothing else)

Qdrant:
└── REMOVED from active code
└── Reference only in legacy/v2/
```

---

## NOT Doing

- ❌ Keeping Qdrant as "alternative backend"
- ❌ Dual indexing paths
- ❌ Metadata in vector store
