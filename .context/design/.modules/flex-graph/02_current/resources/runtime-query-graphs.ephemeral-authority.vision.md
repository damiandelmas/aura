---
session_id: e025fbb0-1abb-46e8-82a1-79c49afcc32d
date: 2025-10-27
type: vision.innovation
resolution: geometric
keywords: "o(k2)-not-o(n2) authority-ranking ephemeral-graphs"
---

# Runtime Query Graphs: O(k²) Authority Discovery

## The Insight

**Build graphs from query results, not corpus.**

Traditional KG: Build O(n²) edges across entire corpus upfront
Runtime graphs: Build O(k²) edges across query results on-demand

The power isn't in precomputing everything. It's in graphing what matters.

## The Geometry

```
Traditional Knowledge Graph (precomputed):

Corpus: 1000 documents
Edges: All possible connections
Complexity: O(n²) = 1,000,000 comparisons
Storage: Graph database with 50,000+ edges
Maintenance: Recompute on every addition

Query: Walk precomputed graph
Time: Fast (microseconds)
Cost: Massive upfront computation


AURA Runtime Graphs (on-demand):

Corpus: 1000 documents
Edges: None stored
Query results: 20-30 chunks
Complexity: O(k²) = 400-900 comparisons
Storage: Ephemeral NetworkX object
Maintenance: Zero (rebuilt each query)

Query: Build graph from results, apply algorithm
Time: Acceptable (~40-100ms construction + algorithm)
Cost: Zero upfront, minimal query-time
```

## The System Property

**Authority emerges from result-set graphs:**

```
Multi-query workflow:

1. Execute 3 semantic searches:
   - "provider agnostic" (decisions) → 10 results
   - "provider patterns" (patterns) → 10 results
   - "provider failures" (failures) → 10 results
   Total: 30 result chunks

2. Build graph from 30 chunks:
   - Nodes: 30 chunks
   - Edges: Metadata relationships
     * Same file_path → file edge
     * Same session_id → session edge
     * Semantic similarity → semantic edge
   Total: ~60-80 edges (sparse graph)

3. Apply PageRank:
   - Most-referenced chunks score higher
   - Bridge concepts identified via centrality
   - Authority emerges from structure

4. Return top 10 by PageRank score
   (Not by original semantic similarity)

5. Discard graph
   (Ephemeral, reconstructed next query)
```

## The Behavior

**Three graph operations:**

1. **Build graph** (from result set)
   - Input: List of chunk IDs
   - Construct: NetworkX DiGraph
   - Add edges: Metadata-based relationships
   - Output: Graph ID (ephemeral)

2. **Apply algorithm** (to graph)
   - Input: Graph ID, algorithm name
   - Execute: PageRank, centrality, clustering
   - Output: Ranked chunk IDs

3. **Discard** (after query)
   - Graphs are query-scoped
   - No persistence needed
   - Reconstructed on next query

## Why This Matters

**Scalability through laziness.**

Corpus growth:
- Traditional KG: O(n²) edges grow exponentially
  * 1000 docs → 50,000 edges
  * 10,000 docs → 5,000,000 edges (100x)

- Runtime graphs: O(k²) constant (k always ~20-30)
  * Any corpus → ~400 edges per query
  * Scales to infinite corpus size

**Authority without precomputation:**

Multi-perspective ranking example:
- Query decisions, failures, patterns separately
- Build graph from combined results
- PageRank identifies most-referenced chunks
- Get authority-based ranking without manual scoring

## The Moat

**Graph algorithms on vectors without graph databases.**

Traditional approach:
- Vector DB (semantic) OR Graph DB (structure)
- Can't combine without dual systems

AURA approach:
- Vector DB for semantic search
- Runtime graphs for structural analysis
- Single system, dual benefits

**O(k²) vs O(n²) = scalability moat.**

At 10,000 documents:
- Precompute all edges: 50,000,000 comparisons
- Runtime graphs on results: 400 comparisons

**125,000x efficiency gain.**
