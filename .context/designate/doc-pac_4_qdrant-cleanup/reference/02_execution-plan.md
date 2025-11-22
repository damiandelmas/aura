# IMEM v3 Extraction: Execution Plan

**Purpose:** Step-by-step tactical instructions for Qdrant isolation and protocol adoption
**Audience:** AI agent executing cleanup
**Prerequisites:** Read `01_audit-report.md` for evidence, `00_clean-up.md` for vision

---

## Overview: Simplified Cleanup

```
Phase 1: QUARANTINE LEGACY (1h)
  → Move Qdrant-hardcoded files to legacy/v2/
  → Update temporary imports
  → Document what v2 provided

Phase 2: DELETE CONFUSED WRAPPERS (1h)
  → Remove get_siblings/genealogy/temporal from protocol
  → Delete implementations from both backends
  → Delete discovery stub processors
  → Use raw SQL queries when needed

Total: 2 hours
```

**NOT doing:**
- ❌ Rewriting indexer (works, can refactor later if needed)
- ❌ Building discovery processors (YAGNI - wait for real usage)
- ❌ Implementing fake Qdrant methods (it can't do these honestly)

---

## Phase 1: Quarantine Legacy (1 hour)

**Goal:** Isolate Qdrant-coupled code as reference, not active imports

### Step 1.1: Create Directory Structure (5 min)

```bash
cd /home/axp/projects/fleet/hangar/code/aura/worktrees/sql-first/imem

# Create legacy directory
mkdir -p src/imem/legacy/v2
```

**Validation:**
```bash
ls -la src/imem/legacy/v2  # Should exist
```

---

### Step 1.2: Move Files (10 min)

**Move legacy implementations:**
```bash
cd src/imem

# Move Qdrant-hardcoded classes
mv ingest.py legacy/v2/
mv search.py legacy/v2/
mv enhanced.py legacy/v2/
mv qdrant_service.py legacy/v2/

# Move Qdrant-specific discovery
mv primitives/discovery.py legacy/v2/
```

**Validation:**
```bash
ls legacy/v2/  # Should show: ingest.py, search.py, enhanced.py, qdrant_service.py, discovery.py
ls *.py | grep -E "(ingest|search|enhanced|qdrant_service)" # Should return nothing
```

---

### Step 1.3: Update Import in Indexer (15 min)

**File:** `src/imem/compile/indexer.py`

**Change line 65:**
```python
# BEFORE:
from ..ingest import EnhancedModularIngest

# AFTER:
from ..legacy.v2.ingest import EnhancedModularIngest
```

**Add TODO comment at line 89:**
```python
# Line 89
# TODO: Remove EnhancedModularIngest dependency
# Replace with: self.store.upsert(chunks) using protocol
ingester = EnhancedModularIngest()
```

**Validation:**
```bash
grep "from.*legacy.v2.ingest" src/imem/compile/indexer.py  # Should show updated import
grep "TODO.*EnhancedModularIngest" src/imem/compile/indexer.py  # Should show TODO
```

---

### Step 1.4: Update Import in CLI Commands (10 min)

**File:** `src/imem/cli/commands.py`

**Change line 268 (service command):**
```python
# BEFORE:
from ..service import QdrantService

# AFTER:
from ..legacy.v2.qdrant_service import QdrantService
```

**Validation:**
```bash
grep "from.*legacy.v2.qdrant_service" src/imem/cli/commands.py  # Should show updated import
```

---

### Step 1.5: Clean Public API Exports (15 min)

**File:** `src/imem/__init__.py`

**Remove legacy exports:**
```python
# REMOVE these lines:
from .enhanced import EnhancedQdrantSearch
from .search import ModularSearch
from .ingest import EnhancedModularIngest

# Keep protocol-based exports only (if any exist)
```

**Validation:**
```bash
grep -E "(EnhancedQdrantSearch|ModularSearch|EnhancedModularIngest)" src/imem/__init__.py
# Should return nothing
```

---

### Step 1.6: Create Legacy Documentation (30 min)

**File:** `src/imem/legacy/v2/README.md`

**Content:**
```markdown
# IMEM v2 Legacy Code (Qdrant-Hardcoded)

**Status:** Reference implementation (not actively imported)
**Purpose:** Preserve v2 capabilities as specification for v3 features

---

## What v2 Provided

### Rich Metadata Extraction (ingest.py)
- Structured field detection: `has_rationale`, `has_solution`, `has_alternatives`
- Header hierarchy extraction (H2 parent tracking)
- Session linking for conversations
- Category/subtype parsing from frontmatter

### Advanced Search (search.py, enhanced.py)
- Multi-term boolean search (AND/OR operators)
- Hybrid scoring: 0.6×similarity + 0.4×recency
- Multi-model support (MiniLM, MPNet, E5-Large)
- Timestamp parsing (6 different formats)

### Discovery Primitives (discovery.py)
- Semantic + temporal hybrid queries
- Cross-collection genealogy lookup
- Quality filters (`has_rationale=True`)
- Spatial proximity with section type filtering

---

## Why Isolated

**Coupling issues:**
- Hardcoded QdrantClient initialization (no abstraction)
- Host/port hardcoded (`localhost:6334`)
- Bypasses VectorStore protocol
- Cannot swap backends

**Architecture issues:**
- Indexing directly creates Qdrant collections
- Search duplicates functionality in compose/processors
- Discovery not wired to orchestrator

---

## How to Use This Code

**As Specification:**
1. Read patterns and logic
2. Port to v3 protocol-based implementation
3. Test against same inputs/outputs

**Examples:**
- Field detection → Add columns to SQLite schema
- Hybrid scoring → Implement in RankingProcessor
- Discovery → Implement on QdrantVectorStore as protocol methods

**Do NOT:**
- Import directly from active code
- Copy hardcoded patterns
- Bypass protocol abstraction

---

## Files

| File | Purpose | Key Logic |
|------|---------|-----------|
| `ingest.py` | Qdrant ingestion | Lines 734-741: Field detection<br>Lines 851-937: Conversation parsing |
| `search.py` | Multi-collection search | Lines 216-227: Filter construction<br>Lines 286-370: Boolean search |
| `enhanced.py` | Hybrid search | Lines 84-144: Timestamp parsing<br>Lines 255-281: Hybrid scoring |
| `discovery.py` | Graph queries | Lines 14-107: get_siblings()<br>Lines 188-269: get_temporal() |
| `qdrant_service.py` | Service management | Docker/process management |

---

## Migration Status

- [x] Moved to legacy/v2/
- [x] Imports updated in active code
- [ ] Features ported to protocol-based implementations
- [ ] Legacy code can be deleted (when v3 feature-complete)
```

**Save to:** `src/imem/legacy/v2/README.md`

---

### Step 1.7: Validate Phase 1 (15 min)

**Run tests:**
```bash
cd /home/axp/projects/fleet/hangar/code/aura/worktrees/sql-first/imem
pytest src/imem/tests/ -v
```

**Test commands:**
```bash
cd /home/axp/projects/fleet/hangar/code/aura

# Should still work (SQLite path, protocol-based):
python3 worktrees/sql-first/imem/src/imem/cli_new.py index-metadata develop --limit 5
python3 worktrees/sql-first/imem/src/imem/cli_new.py query-metadata --phase develop --limit 3

# Should still work (uses legacy from new location):
python3 worktrees/sql-first/imem/src/imem/cli_new.py index develop --limit 5
```

**Check for import leaks:**
```bash
# Should only show compile/indexer.py and cli/commands.py (with legacy.v2 prefix)
grep -r "from.*ingest import" src/imem/*.py
grep -r "from.*search import" src/imem/*.py
grep -r "from.*enhanced import" src/imem/*.py

# Should show nothing (legacy not imported directly)
grep -r "EnhancedModularIngest" src/imem/*.py | grep -v "legacy.v2" | grep -v "TODO"
```

**Expected state:**
- ✓ `legacy/v2/` directory with 5 files + README
- ✓ Active code imports from `legacy.v2` prefix only in indexer.py, commands.py
- ✓ All commands functional
- ✓ No direct imports of legacy classes (except via legacy.v2 path)

---

## Phase 2: Delete Confused Wrappers (1 hour)

**Goal:** Remove false abstractions over simple SQL queries

### Step 2.1: Remove from Protocol (15 min)

**File:** `src/imem/storage/protocol.py`

**Delete method definitions:**
```python
# DELETE these entire method definitions (including docstrings):
def get_siblings(self, chunk_id: str, limit: int = 5) -> List[SearchResult]:
    """Get spatially proximate chunks..."""
    ...

def get_genealogy(self, chunk_id: str, depth: int = 2) -> List[SearchResult]:
    """Get conversationally related chunks..."""
    ...

def get_temporal(self, chunk_id: str, window_days: int = 7) -> List[SearchResult]:
    """Get temporally proximate chunks..."""
    ...
```

**Validation:**
```bash
grep -E "(get_siblings|get_genealogy|get_temporal)" src/imem/storage/protocol.py
# Should return nothing
```

---

### Step 2.2: Delete from SQLite Backend (20 min)

**File:** `src/imem/storage/sqlite.py`

**Delete entire methods:**
```python
# DELETE lines 245-316
def get_siblings(self, chunk_id, limit=5, same_section=True):
    ...

# DELETE lines 318-379
def get_genealogy(self, chunk_id, depth=2, direction='both'):
    ...

# DELETE lines 381-452
def get_temporal(self, chunk_id, time_window_days=7, limit=10, direction='both'):
    ...
```

**Validation:**
```bash
grep -E "(def get_siblings|def get_genealogy|def get_temporal)" src/imem/storage/sqlite.py
# Should return nothing
```

---

### Step 2.3: Delete from Qdrant Backend (15 min)

**File:** `src/imem/storage/qdrant_backend.py`

**Delete if they exist:**
```python
# DELETE any implementations of:
get_siblings()
get_genealogy()
get_temporal()
```

---

### Step 2.4: Delete Discovery Stubs (10 min)

**File:** `src/imem/compose/orchestrator.py`

**Delete stubbed processor creation (lines ~57-76):**
```python
# DELETE:
if discovery_config.get('siblings'):
    raise NotImplementedError("SiblingDiscovery processor not yet implemented...")

if discovery_config.get('genealogy'):
    raise NotImplementedError("GenealogyDiscovery processor not yet implemented...")

if discovery_config.get('temporal'):
    raise NotImplementedError("TemporalDiscovery processor not yet implemented...")
```

**Replace with comment:**
```python
# Discovery: Query SQL directly when needed. Don't wrap until usage patterns emerge.
# Example: db.execute("SELECT * FROM chunks WHERE file_path = ?", ...)
```

---

### Step 2.5: Validate Phase 2 (10 min)

**Check deletions:**
```bash
# Should return nothing:
grep -E "(get_siblings|get_genealogy|get_temporal)" src/imem/storage/protocol.py
grep -E "(def get_siblings|def get_genealogy|def get_temporal)" src/imem/storage/sqlite.py
grep -E "(def get_siblings|def get_genealogy|def get_temporal)" src/imem/storage/qdrant_backend.py

# Should not crash:
python3 src/imem/cli_new.py query-metadata --phase develop --limit 3
```

**Expected state:**
- ✓ No `get_siblings/genealogy/temporal` in protocol
- ✓ No implementations in backends
- ✓ No discovery stubs raising NotImplementedError
- ✓ Existing queries still work

---

## Final Validation

**DELETED - Not needed. See Phase 2: Discovery via raw SQL when patterns emerge.**

### REMOVED SECTION

**File:** `src/imem/storage/qdrant_backend.py`

**Add methods (reference `legacy/v2/discovery.py` for logic):**

```python
def get_siblings(
    self,
    chunk_id: str,
    limit: int = 5,
    same_section: bool = True
) -> List[SearchResult]:
    """Get spatially proximate chunks (same document)

    Reference: legacy/v2/discovery.py lines 14-107
    """
    from qdrant_client.models import Filter, FieldCondition, MatchValue

    # Get anchor chunk
    anchor = self.client.retrieve(
        collection_name=self.collection_name,
        ids=[chunk_id]
    )[0]

    file_path = anchor.payload.get('file_path')

    # Query chunks with same file_path
    conditions = [
        FieldCondition(key='file_path', match=MatchValue(value=file_path))
    ]

    if same_section:
        section_type = anchor.payload.get('section_type')
        if section_type:
            conditions.append(
                FieldCondition(key='section_type', match=MatchValue(value=section_type))
            )

    results = self.client.scroll(
        collection_name=self.collection_name,
        scroll_filter=Filter(must=conditions),
        limit=limit + 1  # +1 to exclude anchor
    )[0]

    # Convert to SearchResult, exclude anchor
    search_results = []
    for point in results:
        if point.id == chunk_id:
            continue
        search_results.append(SearchResult(
            id=str(point.id),
            content=point.payload.get('content', ''),
            score=1.0,
            metadata=point.payload
        ))

    return search_results[:limit]


def get_genealogy(
    self,
    chunk_id: str,
    depth: int = 2,
    direction: str = 'both'
) -> List[SearchResult]:
    """Get conversationally related chunks (same session)

    Reference: legacy/v2/discovery.py lines 110-185
    """
    from qdrant_client.models import Filter, FieldCondition, MatchValue

    # Get anchor chunk
    anchor = self.client.retrieve(
        collection_name=self.collection_name,
        ids=[chunk_id]
    )[0]

    session_id = anchor.payload.get('session_id')
    if not session_id:
        return []

    # Query chunks with same session_id
    results = self.client.scroll(
        collection_name=self.collection_name,
        scroll_filter=Filter(
            must=[FieldCondition(key='session_id', match=MatchValue(value=session_id))]
        ),
        limit=100,
        order_by='timestamp'  # Chronological order
    )[0]

    # Convert and exclude anchor
    search_results = []
    for point in results:
        if point.id == chunk_id:
            continue
        search_results.append(SearchResult(
            id=str(point.id),
            content=point.payload.get('content', ''),
            score=1.0,
            metadata=point.payload
        ))

    return search_results


def get_temporal(
    self,
    chunk_id: str,
    time_window_days: int = 7,
    limit: int = 10,
    direction: str = 'both'
) -> List[SearchResult]:
    """Get temporally proximate chunks

    Reference: legacy/v2/discovery.py lines 188-269
    """
    from datetime import datetime, timedelta
    from qdrant_client.models import Filter, FieldCondition, Range

    # Get anchor chunk
    anchor = self.client.retrieve(
        collection_name=self.collection_name,
        ids=[chunk_id]
    )[0]

    timestamp_str = anchor.payload.get('timestamp')
    if not timestamp_str:
        return []

    # Parse timestamp
    anchor_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))

    # Calculate time range
    if direction == 'after':
        start_time = anchor_time
        end_time = anchor_time + timedelta(days=time_window_days)
    elif direction == 'before':
        start_time = anchor_time - timedelta(days=time_window_days)
        end_time = anchor_time
    else:  # both
        start_time = anchor_time - timedelta(days=time_window_days)
        end_time = anchor_time + timedelta(days=time_window_days)

    # Query with timestamp range
    results = self.client.scroll(
        collection_name=self.collection_name,
        scroll_filter=Filter(
            must=[
                FieldCondition(
                    key='timestamp',
                    range=Range(
                        gte=start_time.isoformat(),
                        lte=end_time.isoformat()
                    )
                )
            ]
        ),
        limit=limit + 1
    )[0]

    # Convert and exclude anchor
    search_results = []
    for point in results:
        if point.id == chunk_id:
            continue
        search_results.append(SearchResult(
            id=str(point.id),
            content=point.payload.get('content', ''),
            score=1.0,
            metadata=point.payload
        ))

    return search_results[:limit]
```

---

### Step 3.2: Create Discovery Processors (2h)

**File:** `src/imem/compose/processors/discovery.py` (NEW)

```python
from typing import List, Dict, Any
from ..protocol import Processor, ProcessorContext
from ...storage.protocol import VectorStore

class SiblingDiscoveryProcessor(Processor):
    """Expand results with spatially proximate chunks"""

    def __init__(self, store: VectorStore):
        self.store = store

    def process(self, ctx: ProcessorContext) -> ProcessorContext:
        """Add siblings for each result"""
        enriched = []

        for result in ctx.results:
            # Add original
            enriched.append(result)

            # Add siblings
            siblings = self.store.get_siblings(result.id, limit=3)
            enriched.extend(siblings)

        ctx.results = enriched
        return ctx


class TemporalDiscoveryProcessor(Processor):
    """Expand results with temporally proximate chunks"""

    def __init__(self, store: VectorStore, window_days: int = 7):
        self.store = store
        self.window_days = window_days

    def process(self, ctx: ProcessorContext) -> ProcessorContext:
        """Add temporal neighbors"""
        enriched = []

        for result in ctx.results:
            enriched.append(result)

            temporal = self.store.get_temporal(
                result.id,
                time_window_days=self.window_days,
                limit=3
            )
            enriched.extend(temporal)

        ctx.results = enriched
        return ctx


class GenealogyDiscoveryProcessor(Processor):
    """Expand results with conversationally related chunks"""

    def __init__(self, store: VectorStore):
        self.store = store

    def process(self, ctx: ProcessorContext) -> ProcessorContext:
        """Add conversation context"""
        enriched = []

        for result in ctx.results:
            enriched.append(result)

            genealogy = self.store.get_genealogy(result.id, depth=2)
            enriched.extend(genealogy)

        ctx.results = enriched
        return ctx
```

---

### Step 3.3: Wire Processors into Orchestrator (1h)

**File:** `src/imem/compose/orchestrator.py`

**Replace lines 57-76:**

```python
# BEFORE:
if discovery_config.get('siblings'):
    raise NotImplementedError(...)

# AFTER:
from .processors.discovery import (
    SiblingDiscoveryProcessor,
    TemporalDiscoveryProcessor,
    GenealogyDiscoveryProcessor
)

if discovery_config.get('siblings'):
    processors.append(SiblingDiscoveryProcessor(store))

if discovery_config.get('temporal'):
    window_days = discovery_config.get('temporal_window_days', 7)
    processors.append(TemporalDiscoveryProcessor(store, window_days=window_days))

if discovery_config.get('genealogy'):
    processors.append(GenealogyDiscoveryProcessor(store))
```

---

### Step 3.4: Validate Phase 3 (30 min)

**Test discovery:**
```bash
cd /home/axp/projects/fleet/hangar/code/aura

# Index some data first
python3 worktrees/sql-first/imem/src/imem/cli_new.py index-metadata develop --limit 10

# Test sibling discovery
python3 worktrees/sql-first/imem/src/imem/cli_new.py compose '{
  "search": {"mode": "metadata", "filters": {"phase": "develop"}},
  "discovery": {"siblings": true}
}'

# Should return results with siblings, no NotImplementedError
```

**Expected state:**
- ✓ Discovery processors exist
- ✓ Orchestrator calls them (no NotImplementedError)
- ✓ Compose with discovery returns enriched results
- ✓ All backends support discovery

---

## Final Validation

### Complete Test Suite

```bash
cd /home/axp/projects/fleet/hangar/code/aura/worktrees/sql-first/imem

# Run all tests
pytest src/imem/tests/ -v

# Test all commands
python3 src/imem/cli_new.py init
python3 src/imem/cli_new.py index develop --backend sqlite --limit 5
python3 src/imem/cli_new.py query-metadata --phase develop
python3 src/imem/cli_new.py stats-metadata
python3 src/imem/cli_new.py compose '{"search": {"mode": "metadata"}}'
python3 src/imem/cli_new.py compose '{"search": {"mode": "metadata"}, "discovery": {"siblings": true}}'
```

### Verify No Legacy Coupling

```bash
# Should return nothing (or only legacy.v2 references):
grep -r "EnhancedModularIngest" src/imem/ | grep -v legacy
grep -r "EnhancedQdrantSearch" src/imem/ | grep -v legacy
grep -r "ModularSearch" src/imem/ | grep -v legacy

# Should only show qdrant_backend.py:
grep -r "from qdrant_client import" src/imem/ | grep -v legacy
```

### Architecture Compliance

**Check protocol usage:**
- [ ] `compile/indexer.py` uses `store.upsert()`
- [ ] No direct QdrantClient outside `storage/qdrant_backend.py`
- [ ] Factory pattern used for backend selection
- [ ] Discovery via protocol methods

**Check domain separation:**
- [ ] COMPILE doesn't import storage implementations
- [ ] COMPOSE uses protocol, not concrete backends
- [ ] CLI uses composition root for dependency injection

---

## Rollback Plan

**If Phase 1 breaks:**
```bash
# Restore files
cp -r src/imem/legacy/v2/* src/imem/
# Revert imports
git checkout src/imem/compile/indexer.py
git checkout src/imem/cli/commands.py
```

**If Phase 2 breaks:**
```bash
# Keep Phase 1 (legacy isolated)
# Revert indexer changes
git checkout src/imem/compile/indexer.py
git checkout src/imem/cli/main.py
```

**If Phase 3 breaks:**
```bash
# Keep Phases 1-2 (indexer uses protocol)
# Remove discovery processors
git checkout src/imem/compose/orchestrator.py
rm src/imem/compose/processors/discovery.py
```

---

## Success Metrics

**After all phases:**
- Zero direct QdrantClient imports in active code (except backend)
- Single indexing code path (no `index` vs `index-metadata` duplication)
- Backend selection via config/factory
- Discovery works end-to-end
- All tests pass
- Legacy code preserved as reference

**Time investment:** ~12-16 hours
**Payoff:** Clean architecture enabling HNSW, relationships table, and incremental feature development
