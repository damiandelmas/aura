# Current State (Post Phase 1-2)

**Date:** 2025-11-21
**Status:** 40% complete - Legacy quarantined, wrappers deleted, but Qdrant still in active pipeline

---

## What's Done

### Phase 1: Quarantine Legacy ✓
```
legacy/v2/
├── __init__.py
├── README.md
├── discovery.py
├── enhanced.py
├── ingest.py
├── qdrant_service.py
└── search.py
```

### Phase 2: Delete Confused Wrappers ✓
- Removed `get_siblings/genealogy/temporal` from protocol
- Deleted implementations from all backends
- Replaced orchestrator stubs with YAGNI comment

### Protocol Now Clean
```python
# storage/protocol.py - ONLY these methods:
upsert()
search()
get_by_ids()
get_stats()
collection_exists()
delete_collection()
```

---

## What Remains (Qdrant Contamination)

### Critical: Indexer Still Uses Legacy

**File:** `compile/indexer.py`
```python
Line 66:  from ..legacy.v2.ingest import EnhancedModularIngest
Line 90:  ingester = EnhancedModularIngest()  # Bypasses protocol!
Line 231: from qdrant_client.models import Distance, VectorParams, HnswConfigDiff
```

**Impact:** `imem index` command only works with Qdrant

---

### Critical: Qdrant Backend Still Exists

**File:** `storage/qdrant_backend.py` (297 lines)
- Full Qdrant implementation
- Should be DELETED (not "optional backend")

**File:** `storage/factory.py`
```python
Line 71-78: Still offers 'qdrant' as backend option
```

**File:** `storage/__init__.py`
```python
Line 13: from .qdrant_backend import QdrantVectorStore
Line 23: Exports QdrantVectorStore
```

---

### Critical: Introspection Hardcoded

**File:** `introspect.py`
```python
Line 16:  from qdrant_client import QdrantClient
Line 40:  client = QdrantClient(host=config.qdrant_host, port=config.qdrant_port)
```

**Impact:** `imem introspect` only works with Qdrant

---

### High: Config Still Has Qdrant

**File:** `config.py`
```python
Line 81: qdrant_port: int = int(os.getenv('IMEM_QDRANT_PORT', '6334'))
Line 82: qdrant_host: str = os.getenv('IMEM_QDRANT_HOST', 'localhost')
Line 83: qdrant_timeout: int = int(os.getenv('IMEM_QDRANT_TIMEOUT', '2'))
```

---

### High: CLI Composition Root

**File:** `cli/main.py`
```python
Line 27:  qdrant_store: Optional[VectorStore] = None
Line 129-147: get_qdrant_store() method
Line 157-158: get_compile_controller() uses Qdrant
```

---

### Medium: Duplicate Commands

```bash
imem index           → Qdrant only (via legacy)
imem index-metadata  → SQLite only (protocol)
```

Should be ONE command: `imem index` → SQLite

---

### Medium: Service Command

**File:** `cli/commands.py`
```python
Line 264-285: service command manages Qdrant Docker
Line 268: from ..service import QdrantService
```

---

## Contamination Summary

| File | Lines | Issue | Priority |
|------|-------|-------|----------|
| `compile/indexer.py` | 66, 90, 231 | Uses legacy + Qdrant models | **CRITICAL** |
| `introspect.py` | 16, 40+ | Hardcoded QdrantClient | **CRITICAL** |
| `cli/main.py` | 27, 129-158 | Qdrant store methods | **CRITICAL** |
| `storage/qdrant_backend.py` | entire | Should be deleted | HIGH |
| `storage/factory.py` | 71-78 | Offers Qdrant option | HIGH |
| `storage/__init__.py` | 13, 23 | Exports QdrantVectorStore | HIGH |
| `config.py` | 81-83 | Qdrant env vars | HIGH |
| `cli/commands.py` | 264-285 | Service command | MEDIUM |

---

## Commands Status

| Command | Backend | Works? | Path |
|---------|---------|--------|------|
| `index` | Qdrant | ✓ (if Docker) | legacy/v2/ingest.py |
| `index-metadata` | SQLite | ✓ | protocol |
| `query-metadata` | SQLite | ✓ | protocol |
| `compose` | SQLite | ✓ | protocol |
| `stats-metadata` | SQLite | ✓ | protocol |
| `introspect` | Qdrant | ✓ (if Docker) | hardcoded |
| `service` | Qdrant | ✓ | legacy/v2/qdrant_service.py |

**5/7 commands work with SQLite. 2 require Qdrant.**

---

## Codebase Shape

```
src/imem/
├── __init__.py              ✓ Clean (protocol exports only)
├── config.py                ✗ Has Qdrant vars
├── introspect.py            ✗ Hardcoded QdrantClient
│
├── cli/
│   ├── main.py              ✗ Has get_qdrant_store()
│   └── commands.py          ✗ Duplicate commands, service cmd
│
├── compile/
│   └── indexer.py           ✗ Uses legacy/v2/ingest.py
│
├── storage/
│   ├── protocol.py          ✓ Clean
│   ├── factory.py           ✗ Offers Qdrant backend
│   ├── sqlite.py            ✓ Clean
│   ├── sqlite_backend.py    ✓ Clean
│   └── qdrant_backend.py    ✗ Should be deleted
│
├── compose/                 ✓ Clean
├── core/                    ✓ Clean
├── manage/                  ✓ Clean
├── parse/                   ✓ Clean
│
└── legacy/v2/               ✓ Quarantined (reference only)
```

---

## Next Steps (Phase 3-6)

1. **Phase 3: Rip Out Indexer** (2h)
   - Rewrite `compile/indexer.py` to use `store.upsert()`
   - Create `compile/parser.py` (port from legacy)

2. **Phase 4: Delete Qdrant Backend** (1h)
   - Delete `storage/qdrant_backend.py`
   - Clean factory, exports, config

3. **Phase 5: Fix Introspection** (2h)
   - Rewrite to accept VectorStore

4. **Phase 6: Unify CLI** (1h)
   - Delete `index-metadata` (merge into `index`)
   - Remove Qdrant methods from main.py
   - Deprecate service command

---

## Validation Commands

```bash
# Current state checks:
grep -r "qdrant" src/imem/ | grep -v legacy | wc -l    # Should be 0 after cleanup
grep -r "QdrantClient" src/imem/ | grep -v legacy      # Should return nothing
python3 -c "from src.imem import *; print('OK')"       # Should work

# Command tests:
imem index-metadata develop --limit 5   # Works now
imem query-metadata --phase develop     # Works now
imem stats-metadata                     # Works now
```
