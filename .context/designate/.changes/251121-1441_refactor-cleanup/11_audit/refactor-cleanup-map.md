# IMEM v3 Refactor Cleanup Map

**Created:** 2025-11-18
**Purpose:** Architectural clarity - understand legacy confusion to avoid perpetuating it

---

## Executive Summary

**Status:** 74% to clean architecture
**Issue:** Clean abstractions exist (VectorStore protocol, processor chain, domains) but strangled by legacy entry points
**Decision Point:** Clean foundation before adding features (HNSW, discovery)

---

## 1. Legacy Confusion Points

### 1.1 CLI Command Duplication: Implementation Detail Leaked

**Current (Confusing):**
```bash
imem index develop              # Qdrant backend
imem index-metadata develop     # SQLite backend
```

**Problem:** Commands expose "which database" instead of "what kind of search"

**Should be:**
```bash
imem index develop --backend qdrant   # or auto from config
imem index develop --backend sqlite
# OR
imem index develop --mode semantic    # needs vectors
imem index develop --mode metadata    # no vectors
```

**Root cause:** Backend abstraction exists but CLI doesn't use it consistently

### 1.2 Parallel Code Paths (Old + New)

**Old Pattern (Still Active):**
- `ingest.py` (1106 lines) - EnhancedModularIngest, hardcoded QdrantClient
- `search.py` (587 lines) - ModularSearch, hardcoded QdrantClient
- `enhanced.py` (445 lines) - EnhancedQdrantSearch, hardcoded QdrantClient

**New Pattern (Refactored):**
- `storage/protocol.py` - VectorStore abstraction
- `storage/factory.py` - Backend factory
- `storage/sqlite_backend.py` - SQLite implementation
- `storage/qdrant_backend.py` - Qdrant implementation

**The Collision:**
```
CLI → DocumentIndexer (NEW) → EnhancedModularIngest (OLD) → Qdrant (HARDCODED)
```

New code wraps old code instead of replacing it.

### 1.3 Inconsistent Domain Naming

- Domain: `compile/` but CLI command: `index` (not `compile`)
- Domain: `compose/` but CLI commands: `compose`, `query-metadata`, `query` (fragmented)
- Intention unclear from naming

### 1.4 Legacy Exports Still Public API

**File:** `__init__.py`
```python
from .enhanced import EnhancedQdrantSearch      # OLD
from .search import ModularSearch               # OLD
from .ingest import EnhancedModularIngest       # OLD
```

Users importing from root get old code, not new abstraction.

---

## 2. Qdrant Pipeline Delineation

### 2.1 Hardcoded Qdrant (Cannot Remove)

**Level 1: Deep Hardcoding**
1. `ingest.py:57` - `client = QdrantClient(host="localhost", port=6334)`
2. `search.py:68` - `client = QdrantClient(...)`
3. `enhanced.py:32` - `client = QdrantClient(...)`

**Level 2: Architecture Hardcoding**
4. `cli/main.py:158` - `get_compile_controller()` only creates Qdrant store
5. `compile/indexer.py:89` - Calls `EnhancedModularIngest()` directly

### 2.2 Commands Requiring Qdrant

| Command | Requires Qdrant | Backend Agnostic |
|---------|-----------------|------------------|
| `index` | YES | NO |
| `index-metadata` | NO | YES |
| `index-conversations` | YES | NO |
| `query-metadata` | NO | YES |
| `compose` | Depends | Partial |

**Finding:** Only 2/9 commands are backend-agnostic.

### 2.3 The `use_vector` Flag: False Abstraction

**Protocol promises:**
```python
def search(query, use_vector=True):
    """If False, metadata search only"""
```

**Reality:**
- SQLite: Ignores flag (no vector support)
- Qdrant: Ignores flag (always uses vectors)
- Flag exists but has no consistent meaning

---

## 3. Quick Refactor Wins

| Work | Effort | Impact | Priority |
|------|--------|--------|----------|
| Fix CLI naming (add --backend flag) | 3h | HIGH | P1 |
| Remove old exports from __init__ | 1h | MED | P1 |
| Merge search.py + enhanced.py | 2h | MED | P2 |
| Bridge: indexer → factory (not old ingester) | 4h | HIGH | P1 |
| Metadata-only path via factory | 2h | MED | P2 |
| Delete EnhancedModularIngest | 1h | MED | P2 |

---

## 4. Current vs Intended Architecture

### Map A: Current Reality (Legacy + Refactor Mixed)

