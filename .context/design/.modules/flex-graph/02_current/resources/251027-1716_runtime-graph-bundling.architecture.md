---
date: 2025-10-27
type: architecture.implementation
status: planned
keywords: "networkx graph-algorithms python implementation"
---

# Architecture: Runtime Graph Bundling Implementation

## Components

**Location:** `imem/src/imem/graph_ops.py`
**Status:** Planned (Phase 7)
**Effort:** ~200 lines

---

## Data Structures

### Graph Representation

```python
import networkx as nx

# Directed graph with node/edge metadata
G = nx.DiGraph()

# Node structure
G.add_node(
    "result_id_123",
    result=result_object,  # Full chunk data
    score=0.85,            # Original semantic score
    metadata={             # Chunk metadata
        'file_path': '...',
        'session_id': '...',
        'timestamp': '...',
        'section_type': 'Decisions'
    }
)

# Edge structure
G.add_edge(
    "result_id_123",
    "result_id_456",
    type='sibling',        # Edge type
    weight=0.9,            # Strength
    metadata={             # Edge context
        'reason': 'Same file_path'
    }
)
```

---

## Core Operations

### Primitive 1: build_graph

```python
from typing import List, Dict
import networkx as nx
from itertools import combinations

def build_graph(
    result_ids: List[str],
    collection_name: str,
    edge_types: List[str] = ['sibling', 'genealogy', 'semantic']
) -> str:
    """Build runtime graph from result IDs

    Args:
        result_ids: List of Qdrant result IDs
        collection_name: Which collection to load from
        edge_types: Which relationship types to include

    Returns:
        graph_id: Identifier for persisted graph
    """

    # 1. Load full result objects
    results = client.retrieve(
        collection_name=collection_name,
        ids=result_ids
    )

    # 2. Create directed graph
    G = nx.DiGraph()

    # 3. Add nodes
    for result in results:
        G.add_node(
            result.id,
            result=result,
            score=result.score,
            metadata=result.payload
        )

    # 4. Add edges based on metadata
    for r1, r2 in combinations(results, 2):
        # Sibling relationship (same file)
        if 'sibling' in edge_types:
            if r1.payload['file_path'] == r2.payload['file_path']:
                G.add_edge(
                    r1.id, r2.id,
                    type='sibling',
                    weight=0.9,
                    metadata={'reason': 'Same file'}
                )

        # Genealogy relationship (same session)
        if 'genealogy' in edge_types:
            if r1.payload.get('session_id') == r2.payload.get('session_id'):
                G.add_edge(
                    r1.id, r2.id,
                    type='genealogy',
                    weight=0.85,
                    metadata={'reason': 'Same session'}
                )

        # Semantic relationship (high similarity)
        if 'semantic' in edge_types:
            similarity = cosine_similarity(
                r1.vector['e5-large-v2'],
                r2.vector['e5-large-v2']
            )
            if similarity > 0.85:
                G.add_edge(
                    r1.id, r2.id,
                    type='semantic',
                    weight=similarity,
                    metadata={'reason': f'Similarity {similarity:.2f}'}
                )

    # 5. Store graph metadata
    G.graph['created'] = datetime.now().isoformat()
    G.graph['node_count'] = len(results)
    G.graph['edge_count'] = G.number_of_edges()

    # 6. Persist graph
    graph_id = _generate_graph_id(result_ids)
    _save_graph(graph_id, G)

    return graph_id
```

### Primitive 2: apply_algorithm

```python
def apply_algorithm(
    graph_id: str,
    algorithm: str,
    top: int = None
) -> List[Dict]:
    """Apply ranking algorithm to graph

    Args:
        graph_id: Identifier for persisted graph
        algorithm: 'pagerank', 'centrality', 'communities'
        top: Return top N results (None = all)

    Returns:
        Ranked results with scores
    """

    # 1. Load graph
    G = _load_graph(graph_id)

    # 2. Apply algorithm
    if algorithm == 'pagerank':
        scores = nx.pagerank(G, weight='weight')
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    elif algorithm == 'centrality':
        scores = nx.betweenness_centrality(G, weight='weight')
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    elif algorithm == 'communities':
        from networkx.algorithms import community
        communities = community.louvain_communities(G, weight='weight')
        return [
            {
                'cluster_id': i,
                'members': list(comm),
                'size': len(comm)
            }
            for i, comm in enumerate(communities)
        ]

    else:
        raise ValueError(f"Unknown algorithm: {algorithm}")

    # 3. Return results with scores
    results = []
    for node_id, score in ranked:
        node_data = G.nodes[node_id]
        results.append({
            'id': node_id,
            'content': node_data['result'].payload['content'],
            'original_score': node_data['score'],
            'graph_score': score,
            'metadata': node_data['metadata']
        })

    return results[:top] if top else results
```

