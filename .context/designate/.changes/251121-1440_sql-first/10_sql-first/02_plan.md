# Implementation Plan

## Phase 1: SQLite-First Indexing + Resolution (5-6 hours)

### 1.0 COMPILE Resolution Setup (2 hours)

**Create resolution infrastructure:**

```python
# imem/compile/resolver.py
class CompileResolver:
    """Resolve structural variations during parsing"""

    PHASE_MAPPINGS = {
        'design': ['design', 'planning', 'research', 'exploration', 'ideation'],
        'designate': ['designate', 'spec', 'specification', 'architecture', 'plan'],
        'develop': ['develop', 'implementation', 'code', 'build', 'coding'],
        'document': ['document', 'docs', 'documentation', 'readme', 'write-up']
    }

    SECTION_MAPPINGS = {
        'Decision': ['Decision', 'Decisions', 'Decision:', 'Choice', 'We Decided'],
        'Pattern': ['Pattern', 'Patterns', 'Best Practice', 'Approach'],
        'Implementation': ['Implementation', 'Code', 'Solution', 'How We Built'],
        'Context': ['Context', 'Background', 'Why', 'Situation'],
        'Failure': ['Failure', 'Mistake', 'What Went Wrong', 'Gotcha']
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

**Schema:**
```sql
-- storage/sqlite.py - Add resolution tables
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

CREATE INDEX idx_phase_canonical ON phase_resolution(canonical);
CREATE INDEX idx_section_canonical ON section_type_resolution(canonical);
```

**Files:**
- Create `imem/compile/resolver.py`
- Update `imem/storage/sqlite.py` schema
- Seed on first init

### 1.1 Make SQLite Primary (1 hour)

**Modify `imem index` to populate SQLite first:**

```python
# cli.py - Update index command
@imem.command('index')
def index_source(source, vectorize=False, **kwargs):
    """Index source (SQLite always, Qdrant optional)"""
    # Parse markdown → canonical chunks
    chunks = parser.parse(source)

    # Store in SQLite (always)
    sqlite_store.upsert_chunks(chunks)

    # Optionally vectorize
    if vectorize:
        qdrant_store.upsert_vectors(chunks)
```

**Files:**
- `cli.py` - Add `--vectorize` flag, default False
- Update `_index_phase()` to call SQLiteStore first
- Update `_index_conversations()` to call SQLiteStore first

### 1.2 Unified Schema (1 hour)

**Ensure SQLite and Qdrant use same field names:**

```sql
-- storage/sqlite.py - Update schema
CREATE TABLE chunks (
    id TEXT PRIMARY KEY,
    source TEXT,           -- Match Qdrant payload
    phase TEXT,
    section_type TEXT,
    section_name TEXT,
    content TEXT,
    file_path TEXT,
    timestamp TEXT,
    session_id TEXT,
    metadata JSON,
    schema_version TEXT DEFAULT 'v1.0'
);
```

**Files:**
- `storage/sqlite.py` - Add migration for schema_version
- `storage/sqlite.py` - Rename fields to match Qdrant
- `ingest.py` - Use shared schema constants

### 1.3 Qdrant as Derived Index (1 hour)

**Qdrant stores vectors + ID reference only:**

```python
# storage/qdrant.py - Minimal payload
payload = {
    'chunk_id': chunk['id'],  # Reference to SQLite
    'source': chunk['source'], # For routing only
    'phase': chunk['phase']    # For filtering only
}
# No content duplication
```

**Files:**
- `storage/qdrant.py` - Strip payload to minimal fields
- `ingest.py` - Reference SQLite for full metadata
- Update compose to join Qdrant results with SQLite data

### 1.4 Testing (30 min)

```bash
# Test SQLite-first indexing
imem index develop
imem stats-metadata  # Should show 283 files

# Test optional vectorization
imem index develop --vectorize
# Qdrant should have vectors, SQLite has metadata
```

**Verify:**
- SQLite populated on every index
- Qdrant only populated with `--vectorize`
- No metadata duplication
- Query works with both backends

---

## Phase 2: Processor Chain (4-6 hours)

### 2.1 Core Abstractions + Async Helpers (1.5 hours)

**Create chain infrastructure:**

```python
# imem/core/chain.py
class Processor(Protocol):
    def process(self, ctx: RetrievalContext) -> RetrievalContext: ...

class Chain:
    def __init__(self, processors: List[Processor]):
        self.processors = processors

    def execute(self, ctx: RetrievalContext) -> RetrievalContext:
        for processor in self.processors:
            ctx = processor.process(ctx)
        return ctx

