# BRAIN Persistence Layer: Learned Metadata

**Feature Status:** Designed, not implemented

---

## The Concept

Three layers of metadata with different update frequencies:

```
Layer 1: Static (Qdrant)     - timestamp, type, content (never changes)
Layer 2: Dynamic (BRAIN)     - reference_count, pagerank (changes frequently)
Layer 3: Composition (API)   - ephemeral views assembled at query time
```

**The Insight:** Not all metadata ages the same. Separate what's written from what's learned.

---

## Architecture

```
Qdrant (immutable content)
↓
SQLite graph.db (BRAIN):
  - edges (persistent graph)
  - brain_stats: reference_count, last_accessed
  - brain_metrics: pagerank_score, superseded_by
↓
Graph API (ephemeral composition)
```

---

## BRAIN Conceptualization (3 Layers)

### Layer 1: Static Metadata (Never Changes)

From Qdrant, copied to graph:
```
nodes: id, timestamp, type, keywords, content_hash
```

### Layer 2: Dynamic Stats (Updates Every Query)

```sql
brain_stats:
  chunk_id,
  reference_count,      -- Increment on every retrieval
  last_accessed,        -- Update timestamp
  access_frequency      -- Rolling 7-day average
```

**Adaptive Level:** High (real-time)
**Cost:** ~1ms per query (simple UPDATE)

### Layer 3: Computed Metrics (Batch Recompute)

```sql
brain_metrics:
  chunk_id,
  pagerank_score,       -- Recompute nightly
  centrality_score,     -- Recompute nightly
  superseded_by,        -- Detect weekly (LLM)
  supersession_confidence
```

**Adaptive Level:** Medium (nightly/weekly)
**Cost:** Nightly (5 min), Weekly LLM ($0.01)

---

## BRAIN Adaptiveness

**Real-time (every query):**
- ✅ `reference_count++`
- ✅ `last_accessed = now()`

**Fast batch (nightly):**
- ✅ Recompute PageRank
- ✅ Recompute centrality
- ✅ Update `age_months`

**Slow batch (weekly):**
- ✅ Entity resolution (LLM)
- ✅ Supersession detection (LLM)
- ✅ Pattern mining

**Why this split?**
- Real-time: Cheap operations, high value
- Nightly: Expensive graph algorithms, update while you sleep
- Weekly: LLM costs, diminishing returns on daily updates

---

## Key Terms

- **Static Metadata**: Never changes (timestamp, type, content_hash)
- **Learned Metadata**: Accumulates from usage (reference_count, pagerank)
- **Adaptive Levels**: Real-time vs Batch vs LLM (stratified by cost/value)
- **Separate Persistence**: BRAIN lives in SQLite, not Qdrant

---

## The Value

- **Qdrant stays immutable** (vector search only)
- **BRAIN learns from usage** (which chunks are authoritative?)
- **Ephemeral composition** (assemble views at query time, don't store)
- **Continuous learning** without rewriting history

---

## Related Concepts

See: [VISION.md](./VISION.md) - Principle #4: Stratified Learning
See: [knowledge-graph.md](./knowledge-graph.md) - SQLite storage architecture
See: [adaptive-updates.md](./adaptive-updates.md) - Update frequency details
