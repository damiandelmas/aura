---
session_id: ca22384b-3a6d-4821-8b70-2aa1a89ea4ba
date: 2025-10-27
level: architecture-implementation
innovation: cross-project-transfer
---

# Cross-Project Transfer: Implementation Specification

## Project Registry

**Tracking all indexed projects:**

```python
# imem/src/imem/registry.py

class ProjectRegistry:
    """Manage multi-project collections"""

    def __init__(self, registry_file="~/.context/imem_registry.json"):
        self.registry_file = Path(registry_file).expanduser()
        self.load()

    def register_project(self, project_root: str):
        """Register new project, create collection"""
        project_id = hashlib.md5(project_root.encode()).hexdigest()[:8]
        collection_name = f"imem_{project_id}"

        self.projects[project_root] = {
            "collection_name": collection_name,
            "registered_at": datetime.now().isoformat(),
            "last_indexed": None
        }
        self.save()

        return collection_name

    def list_projects(self) -> List[Dict]:
        """Get all registered projects"""
        return [
            {"root": root, **meta}
            for root, meta in self.projects.items()
        ]
```

## Multi-Collection Query

**Pattern-only cross-project search:**

```python
# imem/src/imem/cross_project.py

def search_all_projects(
    query: str,
    layer: str = 'pattern',
    limit_per_project: int = 5
) -> List[ScoredPoint]:
    """Query patterns across all projects"""

    registry = ProjectRegistry()
    all_results = []

    query_vector = embed(query)

    for project in registry.list_projects():
        try:
            results = qdrant_client.search(
                collection_name=project['collection_name'],
                query_vector=query_vector,
                query_filter=Filter(must=[
                    FieldCondition(
                        key='layer',
                        match=MatchValue(value=layer)
                    )
                ]),
                limit=limit_per_project
            )

            # Tag with source project
            for result in results:
                result.payload['_source_project'] = project['root']

            all_results.extend(results)

        except Exception as e:
            # Collection doesn't exist or other error
            continue

    # Deduplicate by content similarity
    deduplicated = deduplicate_patterns(all_results)

    # Rank by multi-project authority
    ranked = rank_by_authority(deduplicated)

    return ranked
```

## Deduplication Logic

**Identify same pattern across projects:**

```python
def deduplicate_patterns(results: List[ScoredPoint]) -> List[ScoredPoint]:
    """Merge duplicate patterns, accumulate project count"""

    pattern_groups = {}

    for result in results:
        # Group by high semantic similarity
        content_hash = compute_fuzzy_hash(result.payload['content'])

        if content_hash not in pattern_groups:
            pattern_groups[content_hash] = {
                'representative': result,
                'projects': set(),
                'instances': []
            }

        group = pattern_groups[content_hash]
        group['projects'].add(result.payload['_source_project'])
        group['instances'].append(result)

    # Return one per group with project count
    deduplicated = []
    for group in pattern_groups.values():
        rep = group['representative']
        rep.payload['_cross_project_count'] = len(group['projects'])
        rep.payload['_source_projects'] = list(group['projects'])
        deduplicated.append(rep)

    return deduplicated
```

## Authority Ranking

**Multi-project validation scoring:**

```python
def rank_by_authority(results: List[ScoredPoint]) -> List[ScoredPoint]:
    """Rank by cross-project validation"""

    def authority_score(result):
        base_score = result.score  # Semantic similarity
        project_count = result.payload.get('_cross_project_count', 1)

        # Boost by logarithmic project count
        authority_boost = 1 + math.log(project_count + 1)

        return base_score * authority_boost

    return sorted(results, key=authority_score, reverse=True)
```

## CLI Interface

```bash
# Single project (default)
imem search "authentication"
# Queries: Current project only
# Returns: Implementation + patterns

# Pattern-only, current project
imem search "authentication" --pattern
# Queries: Current project only
# Filter: layer='pattern'
# Returns: Patterns from current project

# Cross-project pattern search
imem search "authentication" --pattern --all-projects
# Queries: All registered projects
# Filter: layer='pattern'
# Returns: Patterns from all projects, ranked by authority

# Cross-project with graph ranking
imem search "provider agnostic" --pattern --all-projects --graph pagerank
# Queries: All projects
# Builds: Graph with cross-project edges
# Applies: PageRank
# Returns: Most central patterns
```

## Implementation in CLI

```python
# imem/src/imem/cli.py

@click.command()
@click.argument('query')
@click.option('--pattern', is_flag=True, help='Pattern layer only')
@click.option('--all-projects', is_flag=True, help='Search all projects')
@click.option('--graph', type=str, help='Apply graph algorithm: pagerank|centrality')
def search(query, pattern, all_projects, graph):
    """Search with optional cross-project pattern mode"""

    if all_projects:
        if not pattern:
            click.echo("Warning: --all-projects implies --pattern")
            pattern = True

        # Cross-project search
        results = search_all_projects(
            query=query,
            layer='pattern',
            limit_per_project=10
        )

        if graph:
            # Build graph from results
            graph_id = build_cross_project_graph(results)
            results = apply_graph_algorithm(graph_id, graph)

    else:
        # Single project search
        layer_filter = {'layer': 'pattern'} if pattern else {}
        results = search_current_project(
            query=query,
            filters=layer_filter
        )

    display_results(results)
```

## Cross-Project Graph Construction

```python
def build_cross_project_graph(results: List[ScoredPoint]) -> str:
    """Build graph with cross-project edges"""

    import networkx as nx
    G = nx.DiGraph()

    # Add nodes
    for result in results:
        G.add_node(result.id, result=result)

    # Add edges
    for i, r1 in enumerate(results):
        for j, r2 in enumerate(results):
            if i >= j:
                continue

            # Same pattern across projects
            if is_similar_pattern(r1, r2) and \
               r1.payload['_source_project'] != r2.payload['_source_project']:
                weight = cosine_similarity(r1.vector, r2.vector)
                G.add_edge(r1.id, r2.id, type='cross_project', weight=weight)

    graph_id = save_graph(G)
    return graph_id
```

## Validation

```python
def test_cross_project_search():
    """Verify pattern isolation"""

    # Query from Python project
    os.chdir('/path/to/python-project')

    # Should return patterns only
    results = search_all_projects("authentication", layer='pattern')

    for result in results:
        assert result.payload['layer'] == 'pattern'
        # No code snippets
        assert 'import' not in result.payload['content'].lower()
        assert 'class' not in result.payload['content'].lower()


def test_authority_ranking():
    """Verify multi-project boost"""

    results = search_all_projects("provider agnostic", layer='pattern')

    # Pattern in 5 projects should rank higher than pattern in 1 project
    # even if semantic scores are similar
    top_result = results[0]
    assert top_result.payload['_cross_project_count'] >= 2
```

## Performance

- **Multi-collection query**: O(N × k) where N=projects, k=limit
- **Deduplication**: O(m log m) where m=total results
- **Authority ranking**: O(m) additional sorting
- **Typical**: ~100-200ms for 5 projects × 10 results each
