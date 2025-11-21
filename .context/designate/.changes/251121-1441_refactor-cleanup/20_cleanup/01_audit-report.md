# IMEM v3 Codebase Audit Report

**Date:** 2025-11-18
**Purpose:** Forensic analysis of current state vs intended architecture
**Source:** Explore agent deep-dive into coupling, imports, and protocol usage

---

## Executive Summary

**Finding:** Codebase is 60% ready for extraction. Protocol-based architecture exists and works for SQLite path. Qdrant path still hardcoded through legacy classes. Discovery processors stubbed. Relationships table doesn't exist yet.

**Key Issue:** `compile/indexer.py` accepts VectorStore via injection but calls `EnhancedModularIngest()` instead—bypassing the abstraction entirely.

**Extraction Effort:** ~16 hours (2h move files, 4h rewrite indexer, 6h implement discovery, 4h testing)

---

## Section A: Current Reality (Line-Level Evidence)

### A1. Qdrant Import Map (8 Files with Direct Coupling)

| File | Line | Import | Usage |
|------|------|--------|-------|
| `ingest.py` | 23 | `from qdrant_client import QdrantClient` | Line 57: `self.client = QdrantClient(host="localhost", port=6334)` |
| `ingest.py` | 24 | `from qdrant_client.models import Distance, VectorParams` | Lines 229-254: Collection creation with Qdrant models |
| `enhanced.py` | 18 | `from qdrant_client import QdrantClient` | Line 32: `self.client = QdrantClient(host=host, port=port)` |
| `search.py` | 13 | `from qdrant_client import QdrantClient` | Line 68: `self.client = QdrantClient(...)` |
| `search.py` | 14 | `from qdrant_client.models import Filter, FieldCondition` | Filter construction for Qdrant API |
| `primitives/discovery.py` | 7 | `from qdrant_client import QdrantClient` | Lines 40, 43, 78: Direct scroll/retrieve calls |
| `storage/qdrant_backend.py` | 10-11 | `from qdrant_client import QdrantClient` | Lines 57, 63-68: Protocol implementation |
| `introspect.py` | 16 | `from qdrant_client import QdrantClient` | Line 40: Client instantiation |

**Impact:** 7 files bypass protocol abstraction. Only `storage/qdrant_backend.py` is legitimate (backend implementation).

---

### A2. Legacy Classes Still Active

| Class | File | LOC | Status | Called By |
|-------|------|-----|--------|-----------|
| `EnhancedModularIngest` | `ingest.py` | ~400 | ACTIVE | `compile/indexer.py:89` |
| `EnhancedQdrantSearch` | `enhanced.py` | ~200 | DORMANT | Not called by CLI |
| `ModularSearch` | `search.py` | ~300 | DORMANT | Not called by new code |
| Discovery primitives | `primitives/discovery.py` | ~300 | DORMANT | Not wired to protocol |

**Critical:** `EnhancedModularIngest` is the only legacy class actively used. Removing it breaks indexing.

---

### A3. The Indexing Path Coupling

**Evidence of hardcoded Qdrant in compilation:**

```python
# compile/indexer.py

Line 65:
from ..ingest import EnhancedModularIngest  # Direct import of legacy class

Line 89:
ingester = EnhancedModularIngest()  # Instantiation without protocol

Line 118:
ingester.ingest_markdown_chunked(md_file, phase=phase, ...)  # Legacy API

Lines 229-254:
from qdrant_client.models import Distance, VectorParams, HnswConfigDiff
ingester.client.create_collection(...)  # Direct Qdrant client access
```

**The Bug:**
```python
# Line 29: DocumentIndexer accepts store
def __init__(self, store: Optional[VectorStore] = None):
    self.store = store  # ← Saved but NEVER USED

# Line 89: Uses legacy instead
ingester = EnhancedModularIngest()  # ← Ignores self.store
```

**Composition Root Tries to Inject:**
```python
# cli/main.py line 158
def get_compile_controller(self):
    store = self.get_qdrant_store()  # ← Creates protocol backend
    return DocumentIndexer(store=store)  # ← Injects it
    # But DocumentIndexer never uses it!
```

---

### A4. Commands: Protocol vs Legacy

