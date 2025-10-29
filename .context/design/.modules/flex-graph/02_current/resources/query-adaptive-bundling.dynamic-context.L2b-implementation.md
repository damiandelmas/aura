# Query-Adaptive Bundling: Implementation Specification

**Session:** a86bc733-c4e3-4d88-b17f-2f9e330ca11a
**Level:** Implementation (L2b)
**Date:** 2025-10-27

## Bundling Strategy Implementations

### Strategy 1: Authority Bundling (PageRank)

```python
def bundle_authority(query: str, top_n: int = 5) -> dict:
    """
    Find most authoritative knowledge via PageRank.

    Use case: "Show me the most authoritative pattern for X"
    """
    # 1. Multi-query search
    results = []
    for query_variant in generate_variants(query):
        results.extend(search(query_variant, limit=10))

    # 2. Build graph
    graph_id = build_graph([r.id for r in results])

    # 3. Apply PageRank
    ranked_ids = apply_algorithm(graph_id, 'pagerank')

    # 4. Get top N with full context
    bundled = []
    for result_id in ranked_ids[:top_n]:
        primary = load_result(result_id)
        siblings = get_siblings(result_id)

        bundled.append({
            'primary': primary,
            'context': siblings,
            'rank': ranked_ids.index(result_id) + 1,
            'authority_score': compute_pagerank_score(graph_id, result_id)
        })

    return {
        'results': bundled,
        'strategy': 'authority',
        'rationale': 'Most-referenced decisions with full file context'
    }


# Slash command wrapper
# .claude/commands/explore-authority.md
"""
Find most authoritative knowledge via PageRank.

Usage: /explore-authority <topic>

Executes:
  results = search multiple variants of topic
  graph = build from all results
  ranked = apply PageRank
  return top 5 with siblings
"""
```

### Strategy 2: Context Bundling (Complete Genealogy)

```python
def bundle_context(query: str) -> dict:
    """
    Get complete context: decision + implementation + constraints + origin.

    Use case: "Explain this decision completely"
    """
    # 1. Find primary decision
    results = search(query, filters={'section_type': 'Decisions'}, limit=1)
    if not results:
        return {'error': 'No decision found'}

    primary = results[0]

    # 2. Get siblings (same file context)
    siblings = get_siblings(primary.id)

    # 3. Get origin conversation
    conversation = get_session_chain(primary.id)

    # 4. Assemble by section type
    return {
        'decision': primary,
        'implementation': [s for s in siblings if s.payload.get('section_type') == 'Implementation'],
        'constraints': [s for s in siblings if s.payload.get('section_type') == 'Constraints'],
        'patterns': [s for s in siblings if s.payload.get('section_type') == 'Patterns'],
        'origin_conversation': conversation,
        'strategy': 'context',
        'rationale': 'Complete genealogy from decision to implementation'
    }


# Slash command wrapper
# .claude/commands/explain-decision.md
"""
Get complete context for a decision.

Usage: /explain-decision <query>

Executes:
  decision = search for decision
  siblings = get same-file context
  conversation = get origin discussion
  return bundled context
"""
```

### Strategy 3: Bridge Bundling (Centrality)

