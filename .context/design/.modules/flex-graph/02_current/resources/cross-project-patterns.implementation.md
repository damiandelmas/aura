---
session_id: eee3b7a5-3870-4b50-984c-19eb2e2fa729
date: 2025-10-27
type: implementation.specification
resolution: level-2b
keywords: "multi-collection-query registry pattern-filter authority-score"
---

# Cross-Project Patterns: Implementation Specification

## Registry Management

```python
# ~/.context/imem_registry.json
{
    "projects": {
        "/home/user/typescript-project": {
            "collection": "imem_ts_a1b2c3d4",
            "indexed_at": "2025-10-27T12:00:00",
            "pattern_count": 47
        },
        "/home/user/python-project": {
            "collection": "imem_py_e5f6g7h8",
            "indexed_at": "2025-10-27T13:00:00",
            "pattern_count": 23
        }
    }
}
```

---

## Cross-Project Query

```python
def search_all_projects(query, pattern_only=True):
    """Query across all registered projects."""
    registry = load_registry()
    all_results = []

    for project_path, metadata in registry['projects'].items():
        collection = metadata['collection']

        # Build filter
        filters = {}
        if pattern_only:
            filters['layer'] = 'pattern'

        # Query collection
        results = qdrant.query_points(
            collection_name=collection,
            query=embed(query),
            query_filter=build_filter(filters),
            limit=10
        )

        # Tag with source project
        for result in results.points:
            result.payload['source_project'] = project_path
            all_results.append(result)

    # Rank by authority
    return rank_by_authority(all_results)
```

---

## Authority Ranking

```python
def rank_by_authority(results):
    """Rank patterns by cross-project validation."""
    # Group by semantic similarity
    pattern_groups = group_similar_patterns(results, threshold=0.85)

    ranked = []
    for group in pattern_groups:
        # Authority = projects where pattern appears
        project_count = len(set(r.payload['source_project'] for r in group))

        # Boost score by validation count
        for result in group:
            result.authority_score = result.score * (1 + 0.2 * project_count)

        ranked.extend(group)

    return sorted(ranked, key=lambda r: r.authority_score, reverse=True)
```

---

## CLI Interface

```bash
# Current project only (default)
imem search "authentication"

# All projects, pattern-only (safe)
imem search "authentication" --all-projects --pattern-only

# All projects, all layers (requires confirmation)
imem search "authentication" --all-projects --include-implementations
# Prompts: "Warning: Cross-project implementation search. Continue? [y/N]"

# Specific projects
imem search "authentication" --projects typescript-api,python-worker --pattern-only

# Authority ranking
imem search "authentication" --all-projects --pattern-only --rank-by-authority
```

---

## Pattern Extraction

```bash
# Manual extraction
imem extract-pattern .context/develop/.changes/251011-1200_auth.md

# Prompts:
# 1. "Strip tech-specific details? [Y/n]"
# 2. "Framework references found: Express.js, jsonwebtoken. Abstract? [Y/n]"
# 3. "Generate .pattern.md? [Y/n]"

# Creates: 251011-1200_auth.pattern.md
# Indexes both: implementation + pattern
```

---

## Contamination Prevention

```python
def query_with_safety(query, all_projects=False, include_implementations=False):
    """Enforce anti-contamination rules."""
    if all_projects and include_implementations:
        # Require explicit confirmation
        print("⚠️  Warning: Cross-project implementation query")
        print("   May return code from different languages/frameworks")
        confirm = input("   Continue? [y/N]: ")
        if confirm.lower() != 'y':
            print("   Switching to pattern-only mode (safe)")
            include_implementations = False

    # Enforce pattern-only for cross-project
    if all_projects and not include_implementations:
        return search_all_projects(query, pattern_only=True)

    # Single project: allow implementations
    return search_current_project(query)
```

---

## Authority Display

```bash
$ imem search "stateless authentication" --all-projects --pattern-only

Results (ranked by authority):

1. Stateless Authentication via Signed Tokens [⭐⭐⭐]
   Authority: Validated in 3 projects (TypeScript, Python, Rust)
   Pattern: Token-based auth with asymmetric signing
   Projects:
   - typescript-api: JWT implementation (2025-10-11)
   - python-worker: PyJWT implementation (2025-10-18)
   - rust-service: Custom tokens (2025-10-25)

2. Session-Based Authentication [⭐]
   Authority: Used in 1 project (TypeScript)
   Pattern: Server-side session storage
   Projects:
   - typescript-api: Redis sessions (2025-09-15, superseded)
```

---

## Multi-Project Graph

```python
def build_cross_project_graph(pattern_query):
    """Build graph connecting patterns across projects."""
    # Query all projects
    results = search_all_projects(pattern_query, pattern_only=True)

    # Build graph
    graph = nx.Graph()

    for result in results:
        # Add node
        graph.add_node(
            result.id,
            content=result.payload['content'],
            project=result.payload['source_project']
        )

        # Add edges (semantic similarity)
        for other in results:
            if result.id != other.id:
                similarity = cosine_similarity(result.vector, other.vector)
                if similarity > 0.80:
                    graph.add_edge(result.id, other.id, weight=similarity)

    # PageRank on pattern graph
    scores = nx.pagerank(graph, weight='weight')

    return graph, scores
```

---

## Performance

**Registry lookup:** O(1) hash lookup
**Per-collection query:** O(log n) via HNSW
**Result merging:** O(k log k) where k = result count
**Authority ranking:** O(k²) for similarity grouping

**Optimization:** Cache pattern groups per query for 1 hour.
