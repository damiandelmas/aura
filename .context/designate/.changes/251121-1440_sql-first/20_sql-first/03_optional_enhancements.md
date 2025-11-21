# Optional Enhancements (Post-Phase 6)

**Note:** These enhancements are valuable but NOT required to complete the SQLite-first vision. Implement after Phases 4-6 are complete.

---

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

## Enhanced Entity Consolidation

**From AgentDB pattern - currently using simple regex**

### Current vs Enhanced

**Current (Phase 3):**
- Simple regex entity extraction (camelCase, snake_case, UPPER_CASE)
- String normalization (lowercase, strip whitespace)
- Manual stopword filtering
- Works for 80% of cases

**Enhanced (Optional):**
- Statistical co-occurrence analysis
- Levenshtein distance clustering
- TF-IDF scoring for relevance
- Temporal trend detection

### Enhanced Implementation
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
| **HNSW Backend** | Zero-Docker semantic search | 8h | P1 | After Phase 6 |
| **Enhanced Entity Consolidation** | Statistical clustering | 6h | P2 | After Phase 5 |
| **LLM-Assisted Resolution** | Better entity normalization | 4h | P2 | After Phase 5 |

**P1 (High value):** Add after completing vision (Phases 4-6)
**P2 (Nice to have):** Add when simple approaches show limitations

**Note:** CLI composition root and basic entity consolidation already shipped in Phases 1-3.