```python
def bundle_bridges(topic1: str, topic2: str, top_n: int = 5) -> dict:
    """
    Find concepts connecting two topics via betweenness centrality.

    Use case: "How does chunking relate to indexing?"
    """
    # 1. Search both topics
    results1 = search(topic1, limit=15)
    results2 = search(topic2, limit=15)
    all_results = results1 + results2

    # 2. Build graph with all edge types
    graph_id = build_graph([r.id for r in all_results])

    # 3. Compute centrality
    ranked_ids = apply_algorithm(graph_id, 'centrality')

    # 4. Get top bridges with context
    bridges = []
    for result_id in ranked_ids[:top_n]:
        result = load_result(result_id)

        # Find what this bridges between
        connections = analyze_connections(graph_id, result_id, topic1, topic2)

        bridges.append({
            'content': result,
            'connects': [topic1, topic2],
            'centrality_score': compute_centrality_score(graph_id, result_id),
            'connection_paths': connections
        })

    return {
        'bridges': bridges,
        'topics': [topic1, topic2],
        'strategy': 'bridge',
        'rationale': 'Concepts with high betweenness centrality connecting topics'
    }


def analyze_connections(graph_id: str, node_id: str, topic1: str, topic2: str) -> list:
    """Analyze how a node bridges two topics"""
    G = load_graph(graph_id)

    # Find nodes related to each topic
    topic1_nodes = [n for n in G.nodes if topic1.lower() in G.nodes[n].get('content', '').lower()]
    topic2_nodes = [n for n in G.nodes if topic2.lower() in G.nodes[n].get('content', '').lower()]

    # Find shortest paths through this node
    paths = []
    for t1_node in topic1_nodes:
        for t2_node in topic2_nodes:
            try:
                path = nx.shortest_path(G, t1_node, t2_node)
                if node_id in path:
                    paths.append(path)
            except nx.NetworkXNoPath:
                continue

    return paths


# Slash command wrapper
# .claude/commands/find-bridges.md
"""
Find concepts connecting two topics.

Usage: /find-bridges <topic1> <topic2>

Executes:
  results = search both topics
  graph = build from combined results
  bridges = apply centrality
  return top connecting concepts
"""
```

### Strategy 4: Timeline Bundling (Temporal Evolution)

```python
def bundle_timeline(query: str) -> dict:
    """
    Track decision evolution over time.

    Use case: "Show me how this decision evolved"
    """
    # 1. Find original decision
    results = search(query, filters={'section_type': 'Decisions'}, limit=1)
    if not results:
        return {'error': 'No decision found'}

    original = results[0]

    # 2. Get temporal descendants (forward)
    descendants = get_temporal_chain(original.id, direction='forward')

    # 3. Get same-session refinements
    session_chain = get_session_chain(original.id)
    later_in_session = [
        s for s in session_chain
        if s.payload.get('timestamp', '') > original.payload.get('timestamp', '')
    ]

    # 4. Assemble chronologically
    timeline = [original] + descendants + later_in_session
    timeline.sort(key=lambda x: x.payload.get('timestamp', ''))

    return {
        'original': original,
        'evolution': [
            {
                'content': item,
                'timestamp': item.payload.get('timestamp'),
                'relation': classify_relation(original, item)
            }
            for item in timeline[1:]
        ],
        'strategy': 'timeline',
        'rationale': 'Decision evolution over time'
    }


def classify_relation(original, descendant) -> str:
    """Classify relationship between original and descendant"""
    if descendant.payload.get('session_id') == original.payload.get('session_id'):
        return 'same_session_refinement'
    elif descendant.payload.get('file_path') == original.payload.get('file_path'):
        return 'same_file_update'
    else:
        return 'semantic_descendant'


# Slash command wrapper
# .claude/commands/trace-evolution.md
"""
Track how a decision evolved over time.

Usage: /trace-evolution <query>

Executes:
  original = find decision
  descendants = get temporal chain (forward)
  session_updates = get same-session refinements
  return chronological timeline
"""
```

---

## Unified Batch Interface

```python
def batch_bundle(config: dict) -> dict:
    """
    Unified interface for all bundling strategies.
    Strategy determined by config.
    """
    strategy = config.get('strategy', 'detect')

    if strategy == 'detect':
        # Intent detection from query
        query = config['query']
        if 'most authoritative' in query.lower() or 'best' in query.lower():
            strategy = 'authority'
        elif 'explain' in query.lower() or 'understand' in query.lower():
            strategy = 'context'
        elif 'connect' in query.lower() or 'relate' in query.lower():
            strategy = 'bridge'
        elif 'evolve' in query.lower() or 'history' in query.lower():
            strategy = 'timeline'
        else:
            strategy = 'context'  # Default

    # Execute strategy
    if strategy == 'authority':
        return bundle_authority(config['query'], top_n=config.get('top_n', 5))
    elif strategy == 'context':
        return bundle_context(config['query'])
    elif strategy == 'bridge':
        return bundle_bridges(config['topic1'], config['topic2'], top_n=config.get('top_n', 5))
    elif strategy == 'timeline':
        return bundle_timeline(config['query'])
    else:
        raise ValueError(f"Unknown strategy: {strategy}")
```

