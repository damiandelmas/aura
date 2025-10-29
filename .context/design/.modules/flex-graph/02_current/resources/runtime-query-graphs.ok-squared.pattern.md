---
session_id: ca22384b-3a6d-4821-8b70-2aa1a89ea4ba
date: 2025-10-27
level: architecture-pattern
innovation: runtime-query-graphs
---

# Runtime Query Graphs: Architecture Pattern

## Core Mechanism

**Three-step pattern:**

1. **Query:** Vector search returns top-k results (k=10-30)
2. **Build:** Construct NetworkX graph from result set
3. **Apply:** Run algorithm (PageRank, centrality, communities)
4. **Discard:** Ephemeral by default, optionally persist

**Graph construction:**
```
Nodes: k results from search
Edges: Metadata-based relationships
  - Same file_path → sibling edge (weight=0.9)
  - Same session_id → genealogy edge (weight=0.8)
  - Cosine similarity > 0.85 → semantic edge (weight=similarity)

Complexity: O(k²) edge computation where k << n
```

## Algorithms Enabled

**PageRank (authority):**
- Most-referenced chunks in result set
- Use case: "What's the canonical decision?"

**Betweenness Centrality (bridges):**
- Chunks connecting different concepts
- Use case: "What ties UI + backend + security?"

**Community Detection (clusters):**
- Groups of related decisions
- Use case: "What are the decision clusters?"

**Shortest Path (genealogy):**
- Trace from conversation → decision → refinement
- Use case: "How did we arrive here?"

## Query-Specific Graphs

**Different queries = different graphs:**

```
Query: "refactor patterns" --decisions
→ k=20 refactor decisions
→ Graph with refactor-specific edges
→ PageRank shows most-cited refactor patterns

Query: "authentication" --decisions
→ k=20 auth decisions
→ Graph with auth-specific edges
→ PageRank shows most-cited auth patterns
```

**Authority is context-dependent, not global.**

## Performance Trade-Off

**Precomputed (traditional):**
- Build: O(n²) at index time (n=500 docs → 125k edges)
- Query: O(1) lookup
- Maintenance: O(n) on each update

**Runtime (AURA):**
- Build: O(k²) at query time (k=20 → 400 edges)
- Query: 40-100ms additional latency
- Maintenance: Zero (ephemeral)

**Break-even:** k < √n (20 < √500 ≈ 22) → runtime wins

## Persistence Strategy

**Default: Ephemeral**
- Build graph per query
- Discard after use
- No storage overhead

**Optional: Persist**
- Save graph with ID
- Reuse for inspection/debugging
- Prune after N days

**Hybrid: Session-scoped**
- Keep graphs for current session
- Discard on session end
- Enables multi-step analysis
