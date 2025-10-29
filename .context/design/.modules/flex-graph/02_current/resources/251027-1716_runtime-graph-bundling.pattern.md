---
date: 2025-10-27
type: pattern.reusable
status: current
keywords: "query-time-graph ephemeral-structure lazy-evaluation adaptive-ranking"
---

# Pattern: Query-Time Graph Construction

## Problem

Need to discover relationships between results and rank by connectivity.

**Typical scenario:**
- Search returns 30 relevant results
- Want to find "most important" (most-connected) results
- Relationships not precomputed

**Requirements:**
- Flexible ranking (authority vs bridges vs clusters)
- Relationships emerge from metadata
- Adapt strategy per query intent

---

## Anti-Pattern: Precomputed Graph Index

```
# Anti-pattern: Build complete graph at write time

function index_document(doc):
    # Compute all relationships to existing documents
    for existing_doc in database:
        if related(doc, existing_doc):
            create_edge(doc, existing_doc)

# Problems:
# - O(n²) edge precomputation (n = all documents)
# - Fixed relationship types at write time
# - Cannot adapt ranking strategy per query
# - Reindex when relationship logic changes
```

**Cost:** n² edges to precompute (millions for large corpus)

---

## Pattern: Query-Time Construction

### Core Flow

```
1. Semantic Search → Candidate Set (k results)
2. Build Graph on Candidates → k² edges to compute
3. Apply Algorithm → Rank by connectivity
4. Return Reranked Results
5. Discard Graph (ephemeral)
```

### Complexity Comparison

```
Precomputed approach:
- Write time: O(n²) where n = corpus size (10,000 docs)
- Edge count: 10,000² = 100,000,000 edges
- Read time: O(1) graph lookup

Query-time approach:
- Write time: O(1) no precomputation
- Edge count: k² where k = result set (50 results)
- Edge count: 50² = 2,500 edges
- Read time: O(k²) construction + O(algorithm)
```

**40,000× fewer edges to compute.**

---

## Implementation Pattern

### Step 1: Retrieve Candidates

```
function search_candidates(query, filters, limit):
    # Standard semantic search
    results = vector_db.search(
        query=query,
        filters=filters,
        limit=limit  # Typical: 20-50
    )
    return results
```

### Step 2: Build Graph from Results

```
function build_result_graph(results):
    graph = DirectedGraph()

    # Add nodes
    for result in results:
        graph.add_node(result.id, data=result)

    # Add edges (relationship discovery)
    for r1 in results:
        for r2 in results:
            if r1 == r2:
                continue

            # Edge type 1: Metadata match
            if r1.metadata.file_path == r2.metadata.file_path:
                graph.add_edge(r1.id, r2.id,
                    type='sibling',
                    weight=0.9
                )

            # Edge type 2: Temporal + semantic
            if r1.timestamp < r2.timestamp:
                similarity = cosine(r1.vector, r2.vector)
                if similarity > 0.85:
                    graph.add_edge(r1.id, r2.id,
                        type='evolution',
                        weight=similarity
                    )

    return graph
```

### Step 3: Apply Ranking Algorithm

```
function rank_by_connectivity(graph, algorithm):
    if algorithm == 'authority':
        # PageRank: Find most-referenced
        scores = pagerank(graph, weight='weight')

    elif algorithm == 'bridges':
        # Betweenness: Find connectors
        scores = betweenness_centrality(graph, weight='weight')

    elif algorithm == 'clusters':
        # Community detection
        return community_detection(graph)

    # Sort by score
    ranked = sort_by(scores, descending=True)
    return ranked
```

### Step 4: Return Reranked

```
function query_with_graph_ranking(query, algorithm):
    # 1. Get candidates
    results = search_candidates(query, limit=30)

    # 2. Build graph
    graph = build_result_graph(results)

    # 3. Rank
    ranked = rank_by_connectivity(graph, algorithm)

    # 4. Discard graph (ephemeral)
    return ranked
```

---

## Relationship Discovery Pattern

**Metadata-driven edges:**

```
function discover_edges(result1, result2):
    edges = []

    # Same document → sibling
    if result1.file_path == result2.file_path:
        edges.append({
            type: 'sibling',
            weight: 0.9,
            reason: 'Same document'
        })

    # Same conversation → genealogy
    if result1.session_id == result2.session_id:
        edges.append({
            type: 'genealogy',
            weight: 0.85,
            reason: 'Same session'
        })

    # Temporal + semantic → evolution
    if result1.timestamp < result2.timestamp:
        similarity = cosine(result1.vector, result2.vector)
        if similarity > 0.85:
            edges.append({
                type: 'evolution',
                weight: similarity,
                reason: 'Later + similar'
            })

    return edges
```

**Key: Relationships discovered from metadata, not precomputed.**

---

## Query-Adaptive Algorithm Selection

### Use Case 1: Authority (PageRank)

```
Query: "What's the most authoritative caching pattern?"

graph = build_result_graph(search("caching patterns"))
ranked = pagerank(graph)

# Returns: Most-referenced patterns (high in-degree)
```

**Interpretation:** Patterns cited by many other chunks.

### Use Case 2: Bridges (Centrality)