---

## CLI Interface

```bash
# Authority bundling
imem bundle --strategy authority "authentication patterns"

# Context bundling (default)
imem bundle "LlamaIndex chunking decision"

# Bridge bundling
imem bundle --strategy bridge --topic1 "chunking" --topic2 "indexing"

# Timeline bundling
imem bundle --strategy timeline "JWT authentication"

# Auto-detect strategy from query
imem bundle "Show me the most authoritative refactor pattern"  # → authority
imem bundle "Explain the database schema decision completely"  # → context
```

---

## Usage in Slash Commands

```markdown
# .claude/commands/adaptive-explore.md

Explore knowledge with intent-adaptive bundling.

Usage: /adaptive-explore <query>

The system will detect your intent and choose the best bundling strategy:
- "most authoritative" → PageRank ranking
- "explain completely" → Full context assembly
- "connect X and Y" → Bridge concept discovery
- "evolution of X" → Timeline tracking

Executes:
  strategy = detect_intent(query)
  result = batch_bundle({
    "query": query,
    "strategy": strategy
  })

Returns context bundled according to your intent.
```

---

## Comparison: Same Query, Different Bundling

Query: "LlamaIndex section chunking"

```bash
# Authority bundling
imem bundle --strategy authority "LlamaIndex section chunking"
# → Most-referenced chunking decision + siblings

# Context bundling
imem bundle --strategy context "LlamaIndex section chunking"
# → Decision + implementation + constraints + origin conversation

# Bridge bundling (if also searching "batch processing")
imem bundle --strategy bridge --topic1 "section chunking" --topic2 "batch processing"
# → Concepts linking chunking to batch upsert

# Timeline bundling
imem bundle --strategy timeline "LlamaIndex section chunking"
# → Original decision + later refinements chronologically
```

Four different responses from same knowledge base.

---

## File Structure

```
imem/
├── src/imem/
│   ├── bundling/
│   │   ├── __init__.py
│   │   ├── authority.py    (~100 lines)
│   │   ├── context.py      (~80 lines)
│   │   ├── bridges.py      (~120 lines)
│   │   └── timeline.py     (~90 lines)
│   ├── batch.py            (unified interface)
│   └── cli.py              (bundle command)
```

---

## Testing

```python
def test_authority_bundling():
    """Test PageRank-based bundling"""
    result = bundle_authority("authentication patterns", top_n=3)
    assert len(result['results']) == 3
    assert result['strategy'] == 'authority'
    assert all('authority_score' in r for r in result['results'])


def test_context_bundling():
    """Test complete context assembly"""
    result = bundle_context("LlamaIndex chunking")
    assert 'decision' in result
    assert 'implementation' in result
    assert 'origin_conversation' in result


def test_strategy_detection():
    """Test intent detection"""
    config1 = {"query": "most authoritative pattern"}
    assert batch_bundle(config1)['strategy'] == 'authority'

    config2 = {"query": "explain this decision"}
    assert batch_bundle(config2)['strategy'] == 'context'
```

---

## Performance

- Authority bundling: ~200ms (multi-query + graph + PageRank)
- Context bundling: ~50ms (single query + siblings + session)
- Bridge bundling: ~250ms (two queries + graph + centrality)
- Timeline bundling: ~80ms (single query + temporal chain)

## The Key Insight

Same chunks, same metadata, different bundling strategies.

Knowledge Graphs can't do this—their edge schema is fixed.
AURA can—edges discovered and bundled at runtime based on query intent.