---

## Graph Persistence

### Storage Strategy

```python
import pickle
from pathlib import Path

GRAPH_STORAGE = Path.home() / '.context' / 'imem_graphs'

def _generate_graph_id(result_ids: List[str]) -> str:
    """Generate deterministic graph ID"""
    import hashlib
    content = ''.join(sorted(result_ids))
    return hashlib.md5(content.encode()).hexdigest()[:8]

def _save_graph(graph_id: str, G: nx.DiGraph) -> None:
    """Persist graph to disk"""
    GRAPH_STORAGE.mkdir(parents=True, exist_ok=True)
    graph_path = GRAPH_STORAGE / f"{graph_id}.pkl"
    nx.write_gpickle(G, graph_path)

def _load_graph(graph_id: str) -> nx.DiGraph:
    """Load graph from disk"""
    graph_path = GRAPH_STORAGE / f"{graph_id}.pkl"
    if not graph_path.exists():
        raise FileNotFoundError(f"Graph {graph_id} not found")
    return nx.read_gpickle(graph_path)
```

**Storage format:**
- NetworkX pickle (preserves full graph + metadata)
- Location: `~/.context/imem_graphs/<graph-id>.pkl`
- Lifetime: Ephemeral by default (can persist for session)

---

## CLI Interface

```python
# imem/src/imem/cli.py

@click.group()
def graph():
    """Graph operations"""
    pass

@graph.command()
@click.argument('result_ids', nargs=-1)
@click.option('--edges', default='sibling,genealogy,semantic')
def build(result_ids, edges):
    """Build graph from result IDs

    Example:
        imem graph build abc123 def456 xyz789
    """
    edge_types = edges.split(',')
    graph_id = build_graph(list(result_ids), get_collection(), edge_types)
    click.echo(f"Graph created: {graph_id}")

@graph.command()
@click.argument('graph_id')
@click.argument('algorithm', type=click.Choice(['pagerank', 'centrality', 'communities']))
@click.option('--top', type=int, default=None)
def apply(graph_id, algorithm, top):
    """Apply algorithm to graph

    Example:
        imem graph apply a7f3d2c1 pagerank --top 10
    """
    results = apply_algorithm(graph_id, algorithm, top)

    for i, result in enumerate(results, 1):
        click.echo(f"{i}. {result['id']} (score: {result['graph_score']:.3f})")
        click.echo(f"   {result['content'][:100]}...")
```

---

## Integration with batch Primitive

### Batch with Graph Operations

```python
# In batch.py

async def _execute_query_sugar(config: Dict) -> Dict[str, Any]:
    """Handle queries + combine + graph sugar"""

    # 1. Execute queries in parallel
    query_specs = config['queries']
    results_list = await asyncio.gather(*[
        _async_search(q['text'], q.get('filters', {}), q.get('limit', 10))
        for q in query_specs
    ])

    # 2. Combine results
    if config.get('combine'):
        results = _combine_results(results_list)
    else:
        return {'results': results_list}

    # 3. Graph operations (if requested)
    if config.get('graph'):
        graph_config = config['graph']

        # Build graph from combined results
        result_ids = [r.id for r in results]
        graph_id = build_graph(result_ids, get_collection())

        # Apply algorithm
        ranked = apply_algorithm(
            graph_id,
            graph_config['algorithm'],
            graph_config.get('top')
        )

        return {'results': ranked}

    return {'results': results}
```

**Usage:**
```bash
imem batch '{
  "queries": [
    {"text": "auth", "filters": {"decisions": true}},
    {"text": "auth", "filters": {"failures": true}}
  ],
  "combine": true,
  "graph": {"algorithm": "pagerank", "top": 10}
}'
```

---

## Algorithm Selection Guide