```
Query: "Find concepts connecting auth and caching"

results = search("auth") + search("caching")
graph = build_result_graph(results)
ranked = betweenness_centrality(graph)

# Returns: Chunks on shortest paths between auth/cache clusters
```

**Interpretation:** Architectural patterns bridging domains.

### Use Case 3: Clusters (Community Detection)

```
Query: "Group security patterns"

graph = build_result_graph(search("security"))
clusters = community_detection(graph)

# Returns: Natural groupings (auth cluster, encryption cluster, etc.)
```

**Interpretation:** Semantically related subgroups.

---

## Ephemeral vs Persistent Graphs

### Ephemeral (Default Pattern)

```
# Build, use, discard
results = query_with_graph_ranking("query", algorithm='pagerank')
# Graph no longer exists
```

**When:** One-time ranking needed.

### Session Persistent

```
# Build once, reuse in session
graph_id = build_result_graph(search("topic"))

# Apply multiple algorithms
authority = rank_by(graph_id, 'pagerank')
bridges = rank_by(graph_id, 'centrality')
clusters = group_by(graph_id, 'communities')

# Expires with session
```

**When:** Multiple ranking strategies on same results.

### Canonical Persistent

```
# Store frequently-used graphs
if not exists('canonical-patterns-graph'):
    graph = build_result_graph(all_patterns)
    save_graph('canonical-patterns-graph', graph)

# Reuse across queries
authority = rank_by('canonical-patterns-graph', 'pagerank')
```

**When:** Expensive to rebuild, stable over time.

---

## When to Use This Pattern

**Use when:**
- Need ranking by connectivity, not just semantic similarity
- Relationship types emerge from metadata (not predefined)
- Query intent varies (authority vs bridges vs clusters)
- Result sets small (20-50 typical)

**Don't use when:**
- Relationships fixed and known at write time
- Graph analytics needed on full corpus (not result sets)
- Latency critical (<10ms required)
- Simple semantic ranking sufficient

---

## Trade-off Analysis

### Query-Time Construction

**Pros:**
- Flexible: Algorithm choice at query time
- Adaptive: New relationship types via metadata
- Scalable: O(k²) not O(n²)
- Fresh: Always reflects current metadata

**Cons:**
- Slower: 60-150ms construction overhead
- No precomputation: Can't leverage prepared analytics
- Ephemeral: Must rebuild for each query

### Precomputed Index

**Pros:**
- Fast: O(1) graph lookup
- Prepared: Analytics precomputed
- Permanent: Persistent structure

**Cons:**
- Rigid: Relationship types fixed at write time
- Expensive: O(n²) precomputation
- Stale: Relationships static until reindex

---

## Real-World Analogies

**SQL query optimizer:**
- Builds execution plan at query time (not write time)
- Adapts to query structure and filters
- Plan discarded after execution

**JIT compilation:**
- Compiles hot paths at runtime (not ahead-of-time)
- Adapts to actual execution patterns
- Compiled code cached but can be regenerated

**This pattern:**
- Builds graph at query time (not index time)
- Adapts to query intent and result set
- Graph ephemeral but can be cached

---

## Extension: Multi-Query Graph Bundling

```
function multi_query_with_bundling(queries, algorithm):
    # 1. Execute multiple queries in parallel
    result_sets = parallel_map(queries, search_candidates)

    # 2. Combine result sets
    all_results = flatten(result_sets)

    # 3. Build graph from combined results
    graph = build_result_graph(all_results)

    # 4. Rank by connectivity
    ranked = rank_by_connectivity(graph, algorithm)

    return ranked
```

**Use case:** "Find authoritative patterns across auth, caching, and validation"

---

## Key Insights

1. **Graph as query operator, not storage layer**
   - Build from results, rank, discard
   - Like SQL ORDER BY (operates on results)

2. **O(k²) not O(n²) complexity**
   - Graph on 50 results, not 10,000 documents
   - 40,000× fewer edges to compute

3. **Query-adaptive ranking**
   - Authority (PageRank), bridges (centrality), clusters (communities)
   - Same chunks, different insights

4. **Metadata enables relationship discovery**
   - Edges from file_path, session_id, timestamp, semantic similarity
   - No precomputation needed

5. **Ephemeral by default, persistent when valuable**
   - Build/use/discard for one-time ranking
   - Cache for session or canonical graphs

---

## Language-Agnostic Implementation Hints

**Graph libraries:**
- Python: NetworkX
- JavaScript: graphlib (built-in), cytoscape.js
- Java: JGraphT
- Rust: petgraph
- Go: gonum/graph

**Algorithms:**
- PageRank: Available in all major graph libraries
- Betweenness Centrality: O(VE) typically
- Community Detection: Louvain algorithm (common)

---

## Bottom Line

**Problem:** Need flexible ranking by connectivity, not just semantic similarity.

**Anti-pattern:** Precompute O(n²) graph index at write time.

**Pattern:** Build O(k²) graph at query time, rank, discard.

**Benefits:**
- Query-adaptive (algorithm choice)
- Metadata-driven (relationships emerge)
- Scalable (40,000× fewer edges)
- Fresh (always current)

**Trade-off:** Flexibility vs precomputed speed (60-150ms overhead).

**Essence:** Graph as query operator, not storage layer.
