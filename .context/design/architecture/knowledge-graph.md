# Knowledge Graph: Explicit Persistence

**Feature Status:** Designed, not implemented
**Current:** 60-80% there (implicit graph via metadata)

---

## The Problem

Currently edges are computed at query time from metadata. Fast enough, but:
- Can't run graph algorithms (PageRank needs stable topology)
- Recomputes same relationships every query
- No foundation for BRAIN metrics

---

## Current State: Implicit Graph

```
Metadata → Edges computed at query time
session_id → Genealogy edge (ephemeral)
timestamp+semantic → Temporal edge (ephemeral)
file_path → Sibling edge (ephemeral)
```

**Problem:** Recomputing edges every query

---

## Proposed: Explicit Lightweight Graph

**Storage:** SQLite (graph.db)

```sql
TABLE nodes:
  id, chunk_id, timestamp, type, keywords

TABLE edges:
  from_id, to_id, edge_type, weight, created_at

TABLE brain_stats:
  chunk_id, reference_count, pagerank, age_months, last_accessed
```

**On new changelog indexed:**
```python
# Add nodes
for chunk in chunks:
    graph.add_node(chunk['id'], metadata=chunk['payload'])

# Add edges (from metadata)
for chunk in chunks:
    # Sibling edges
    siblings = get_chunks_with_same_file_path(chunk['file_path'])
    for sibling in siblings:
        graph.add_edge(chunk['id'], sibling['id'], type='sibling', weight=0.9)

    # Session edges (if session_id exists)
    if chunk['session_id']:
        conversations = get_chunks_with_session(chunk['session_id'])
        for conv in conversations:
            graph.add_edge(chunk['id'], conv['id'], type='genealogy', weight=0.85)

# Update BRAIN stats (nightly batch)
brain.recompute_pagerank()
```

**Benefits:**
- Edges computed once (not per query)
- Graph persisted (queryable)
- BRAIN metrics precomputed
- Query time just reads graph

---

## Storage Choice: SQLite

**Why SQLite over JSON:**

JSON issues:
```python
# Every query loads entire file
brain = json.load('brain.json')  # Load 10MB
brain['stats'][chunk_id]['reference_count'] += 1
json.dump(brain, 'brain.json')  # Write 10MB
# Concurrent queries = race conditions
```

SQLite benefits:
```python
# Atomic updates, concurrent safe
db.execute(
    "UPDATE brain_stats SET reference_count = reference_count + 1 WHERE chunk_id = ?",
    (chunk_id,)
)  # ~1ms, indexed, concurrent-safe
```

**Size comparison:**
- 1000 chunks: JSON = 5MB, SQLite = 500KB
- 10000 chunks: JSON = 50MB, SQLite = 5MB

---

## Architecture: Explicit Graph + Adaptive BRAIN

```
┌─────────────────────────────────────┐
│ Qdrant (Immutable Content)         │
│ - Chunks with embeddings           │
│ - Search only, not queried for KG  │
└─────────────────────────────────────┘
           ↓ (indexed once)
┌─────────────────────────────────────┐
│ graph.db (SQLite)                  │
│                                     │
│ [nodes] - Static metadata          │
│ [edges] - Computed from metadata   │
│           (sibling, genealogy)     │
│                                     │
│ [brain_stats] (adaptive)           │
│ - reference_count (real-time)      │
│ - last_accessed (real-time)        │
│                                     │
│ [brain_metrics] (batch)            │
│ - pagerank_score (nightly)         │
│ - superseded_by (weekly)           │
│                                     │
│ [entity_map]                       │
│ - canonical → aliases (weekly)     │
└─────────────────────────────────────┘
           ↓ (query time)
┌─────────────────────────────────────┐
│ Graph API (Ephemeral Composition)  │
│                                     │
│ 1. Resolve entities (entity_map)   │
│ 2. Traverse graph (edges)          │
│ 3. Lookup stats (brain_stats)      │
│ 4. Detect topology                 │
│ 5. Enrich with BRAIN context       │
│ 6. Structure for serving           │
└─────────────────────────────────────┘
```

---

## Implementation Cost

**Initial build (~1 hour one-time):**
```python
# Convert existing metadata → explicit graph
for changelog in all_changelogs:
    chunks = qdrant.get_chunks(changelog)
    for chunk in chunks:
        graph.add_node(chunk)
        add_edges_from_metadata(chunk)

# Initial metrics
compute_pagerank()
compute_centrality()
```

**Ongoing:**
- Per query (real-time): `UPDATE brain_stats SET reference_count += 1` (~1ms)
- Nightly (batch): `compute_pagerank()` (~5 min for 10K nodes)
- Weekly (LLM): `update_entity_map()` (~$0.01)

---

## Bottom Line

Yes, build the explicit knowledge graph:
- You're 60-80% there (metadata = edges)
- Just persist it in SQLite
- BRAIN = stats + metrics in same DB
- Adaptive at 3 levels (real-time, nightly, weekly)

---

## Related Concepts

See: [VISION.md](./VISION.md) - Principle #3: Persistent Relationships
See: [brain-persistence.md](./brain-persistence.md) - BRAIN metadata storage
See: [adaptive-updates.md](./adaptive-updates.md) - Update frequency stratification
