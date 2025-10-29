---
session_id: e025fbb0-1abb-46e8-82a1-79c49afcc32d
date: 2025-10-27
type: pattern.innovation
resolution: architectural
keywords: "networkx-construction pagerank-reranking ephemeral-storage"
---

# Runtime Query Graphs Pattern

## Pattern Structure

**Ephemeral graphs from query results.**

### Component Relationship

```
Query phase:
├─ Execute multiple searches
├─ Collect result IDs
└─ Pass to graph builder

Graph construction:
├─ Retrieve chunks
├─ Build NetworkX graph
│   ├─ Nodes: Chunks
│   └─ Edges: Metadata relationships
└─ Save temporarily (optional)

Algorithm application:
├─ Load graph
├─ Apply algorithm (PageRank, centrality)
└─ Return ranked chunk IDs

Cleanup:
└─ Discard graph (ephemeral)
```

## Invariants

1. **Graphs from results only**
   - Build from k query results (k=20-30)
   - Never from entire corpus (n=1000+)
   - O(k²) complexity maintained

2. **Ephemeral by default**
   - Query-scoped lifetime
   - Optional persistence for debugging
   - No long-term storage overhead

3. **Metadata-based edges**
   - Relationships from chunk metadata
   - No edge precomputation
   - Discovered at graph-build time

## Graph Construction Algorithm

```
def build_graph(result_ids):
    """Build NetworkX graph from query results"""
    import networkx as nx

    # Retrieve chunks
    chunks = [retrieve(rid) for rid in result_ids]

    # Initialize graph
    G = nx.DiGraph()

    # Add nodes
    for i, chunk in enumerate(chunks):
        G.add_node(i,
            chunk_id=chunk.id,
            score=chunk.score,
            file_path=chunk.payload['file_path'],
            session_id=chunk.payload.get('session_id')
        )

    # Add edges based on metadata
    for i, c1 in enumerate(chunks):
        for j, c2 in enumerate(chunks):
            if i == j:
                continue

            # Same file edge
            if c1.payload['file_path'] == c2.payload['file_path']:
                G.add_edge(i, j, type='file', weight=0.8)

            # Same session edge
            if c1.payload.get('session_id') == c2.payload.get('session_id'):
                G.add_edge(i, j, type='session', weight=0.9)

            # Semantic similarity edge
            similarity = cosine_similarity(c1.vector, c2.vector)
            if similarity > 0.85:
                G.add_edge(i, j, type='semantic', weight=similarity)

    return G
```

## Algorithm Application

```
def apply_algorithm(graph, algorithm):
    """Apply NetworkX algorithm to graph"""
    import networkx as nx

    if algorithm == 'pagerank':
        # Authority: Most-referenced chunks
        scores = nx.pagerank(graph, weight='weight')

    elif algorithm == 'centrality':
        # Bridge concepts: Connect different topics
        scores = nx.betweenness_centrality(graph, weight='weight')

    elif algorithm == 'clustering':
        # Communities: Related chunk clusters
        communities = nx.community.greedy_modularity_communities(graph)
        return communities

    else:
        raise ValueError(f"Unknown algorithm: {algorithm}")

    # Sort by score
    ranked_nodes = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    # Return chunk IDs
    return [graph.nodes[node_id]['chunk_id'] for node_id, _ in ranked_nodes]
```

## Storage Strategy

```
Optional ephemeral storage:

~/.context/imem_graphs/
├─ <graph_id>.pkl  # NetworkX pickle
└─ <graph_id>.meta.json  # Metadata

Graph metadata:
{
  "created": "2025-10-27T12:00:00",
  "query": "provider agnostic design",
  "node_count": 30,
  "edge_count": 67,
  "algorithms_applied": ["pagerank"],
  "ttl": 3600  # 1 hour
}

Cleanup policy:
- Delete graphs older than TTL
- Or: Keep only last 10 graphs
- Or: Fully ephemeral (no storage)
```

## Edge Type Weights

```
Edge weight strategy:

file_path match (siblings):
  weight = 0.8
  reason = Strong structural relationship

session_id match (genealogy):
  weight = 0.9
  reason = Strongest causal relationship

semantic similarity > 0.85:
  weight = similarity score
  reason = Variable strength by topic overlap

temporal (same session, timestamp ordered):
  weight = 0.7
  reason = Temporal causality, moderate strength
```

## Benefits

- **Scalable**: O(k²) not O(n²)
- **Flexible**: Any NetworkX algorithm
- **Authority**: PageRank without manual scoring
- **Zero maintenance**: No graph to update

## Trade-offs

- **Construction cost**: 40-100ms per query
- **Acceptable for**: Human-in-loop queries
- **Not acceptable for**: Real-time, high-frequency
- **Good enough**: AI agent workflows

## When to Use

Use when:
- Multi-query composition (combine results)
- Authority ranking needed (PageRank)
- Bridge concepts (centrality analysis)
- Cluster detection (communities)

Avoid when:
- Single query sufficient
- Semantic ranking adequate
- Real-time performance critical
- Query frequency very high
