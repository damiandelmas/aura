# 3 Critical Patterns from AgentDB

## 1. Episodic Consolidation = Automatic Schema Evolution

**Core Insight**: AgentDB uses **pure SQL analytics** (GROUP BY, keyword frequency) to discover patterns from successful episodes, then consolidates them into reusable skills with confidence scores.

**AgentDB Pattern** (lines 232-347):
```typescript
async consolidateEpisodesIntoSkills() {
  // 1. SQL: Group episodes by task, filter by quality (reward ≥ 0.7)
  // 2. Extract keyword frequency from outputs (NLP-lite)
  // 3. Calculate confidence from sample size + success rate
  // 4. Store as skill with metadata
}
```

**5 Pattern Extraction Techniques**:
1. Keyword frequency (TF-IDF lite)
2. Metadata consistency detection
3. Statistical aggregation (reward distribution)
4. Temporal trend analysis (learning curves)
5. Cluster by similarity (Levenshtein distance)

**IMEM Application**: `manage/consolidator.py` for automatic entity discovery
- Query: `SELECT DISTINCT section_name, COUNT(*) FROM chunks GROUP BY section_name`
- Cluster variations: `['jwt', 'JWT', 'json-web-tokens']` → canonical `jwt`
- Store in Registry with confidence score
- **No embeddings needed** — pure SQL + string similarity

**Why Critical**: Validates conversation line 1441: *"SQLite is the unlock, not vector embeddings"*

## 2. HNSW Index = Local Vector Search (No Qdrant)

**Core Insight**: HNSW (Hierarchical Navigable Small World) provides **O(log n) approximate k-NN** search, achieving 10-100x speedup over brute force while maintaining 95-99% accuracy.

**AgentDB Pattern** (lines 332-464):
```typescript
class HNSWIndex {
  private idToLabel: Map<number, number>;  // DB ID → HNSW label mapping

  async buildIndex() {
    const rows = db.prepare(`SELECT id, embedding FROM episodes`).all();
    this.index.initIndex(rows.length, M=16, efConstruction=200);
    for (const row of rows) this.index.addPoint(row.embedding, row.id);
    await this.saveIndex('./agentdb.hnsw');  // Persist to disk
  }

  async search(queryVector, k) {
    return this.index.searchKnn(queryVector, k);  // 5ms vs 200ms brute force
  }
}
```

**Key Architecture Decisions**:
1. **Separate index lifecycle**: Build explicitly, not on every query
2. **Persistent index**: Serialize to disk, avoid rebuild on restart
3. **Graceful degradation**: Falls back to brute force if build fails
4. **Rebuild threshold**: Track updates, rebuild when >10% corpus changed

**IMEM Application**: `storage/hnsw_backend.py`
- SQLite stores embeddings as BLOBs
- HNSW index built from SQLite, persisted as `.hnsw` file
- **Performance**: 15s build for 50k chunks, 5ms queries (vs 15min Qdrant upload)
- **Deployment**: `imem compile --backend sqlite+hnsw` (zero Docker)

**Why Critical**: Completes SQLite-first architecture — metadata (SQL) + semantic (HNSW) in single database

## 3. CLI Composition Root = Fix 1800 LOC Bloat

**Core Insight**: CLI should be **composition root** — single initialization point for all dependencies (DB, embedder, controllers), with commands as thin wrappers delegating to domain controllers.

**AgentDB Pattern** (lines 51-130):
```typescript
class AgentDBCLI {
  async initialize(dbPath: string) {
    this.db = await createDatabase(dbPath);
    this.db.pragma('journal_mode = WAL');  // Performance tuning

    this.embedder = new EmbeddingService({...});
    await this.embedder.initialize();  // EXPENSIVE (2s model download), do ONCE

    // Inject dependencies into controllers
    this.reflexion = new ReflexionMemory(this.db, this.embedder);
    this.skills = new SkillLibrary(this.db, this.embedder);
  }

  async storeEpisode(params) {
    return this.reflexion.storeEpisode(params);  // Thin wrapper
  }
}
```

