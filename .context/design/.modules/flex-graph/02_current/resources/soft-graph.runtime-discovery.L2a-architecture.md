# Soft-Graph: Architecture Pattern

**Session:** a86bc733-c4e3-4d88-b17f-2f9e330ca11a
**Level:** Architecture Pattern (L2a)
**Date:** 2025-10-27

## System Topology

```
Query Results (top-k chunks with metadata)
    ↓
Temporary Graph Construction (O(k²) edges)
    ↓
Algorithm Application (PageRank, centrality)
    ↓
Ranked Results
    ↓
Graph Discarded
```

## Edge Discovery Mechanism

Edges = metadata predicates (materialized at query time):

| Edge Type | Discovery Predicate | Weight | Use Case |
|-----------|---------------------|--------|----------|
| FILE | file_path == X | 0.8 | Same document context |
| SESSION | session_id == Y | 0.9 | Conversation genealogy |
| TEMPORAL | timestamp > Z ∧ semantic > 0.7 | 0.7 | Evolution tracking |
| SEMANTIC | cosine_similarity > 0.8 | variable | Topical relatedness |

No edge storage. Relationships computed on-demand via filtered queries.

## Graph Construction Algorithm

**Input:** Query results (k chunks with metadata)
**Output:** NetworkX DiGraph with k nodes, ~k² edges

```
1. Create empty directed graph G
2. For each result r in results:
   - Add node(r.id, metadata=r.payload, score=r.score)
3. For each pair (r1, r2) in results × results:
   - If r1.file_path == r2.file_path:
       Add edge(r1, r2, type='file', weight=0.8)
   - If r1.session_id == r2.session_id:
       Add edge(r1, r2, type='session', weight=0.9)
   - If r2.timestamp > r1.timestamp AND similarity(r1, r2) > 0.7:
       Add edge(r1, r2, type='temporal', weight=0.7)
4. Return graph_id (persist temporarily or return in-memory)
```

## Algorithm Application

**PageRank:** Find authoritative nodes (most-referenced)
**Betweenness Centrality:** Find bridge nodes (connecting concepts)
**Community Detection:** Find clusters (related work)
**Shortest Path:** Navigate to target concept

Same graph, different algorithms → different insights.

## Complexity Analysis

| Operation | Precomputed KG | Soft-Graph |
|-----------|----------------|------------|
| Index time | O(n²) edges | O(0) |
| Storage | O(n²) | O(0) |
| Query time | O(1) traversal | O(k²) construction |
| Maintenance | O(n) rebuild on change | O(0) |

Where:
- n = total documents (thousands)
- k = query results (typically 20-50)

**Key insight:** k << n, so O(k²) << O(n²)

## Lifecycle

1. **Construction:** On-demand from query results
2. **Usage:** Apply algorithms for ranking
3. **Persistence:** Optional (session-scoped)
4. **Cleanup:** Automatic or explicit

Graphs are ephemeral by default. Persist only if reuse validated.

## Interface Contracts

```
IRelationshipDiscovery:
  get_siblings(result_id) → ResultSet      # FILE edges
  get_temporal(result_id, direction) → ResultSet  # TEMPORAL edges
  get_session(result_id) → ResultSet       # SESSION edges

IGraphOperations:
  build(result_ids) → graph_id
  apply(graph_id, algorithm) → Rankings
  export(graph_id) → JSON

IPersistence:
  save(graph, metadata) → graph_id
  load(graph_id) → Graph
  cleanup(older_than) → void
```

## Architectural Properties

**Composability:** Graph operations combine with search primitives
**Evolvability:** New edge types = new metadata predicates
**Observability:** Graph construction logged for pattern mining
**Zero Maintenance:** No rebuild on document change
**Query-Adaptive:** Different graph per query intent

## The Innovation

Not precomputed knowledge graphs, but **query-time graph views over metadata-enriched vector results**.

Relationships as a service, not a storage layer.