### PageRank: Authority Ranking

**When to use:**
- Find "most important" chunks
- Authority = how many other chunks reference it

**Interpretation:**
- High score = highly connected (many sibling/genealogy edges)
- Indicates: Frequently referenced decisions

### Betweenness Centrality: Bridge Detection

**When to use:**
- Find concepts connecting disparate topics
- Bridge = lies on shortest paths between other nodes

**Interpretation:**
- High score = connects multiple clusters
- Indicates: Architectural patterns, cross-cutting concerns

### Community Detection: Clustering

**When to use:**
- Group related concepts
- Find natural semantic clusters

**Interpretation:**
- Chunks in same community = semantically related
- Indicates: Topic boundaries

---

## Performance Characteristics

**Graph construction:**
- 20 nodes: ~40ms (190 edge checks)
- 50 nodes: ~100ms (1,225 edge checks)
- 100 nodes: ~400ms (4,950 edge checks)

**Algorithm application:**
- PageRank: O(n × edges) ≈ 20-50ms for typical graphs
- Centrality: O(n × edges²) ≈ 50-100ms
- Communities: O(n log n) ≈ 30-60ms

**Total latency:** 80-200ms for typical query

**Bottleneck:** Edge construction (cosine similarity computations)

---

## Optimization Strategies

### Strategy 1: Edge Type Selection

```python
# Fast: Only sibling edges (metadata comparison)
build_graph(ids, edge_types=['sibling'])  # ~30ms

# Slow: Semantic edges (cosine computations)
build_graph(ids, edge_types=['semantic'])  # ~100ms

# Balanced: Sibling + genealogy (no vector ops)
build_graph(ids, edge_types=['sibling', 'genealogy'])  # ~40ms
```

### Strategy 2: Result Set Limiting

```python
# Fast: Small result set
batch({'queries': [...], 'limit': 10})  # 10 nodes → 45 edges

# Slow: Large result set
batch({'queries': [...], 'limit': 50})  # 50 nodes → 1,225 edges
```

### Strategy 3: Session Caching

```python
# Build once, apply multiple algorithms
graph_id = build_graph(result_ids)
pagerank_results = apply_algorithm(graph_id, 'pagerank')
centrality_results = apply_algorithm(graph_id, 'centrality')

# Reuse graph (no rebuild cost)
```

---

## Error Handling

```python
def build_graph(result_ids: List[str], **kwargs) -> str:
    """Build with validation"""

    # Check minimum nodes
    if len(result_ids) < 2:
        raise ValueError("Need at least 2 nodes for graph")

    # Load results (may fail if IDs invalid)
    try:
        results = client.retrieve(collection, ids=result_ids)
    except Exception as e:
        raise ValueError(f"Failed to load results: {e}")

    # Build graph
    G = nx.DiGraph()

    # ... construction logic ...

    # Validate graph
    if G.number_of_nodes() == 0:
        raise ValueError("Graph has no nodes")

    return graph_id
```

---

## Testing Strategy

```python
# test_graph_ops.py

def test_graph_build():
    """Test graph construction"""
    result_ids = ['id1', 'id2', 'id3']
    graph_id = build_graph(result_ids, 'test_collection')

    G = _load_graph(graph_id)
    assert G.number_of_nodes() == 3
    assert G.number_of_edges() > 0

def test_pagerank():
    """Test PageRank ranking"""
    graph_id = build_graph(['id1', 'id2', 'id3'], 'test_collection')
    results = apply_algorithm(graph_id, 'pagerank')

    assert len(results) == 3
    # Scores should be descending
    assert results[0]['graph_score'] >= results[1]['graph_score']
```

---

## Dependencies

```python
# requirements.txt
networkx>=3.0
numpy>=1.24  # For cosine similarity
```

---

## Summary

**Implementation:**
- ~200 lines (graph_ops.py)
- NetworkX for graph structure
- Pickle for persistence
- CLI: `imem graph build/apply`

**Primitives:**
- build_graph: Construct from results (~40-100ms)
- apply_algorithm: Rank nodes (~20-50ms)
- Total: 60-150ms per query

**Integration:**
- Works with batch primitive (queries + graph)
- Ephemeral by default (build, use, discard)
- Can persist for session reuse

**Next:** See `.pattern.md` for language-agnostic principle.