# imem/core/context.py
@dataclass
class RetrievalContext:
    query: str
    config: dict
    results: List[Dict] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)

# imem/core/storage.py
class StorageProtocol(Protocol):
    def query(self, filters: dict, mode: str) -> List[Dict]: ...
    def get_siblings(self, chunk_id: str, **kwargs) -> List[Dict]: ...
    def get_temporal(self, chunk_id: str, **kwargs) -> List[Dict]: ...
    def get_genealogy(self, chunk_id: str, **kwargs) -> List[Dict]: ...

# imem/core/async_helpers.py
import asyncio
from typing import Coroutine, List, Any

async def semaphore_gather(
    *coroutines: Coroutine,
    max_coroutines: int = 20
) -> List[Any]:
    """Bounded concurrency primitive (from Graphiti pattern)

    Prevents SQLite connection pool exhaustion during parallel operations.
    SQLite in WAL mode supports concurrent reads but bounded writes.

    Args:
        *coroutines: Coroutines to execute in parallel
        max_coroutines: Maximum concurrent operations (default: 20)

    Returns:
        List of results in same order as input coroutines
    """
    semaphore = asyncio.Semaphore(max_coroutines)

    async def _wrap_coroutine(coro):
        async with semaphore:
            return await coro

    return await asyncio.gather(*(_wrap_coroutine(c) for c in coroutines))
```

**Files to create:**
- `imem/core/__init__.py`
- `imem/core/chain.py`
- `imem/core/context.py`
- `imem/core/storage.py`
- `imem/core/async_helpers.py` (NEW - Graphiti bounded concurrency)

### 2.2 Extract Processors (2 hours)

**Create processor implementations from compose.py:**

```python
# imem/compose/processors/search.py
class SearchProcessor(Processor):
    def __init__(self, store: StorageProtocol, mode='metadata'):
        self.store = store
        self.mode = mode

    def process(self, ctx: RetrievalContext) -> RetrievalContext:
        ctx.results = self.store.query(
            filters=ctx.config.get('search', {}).get('filters', {}),
            mode=self.mode
        )
        return ctx

# imem/compose/processors/discovery.py
from imem.core.async_helpers import semaphore_gather

class SiblingDiscovery(Processor):
    def __init__(self, store: StorageProtocol):
        self.store = store

    async def process_async(self, ctx: RetrievalContext) -> RetrievalContext:
        """Async version with bounded concurrency"""
        sibling_config = ctx.config.get('discovery', {}).get('siblings')
        if not sibling_config:
            return ctx

        # Parallel sibling queries with bounded concurrency
        sibling_tasks = [
            self._get_siblings_async(result['id'], sibling_config)
            for result in ctx.results
        ]
        siblings_list = await semaphore_gather(*sibling_tasks, max_coroutines=30)

        for result, siblings in zip(ctx.results, siblings_list):
            result['siblings'] = siblings
        return ctx

    async def _get_siblings_async(self, chunk_id: str, config):
        """Wrap sync store call in executor"""
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.store.get_siblings,
            chunk_id,
            **(config if isinstance(config, dict) else {})
        )

# Similar for TemporalDiscovery, GenealogyDiscovery
```

**Files to create:**
- `imem/compose/processors/__init__.py`
- `imem/compose/processors/search.py`
- `imem/compose/processors/discovery.py` (with async + semaphore)
- `imem/compose/processors/filter.py`

### 2.3 Storage Protocol Implementation (1 hour)

**Make SQLiteStore and QdrantStore implement StorageProtocol:**

```python
# imem/storage/sqlite.py
class SQLiteStore(StorageProtocol):
    def query(self, filters: dict, mode: str) -> List[Dict]:
        # Existing implementation
        ...

    def get_siblings(self, chunk_id: str, **kwargs) -> List[Dict]:
        # Existing implementation
        ...

    # Implement full protocol
```

**Files to modify:**
- `imem/storage/sqlite.py` - Add Protocol inheritance
- `imem/storage/qdrant.py` - Create wrapper implementing Protocol

### 2.4 Update Compose (1 hour)

**Replace hardcoded pipeline with chain:**

```python
# imem/compose/orchestrator.py (new)
def build_chain(config: dict, store: StorageProtocol) -> Chain:
    """Build processor chain from config"""
    processors = [SearchProcessor(store, mode=config.get('mode', 'metadata'))]

    if config.get('discovery', {}).get('siblings'):
        processors.append(SiblingDiscovery(store))

    if config.get('discovery', {}).get('temporal'):
        processors.append(TemporalDiscovery(store))

    if config.get('discovery', {}).get('genealogy'):
        processors.append(GenealogyDiscovery(store))

    processors.append(FilterProcessor())

    return Chain(processors)

