# IMEM v3 Codebase Audit Report

**Date:** 2025-11-18
**Purpose:** Forensic analysis of current state vs intended architecture
**Source:** Explore agent deep-dive into coupling, imports, and protocol usage

---

## Executive Summary

**Finding:** Protocol abstraction works but carries confused naming from Qdrant legacy. Discovery methods (`get_siblings/genealogy/temporal`) are simple SQL queries wrapped unnecessarily—inherited vague names that don't describe relationships.

**Key Issue:** False abstractions over 1-line queries. Qdrant can't actually implement these (no file_path/timestamp indexing) but pretends to via semantic search hacks. SQLite has same confused names.

**Cleanup Effort:** ~2 hours (1h quarantine legacy, 1h delete confused wrappers, use raw SQL when needed)

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

### A5. Confused Discovery Wrappers (Delete These)

**Both backends have vague names inherited from Qdrant:**
```python
# storage/sqlite.py AND storage/qdrant_backend.py
- get_siblings() (lines 245-316)      # Vague: siblings of what?
- get_genealogy() (lines 318-379)     # Misleading: returns session chunks, not lineage
- get_temporal() (lines 381-452)      # Vague: temporal what?
```

**What they actually do (SQLite):**
```python
# get_siblings = SELECT * FROM chunks WHERE file_path = ? AND id != ?
# get_genealogy = SELECT * FROM chunks WHERE session_id = ?
# get_temporal = SELECT * FROM chunks WHERE timestamp BETWEEN ? AND ?
```

**Problem:** Simple 1-line queries wrapped in confusing abstraction. Qdrant can't actually do these (no file_path/timestamp indexes), fakes them with semantic similarity.

**Solution:** Delete wrappers. Query SQL directly when needed. Don't wrap until 2-3 usage patterns prove abstraction needed (YAGNI).

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

### B2. Methods to DELETE (Not Move)

**Remove from VectorStore protocol:**
```python
# storage/protocol.py - DELETE these method definitions:
get_siblings()      # Lines ~118-137
get_genealogy()     # Lines ~139-157
get_temporal()      # Lines ~159-177
```

**Remove from both backend implementations:**
```python
# storage/sqlite.py - DELETE
get_siblings()      # Lines 245-316
get_genealogy()     # Lines 318-379
get_temporal()      # Lines 381-452

# storage/qdrant_backend.py - DELETE (if they exist)
get_siblings()
get_genealogy()
get_temporal()
```

**Why delete:** These wrap 1-line SQL queries. Use `db.execute("SELECT...")` directly when needed. Don't abstract until pattern emerges from real usage.

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
| Legacy quarantine | Files in active codebase | Move to `legacy/v2/` | HIGH | 1h |
| Confused wrappers | `get_siblings/genealogy/temporal` | DELETE, query SQL directly | HIGH | 1h |
| Discovery stubs | `NotImplementedError` in orchestrator | DELETE stubs (YAGNI) | LOW | 15min |

**Total effort:** ~2 hours

**NOT doing:**
- ❌ Rewriting indexer (can do later if needed)
- ❌ Implementing discovery processors (wait for real usage patterns)
- ❌ Adding methods to Qdrant (it can't do these honestly)

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