**Key Decisions**:
1. **Single initialization**: Create DB + embedder once, reuse across all commands
2. **Dependency injection**: Controllers receive dependencies via constructor, never instantiate
3. **Thin commands**: 10-20 LOC wrappers, business logic in domain controllers
4. **Schema fallback**: Load from multiple paths (dist, src, node_modules) for robustness

**IMEM Refactor**: `cli/main.py` (~200 LOC) replaces `cli.py` (1800 LOC)
```
cli/main.py         → IMEMCLI class + initialize()
compile/parser.py   → _index_phase() logic moved here
retrieve/orchestrator.py → compose() logic moved here
storage/factory.py  → Backend instantiation
```

**Why Critical**: Prevents "shotgun initialization" (every command creates own DB/embedder), enables shared resources, consistent config

**Critical Implementation Details** (from AgentDB lines 512-563):
```typescript
// 1. DB Pragmas (applied ONCE at init)
this.db.pragma('journal_mode = WAL');      // Write-Ahead Logging (concurrency)
this.db.pragma('synchronous = NORMAL');    // Balance safety/speed
this.db.pragma('cache_size = -64000');     // 64MB cache

// 2. Schema Loading (fallback paths for robustness)
const basePaths = [
  path.join(__dirname, '../schemas'),
  path.join(process.cwd(), 'dist/schemas'),
  path.join(process.cwd(), 'node_modules/agentdb/dist/schemas')
];
// Try each path, stop at first success

// 3. Controller Instantiation Order (dependencies first)
this.db = await createDatabase(dbPath);                    // 1. Storage
this.embedder = new EmbeddingService({...});               // 2. Shared service
await this.embedder.initialize();                          // EXPENSIVE (~2s)
this.reflexion = new ReflexionMemory(this.db, this.embedder); // 3. Controllers
```

**IMEM Signature**:
```python
class IMEMCLI:
    async def initialize(self, config: IMEMConfig):
        # 1. DB with pragmas
        self.db = create_db(config.db_path)
        self.db.execute("PRAGMA journal_mode = WAL")
        self.db.execute("PRAGMA cache_size = -64000")

        # 2. Embedder (expensive, do once)
        self.embedder = EmbedderFactory.create(config.embeddings)
        await self.embedder.initialize()

        # 3. Controllers (inject dependencies)
        self.parser = Parser(self.db, self.embedder)
        self.resolver = SchemaResolver(self.db)
        self.orchestrator = Orchestrator(self.db, self.embedder)
        self.consolidator = EntityConsolidator(self.db, self.resolver)
```

---

## Implementation Priorities

| Pattern | Impact | Effort | Priority |
|---------|--------|--------|----------|
| **CLI Composition Root** | Fix 1800 LOC bloat, shared resources | 4h | **P0** |
| **Entity Consolidation** | Automatic schema evolution | 6h | **P0** |
| **HNSW Index** | Local semantic search (replaces Qdrant) | 8h | **P1** |

**Skipped Patterns**:
- Controller DI: Already implicit in current code
- Causal Graphs: Research-phase, requires A/B testing infrastructure

---

## Architectural Validation

Your conversation insight (line 1441): **"SQLite is the unlock, not vector embeddings"**

AgentDB (state-of-the-art agent memory system) confirms:
1. Pattern discovery = SQL analytics (GROUP BY, frequency) — no embeddings
2. Vector search = Optional, stored as BLOBs in SQLite
3. Single DB = Composition root, shared resources

**You're architecturally correct.**

---

## HNSW Explainer

**What**: Approximate k-NN algorithm using hierarchical graph structure (like skip list for vectors)
**Performance**: O(log n) vs O(n) brute force — 40-625x speedup
**Trade-off**: 95-99% accuracy (vs 100% exact), negligible in practice

**Multi-level Search**:
```
Level 2 (sparse): A -------> B -------> C
Level 1 (medium): A -> D -> B -> E -> C -> F
Level 0 (dense):  A-D-G-B-E-H-C-F-I-J
```
Start at top → long jumps to region → descend → refine → exact neighbors at bottom

**Parameters** (AgentDB defaults):
- `M=16`: Connections per node (higher = better recall, slower build)
- `efConstruction=200`: Build-time candidates (quality)
- `efSearch=100`: Query-time candidates (speed)
- `rebuildThreshold=0.1`: Rebuild after 10% updates