def compose(config: dict, store: StorageProtocol) -> dict:
    """Execute retrieval pipeline"""
    chain = build_chain(config, store)
    ctx = RetrievalContext(
        query=config.get('search', {}).get('text', ''),
        config=config
    )
    result_ctx = chain.execute(ctx)
    return {"results": result_ctx.results}
```

**Files:**
- Create `imem/compose/orchestrator.py`
- Update `imem/compose.py` to use orchestrator
- Keep old compose.py for backward compat (deprecated)

### 2.5 Multi-Phase Ranking (1 hour)

**Add progressive refinement (Vespa pattern):**

```python
# imem/compose/processors/ranking.py
from typing import Callable, Optional

class RankingPhase:
    """Single ranking phase with optional top-k limit"""
    def __init__(
        self,
        name: str,
        scorer: Callable[[List[Dict]], List[Dict]],
        rerank_count: Optional[int] = None
    ):
        self.name = name
        self.scorer = scorer
        self.rerank_count = rerank_count

class MultiPhaseRanker(Processor):
    """Progressive refinement through multiple ranking phases

    Example:
        Phase 1: Metadata filter (1000s → 100s)
        Phase 2: Reference counting (100s → 20s)
        Phase 3: Graph authority (20s → 10 final)

    Benefits:
        - Limits expensive operations (PageRank) to finalists only
        - 25x fewer graph computations vs single-pass ranking
    """
    def __init__(self, phases: List[RankingPhase]):
        self.phases = phases

    def process(self, ctx: RetrievalContext) -> RetrievalContext:
        for phase in self.phases:
            # Apply top-k limit if specified
            if phase.rerank_count:
                ctx.results = ctx.results[:phase.rerank_count]

            # Score and re-rank
            ctx.results = phase.scorer(ctx.results)

        return ctx

# Example scorers
def count_references(results: List[Dict]) -> List[Dict]:
    """Phase 2: Count how many chunks reference this one"""
    # TODO: SQL query to count references
    return sorted(results, key=lambda r: r.get('reference_count', 0), reverse=True)

def apply_pagerank(results: List[Dict]) -> List[Dict]:
    """Phase 3: Graph centrality (expensive, run on finalists only)"""
    # TODO: NetworkX PageRank on result subgraph
    return sorted(results, key=lambda r: r.get('pagerank_score', 0), reverse=True)
```

**Usage in orchestrator:**
```python
# Build chain with multi-phase ranking
processors = [
    SearchProcessor(store),
    SiblingDiscovery(store),
    MultiPhaseRanker([
        RankingPhase("metadata", lambda r: r, rerank_count=100),
        RankingPhase("references", count_references, rerank_count=20),
        RankingPhase("authority", apply_pagerank, rerank_count=10)
    ]),
    FilterProcessor()
]
```

**Files to create:**
- `imem/compose/processors/ranking.py` (NEW - Vespa multi-phase pattern)

### 2.6 Testing (30 min)

```python
# Test individual processors
def test_sibling_discovery():
    store = SQLiteStore(project_root)
    processor = SiblingDiscovery(store)
    ctx = RetrievalContext(
        results=[{'id': 'chunk_1'}],
        config={'discovery': {'siblings': {'limit': 3}}}
    )
    result = await processor.process_async(ctx)
    assert 'siblings' in result.results[0]

# Test bounded concurrency
async def test_semaphore_gather():
    from imem.core.async_helpers import semaphore_gather

    async def slow_task(n):
        await asyncio.sleep(0.1)
        return n

    results = await semaphore_gather(
        *[slow_task(i) for i in range(100)],
        max_coroutines=10
    )
    assert results == list(range(100))

# Test chain composition
def test_retrieval_chain():
    chain = Chain([
        SearchProcessor(store),
        SiblingDiscovery(store),
        MultiPhaseRanker([...]),
        FilterProcessor()
    ])
    result = chain.execute(ctx)
    assert len(result.results) > 0

# Test multi-phase ranking
def test_multi_phase_ranking():
    results = [{'id': i, 'score': i} for i in range(100)]
    ctx = RetrievalContext(results=results, config={})

    ranker = MultiPhaseRanker([
        RankingPhase("phase1", lambda r: r, rerank_count=50),
        RankingPhase("phase2", lambda r: r, rerank_count=10)
    ])

    result = ranker.process(ctx)
    assert len(result.results) == 10  # Final top-k
