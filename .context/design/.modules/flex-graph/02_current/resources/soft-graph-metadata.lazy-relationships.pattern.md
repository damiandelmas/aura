---
session_id: e025fbb0-1abb-46e8-82a1-79c49afcc32d
date: 2025-10-27
type: pattern.innovation
resolution: architectural
keywords: "metadata-filters relationship-discovery query-time-graphs"
---

# Soft-Graph via Metadata Pattern

## Pattern Structure

**Relationships as metadata queries, not stored edges.**

### Component Relationship

```
Storage layer:
├─ Chunks with rich metadata
├─ No edge table
└─ No relationship precomputation

Query layer:
├─ Filter primitives (metadata dimensions)
├─ Combine results (relationship discovery)
└─ Optional graph construction (ephemeral)

Composition layer:
└─ Chain filters to navigate "graph"
```

## Invariants

1. **No edges stored**
   - Metadata only
   - Relationships implicit

2. **Discovery at query time**
   - Filter by metadata
   - Combine results
   - Ephemeral connections

3. **Infinite extensibility**
   - New metadata dimension = new relationship type
   - No schema migration
   - No edge recomputation

## Relationship Primitives

```
Primitive 1: siblings(chunk_id)
Implementation: Filter WHERE file_path == chunk.file_path
Returns: All chunks from same document

Primitive 2: genealogy(chunk_id)
Implementation: Filter WHERE session_id == chunk.session_id
Returns: All chunks from same conversation

Primitive 3: temporal_before(chunk_id)
Implementation: Filter WHERE timestamp < chunk.timestamp AND session_id == chunk.session_id
Returns: Earlier work in same session

Primitive 4: temporal_after(chunk_id, semantic=True)
Implementation:
  if semantic:
    Filter WHERE timestamp > chunk.timestamp AND similarity(vector, chunk.vector) > 0.85
  else:
    Filter WHERE timestamp > chunk.timestamp
Returns: Later refinements (optional semantic match)

Primitive 5: pattern_layer(chunk_id)
Implementation: Naming convention .md → .pattern.md
Returns: Abstraction twin if exists
```

## Query Composition

```
Example: Full context for decision

def get_decision_context(decision_id):
    # Get decision chunk
    decision = retrieve(decision_id)

    # Discover relationships via filters
    siblings = filter(file_path=decision.file_path)
    conversation = filter(session_id=decision.session_id, source='conversation')
    pattern = get_pattern(decision.file_path)

    # Compose context
    return {
        'decision': decision,
        'constraints': [s for s in siblings if s.section_type == 'Constraints'],
        'failures': [s for s in siblings if s.section_type == 'Failures'],
        'conversation': conversation,
        'pattern': pattern
    }
```

## Metadata Schema

```
Chunk metadata (enables soft-graph):
{
  # Structural relationships
  'file_path': str,
  'section_type': str,

  # Genealogical relationships
  'session_id': str,

  # Temporal relationships
  'timestamp': ISO datetime,

  # Abstraction relationships
  'layer': 'implementation' | 'pattern',

  # Semantic relationships
  'vector': [1024-dim embedding],

  # Custom relationships (extensible)
  'author': str,
  'keyword': List[str],
  'status': str,
  'type': str
}
```

## Discovery Algorithm

```
def discover_related(chunk, relationship_type):
    """Generic relationship discovery via metadata"""

    if relationship_type == 'siblings':
        return filter(file_path=chunk.file_path)

    elif relationship_type == 'genealogy':
        return filter(session_id=chunk.session_id)

    elif relationship_type == 'temporal_forward':
        return filter(
            timestamp_gt=chunk.timestamp,
            semantic_similar=chunk.id,
            threshold=0.85
        )

    elif relationship_type == 'pattern':
        pattern_path = chunk.file_path.replace('.md', '.pattern.md')
        return filter(file_path=pattern_path)

    # Extensible: Add new relationship types
    elif relationship_type == 'by_author':
        return filter(author=chunk.author)

    elif relationship_type == 'by_keyword':
        return filter(keywords_overlap=chunk.keywords)
```

## Benefits

- **Zero maintenance**: No edges to update
- **Infinite extensibility**: New metadata = new relationships
- **Flexible**: Query any dimension
- **Scalable**: No O(n²) edge computation

## Trade-offs

- **Slower than indexed edges**: Filter scan vs pointer follow
- **Good enough**: 10-50ms vs microseconds
- **Acceptable**: For evolving knowledge, rare queries
- **Not acceptable**: For high-frequency graph analytics

## When to Use

Use when:
- Relationships evolve (knowledge changes)
- Need flexibility (new relationship types)
- Query frequency low (human-in-loop)
- Metadata already captured

Avoid when:
- Static relationships (predefined graph)
- High query frequency (need indexed edges)
- Real-time graph analytics (need precomputed)
