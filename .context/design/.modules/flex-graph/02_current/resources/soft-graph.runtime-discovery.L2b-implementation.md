# Soft-Graph: Implementation Specification

**Session:** a86bc733-c4e3-4d88-b17f-2f9e330ca11a
**Level:** Implementation (L2b)
**Date:** 2025-10-27

## Component: `imem/src/imem/relationships.py`

### Relationship Discovery Primitives

```python
def get_siblings(result_id: str, collection_name: str) -> List[ScoredPoint]:
    """
    Discover FILE edges via metadata query.
    Returns all chunks from same file_path.
    """
    result = client.retrieve(collection_name, ids=[result_id])[0]
    file_path = result.payload['file_path']

    return client.scroll(
        collection_name=collection_name,
        scroll_filter=Filter(must=[
            FieldCondition(key='file_path', match=MatchValue(value=file_path))
        ])
    )[0]  # Returns (points, next_offset)


def get_temporal_chain(result_id: str, direction: str = 'forward',
                       threshold: float = 0.7) -> List[ScoredPoint]:
    """
    Discover TEMPORAL edges via timestamp + semantic similarity.
    Returns earlier/later chunks semantically related.
    """
    result = client.retrieve(collection_name, ids=[result_id])[0]
    timestamp = result.payload['timestamp']

    # Query by timestamp direction
    timestamp_filter = f">{timestamp}" if direction == 'forward' else f"<{timestamp}"
    candidates = client.scroll(
        collection_name=collection_name,
        scroll_filter=Filter(must=[
            FieldCondition(key='timestamp', range={'gt' if direction == 'forward' else 'lt': timestamp})
        ])
    )[0]

    # Filter by semantic similarity
    from qdrant_client.models import SearchParams
    semantic_results = client.search(
        collection_name=collection_name,
        query_vector=result.vector,
        limit=100,
        score_threshold=threshold
    )

    # Intersect: timestamp-filtered AND semantically similar
    candidate_ids = {p.id for p in candidates}
    return [r for r in semantic_results if r.id in candidate_ids]


def get_session_chain(result_id: str) -> List[ScoredPoint]:
    """
    Discover SESSION edges via session_id metadata.
    Returns all chunks from same conversation.
    """
    result = client.retrieve(collection_name, ids=[result_id])[0]
    session_id = result.payload.get('session_id')

    if not session_id:
        return []

    return client.scroll(
        collection_name=collection_name,
        scroll_filter=Filter(must=[
            FieldCondition(key='session_id', match=MatchValue(value=session_id))
        ])
    )[0]
```

### CLI Exposure

```python
# imem/src/imem/cli.py

@imem.command()
@click.argument('result_id')
def siblings(result_id):
    """Get all chunks from same file (FILE edges)"""
    from imem.relationships import get_siblings
    results = get_siblings(result_id, collection_name)
    display_results(results)


@imem.command()
@click.argument('result_id')
@click.option('--direction', type=click.Choice(['forward', 'backward']), default='forward')
def temporal(result_id, direction):
    """Get temporally related chunks (TEMPORAL edges)"""
    from imem.relationships import get_temporal_chain
    results = get_temporal_chain(result_id, direction)
    display_results(results)


@imem.command()
@click.argument('result_id')
def session(result_id):
    """Get all chunks from same conversation (SESSION edges)"""
    from imem.relationships import get_session_chain
    results = get_session_chain(result_id)
    display_results(results)
```

---

## Component: `imem/src/imem/graph_ops.py`

### Graph Construction

```python
import networkx as nx
import hashlib
import pickle
from pathlib import Path
from datetime import datetime

GRAPH_DIR = Path.home() / '.context' / 'imem_graphs'
GRAPH_DIR.mkdir(parents=True, exist_ok=True)


def build_graph(result_ids: List[str], collection_name: str) -> str:
    """
    Construct NetworkX graph from query results.
    Returns graph_id for later operations.
    """
    # Retrieve all results
    results = []
    for rid in result_ids:
        point = client.retrieve(collection_name, ids=[rid])[0]
        results.append(point)

    # Create directed graph
    G = nx.DiGraph()

    # Add nodes with metadata
    for i, result in enumerate(results):
        G.add_node(i,
                   result_id=result.id,
                   score=result.score,
                   file_path=result.payload.get('file_path'),
                   session_id=result.payload.get('session_id'),
                   timestamp=result.payload.get('timestamp'),
                   section_type=result.payload.get('section_type'))

    # Add edges based on metadata relationships
    for i, r1 in enumerate(results):
        for j, r2 in enumerate(results):
            if i == j:
                continue

            # FILE edge (same document)
            if r1.payload.get('file_path') == r2.payload.get('file_path'):
                G.add_edge(i, j, type='file', weight=0.8)

            # SESSION edge (same conversation)
            if r1.payload.get('session_id') == r2.payload.get('session_id'):
                G.add_edge(i, j, type='session', weight=0.9)

            # TEMPORAL edge (later + semantically similar)
            ts1 = r1.payload.get('timestamp')
            ts2 = r2.payload.get('timestamp')
            if ts1 and ts2 and ts2 > ts1:
                # Could add semantic similarity check here
                # For now, just temporal
                G.add_edge(i, j, type='temporal', weight=0.7)

    # Embed metadata in graph object
    G.graph['created'] = datetime.now().isoformat()
    G.graph['node_count'] = len(results)
    G.graph['result_ids'] = result_ids

    # Generate graph ID
    graph_id = hashlib.md5(str(sorted(result_ids)).encode()).hexdigest()[:8]

    # Persist graph
    graph_path = GRAPH_DIR / f"{graph_id}.pkl"
    nx.write_gpickle(G, graph_path)

    return graph_id


def apply_algorithm(graph_id: str, algorithm: str) -> List[str]:
    """
    Apply ranking algorithm to constructed graph.
    Returns ranked list of result IDs.
    """
    # Load graph
    graph_path = GRAPH_DIR / f"{graph_id}.pkl"
    G = nx.read_gpickle(graph_path)

    # Apply algorithm
    if algorithm == 'pagerank':
        scores = nx.pagerank(G, weight='weight')
    elif algorithm == 'centrality':
        scores = nx.betweenness_centrality(G, weight='weight')
    elif algorithm == 'closeness':
        scores = nx.closeness_centrality(G, distance='weight')
    else:
        raise ValueError(f"Unknown algorithm: {algorithm}")

    # Sort nodes by score
    ranked_nodes = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    # Return result IDs in ranked order
    result_ids = [G.nodes[node_id]['result_id'] for node_id, score in ranked_nodes]

    return result_ids


def export_graph(graph_id: str) -> dict:
    """Export graph as JSON for external processing"""
    graph_path = GRAPH_DIR / f"{graph_id}.pkl"
    G = nx.read_gpickle(graph_path)
    return nx.node_link_data(G)
```