```

**Files:**
- `tests/test_processors.py`
- `tests/test_chain.py`
- `tests/test_async_helpers.py` (NEW)
- `tests/test_ranking.py` (NEW)

---

## Phase 3: Domain Separation + CLI Composition Root (8-10 hours)

### 3.0 CLI Composition Root (2 hours)

**Create single initialization point:**

```python
# imem/cli/main.py
class IMEMCLI:
    """Composition root - single initialization for all dependencies"""

    def __init__(self, config_path: Optional[Path] = None):
        self.config = self._load_config(config_path)
        self.db = None
        self.embedder = None
        self.controllers = {}

    async def initialize(self):
        """Initialize shared resources (DB, embedder, controllers)"""

        # 1. Database with performance pragmas (ONCE)
        self.db = sqlite3.connect(self.config.db_path)
        self.db.execute("PRAGMA journal_mode = WAL")
        self.db.execute("PRAGMA synchronous = NORMAL")
        self.db.execute("PRAGMA cache_size = -64000")  # 64MB

        # 2. Embedder (expensive ~2s, do ONCE if needed)
        if self.config.embeddings_enabled:
            self.embedder = SentenceTransformer(self.config.model)

        # 3. Controllers (inject dependencies)
        from imem.compile import ParseController
        from imem.manage import ManageController
        from imem.compose import ComposeController

        self.controllers['parse'] = ParseController(self.db, self.embedder)
        self.controllers['manage'] = ManageController(self.db)
        self.controllers['compose'] = ComposeController(self.db, self.embedder)

# Global instance
app = IMEMCLI()

# imem/cli/commands.py (thin wrappers)
@click.group()
def cli():
    """IMEM CLI - thin routing layer"""
    asyncio.run(app.initialize())

@cli.command('index')
@click.option('--vectorize', is_flag=True)
def index_source(source, vectorize, **kwargs):
    """Index source (delegates to ParseController)"""
    return app.controllers['parse'].index(source, vectorize=vectorize, **kwargs)
```

**Benefits:**
- DB + embedder initialized once (saves 2s per command)
- Shared resources across commands
- Clean dependency injection
- CLI becomes ~200 LOC router

**Files:**
- Create `imem/cli/main.py` (IMEMCLI class)
- Create `imem/cli/commands.py` (Click decorators)
- Extract business logic to controllers

### 3.1 Extract Parsing Logic (2 hours)

**Move from `ingest.py` (1200 LOC) to `compile/`:**

```python
# imem/compile/parser.py
class MarkdownParser:
    def parse(self, file_path: Path) -> List[Dict]:
        """Parse markdown to canonical chunks"""
        # Extract from ingest.py
        ...

# imem/compile/templates/changelog.py
class ChangelogTemplate:
    def extract(self, content: str) -> List[Dict]:
        """Changelog-specific parsing"""
        ...
```

**Files to create:**
- `imem/compile/__init__.py`
- `imem/compile/parser.py` (from ingest.py lines 627-804)
- `imem/compile/templates/changelog.py`
- `imem/compile/templates/conversation.py`

### 3.2 Extract Management Logic + Entity Consolidation (3 hours)

**Create `manage/` domain with entity resolution:**

```python
# imem/manage/temporal.py
class TemporalValidator:
    def validate_against_git(self, chunk: Dict) -> Dict:
        """Compare documented decisions vs git commits"""
        # New functionality using SQL JOINs
        ...

# imem/manage/resolver.py
class EntityResolver:
    """MANAGE resolution - project-scoped entities"""

    def __init__(self, project_id: str, db):
        self.project_id = project_id
        self.db = db

    def resolve_entity(self, term: str) -> str:
        """Map entity variation → canonical within project"""
        canonical = self.db.execute('''
            SELECT canonical FROM entity_resolution
            WHERE project_id = ? AND variation = ? COLLATE NOCASE
        ''', (self.project_id, term)).fetchone()

        return canonical['canonical'] if canonical else term

    def expand_query(self, canonical: str) -> List[str]:
        """Expand canonical → all variations"""
        variants = self.db.execute('''
            SELECT variation FROM entity_resolution
            WHERE project_id = ? AND canonical = ?
        ''', (self.project_id, canonical)).fetchall()

        return [canonical] + [v['variation'] for v in variants]

