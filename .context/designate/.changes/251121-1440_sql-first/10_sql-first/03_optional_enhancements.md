# Optional Enhancements (Post-Phase 3)

## HNSW Local Vector Search (Replace Qdrant)

**From AgentDB validation - 11_edits.md**

### Why HNSW

**Current (Qdrant):**
- External service (Docker required)
- 15min upload time for 50k chunks
- Network overhead per query
- Production-scale infrastructure (overkill for 50k-500k chunks)

**HNSW (Local):**
- In-process library (`pip install hnswlib`)
- 15s build time for 50k chunks
- <5ms queries (vs 3ms Qdrant, negligible difference)
- Zero dependencies, single database

### Architecture

```
SQLite (single database)
├── Metadata (tables) ← 90% of queries
├── Embeddings (BLOBs) ← Optional
└── HNSW index (.hnsw file) ← 5ms semantic search

No Qdrant. No Docker.
```

### Implementation

**Schema change:**
```sql
-- Add embedding column
ALTER TABLE chunks ADD COLUMN embedding BLOB;

-- Track HNSW state
CREATE TABLE hnsw_metadata (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Backend:**
```python
# imem/storage/hnsw_backend.py
class HNSWBackend(StorageProtocol):
    def __init__(self, db_path, dimension=384):
        self.db = sqlite3.connect(db_path)
        self.index = hnswlib.Index(space='cosine', dim=dimension)
        self._load_or_build_index()

    def _load_or_build_index(self):
        if Path('.imem/corpus.hnsw').exists():
            self.index.load_index('.imem/corpus.hnsw')
        else:
            # Build from SQLite BLOBs
            rows = self.db.execute(
                "SELECT id, embedding FROM chunks WHERE embedding IS NOT NULL"
            ).fetchall()
            self.index.init_index(len(rows), M=16, efConstruction=200)
            for row in rows:
                self.index.add_items([row['embedding']], [row['id']])
            self.index.save_index('.imem/corpus.hnsw')
```

**Usage:**
```bash
# Metadata only (fastest)
imem compile --backend sqlite

# + Local semantic search (dev default)
imem compile --backend sqlite+hnsw

# Production scale (optional, if >1M vectors)
imem compile --backend qdrant
```

### Performance

**50k chunks, 384-dim embeddings:**
```
Qdrant:     3ms query,  15min upload,  Docker required
HNSW:       5ms query,  15s build,     pip install
Brute SQL:  180ms query, 0s build,     already have
```

**Query distribution (from conversation analysis):**
- 90%: Metadata (SQL) - phase filters, siblings, genealogy
- 10%: Semantic (HNSW) - "find similar patterns"

**Cost analysis:**
- Qdrant overhead unjustified for 10% use case
- HNSW sufficient for IMEM scale (50k-500k chunks)

### Parameters

**From AgentDB defaults:**
- `M=16`: Connections per node (recall quality)
- `efConstruction=200`: Build-time candidates
- `efSearch=100`: Query-time candidates
- `rebuildThreshold=0.1`: Rebuild after 10% updates

### Timeline

**Effort:** 8 hours
- SQLite BLOB storage: 2 hours
- HNSW integration: 4 hours
- Testing + benchmarks: 2 hours

**Priority:** P1 (after Phase 3)
- Enables zero-Docker deployment
- Completes SQLite-first vision
- Qdrant becomes truly optional

---

## CLI Composition Root (Fix 1800 LOC)

**From AgentDB pattern - 11_edits.md**

### The Problem

**Current:**
- Every command creates own DB connection
- Embedder initialized multiple times (~2s each)
- Business logic scattered in CLI (1800 LOC)
- No shared resources

**Result:** Slow startup, code duplication, shotgun initialization

### The Pattern

**Composition Root:** Single initialization point for all dependencies

```python
# imem/cli/main.py
class IMEMCLI:
    async def initialize(self, config: IMEMConfig):
        # 1. DB with performance pragmas (ONCE)
        self.db = sqlite3.connect(config.db_path)
        self.db.execute("PRAGMA journal_mode = WAL")
        self.db.execute("PRAGMA synchronous = NORMAL")
        self.db.execute("PRAGMA cache_size = -64000")  # 64MB

        # 2. Embedder (expensive ~2s, do ONCE)
        if config.embeddings_enabled:
            self.embedder = SentenceTransformer(config.model)

        # 3. Controllers (inject dependencies)
        self.parser = Parser(self.db, self.embedder)
        self.resolver = CompileResolver(self.db)
        self.orchestrator = Orchestrator(self.db, self.embedder)
        self.consolidator = EntityConsolidator(self.db)
```

**Commands become thin wrappers:**
```python
@cli.command('index')
def index_source(source, **kwargs):
    return app.parser.index(source, **kwargs)  # 10 LOC, delegates to domain
