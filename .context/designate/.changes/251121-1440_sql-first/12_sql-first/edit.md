## ✅ Bug #2: O(n²) Loop CONFIRMED

**Lines 132-155**: For EACH ID, queries ENTIRE corpus, then filters in Python.

**Performance:**
- 10 IDs × 10k chunks = 100k comparisons
- 100 IDs × 10k chunks = 1M comparisons

**This is TERRIBLE.**

**You're right — Bug #2 exists and is critical.**

---

# Agreed with Modifications

## Your 6 Tasks Are Correct

**✅ Task 1: Fix factory call** (15 min)  
**✅ Task 2: Fix get_by_ids O(n²)** (20 min)  
**✅ Task 3: Discovery processor errors** (10 min)  
**✅ Task 4: Ranking scorer** (30 min)  
**✅ Task 5: Manual smoke tests** (20 min)  
**✅ Task 6: Basic integration test** (10 min)

**Total: 1 hour 45 min** (your estimate: 1.5 hours)

---

## Execution Order (Adjusted)

### **Phase 1: Critical Fixes (45 min)**

1. **Bug #2: get_by_ids() O(n²)** (20 min) **← DO FIRST**
   - Most critical performance bug
   - Blocks HNSW backend (relies on get_by_ids)
   - Blocks multi-phase ranking (relies on get_by_ids)

2. **Bug #1: Factory signature** (15 min)
   - Breaks Qdrant backend initialization
   - Easy fix (unwrap dict → kwargs)

3. **Bug #3: Discovery warnings** (10 min)
   - Replace `logger.warning` → `raise NotImplementedError`
   - Clear error message

---

### **Phase 2: Feature Completion (30 min)**

4. **Ranking scorer** (30 min)
   - Implement metadata recency scorer
   - Leave others as identity (with TODOs)

---

### **Phase 3: Validation (30 min)**

5. **Smoke tests** (20 min)
   - Test 3 CLI commands manually
   - Verify no crashes

6. **Integration test** (10 min)
   - Create `tests/test_phase3_smoke.py`
   - Test factory, indexer, compose

---

## Implementation Details

### **Bug #2 Fix (Priority 1)**

**File:** `storage/sqlite_backend.py:121-155`

**Replace:**
```python
def get_by_ids(self, ids: List[str]) -> List[SearchResult]:
    """O(n²) - queries entire corpus for each ID"""
    results = []
    for chunk_id in ids:
        raw_results = self.store.query(filters={}, limit=1)  # ← SLOW
        matching = [r for r in raw_results if r['id'] == chunk_id]  # ← O(n)
        ...
```

**With:**
```python
def get_by_ids(self, ids: List[str]) -> List[SearchResult]:
    """O(n) - single SQL WHERE IN query"""
    if not ids:
        return []
    
    # Build SQL WHERE IN clause
    placeholders = ','.join('?' * len(ids))
    query = f"""
        SELECT 
            id, content, file_path, phase, section_type, 
            section_name, timestamp, session_id, metadata
        FROM chunks
        WHERE id IN ({placeholders})
    """
    
    conn = self.store.db  # Access underlying SQLite connection
    cursor = conn.execute(query, ids)
    rows = cursor.fetchall()
    
    # Convert to SearchResult
    results = []
    for row in rows:
        results.append(SearchResult(
            id=row['id'],
            content=row['content'] or '',
            score=1.0,
            metadata={
                'file_path': row['file_path'],
                'phase': row['phase'],
                'section_type': row['section_type'],
                'section_name': row['section_name'],
                'timestamp': row['timestamp'],
                'session_id': row['session_id'],
                **json.loads(row['metadata'] or '{}')
            }
        ))
    
    return results
```

**Performance:**
- Before: O(n × m) where n = IDs, m = corpus size
- After: O(n) - single query

---

### **Bug #1 Fix**

**File:** `cli/main.py:140-147`

**Replace:**
```python
self.state.qdrant_store = create_store(
    'qdrant',
    {  # ← WRONG: Passing dict as positional arg
        'project_root': str(project_root),
        'host': self.config.qdrant_host,
        'port': self.config.qdrant_port
    }
)
```

**With:**
```python
self.state.qdrant_store = create_store(
    backend='qdrant',
    project_root=project_root,  # ← CORRECT: kwargs
    collection_name='docs_default',
    host=self.config.qdrant_host,
    port=self.config.qdrant_port
)
```

