---
session_id: e025fbb0-1abb-46e8-82a1-79c49afcc32d
date: 2025-10-27
type: pattern.innovation
resolution: architectural
keywords: "multi-collection pattern-layer query-isolation"
---

# Cross-Project Intellectual Capital Pattern

## Pattern Structure

**Isolated collections, unified pattern layer.**

### Component Relationship

```
Registry (tracks all projects):
└─ Projects
    ├─ Project A
    │   ├─ Collection: imem_<hash_a>
    │   ├─ Impl chunks (TypeScript code)
    │   └─ Pattern chunks (agnostic)
    │
    ├─ Project B
    │   ├─ Collection: imem_<hash_b>
    │   ├─ Impl chunks (Python code)
    │   └─ Pattern chunks (agnostic)
    │
    └─ Project C
        ├─ Collection: imem_<hash_c>
        ├─ Impl chunks (Rust code)
        └─ Pattern chunks (agnostic)

Cross-project query:
- Query patterns only (layer='pattern')
- Across all collections
- Merge and rank results
- Zero code contamination
```

## Invariants

1. **Pattern chunks tagged consistently**
   - All pattern chunks: `layer: 'pattern'`
   - Enables: Filter by layer across collections
   - Guarantees: No implementation leakage

2. **Collection isolation**
   - Each project = separate collection
   - No cross-contamination by default
   - Explicit opt-in for cross-project

3. **Registry maintains project index**
   - Tracks all initialized projects
   - Maps paths to collection IDs
   - Enables multi-collection queries

## Query Modes

```
Mode 1: Single project (default)
  collection = current_project_collection
  filters = (any)
  result = project-specific

Mode 2: Cross-project patterns
  collections = registry.all_projects()
  filters = {layer: 'pattern'}
  result = language-agnostic

Mode 3: Specific project implementation
  collection = target_project_collection
  filters = {layer: 'implementation'}
  result = code-specific
```

## Metadata Schema

```
Pattern chunk (cross-project compatible):
{
  layer: 'pattern',
  cross_project_compatible: true,
  source_impl_id: '<impl_chunk_id>',
  content: '<language-agnostic description>'
}

Implementation chunk (project-specific):
{
  layer: 'implementation',
  cross_project_compatible: false,
  pattern_chunk_id: '<pattern_chunk_id>',
  language: 'typescript',
  framework: 'express',
  content: '<code and specifics>'
}
```

## Cross-Project Algorithm

```
def search_patterns_across_projects(query, projects='all'):
    """Query pattern layer across multiple projects"""

    if projects == 'all':
        collections = registry.list_all_projects()
    else:
        collections = [registry.get_collection(p) for p in projects]

    results = []
    for collection in collections:
        # Query patterns only
        hits = qdrant.search(
            collection=collection,
            query=embed(query),
            filter={'layer': 'pattern'}  # Critical filter
        )
        results.extend(hits)

    # Merge and rank
    return rank_by_similarity(results)
```

## Authority Scoring

```
Pattern authority = f(appearances, projects, recency)

def calculate_pattern_authority(pattern_chunk):
    """How validated is this pattern?"""

    # Find all instances of this pattern
    similar_patterns = search_similar_patterns(
        pattern_chunk.vector,
        threshold=0.90
    )

    # Count unique projects
    projects = set(p.metadata['project_id'] for p in similar_patterns)

    # Weight by recency
    recency_score = mean(
        time_decay(p.metadata['timestamp']) for p in similar_patterns
    )

    return len(projects) * recency_score
```

## Benefits

- **Anti-contamination**: Pattern layer isolates principles
- **Authority tracking**: Count pattern appearances across projects
- **Portable learning**: Apply proven patterns anywhere
- **Career-long memory**: Knowledge transcends project boundaries

## When to Use

Use when:
- Working across multiple projects
- Want to learn from past decisions
- Need language-agnostic principles
- Building new project in different stack

Avoid when:
- Single project scope
- Need exact implementation details
- Code-specific queries required