# imem/manage/consolidator.py
class EntityConsolidator:
    """Automatic entity discovery via SQL analytics"""

    def consolidate_from_corpus(self, project_id: str, min_mentions=5):
        """Discover entities, cluster to canonical, store"""

        # SQL analytics to find frequent entities
        entities = self.db.execute('''
            WITH entity_mentions AS (
                SELECT
                    content,
                    COUNT(*) as mentions
                FROM chunks
                WHERE project_id = ?
                GROUP BY content
                HAVING mentions >= ?
            )
            SELECT * FROM entity_mentions
        ''', (project_id, min_mentions)).fetchall()

        # Cluster and store
        for entity in entities:
            # Use string similarity, frequency analysis
            canonical = self._cluster_to_canonical(entity)
            self._store_resolution(project_id, entity, canonical)
```

**Schema:**
```sql
-- Entity resolution (project-scoped)
CREATE TABLE IF NOT EXISTS entity_resolution (
    project_id TEXT NOT NULL,
    variation TEXT NOT NULL,
    canonical TEXT NOT NULL,
    context TEXT,
    confidence REAL DEFAULT 1.0,
    occurrences INTEGER DEFAULT 1,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (project_id, variation)
);

CREATE INDEX idx_entity_canonical ON entity_resolution(project_id, canonical);
```

**Files to create:**
- `imem/manage/__init__.py`
- `imem/manage/temporal.py` (git validation)
- `imem/manage/resolver.py` (entity resolution - query time)
- `imem/manage/consolidator.py` (entity discovery - SQL analytics)
- `imem/manage/registry.py` (move from root)

### 3.3 Slim Down CLI (2 hours)

**Extract logic from cli.py to domains:**

```python
# cli.py (target: ~200 LOC)
@imem.command('index')
@click.option('--vectorize', is_flag=True)
def index_source(source, vectorize, **kwargs):
    """Index source to SQLite (optionally Qdrant)"""
    from imem.compile import Compiler
    from imem.storage import SQLiteStore, QdrantStore

    compiler = Compiler()
    chunks = compiler.parse(source)

    sqlite_store = SQLiteStore(project_root)
    sqlite_store.upsert_chunks(chunks)

    if vectorize:
        qdrant_store = QdrantStore(project_root)
        qdrant_store.upsert_vectors(chunks)

# Move these OUT of cli.py:
# - _index_phase() → compile/parser.py
# - _index_conversations() → compile/parser.py
# - Collection management → storage/qdrant.py
# - Registry operations → manage/registry.py
```

**Refactor:**
- Extract `_index_phase()` (100+ LOC) → `compile/parser.py`
- Extract `_index_conversations()` (100+ LOC) → `compile/parser.py`
- Extract collection logic (100+ LOC) → `storage/qdrant.py`
- Keep only Click decorators + routing in `cli.py`

### 3.4 Testing (1 hour)

**Integration tests:**

```bash
# Test full pipeline
imem index develop
imem compose '{"search": {"mode": "metadata", "filters": {"phase": "develop"}}}'

# Test with vectorization
imem index develop --vectorize
imem compose '{"search": {"mode": "semantic", "text": "authentication"}}'

# Test domain separation
python -c "from imem.compile import Parser; from imem.manage import Registry"
```

---

## Migration Strategy

### Backward Compatibility

1. **Keep old commands working:**
   - `imem index develop` → Auto-populates SQLite now
   - `imem search` → Still works (uses SQLite or Qdrant)
   - `imem compose` → Same config format

2. **Deprecation warnings:**
   - `imem index-metadata` → "Use 'imem index' (SQLite is always indexed)"
   - Old compose.py → "Import from imem.compose.orchestrator"

3. **Migration path:**
   ```bash
   # Migrate existing Qdrant data to SQLite
   imem migrate qdrant-to-sqlite

   # Re-index with new architecture
   imem index develop --force
   ```

### Rollback Safety

- Keep old `compose.py` as `compose_legacy.py`
- Feature flag: `IMEM_USE_LEGACY_COMPOSE=1`
- Test suite validates both paths

---

## Success Criteria

**Phase 1:**
- ✅ `imem index` populates SQLite (always)
- ✅ Qdrant only with `--vectorize` flag
- ✅ No metadata duplication
- ✅ Discovery works on all 283 files

**Phase 2:**
- ✅ Processor chain executes queries
- ✅ Each processor independently testable
- ✅ Backend swappable via StorageProtocol
- ✅ Config-driven pipeline composition

**Phase 3:**
- ✅ `cli.py` < 250 LOC
- ✅ Logic separated into 5 domains
- ✅ Unit tests for each domain
- ✅ Backward compatible

**Overall:**
- ✅ Reindex 283 files in <10 seconds (was 15 min)
- ✅ Experiment with parsing strategies (instant iteration)
- ✅ SQL analytics for pattern mining
- ✅ Foundation for manage/Temporal + manage/Resolver