| Command | Entry Point | Path | Backend | Protocol? |
|---------|-------------|------|---------|-----------|
| `index` | `cli/commands.py:33` | `DocumentIndexer` → `EnhancedModularIngest` | Qdrant | ✗ Legacy |
| `index-metadata` | `cli/commands.py:85` | Manual parser → `SQLiteVectorStore.upsert()` | SQLite | ✓ Protocol |
| `query-metadata` | `cli/commands.py:150` | `SQLiteVectorStore.search()` | SQLite | ✓ Protocol |
| `compose` | `cli/commands.py:186` | `Orchestrator` → protocol | Either | ✓ Protocol |
| `stats-metadata` | `cli/commands.py:138` | `SQLiteVectorStore.get_stats()` | SQLite | ✓ Protocol |

**Finding:** 4/9 commands use protocol. Indexing commands still legacy.

---

### A5. Discovery Processors: Implemented in Storage, Stubbed in Compose

**Storage Layer (Works):**
```python
# storage/sqlite.py has working implementations:
- get_siblings() (line 245-316)
- get_genealogy() (line 318-379)
- get_temporal() (line 381-452)

# storage/sqlite_backend.py delegates to SQLiteStore
- All three methods functional via delegation
```

**Compose Layer (Stubbed):**
```python
# compose/orchestrator.py lines 57-76
if discovery_config.get('siblings'):
    raise NotImplementedError(
        "SiblingDiscovery processor not yet implemented..."
    )
# Same for temporal, genealogy
```

**Impact:** Discovery methods exist in storage but not exposed via compose pipeline. Can't use them from CLI.

---

### A6. What Works vs Broken

| Feature | Status | Evidence |
|---------|--------|----------|
| Metadata indexing (SQLite) | ✓ Works | `index-metadata` uses `SQLiteVectorStore.upsert()` |
| Metadata search | ✓ Works | `query-metadata` uses `VectorStore.search(use_vector=False)` |
| Qdrant indexing | ✓ Works | `index` uses legacy `EnhancedModularIngest` |
| Spatial discovery (SQL) | ✓ Works | `SQLiteStore.get_siblings()` functional |
| Discovery in compose | ✗ Stubbed | Orchestrator raises NotImplementedError |
| Qdrant discovery | ✗ Missing | `QdrantVectorStore` has no discovery methods |
| Relationships table | ✗ Missing | No schema, discovery uses metadata inference |

---

## Section B: Files to Move to `legacy/v2/`

### B1. Primary Candidates (High Coupling)

| File | Size | Coupling Evidence | Keep or Move? |
|------|------|-------------------|---------------|
| `ingest.py` | ~400 LOC | Line 23: QdrantClient import<br>Line 57: Hardcoded host/port<br>Called by: `indexer.py:89` | **MOVE** |
| `enhanced.py` | ~200 LOC | Line 18: QdrantClient import<br>Line 32: Hardcoded connection<br>Not called by CLI | **MOVE** |
| `search.py` | ~300 LOC | Line 13: QdrantClient import<br>Line 68: Hardcoded connection<br>Parallel to SearchProcessor | **MOVE** |
| `primitives/discovery.py` | ~300 LOC | Line 7: QdrantClient import<br>All functions Qdrant-specific<br>Not called via protocol | **MOVE** |
| `qdrant_service.py` | ~50 LOC | Service management (Docker)<br>Qdrant-specific | **MOVE** |

### B2. Do NOT Move (Protocol Implementations)

| File | Why Keep |
|------|----------|
| `storage/qdrant_backend.py` | Legitimate protocol implementation (uses QdrantClient correctly) |
| `storage/sqlite_backend.py` | Protocol implementation, works |
| `storage/protocol.py` | The abstraction itself |
| `storage/factory.py` | Backend selection logic |

---

### B3. Import Dependencies

**Files that import legacy classes:**

```python
# compile/indexer.py
Line 65: from ..ingest import EnhancedModularIngest

# cli/commands.py
Line 268: from ..service import QdrantService  # Only for service_cmd

# __init__.py (public exports)
from .enhanced import EnhancedQdrantSearch
from .search import ModularSearch
from .ingest import EnhancedModularIngest
```

**After moving to `legacy/v2/`, these imports break unless updated.**

---

## Section C: Features at Risk (What v2 Provides)

### C1. Rich Capabilities in Legacy Code

