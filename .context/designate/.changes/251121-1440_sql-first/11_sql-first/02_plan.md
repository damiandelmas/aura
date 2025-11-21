# Implementation Plan

**Status:** Phases 1-2 complete, Phase 3 in progress

---

## Phase 1: Storage Abstraction ✅

**Commit:** 2208be8 | **Time:** ~2 hours

**Built:**
- VectorStore protocol (`storage/protocol.py`)
- SQLiteVectorStore backend (`storage/sqlite_backend.py`)
- QdrantVectorStore backend (`storage/qdrant_backend.py`)
- Factory pattern (`storage/factory.py`)
- SearchResult dataclass (unified format)

---

## Phase 2: Processor Chain ✅

**Commit:** 539f2b3 | **Time:** ~2 hours

**Built:**
- Chain + Processor protocol (`core/chain.py` - 110 lines)
- RetrievalContext dataclass
- Bounded concurrency (`core/async_helpers.py` - 58 lines, Graphiti pattern)
- SearchProcessor (`compose/processors/search.py` - 100 lines)
- MultiPhaseRanker (`compose/processors/ranking.py` - 172 lines, Vespa pattern)

---

## Phase 3: Domain Separation ⏳ IN PROGRESS

**Commit:** 4884372 | **Time so far:** ~3 hours | **Remaining:** 3-4 hours

**Built:**
- compile/DocumentIndexer (255 lines extracted from cli.py)
- manage/ wrappers (introspection, registry)
- service/ wrapper (Qdrant lifecycle)
- History tracking (created_at, updated_at columns in SQLite)

**Remaining:**
- CLI composition root (IMEMCLI class)
- compose/orchestrator.py (integrate Chain)
- CLI reduction (1772 → ~600 LOC)
- Resolution tables (phase/section/entity)

**Next steps:** See **HANDOFF.md** for 4 specific tasks (3-4 hours)

---

## Phase 3 Task Details

### 3.0 CLI Composition Root (1.5 hours)

**Create single initialization point:**

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

**Files:**
- Create `imem/cli/main.py` (IMEMCLI class)
- Create `imem/cli/commands.py` (Click decorators)
- Extract business logic to controllers

---

### 3.1 Integrate Processor Chain (1 hour)

**Create orchestrator:**

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

**Files:**
- Create `imem/compose/orchestrator.py`
- Update `imem compose` command
- Deprecate old compose.py

---

### 3.2 Add Resolution Tables (1 hour)

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
    canonical TEXT NOT NULL,
    confidence REAL DEFAULT 1.0,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- MANAGE resolution (entity normalization)
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
        for canonical, variations in self.PHASE_MAPPINGS.items():
            for variation in variations:
                db.execute('''
                    INSERT OR IGNORE INTO phase_resolution (variation, canonical)
                    VALUES (?, ?)
                ''', (variation, canonical))
```

**Files:**
- Update `imem/storage/sqlite.py` schema
- Create `imem/compile/resolver.py`
- Seed on first init

---

### 3.3 Final CLI Cleanup (30 min)

**Extract remaining logic:**
- `_index_phase()` → `compile/indexer.py`
- `_index_conversations()` → `compile/indexer.py`
- Collection management → `storage/qdrant_backend.py`
- Registry operations → `manage/registry.py`

**Keep only:**
- Click decorators
- Command routing
- Argument parsing

**Target:** cli.py < 600 LOC

---

## Success Criteria

**Phase 3 complete when:**
- ✅ CLI < 600 LOC
- ✅ IMEMCLI class with shared DB/embedder
- ✅ compose command uses processor chain
- ✅ Resolution tables exist and seeded
- ✅ All commands still work (backward compatible)
