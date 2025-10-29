---
session_id: e025fbb0-1abb-46e8-82a1-79c49afcc32d
date: 2025-10-27
type: implementation.innovation
resolution: code-ready
keywords: "multi-collection registry pattern-filter authority-ranking"
---

# Cross-Project Intellectual Capital Implementation

## Registry Management

**Track all projects in global registry:**

```python
# ~/.context/imem_registry.json
{
  "projects": {
    "/home/user/project-typescript": {
      "collection": "imem_a1b2c3d4",
      "language": "typescript",
      "indexed_at": "2025-10-27T12:00:00",
      "doc_count": 347,
      "pattern_count": 89
    },
    "/home/user/project-python": {
      "collection": "imem_e5f6g7h8",
      "language": "python",
      "indexed_at": "2025-10-27T13:00:00",
      "doc_count": 128,
      "pattern_count": 34
    },
    "/home/user/project-rust": {
      "collection": "imem_i9j0k1l2",
      "language": "rust",
      "indexed_at": "2025-10-27T14:00:00",
      "doc_count": 256,
      "pattern_count": 67
    }
  }
}


class ProjectRegistry:
    """Manage multi-project knowledge base"""

    REGISTRY_PATH = Path.home() / '.context' / 'imem_registry.json'

    @classmethod
    def load(cls):
        if cls.REGISTRY_PATH.exists():
            return json.loads(cls.REGISTRY_PATH.read_text())
        return {'projects': {}}

    @classmethod
    def register_project(cls, project_path, collection_name, language):
        registry = cls.load()
        registry['projects'][str(project_path)] = {
            'collection': collection_name,
            'language': language,
            'indexed_at': datetime.now().isoformat(),
            'doc_count': 0,
            'pattern_count': 0
        }
        cls.REGISTRY_PATH.write_text(json.dumps(registry, indent=2))

    @classmethod
    def list_all_collections(cls):
        registry = cls.load()
        return [p['collection'] for p in registry['projects'].values()]

    @classmethod
    def get_current_project(cls):
        current_path = os.getcwd()
        registry = cls.load()
        return registry['projects'].get(current_path)
```

## Cross-Project Search

**CLI interface:**

```python
# In imem/src/imem/cli.py

@click.command()
@click.argument('query')
@click.option('--all-projects', is_flag=True, help='Search across all projects')
@click.option('--pattern-only', is_flag=True, help='Pattern layer only')
@click.option('--project', help='Specific project path')
def search(query, all_projects, pattern_only, project):
    """Search with multi-project support"""

    if all_projects:
        collections = ProjectRegistry.list_all_collections()
        results = cross_project_search(query, collections, pattern_only)
    elif project:
        collection = ProjectRegistry.get_collection(project)
        results = single_project_search(query, collection, pattern_only)
    else:
        collection = ProjectRegistry.get_current_project()['collection']
        results = single_project_search(query, collection, pattern_only)

    display_results(results)


def cross_project_search(query, collections, pattern_only):
    """Query across multiple collections"""

    all_results = []

    for collection in collections:
        # Build filter
        filters = {}
        if pattern_only:
            filters['layer'] = 'pattern'

        # Search in collection
        results = qdrant_client.search(
            collection_name=collection,
            query_vector=embed(query),
            limit=10,
            query_filter=filters
        )

        # Add project metadata
        for r in results:
            r.payload['_source_collection'] = collection
            r.payload['_source_project'] = get_project_path(collection)

        all_results.extend(results)

    # Merge and rank
    return rank_cross_project_results(all_results)


def rank_cross_project_results(results):
    """Rank with cross-project authority"""

    # Group by semantic similarity
    clusters = cluster_similar_patterns(results, threshold=0.90)

    # Score by cluster size (authority = reappearance)
    for cluster in clusters:
        projects_seen = set(r.payload['_source_project'] for r in cluster)
        authority_boost = len(projects_seen) * 0.2

        for result in cluster:
            result.score += authority_boost

    # Sort by adjusted score
    return sorted(results, key=lambda r: r.score, reverse=True)
```

## Pattern-Layer Filtering

**Ensure no implementation leakage:**

```python
def ensure_pattern_purity(chunk):
    """Validate pattern chunk has no code"""

    content = chunk.payload['content']

    # Check for code indicators
    code_indicators = [
        'import ',
        'from ',
        'function ',
        'class ',
        'def ',
        'const ',
        'let ',
        'var ',
        '```'  # code blocks
    ]

    for indicator in code_indicators:
        if indicator in content:
            raise ValueError(
                f"Pattern chunk contains code: {indicator}"
            )

    # Check for framework names
    framework_names = [
        'express', 'fastapi', 'django', 'flask',
        'react', 'vue', 'angular',
        'typescript', 'python', 'rust', 'go'
    ]

    content_lower = content.lower()
    for framework in framework_names:
        if framework in content_lower:
            warnings.warn(
                f"Pattern mentions framework: {framework}"
            )

    return True
```

## CLI Usage Examples

```bash
# Current project only (default)
imem search "authentication"
# → Returns: Implementations + patterns from current project

# Cross-project patterns only
imem search "authentication" --all-projects --pattern-only
# → Returns: All auth patterns from all projects (no code)

# Specific project implementation
imem search "authentication" --project ~/project-typescript
# → Returns: TypeScript auth implementation

# Authority-ranked patterns
imem search "provider agnostic" --all-projects --pattern-only
# → Returns: Patterns ranked by appearance count across projects
```

## Authority Display

```bash
$ imem search "stateless auth" --all-projects --pattern-only

Results (cross-project patterns):

1. Stateless Authentication Pattern (score: 0.94, authority: 3 projects)
   Found in: project-typescript, project-python, project-rust
   Context: Distributed systems without shared session store
   Solution: Token-based auth with asymmetric signing
   [Pattern details...]

2. Session-Based Authentication Pattern (score: 0.87, authority: 1 project)
   Found in: project-monolith
   Context: Single-server application with state management
   Solution: Server-side sessions with cookie-based tracking
   [Pattern details...]
```

## Files Modified

```
imem/src/imem/registry.py (new)
├─ ProjectRegistry class
├─ register_project()
├─ list_all_collections()
└─ get_collection()

imem/src/imem/cli.py
├─ search() - add --all-projects, --pattern-only flags
├─ cross_project_search()
└─ rank_cross_project_results()

imem/src/imem/validation.py
└─ ensure_pattern_purity()

~/.context/imem_registry.json (new)
└─ Global project registry
```

## Performance

- **Multi-collection query**: O(k * collections) where k=limit
- **Clustering**: O(n²) but n=results (typically <50)
- **Authority calculation**: O(n) single pass
- **Total overhead**: +50-100ms for cross-project vs single-project

## Validation

```python
def test_cross_project_isolation():
    # Index TypeScript project
    register_project("~/ts-project", "imem_ts", "typescript")
    index_file("auth.md")  # Contains TypeScript code

    # Index Python project
    register_project("~/py-project", "imem_py", "python")

    # Cross-project pattern query should not return TypeScript code
    results = search("auth", all_projects=True, pattern_only=True)

    for r in results:
        assert 'layer' in r.payload
        assert r.payload['layer'] == 'pattern'
        ensure_pattern_purity(r)  # No code leakage
```