**From `ingest.py`:**
- Structured field detection (lines 734-741):
  - `has_rationale`, `has_solution`, `has_alternatives`
  - `has_benefits`, `has_drawbacks`, `has_approach`, `has_context`
- Header hierarchy extraction (lines 720-732)
- Session linking for conversations (lines 851-937)

**From `enhanced.py`:**
- Timestamp parsing (6 different formats, lines 123-144)
- Hybrid scoring: 0.6×similarity + 0.4×recency (lines 255-281)
- Multi-model support (MiniLM, MPNet, E5-Large detection)

**From `search.py`:**
- Multi-term boolean search (AND/OR operators)
- Per-term scoring and tracking

**From `primitives/discovery.py`:**
- Semantic + temporal hybrid in `get_temporal()`
- Cross-collection genealogy lookup
- Quality filters (`has_rationale=True`)

### C2. Missing from SQLite Path

| Feature | v2 (Qdrant) | v3 (SQLite) | Gap |
|---------|-------------|-------------|-----|
| Structured field storage | ✓ Boolean flags in payload | ✗ Not in schema | Need columns |
| Hybrid scoring | ✓ 0.6×sim + 0.4×recency | ✗ Recency only | Need formula |
| Multi-term search | ✓ AND/OR operators | ✗ Simple filters | Need logic |
| Cross-collection lookup | ✓ Routes to conversation collection | ✗ Single table | Need table |
| Semantic temporal | ✓ Vector + timestamp | ✗ Timestamp only | Need vectors |

---

## Section D: Extraction Validation

### D1. Phase 1 Checklist (File Moves)

**Create structure:**
```bash
mkdir -p src/imem/legacy/v2
```

**Move files:**
```bash
mv src/imem/ingest.py src/imem/legacy/v2/
mv src/imem/search.py src/imem/legacy/v2/
mv src/imem/enhanced.py src/imem/legacy/v2/
mv src/imem/primitives/discovery.py src/imem/legacy/v2/
mv src/imem/qdrant_service.py src/imem/legacy/v2/
```

**Update imports:**
- `compile/indexer.py:65` → `from ..legacy.v2.ingest import EnhancedModularIngest`
- `cli/commands.py:268` → `from ..legacy.v2.qdrant_service import QdrantService`
- `__init__.py` → Remove all legacy exports

**Create documentation:**
- `legacy/v2/README.md` documenting:
  - What v2 could do
  - Why it's isolated
  - How to reference as spec

**Validation:**
```bash
# Should still work:
imem init
imem index-metadata develop --limit 5
imem query-metadata --phase develop
imem index develop  # Uses legacy from new location

# Should have no imports from legacy in main code (except indexer.py with TODO)
grep -r "from.*ingest import" src/imem/*.py  # Should only show indexer.py
```

---

### D2. Phase 2 Checklist (Protocol Adoption)

**Fix DocumentIndexer:**
```python
# compile/indexer.py line 89-122
# BEFORE:
ingester = EnhancedModularIngest()
for md_file in md_files:
    ingester.ingest_markdown_chunked(md_file, phase=phase, ...)

# AFTER:
parser = MarkdownParser()
for md_file in md_files:
    chunks = parser.parse_file(md_file)
    self.store.upsert(chunks)  # Use injected store
```

**Validation:**
```bash
# Should work without EnhancedModularIngest:
imem index develop --backend sqlite
imem index develop --backend qdrant

# Should fail with clear error:
grep -r "EnhancedModularIngest" src/imem/compile/  # Should return nothing
```

---

### D3. Phase 3 Checklist (Discovery Wiring)

**Implement discovery on QdrantVectorStore:**
```python
# storage/qdrant_backend.py
def get_siblings(self, chunk_id, limit=5):
    # Copy logic from legacy/v2/discovery.py
    # Adapt to protocol signature
    ...

def get_genealogy(self, chunk_id, depth=2):
    ...

def get_temporal(self, chunk_id, window_days=7):
    ...
```

**Wire into orchestrator:**
```python
# compose/orchestrator.py lines 57-76
# BEFORE:
if discovery_config.get('siblings'):
    raise NotImplementedError(...)

# AFTER:
if discovery_config.get('siblings'):
    processors.append(SiblingDiscoveryProcessor(store))
```