```
USER: imem index develop
  ↓
CLI: index_cmd()
  ↓
Composition Root: get_compile_controller()
  ↓ Returns: DocumentIndexer with Qdrant store
  ↓
DocumentIndexer.index_phase()
  ↓
EnhancedModularIngest() ← OLD CODE (hardcoded Qdrant)
  ↓
QdrantClient → Docker required


USER: imem index-metadata develop
  ↓
CLI: index_metadata_cmd()
  ↓
MarkdownParser (manual) ← BYPASSES DocumentIndexer
  ↓
SQLiteVectorStore → No Docker

⚠️ PROBLEM: Same work, different paths!
```

### Map B: Intended Clean Architecture

```
USER: imem index develop --backend [qdrant|sqlite|hnsw]
  ↓
CLI: index_cmd(backend)
  ↓
Composition Root: store = create_store(backend) ← FACTORY
  ↓
DocumentIndexer(store) ← BACKEND AGNOSTIC
  ↓
Parse → Chunk → store.upsert() ← UNIFIED
  ↓
        ┌─────┴──────┐
        ▼            ▼
    Qdrant      SQLite      (or HNSW, Pinecone, etc.)

✓ Single code path
✓ Backend selection via config/flag
✓ Easy to add new backends
```

---

## 5. What Blocks Clean State

**Why stuck with mixed legacy/new:**

1. **Entry Point Coupling**
   - `compile/indexer.py` calls `EnhancedModularIngest()` directly
   - Can't delete old code without rewriting indexer
   - New domain model depends on old implementation

2. **API Surface Leakage**
   - Old classes exported from `__init__.py`
   - External code may import old paths
   - Backward compatibility burden

3. **Command Duplication**
   - `index` vs `index-metadata` as separate implementations
   - CLI doesn't abstract backend selection
   - Can't unify until CLI refactored

**Missing from new architecture:**

1. Metadata-only ingestion through DocumentIndexer
2. Config-driven backend selection
3. Consistent `use_vector` flag semantics

---

## 6. Cleanup Phases (Recommended)

### Phase 1: Immediate (4 hours)
1. Fix CLI - add `--backend` flag to `index` command
2. Unify indexing - DocumentIndexer uses factory (not old ingester)
3. Clean exports - deprecate old classes in `__init__.py`

### Phase 2: Short-term (8 hours)
4. Delete old code - remove `EnhancedModularIngest`, `search.py`, `enhanced.py`
5. Implement SQLite as first-class (not "metadata fallback")
6. Config-driven backend selection

### Phase 3: Medium-term (4 hours)
7. Verify backward compatibility
8. Update architecture docs
9. Remove deprecated aliases

---

## 7. Key Decision: Clean Before Build

**Current inflection point:**

```
v2 (working, messy)
  → rushed migration
    → v3 (abstraction exists, half-connected)

Fork:
  Path A: Add features (HNSW, discovery) → build on shaky foundation
  Path B: Clean foundation NOW → features slot in cleanly
```

**Recommendation:** Clean first (4-6h), then HNSW (8h)

**Risk of not cleaning:**
- HNSW becomes third parallel path (more mess)
- Testing reveals "which pipe is correct?"
- Features compound technical debt

---

## Architectural North Star

**Use this map to guide future work:**

1. When adding HNSW: Use factory, respect protocol
2. When refactoring: Move toward Map B incrementally
3. Don't boil ocean: Legacy can coexist during migration
4. Rule: Don't make it worse

**Key principle:** New features should use clean abstraction, even if old code doesn't yet.

---

## Files Referenced

**Legacy (Still Used):**
- `src/imem/ingest.py` - EnhancedModularIngest (1106 lines)
- `src/imem/search.py` - ModularSearch (587 lines)
- `src/imem/enhanced.py` - EnhancedQdrantSearch (445 lines)

**New Pattern:**
- `src/imem/storage/protocol.py` - VectorStore abstraction
- `src/imem/storage/factory.py` - create_store()
- `src/imem/cli/commands.py` - Command definitions
- `src/imem/compile/indexer.py` - DocumentIndexer

**Collision Points:**
- `src/imem/cli/main.py:158` - Hardcoded Qdrant in composition root
- `src/imem/compile/indexer.py:89` - Calls old ingester
- `src/imem/__init__.py` - Exports old classes

---

## Status: 74% Complete

**What works:**
- ✅ Storage protocol abstraction
- ✅ Processor chain pattern
- ✅ Domain separation (compile, manage, compose)
- ✅ Resolution tables

**What's tangled:**
- ⚠️ Entry points use old code paths
- ⚠️ CLI exposes implementation details
- ⚠️ Backend selection not abstracted
- ⚠️ Legacy exports still public

**To reach 100%:**
Unify entry points → Clean CLI → Remove legacy → Test
