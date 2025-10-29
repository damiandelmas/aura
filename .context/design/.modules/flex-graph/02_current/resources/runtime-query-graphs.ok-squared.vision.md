---
session_id: ca22384b-3a6d-4821-8b70-2aa1a89ea4ba
date: 2025-10-27
level: vision
innovation: runtime-query-graphs
---

# Runtime Query Graphs: O(k²) Not O(n²)

## The Geometric Insight

**Graph scope = query results, not entire corpus.**

Traditional: Index all entities → compute all edges → O(n²) where n=corpus
AURA: Query top-k → compute edges → O(k²) where k=20

**The shift:**
```
Neo4j:  n=500 docs → 125k potential edges → precompute all
AURA:   n=500 docs → query returns k=20 → compute 400 edges → discard
```

**Property:** Query first, graph second. Not graph first, query second.

## The Systemic Implication

**Ephemeral graphs enable context-specific algorithms.**

```
Traditional: One graph for all queries (static structure)
AURA: New graph per query context (dynamic structure)
```

**Benefit:** PageRank on "authentication decisions" ≠ PageRank on "database patterns"

**Cost:** ~40-100ms graph construction (vs 0ms with precomputed)
**Gain:** Context-adaptive ranking, zero maintenance

## Pattern-Level Thinking

**Authority = query-specific, not corpus-wide.**

```
Query 1: "refactor patterns"
→ Build graph from 20 refactor results
→ PageRank shows most-referenced refactor patterns

Query 2: "authentication patterns"
→ Build graph from 20 auth results
→ PageRank shows most-referenced auth patterns

Different graphs, different authority rankings.
```

**No precomputation can achieve this.**

## The Innovation

**Graphs constructed at query time from result sets.**

- Nodes: Top-k search results
- Edges: Metadata relationships (siblings, genealogy, semantic)
- Algorithms: PageRank, centrality, communities
- Lifecycle: Build → Apply → Discard

This enables context-specific graph algorithms without O(n²) precomputation tax.