**Validation:**
```bash
# Discovery should work:
imem compose '{
  "search": {"mode": "metadata"},
  "discovery": {"relationships": ["spatial_proximity"]}
}'

# Should return results without NotImplementedError
```

---

## Section E: Gap Analysis

### E1. Architecture Gaps

| Component | Current | Intended | Severity | Effort |
|-----------|---------|----------|----------|--------|
| Indexing entry | Hardcoded `EnhancedModularIngest` | Uses `store.upsert()` | CRITICAL | 4h |
| Discovery processors | Stubbed (NotImplementedError) | Calls store methods | HIGH | 6h |
| Qdrant discovery | Not implemented | Protocol-compliant methods | MEDIUM | 4h |
| Relationships table | Missing | Explicit graph edges | MEDIUM | 2h |
| Backend selection | Composition root hardcoded | Factory-based runtime choice | HIGH | 2h |

**Total effort:** ~18 hours

---

### E2. Coupling Map

**Level 1 (Surface):**
- `__init__.py` exports legacy classes

**Level 2 (Entry Points):**
- `cli/main.py:158` composition root hardcodes Qdrant
- `compile/indexer.py:89` calls legacy directly

**Level 3 (Deep):**
- `ingest.py:57` QdrantClient initialization
- `search.py:68` QdrantClient initialization
- `enhanced.py:32` QdrantClient initialization

**Breaking the coupling requires:**
1. Surface: Remove exports (1h)
2. Entry: Rewrite indexer to use protocol (4h)
3. Deep: Move to legacy/ (2h)

---

## Section F: Timeline and Risk

### F1. Extraction Timeline

| Phase | Description | Effort | Risk |
|-------|-------------|--------|------|
| **Phase 1** | Move files to `legacy/v2/` | 2h | LOW |
| **Phase 2** | Rewrite indexer protocol usage | 4h | MEDIUM |
| **Phase 3** | Implement discovery | 6h | MEDIUM |
| **Phase 4** | Integration testing | 4h | LOW |
| **Total** | Complete extraction | 16h | - |

### F2. Risk Assessment

**LOW RISK:**
- Protocol abstraction exists and works (proven by SQLite path)
- Factory pattern functional
- Clear boundaries between domains

**MEDIUM RISK:**
- Indexer rewrite touches compilation path (core functionality)
- Discovery implementation requires understanding Qdrant patterns

**MITIGATION:**
- Keep legacy code as reference
- Test SQLite path first (simpler, no Docker)
- Incremental validation after each phase

---

## Section G: Success Criteria

**After Phase 1 (Isolation):**
- [ ] `legacy/v2/` directory exists with 5 files
- [ ] No active imports from legacy except `indexer.py` (with TODO)
- [ ] All commands still work
- [ ] Can reference legacy code without affecting main codebase

**After Phase 2 (Protocol Adoption):**
- [ ] `compile/indexer.py` uses `self.store.upsert()`
- [ ] No imports of `EnhancedModularIngest` in active code
- [ ] `imem index develop --backend sqlite` works
- [ ] `imem index develop --backend qdrant` works

**After Phase 3 (Discovery):**
- [ ] `QdrantVectorStore.get_siblings()` implemented
- [ ] Orchestrator calls discovery processors (no NotImplementedError)
- [ ] Compose with discovery config returns results
- [ ] All backends support discovery primitives

**Final State:**
- [ ] All tests pass
- [ ] Zero direct QdrantClient imports outside `storage/qdrant_backend.py`
- [ ] Single indexing code path
- [ ] Backend selection via config/factory
- [ ] Discovery works end-to-end

---

## Appendix: Key Line References

**Critical coupling points:**
- `compile/indexer.py:65` - Legacy import
- `compile/indexer.py:89` - Hardcoded instantiation
- `compile/indexer.py:229-254` - Direct Qdrant API
- `cli/main.py:158` - Composition root
- `compose/orchestrator.py:57-76` - Discovery stubs

**Working protocol examples:**
- `cli/commands.py:85` - SQLite metadata indexing
- `cli/commands.py:153` - VectorStore.search() usage
- `storage/sqlite_backend.py:64-119` - Protocol implementation

**Reference implementations:**
- `storage/protocol.py` - Interface definition
- `storage/factory.py` - Backend selection
- `storage/sqlite.py:245-452` - Discovery methods
