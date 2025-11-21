# Handoff: SQLite-First Refactor (Phase 3 Completion)

**To:** Next agent
**From:** Phase 1 & 2 implementation
**Status:** 75% complete (Phases 1-2 done, Phase 3 in progress)
**Remaining:** 3-4 hours to complete Phase 3

---

## Read This First

**STATUS.md** - Shows exactly what's built, what works, what doesn't
**02_plan.md** - Full implementation plan (Phases 1-2 completed, Phase 3 remaining)
**01_architecture.md** - Target architecture reference

**⚠️ DO NOT read EXECUTE.md** - It's outdated (says "start with Phase 1", but Phases 1-2 are done)

---

## What's Already Done

### ✅ Phase 1: Storage Abstraction (commit 2208be8)

```python
# This already works:
from imem.storage import create_store

store = create_store('sqlite', {...})    # ✅
store = create_store('qdrant', {...})    # ✅
```

**Files:** `imem/storage/protocol.py`, `sqlite_backend.py`, `qdrant_backend.py`, `factory.py`

---

### ✅ Phase 2: Processor Chain (commit 539f2b3)

```python
# This already works:
from imem.core import Chain, RetrievalContext
from imem.compose.processors import SearchProcessor, MultiPhaseRanker

chain = Chain([
    SearchProcessor(store),
    MultiPhaseRanker([...])
])

result = chain.execute(ctx)  # ✅
```

**Files:** `imem/core/chain.py`, `async_helpers.py`, `imem/compose/processors/search.py`, `ranking.py`

---

### ⏳ Phase 3: Domain Separation (commit 4884372 - 80% done)

**What exists:**
```python
from imem.compile import DocumentIndexer   # ✅ Works
from imem.manage import introspect          # ✅ Works
from imem.service import QdrantService      # ✅ Works
```

**What doesn't:**
- ❌ CLI still 1772 LOC (target ~600 LOC)
- ❌ No shared DB/embedder initialization
- ❌ compose.py not using processor chain yet
- ❌ Resolution tables missing (phase/section/entity)

---

## Your Mission: Finish Phase 3 (3-4 hours)

### Task 1: CLI Composition Root (1.5 hours)

**Goal:** Shared DB + embedder initialization, reduce CLI to routing layer

**Create:**
```python
# imem/cli/main.py
class IMEMCLI:
    def __init__(self, config_path=None):
        self.config = load_config(config_path)
        self.db = None
        self.embedder = None
        self.controllers = {}

    async def initialize(self):
        # 1. DB with pragmas (ONCE)
        self.db = sqlite3.connect(self.config.db_path)
        self.db.execute("PRAGMA journal_mode = WAL")
        self.db.execute("PRAGMA cache_size = -64000")

        # 2. Embedder (expensive ~2s, do ONCE)
        if self.config.embeddings_enabled:
            self.embedder = SentenceTransformer(self.config.model)

        # 3. Controllers (inject dependencies)
        self.controllers['compile'] = CompileController(self.db, self.embedder)
        self.controllers['manage'] = ManageController(self.db)
        self.controllers['compose'] = ComposeController(self.db, self.embedder)

# Global instance
app = IMEMCLI()

# imem/cli/commands.py
@click.command('index')
def index_cmd(source, **kwargs):
    return app.controllers['compile'].index(source, **kwargs)  # Thin wrapper
```

**Reference:** `02_plan.md` lines 490-552
**Expected result:** DB + embedder initialized once, commands delegate to controllers

---

### Task 2: Integrate Processor Chain into compose (1 hour)

**Goal:** Replace hardcoded compose.py pipeline with Chain

**Create:**
```python
# imem/compose/orchestrator.py
from imem.core import Chain, RetrievalContext
from imem.compose.processors import SearchProcessor, MultiPhaseRanker

def build_chain(config: dict, store: VectorStore) -> Chain:
    """Build processor chain from config"""
    processors = [SearchProcessor(store, mode=config.get('mode', 'metadata'))]

    # Add discovery processors conditionally
    if config.get('discovery', {}).get('siblings'):
        from imem.compose.processors.discovery import SiblingDiscovery
        processors.append(SiblingDiscovery(store))

    # Add ranking if configured
    if config.get('ranking'):
        processors.append(MultiPhaseRanker(config['ranking']['phases']))

    return Chain(processors)

def compose(config: dict, store: VectorStore) -> dict:
    """Execute retrieval pipeline"""
    chain = build_chain(config, store)
    ctx = RetrievalContext(
        query=config.get('search', {}).get('text', ''),
        config=config
    )
    result_ctx = chain.execute(ctx)
    return {"results": result_ctx.results}
```

**Update CLI:**
```python
# cli.py - Update compose command
@imem.command('compose')
def compose_cmd(config_json):
    from imem.compose.orchestrator import compose as compose_new
    from imem.storage import create_store

    config = json.loads(config_json)
    store = create_store('sqlite', app.config.storage)
    return compose_new(config, store)
```

**Reference:** `02_plan.md` lines 312-349
**Expected result:** compose command uses processor chain, old compose.py deprecated

---

### Task 3: Add Resolution Tables (1 hour)

**Goal:** COMPILE + MANAGE resolution infrastructure

