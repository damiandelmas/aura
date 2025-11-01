# Knowledge Graph: Explicit Persistence

**Feature Status:** Designed, not implemented
**Current:** 60-80% there (implicit graph via metadata)

---

## The Problem

Currently edges are computed at query time from metadata. Fast enough, but:
- Recomputes same relationships every query
- No stable topology for BRAIN infrastructure
- Intelligence layers recompute instead of query

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

## Proposed: Explicit Persistence

**Architecture:**
```
Metadata implies relationships
    ↓
Compute edges once (write-time)
    ↓
Persist in BRAIN infrastructure
    ↓
Intelligence layers query (not recompute)
```

**Edge types from metadata:**
- Same file → Sibling edges
- Same session → Genealogy edges
- Semantic + temporal → Evolution edges

**Benefits:**
- Edges computed once (not per query)
- Graph persisted in BRAIN
- Topology detection reads precomputed structure
- Intelligence layers query (not recompute)

---

## Dataflow

```
Write time:
  Source → Metadata → Derive edges → Persist to BRAIN

Query time:
  BRAIN edges → Topology detection → Relationship labeling

Background:
  BRAIN edges → Graph analysis → Authority metrics
```

**Property:** Relationships explicit, queryable, stable.