### CLI Exposure

```python
# imem/src/imem/cli.py

@imem.group()
def graph():
    """Graph operations"""
    pass


@graph.command()
@click.argument('result_ids', nargs=-1, required=True)
def build(result_ids):
    """Build graph from result IDs"""
    from imem.graph_ops import build_graph
    graph_id = build_graph(list(result_ids), collection_name)
    click.echo(f"Graph built: {graph_id}")


@graph.command()
@click.argument('graph_id')
@click.argument('algorithm', type=click.Choice(['pagerank', 'centrality', 'closeness']))
def apply(graph_id, algorithm):
    """Apply algorithm to graph, return ranked result IDs"""
    from imem.graph_ops import apply_algorithm
    ranked_ids = apply_algorithm(graph_id, algorithm)

    # Display ranked results
    for i, result_id in enumerate(ranked_ids, 1):
        point = client.retrieve(collection_name, ids=[result_id])[0]
        section_name = point.payload.get('section_name', 'Unknown')
        click.echo(f"{i}. [{result_id}] {section_name}")


@graph.command()
@click.argument('graph_id')
def export(graph_id):
    """Export graph as JSON"""
    from imem.graph_ops import export_graph
    import json
    data = export_graph(graph_id)
    click.echo(json.dumps(data, indent=2))
```

---

## Usage Example

```bash
# 1. Search for related topics
r1=$(imem develop search "authentication" --decisions --limit 10 | jq -r '.results[].id')
r2=$(imem develop search "security patterns" --patterns --limit 10 | jq -r '.results[].id')

# 2. Build graph from combined results
graph_id=$(imem graph build $r1 $r2)

# 3. Apply PageRank to find most authoritative
imem graph apply $graph_id pagerank

# 4. Get full context for top result
top_result=$(imem graph apply $graph_id pagerank | head -1 | cut -d' ' -f1)
imem siblings $top_result
```

---

## File Structure

```
imem/
├── src/imem/
│   ├── relationships.py  (NEW - ~100 lines)
│   ├── graph_ops.py      (NEW - ~150 lines)
│   └── cli.py            (UPDATE - add graph commands)
└── ...

~/.context/
└── imem_graphs/
    └── <graph-id>.pkl
```

## Dependencies

```python
# requirements.txt additions
networkx>=3.0
```

## Testing

```python
# tests/test_soft_graph.py

def test_siblings_discovery():
    """Test FILE edge discovery"""
    result = search("test query", limit=1)[0]
    siblings = get_siblings(result.id)
    assert all(s.payload['file_path'] == result.payload['file_path'] for s in siblings)


def test_graph_construction():
    """Test graph building from results"""
    results = search("test", limit=5)
    graph_id = build_graph([r.id for r in results])
    assert (GRAPH_DIR / f"{graph_id}.pkl").exists()


def test_pagerank_ranking():
    """Test PageRank application"""
    results = search("test", limit=10)
    graph_id = build_graph([r.id for r in results])
    ranked = apply_algorithm(graph_id, 'pagerank')
    assert len(ranked) == 10
    assert isinstance(ranked[0], str)  # Result ID
```

---

## Performance Characteristics

- Graph construction: O(k²) where k = result count
- Typical k: 20-50 results
- Construction time: <100ms for 50 nodes
- PageRank computation: <50ms for 50 nodes
- Total overhead: ~150ms per query

## Storage

- Graph size: ~10KB per 50 nodes
- Ephemeral by default (can be persisted)
- Cleanup: Manual or automatic (gc old graphs)