**Create tables:**
```sql
-- COMPILE resolution (structural normalization)
CREATE TABLE IF NOT EXISTS phase_resolution (
    variation TEXT PRIMARY KEY COLLATE NOCASE,
    canonical TEXT NOT NULL CHECK (canonical IN ('design', 'designate', 'develop', 'document')),
    confidence REAL DEFAULT 1.0,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS section_type_resolution (
    variation TEXT PRIMARY KEY COLLATE NOCASE,
    canonical TEXT NOT NULL,  -- Decision, Pattern, Implementation, etc.
    confidence REAL DEFAULT 1.0,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- MANAGE resolution (entity normalization, project-scoped)
CREATE TABLE IF NOT EXISTS entity_resolution (
    project_id TEXT NOT NULL,
    variation TEXT NOT NULL,
    canonical TEXT NOT NULL,
    context TEXT,
    confidence REAL DEFAULT 1.0,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (project_id, variation)
);
```

**Seed with known variations:**
```python
# imem/compile/resolver.py
class CompileResolver:
    PHASE_MAPPINGS = {
        'design': ['design', 'planning', 'research', 'exploration'],
        'designate': ['designate', 'spec', 'specification', 'architecture'],
        'develop': ['develop', 'implementation', 'code', 'build'],
        'document': ['document', 'docs', 'documentation', 'readme']
    }

    SECTION_MAPPINGS = {
        'Decision': ['Decision', 'Decisions', 'Decision:', 'Choice', 'We Decided'],
        'Pattern': ['Pattern', 'Patterns', 'Best Practice', 'Approach'],
        'Implementation': ['Implementation', 'Code', 'Solution'],
        'Context': ['Context', 'Background', 'Why', 'Situation'],
        'Failure': ['Failure', 'Mistake', 'What Went Wrong']
    }

    def seed_resolution_tables(self, db):
        """Populate resolution tables with known mappings"""
        for canonical, variations in self.PHASE_MAPPINGS.items():
            for variation in variations:
                db.execute('''
                    INSERT OR IGNORE INTO phase_resolution (variation, canonical)
                    VALUES (?, ?)
                ''', (variation, canonical))
        # Same for section_type_resolution
```

**Reference:** `02_plan.md` lines 5-66
**Expected result:** Schema evolution tables exist, seeded with common variations

---

### Task 4: Final CLI Cleanup (30 min)

**Goal:** Reduce cli.py from 1772 → ~600 LOC

**Extract remaining logic:**
- `_index_phase()` → `compile/indexer.py` (already partially done)
- `_index_conversations()` → `compile/indexer.py`
- Collection management → `storage/qdrant_backend.py`
- Registry operations → `manage/registry.py`

**Keep only:**
- Click decorators
- Command routing
- Argument parsing

**Reference:** `02_plan.md` lines 669-703
**Expected result:** cli.py < 600 LOC, all business logic in domains

---

## Testing Your Work

**After each task, verify:**

```bash
# Task 1: CLI composition root
python -c "from imem.cli.main import IMEMCLI; app = IMEMCLI(); print('✅ IMEMCLI works')"

# Task 2: Processor chain integration
imem compose '{"search": {"mode": "metadata", "filters": {"phase": "develop"}}}'
# Should execute without errors

# Task 3: Resolution tables
sqlite3 .imem/corpus.db "SELECT COUNT(*) FROM phase_resolution"
# Should show > 0 rows

# Task 4: CLI reduction
wc -l imem/src/imem/cli.py
# Should be < 700 LOC
```

---

## Success Criteria

**Phase 3 complete when:**
- ✅ CLI < 600 LOC
- ✅ IMEMCLI class with shared DB/embedder
- ✅ compose command uses processor chain
- ✅ Resolution tables exist and seeded
- ✅ All commands still work (backward compatible)
- ✅ `imem index develop` works
- ✅ `imem compose '{"search": {...}}'` works

---

## If You Get Stuck

**Architecture questions:** Read `01_architecture.md` (domain structure, storage topology)
**Implementation details:** Read `02_plan.md` Phase 3 (lines 488-778)
**Patterns reference:** Read `04_patterns_applied.md` (what patterns we used, why)

**Key files to reference:**
- Phase 1 example: `imem/storage/protocol.py` (clean protocol definition)
- Phase 2 example: `imem/core/chain.py` (clean abstraction)
- Phase 3 partial: `imem/compile/indexer.py` (domain extraction pattern)

---

## Optional: HNSW Backend (8 hours, do after Phase 3)

**Only if you want zero-Docker deployment:**
- Local vector search (no Qdrant needed)
- 15s build vs 15min upload
- See `03_optional_enhancements.md` for full details

**Not critical for Phase 3 completion.**

---

## Time Estimates

| Task | Estimate | Description |
|------|----------|-------------|
| CLI composition root | 1.5h | IMEMCLI class, shared init |
| Processor chain integration | 1h | orchestrator.py, update compose command |
| Resolution tables | 1h | COMPILE + MANAGE tables, seeding |
| CLI cleanup | 30min | Extract remaining logic |
| **Total** | **4h** | Complete Phase 3 |

---

## Commit Strategy

```bash
# After Task 1
git commit -m "feat(cli): Add composition root (IMEMCLI class)"

# After Task 2
git commit -m "feat(compose): Integrate processor chain"

# After Task 3
git commit -m "feat(resolution): Add COMPILE + MANAGE resolution tables"

# After Task 4 (final)
git commit -m "feat(cli): Complete domain separation - Phase 3 done"
```

---

## Questions to Ask Before Starting

**None.** Phase 1 & 2 are complete and working. You have all the building blocks.

Just follow Tasks 1-4 in order. The architecture is proven (6 production systems validated it).

**You got this.** 🚀
