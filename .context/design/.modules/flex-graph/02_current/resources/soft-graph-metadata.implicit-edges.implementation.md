---
session_id: ca22384b-3a6d-4821-8b70-2aa1a89ea4ba
date: 2025-10-27
level: architecture-implementation
innovation: soft-graph-metadata
---

# Soft-Graph via Metadata: Implementation Specification

## Metadata Schema

**Required fields for relationships:**

```python
chunk_payload = {
    # Sibling relationships
    'file_path': '/path/to/251011-1200_auth.md',

    # Genealogy relationships
    'session_id': 'cb91d93d',

    # Temporal relationships
    'timestamp': '2025-10-11T12:30:00Z',

    # Pattern relationships
    'layer': 'implementation' | 'pattern',

    # Content for semantic relationships
    'content': '...',
    'vector': [...]  # E5-Large-v2 embedding
}
```

## Relationship Primitives

**Siblings (same file):**
```python
def get_siblings(chunk_id: str) -> List[Chunk]:
    chunk = qdrant.retrieve(ids=[chunk_id])[0]

    return qdrant.scroll(
        collection_name=collection,
        scroll_filter=Filter(must=[
            FieldCondition(
                key='file_path',
                match=MatchValue(value=chunk.payload['file_path'])
            )
        ])
    )[0]
```

**Genealogy (same session):**
```python
def get_genealogy(chunk_id: str) -> List[Chunk]:
    chunk = qdrant.retrieve(ids=[chunk_id])[0]

    return qdrant.scroll(
        collection_name=collection,
        scroll_filter=Filter(must=[
            FieldCondition(
                key='session_id',
                match=MatchValue(value=chunk.payload['session_id'])
            )
        ])
    )[0]
```

**Temporal (evolution chain):**
```python
def get_temporal_chain(chunk_id: str, threshold=0.7) -> List[Chunk]:
    chunk = qdrant.retrieve(ids=[chunk_id])[0]

    # Semantic + temporal filter
    return qdrant.search(
        collection_name=collection,
        query_vector=chunk.vector,
        query_filter=Filter(must=[
            FieldCondition(
                key='timestamp',
                range={'gt': chunk.payload['timestamp']}
            )
        ]),
        score_threshold=threshold,
        limit=20
    )
```

**Pattern (abstraction):**
```python
def get_pattern_layer(chunk_id: str) -> Optional[Chunk]:
    chunk = qdrant.retrieve(ids=[chunk_id])[0]

    pattern_path = chunk.payload['file_path'].replace('.md', '.pattern.md')

    results = qdrant.scroll(
        collection_name=collection,
        scroll_filter=Filter(must=[
            FieldCondition(
                key='file_path',
                match=MatchValue(value=pattern_path)
            )
        ])
    )[0]

    return results[0] if results else None
```

## CLI Interface

```bash
# Get siblings
imem siblings <result-id>

# Get genealogy
imem filter --session <session-id>

# Get temporal chain
imem filter --timestamp-after <time> --semantic-similar <result-id>

# Get pattern layer
imem search --file-path <path>.pattern.md
```

## Performance

- **Siblings**: O(log n) metadata filter
- **Genealogy**: O(log n) metadata filter
- **Temporal**: O(k) semantic search + filter
- **Pattern**: O(log n) exact match
- **Typical**: 10-40ms per relationship query