**HNSW vs Qdrant**:
- HNSW: In-process, 0 dependencies, 1k-10M vectors, 5ms queries
- Qdrant: External service, distributed, monitoring, >1M scale
- **IMEM scale (50k-500k)**: HNSW sufficient

## IMEM Migration to SQLite+HNSW

**Current** (Dual Storage):
```
Qdrant (external) ← Vectors + metadata (duplicate)
SQLite (local)    ← Metadata + discovery primitives
→ 15min reindex, Docker required, data in 2 places
```

**Proposed** (Single Storage):
```
SQLite ← Metadata (tables) + Vectors (BLOBs) + HNSW index (.hnsw file)
→ 15s rebuild, zero deps, single source of truth
```

**Query Distribution** (from conversation lines 599-660):
- 90%: Metadata (SQL) — phase=develop, siblings, genealogy, temporal
- 10%: Semantic (HNSW) — "find auth patterns"

**Performance** (50k chunks, 384-dim):
```
Qdrant:     3ms query,  15min upload,  Docker required
HNSW:       5ms query,  15s build,     pip install hnswlib
Brute SQL:  180ms query, 0s build,     already have
```

**Deployment**:
```bash
imem compile --backend sqlite        # Metadata only (fastest)
imem compile --backend sqlite+hnsw   # + Semantic (dev default)
imem compile --backend qdrant        # Production scale (optional)
```

**SQLite Schema Changes**:
```sql
-- Add embedding column to existing chunks table
ALTER TABLE chunks ADD COLUMN embedding BLOB;

-- Index for HNSW build query
CREATE INDEX idx_chunks_with_embeddings
ON chunks(chunk_id) WHERE embedding IS NOT NULL;

-- Track HNSW index state
CREATE TABLE hnsw_metadata (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Storage Factory Pattern**:
```python
class StorageFactory:
    @staticmethod
    def create(backend: str, config: dict) -> ChunkRetriever:
        if backend == 'sqlite':
            return SQLiteStore(config['db_path'])
        elif backend == 'sqlite+hnsw':
            return HNSWBackend(config['db_path'], dimension=384)
        elif backend == 'qdrant':
            return QdrantBackend(config['url'], config['collection'])
```

---

## Key Architectural Insights

**From Conversation (251117-1624.md)**:

1. **Line 1441**: "SQLite is the unlock, not vector embeddings"
   - Discovery primitives work on 100% corpus without vectors
   - Pattern extraction = SQL analytics (no ML needed)
   - Vectors optional, selective (10% of queries)

2. **Lines 599-660**: Query distribution analysis
   - 90% metadata (SQL): filters, siblings, genealogy, temporal
   - 10% semantic (vectors): "find similar patterns"
   - Current Qdrant overhead unjustified for 10% use case

3. **Line 1792**: CLI bloat (1800 LOC) indicates missing abstraction
   - Business logic leaked into command definitions
   - No shared initialization (duplicate DB/embedder creation)
   - Controllers should own domain logic, CLI should route

**From AgentDB Validation**:

1. **Consolidation = Evidence-based schema**
   - Don't hardcode entity types (jwt, auth, pattern)
   - Discover from corpus usage (GROUP BY + frequency)
   - Store with confidence score (sample_size / total_occurrences)

2. **HNSW = Local-first vector search**
   - Build once (15s), persist to disk (.hnsw file)
   - Graceful degradation (falls back to brute force)
   - Rebuild threshold (10% updates triggers reindex)

3. **CLI Root = Dependency graph clarity**
   - Storage → Embedder → Controllers → Commands
   - Expensive ops (embedder init) happen once
   - DB pragmas (WAL, cache) set once, benefit all queries

## Reference Files

**AgentDB Patterns**: `.context/design/async-repo-study-1/00_research/agentdb-patterns.md`
- Pattern 2 (Consolidation): Lines 76-189
- Pattern 4 (HNSW): Lines 332-477
- Pattern 5 (CLI Root): Lines 481-620

**Conversation Context**: `.claude/.convs/251117-1624.md`
- SQLite unlock insight: Line 1441
- Query distribution: Lines 599-660
- CLI bloat: Line 1792