```

### Benefits

**Shared resources:**
- DB connection reused (with pragmas applied once)
- Embedder initialized once (saves 2s per command)
- Controllers share dependencies (no duplication)

**Clean separation:**
- CLI = argument parsing + routing (~200 LOC)
- Controllers = domain logic (compile/, manage/, compose/)
- Single initialization graph (clear dependencies)

### Implementation

**Structure:**
```
imem/cli/
├── main.py         # IMEMCLI class (composition root)
└── commands.py     # Click decorators (thin wrappers)

imem/compile/
└── controller.py   # ParseController (business logic from cli.py)

imem/manage/
└── controller.py   # ManageController (business logic from cli.py)
```

**Migration:**
```python
# Before (cli.py - 1800 LOC)
@imem.command('index')
def index_source(source, **kwargs):
    # 100+ LOC of parsing logic here
    registry = SimpleRegistry()
    db = create_db(...)
    embedder = SentenceTransformer(...)
    # ... business logic ...

# After (cli/commands.py - 10 LOC)
@imem.command('index')
def index_source(source, **kwargs):
    return app.parser.index(source, **kwargs)
```

### Timeline

**Effort:** 4 hours (part of Phase 3)
- Create IMEMCLI class: 1 hour
- Extract to controllers: 2 hours
- Update commands: 1 hour

**Priority:** P0 (include in Phase 3)
- Fixes 1800 LOC bloat
- Enables shared resources
- Required for clean domain separation

---

## Entity Consolidation (Automatic Schema Evolution)

**From AgentDB pattern - 11_edits.md**

### The Pattern

**AgentDB approach:**
- Use SQL analytics to discover entity patterns
- Cluster variations → canonical entities
- Store with confidence scores
- No embeddings needed - pure SQL + string similarity

### For IMEM (MANAGE Resolution)

**Automatic entity discovery:**
```sql
-- Find all entity mentions in project
WITH entity_mentions AS (
  SELECT
    REGEXP_EXTRACT(content, '\b[A-Z]{2,}\b') as term,
    COUNT(*) as mentions
  FROM chunks
  WHERE project_id = ?
  GROUP BY term
  HAVING mentions >= 5  -- Quality threshold
)
SELECT
  LOWER(term) as canonical,
  GROUP_CONCAT(DISTINCT term) as variations,
  mentions,
  mentions * 1.0 / (SELECT COUNT(*) FROM chunks) as confidence
FROM entity_mentions
GROUP BY canonical
ORDER BY confidence DESC;
```

**Result:**
```
jwt   → [JWT, jwt, json-web-tokens]  (confidence: 0.15, 45 mentions)
auth  → [auth, authentication, Auth] (confidence: 0.12, 38 mentions)
redis → [Redis, redis, Redis-DB]     (confidence: 0.08, 25 mentions)
```

**Auto-populate resolution table:**
```python
# imem/manage/consolidator.py
class EntityConsolidator:
    def consolidate_from_corpus(self, project_id: str, min_mentions=5):
        """Discover entities via SQL analytics"""

        # Query corpus for frequent terms
        entities = self.db.execute('''
            -- SQL from above
        ''', (project_id, min_mentions)).fetchall()

        # Store in resolution table
        for entity in entities:
            for variation in entity['variations']:
                self.db.execute('''
                    INSERT OR IGNORE INTO entity_resolution
                    (project_id, variation, canonical, confidence)
                    VALUES (?, ?, ?, ?)
                ''', (project_id, variation, entity['canonical'], entity['confidence']))
```

**Usage:**
```bash
# Index project
imem index develop

# Auto-consolidate entities
imem consolidate --project proj_123 --min-mentions 5

# Query with expansion
imem query-metadata --text "jwt" --project proj_123
# Expands to: jwt, JWT, json-web-tokens automatically
```

### Techniques (from AgentDB)

1. **Keyword frequency** (TF-IDF lite)
2. **Metadata consistency detection**
3. **Statistical aggregation** (co-occurrence)
4. **Temporal trend analysis**
5. **Cluster by similarity** (Levenshtein distance)

### Timeline

**Effort:** 6 hours
- SQL discovery queries: 2 hours
- Clustering algorithms: 2 hours
- Integration with resolver: 2 hours

**Priority:** P0 (include in Phase 1)
- Enables automatic entity resolution
- No manual entity mapping needed
- Validates SQLite-first approach

---

## Summary: Optional Enhancements

| Enhancement | Impact | Effort | Priority | When |
|-------------|--------|--------|----------|------|
| **CLI Composition Root** | Fix 1800 LOC bloat | 4h | P0 | Phase 3 |
| **Entity Consolidation** | Auto entity discovery | 6h | P0 | Phase 1 |
| **HNSW Backend** | Zero-Docker semantic | 8h | P1 | Post-Phase 3 |

**P0 (Essential):** Include in main refactor
**P1 (High value):** Add immediately after Phase 3

Total additional effort: 18 hours
Total project: ~33 hours (15h phases + 18h enhancements)