---

### **Bug #3 Fix**

**File:** `compose/orchestrator.py:58-73`

**Replace:**
```python
if discovery_config.get('siblings'):
    logger.warning("SiblingDiscovery not yet implemented")
```

**With:**
```python
if discovery_config.get('siblings'):
    raise NotImplementedError(
        "SiblingDiscovery processor not yet implemented. "
        "Remove 'discovery.siblings' from config or implement processor at "
        "imem/compose/processors/discovery.py"
    )
```

---

### **Feature: Ranking Scorer**

**File:** `compose/orchestrator.py:94-108`

**Add:**
```python
def _get_scorer(name: str) -> Callable:
    """Map phase name to scorer function"""
    
    if name == 'recency':
        def recency_scorer(results):
            """Sort by timestamp (most recent first)"""
            return sorted(
                results,
                key=lambda r: r.get('timestamp', ''),
                reverse=True
            )
        return recency_scorer
    
    elif name == 'metadata':
        # Identity scorer (no reordering)
        return lambda results: results
    
    elif name == 'authority':
        # TODO: Implement PageRank or reference counting
        logger.warning("Authority scorer not yet implemented, using identity")
        return lambda results: results
    
    else:
        raise ValueError(f"Unknown scorer: {name}. Available: recency, metadata, authority")
```

---

## Smoke Test Commands

```bash
cd /home/axp/projects/fleet/hangar/code/aura/worktrees/sql-first/imem

# Test 1: Index (should work)
python src/imem/cli_new.py index develop --limit 5

# Test 2: Query metadata (should work)
python src/imem/cli_new.py query-metadata --phase develop --limit 5

# Test 3: Compose (will fail if discovery enabled, should pass if metadata-only)
python src/imem/cli_new.py compose '{"search": {"mode": "metadata", "filters": {"phase": "develop"}}}'
```

---

## Integration Test

**File:** `tests/test_phase3_smoke.py`

```python
import pytest
from pathlib import Path
from imem.storage import create_store
from imem.compile import DocumentIndexer
from imem.compose import build_chain
from imem.core import RetrievalContext

def test_factory_creates_sqlite():
    """Test factory creates SQLite backend"""
    store = create_store(
        backend='sqlite',
        project_root=Path.cwd()
    )
    assert store is not None

def test_indexer_works():
    """Test DocumentIndexer can index files"""
    store = create_store(backend='sqlite', project_root=Path.cwd())
    indexer = DocumentIndexer(store)
    # Should not crash (actual indexing tested manually)
    assert indexer is not None

def test_compose_chain_builds():
    """Test processor chain builds from config"""
    store = create_store(backend='sqlite', project_root=Path.cwd())
    config = {'search': {'mode': 'metadata'}}
    chain = build_chain(config, store)
    assert chain is not None

def test_compose_executes():
    """Test chain executes without error"""
    store = create_store(backend='sqlite', project_root=Path.cwd())
    config = {'search': {'mode': 'metadata', 'filters': {}}}
    chain = build_chain(config, store)
    
    ctx = RetrievalContext(query="test", config=config)
    result = chain.execute(ctx)
    
    assert result is not None
    assert isinstance(result.results, list)
```

---

## Final Checklist

**After 1.5 hours:**

- ✅ Bug #1 fixed (factory signature)
- ✅ Bug #2 fixed (get_by_ids O(n²) → O(n))
- ✅ Bug #3 fixed (discovery errors explicit)
- ✅ Ranking scorer implemented (recency)
- ✅ Smoke tests pass (3 CLI commands)
- ✅ Integration test passes (pytest)

**Known limitations (documented):**
- ❌ Discovery processors not implemented (NotImplementedError)
- ❌ Authority ranker not implemented (uses identity)
- ❌ HNSW backend not added

**Result:** Production-ready with documented TODOs.

---

# Agreed?

**Yes**, but with **Bug #2 first** (get_by_ids is critical).

**Order:**
1. Fix get_by_ids() O(n²) → O(n) (20 min)
2. Fix factory signature (15 min)
3. Fix discovery errors (10 min)
4. Add ranking scorer (30 min)
5. Smoke tests (20 min)
6. Integration test (10 min)

**Total: 1h 45m**

**Let's do it.**