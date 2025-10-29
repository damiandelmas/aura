---
session_id: ca22384b-3a6d-4821-8b70-2aa1a89ea4ba
date: 2025-10-27
level: architecture-implementation
innovation: runtime-query-graphs
---

# Runtime Query Graphs: Implementation Specification

## Graph Construction

```python
import networkx as nx
from itertools import combinations

def build_graph(result_ids: List[str], graph_id: str = None) -> str:
    """Build NetworkX graph from search results"""

    # 1. Load results
    results = [qdrant.retrieve(ids=[rid])[0] for rid in result_ids]

    # 2. Create directed graph
    G = nx.DiGraph()

    # 3. Add nodes
    for r in results:
        G.add_node(r.id, result=r, score=r.score)

    # 4. Add edges (O(k²) combinations)
    for r1, r2 in combinations(results, 2):
        # Sibling edge
        if r1.payload['file_path'] == r2.payload['file_path']:
            G.add_edge(r1.id, r2.id, type='sibling', weight=0.9)

        # Genealogy edge
        if r1.payload.get('session_id') == r2.payload.get('session_id'):
            G.add_edge(r1.id, r2.id, type='genealogy', weight=0.8)

        # Semantic edge
        similarity = cosine_similarity(r1.vector, r2.vector)
        if similarity > 0.85:
            G.add_edge(r1.id, r2.id, type='semantic', weight=similarity)

    # 5. Save (optional)
    if graph_id:
        save_graph(graph_id, G)
    else:
        graph_id = generate_id()
        save_ephemeral_graph(graph_id, G)

    return graph_id
```

## Algorithm Application

```python
def apply_algorithm(graph_id: str, algorithm: str, top: int = 10) -> List[Chunk]:
    """Apply NetworkX algorithm, return ranked results"""

    G = load_graph(graph_id)

    # Apply algorithm
    if algorithm == 'pagerank':
        scores = nx.pagerank(G, weight='weight')
    elif algorithm == 'centrality':
        scores = nx.betweenness_centrality(G, weight='weight')
    elif algorithm == 'communities':
        communities = nx.community.louvain_communities(G, weight='weight')
        return communities

    # Rank by score
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    # Return top N results
    return [G.nodes[node_id]['result'] for node_id, _ in ranked[:top]]
```

## CLI Integration

```bash
# Build graph from search results
results=$(imem search "authentication" --decisions --format id)
graph_id=$(imem graph build $results)

# Apply PageRank
imem graph apply $graph_id pagerank --top 10

# Or in one command via batch
imem batch '{
  "queries": [{"text": "auth", "filters": {"decisions": true}}],
  "graph": {"algorithm": "pagerank", "top": 10}
}'
```

## Performance Metrics

**Graph construction (k=20):**
```
Load results: ~5ms (20 Qdrant retrievals)
Add nodes: ~1ms
Compute edges: ~20ms (O(k²) = 400 combinations)
Save graph: ~10ms

Total: ~40ms
```

**Algorithm application:**
```
PageRank: ~30ms (NetworkX)
Centrality: ~50ms (NetworkX)
Communities: ~40ms (NetworkX)

Total: 40ms (build) + 30-50ms (algorithm) = 70-90ms
```

**Break-even analysis:**
```
Precomputed: n=500 docs → 125k edges → 2-5s build time
Runtime: k=20 → 400 edges → 40ms build time

Runtime wins when: k << n (typical case)
```

## Storage

```python
# Ephemeral (default)
ephemeral_graphs = {}  # In-memory only

# Persistent (optional)
def save_graph(graph_id: str, G: nx.DiGraph):
    graph_dir = Path.home() / '.context' / 'imem_graphs'
    graph_dir.mkdir(exist_ok=True)

    import pickle
    with open(graph_dir / f"{graph_id}.pkl", 'wb') as f:
        pickle.dump(G, f)

# Cleanup
def prune_graphs(older_than_days: int = 7):
    """Delete old persistent graphs"""
    ...
```

## Validation

```python
def test_runtime_graph():
    # Search
    results = search("authentication", limit=20)

    # Build graph
    graph_id = build_graph([r.id for r in results])

    # Verify construction
    G = load_graph(graph_id)
    assert len(G.nodes) == 20
    assert len(G.edges) > 0  # Should have some relationships

    # Apply algorithm
    ranked = apply_algorithm(graph_id, 'pagerank', top=5)
    assert len(ranked) == 5
    assert ranked[0].score >= ranked[1].score  # Descending order
```
