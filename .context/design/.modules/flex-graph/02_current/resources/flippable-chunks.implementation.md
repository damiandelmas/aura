---
session_id: eee3b7a5-3870-4b50-984c-19eb2e2fa769
date: 2025-10-27
type: implementation.specification
resolution: level-2b
keywords: "qdrant-metadata serving-function cli-interface"
---

# Flippable Chunks: Implementation Specification

## Metadata Schema

```python
# Implementation chunk
{
    'chunk_id': 'abc123',
    'file_path': '.context/develop/.changes/251011-1200_auth.md',
    'layer': 'implementation',
    'pattern_chunk_id': 'abc123_pattern',
    'has_pattern': True,
    'superseded_by': 'xyz789',  # Set on supersession
    'supersedes': None,
    'content': '...',
}

# Pattern chunk
{
    'chunk_id': 'abc123_pattern',
    'file_path': '.context/develop/.changes/251011-1200_auth.pattern.md',
    'layer': 'pattern',
    'source_impl_id': 'abc123',
    'superseded_by': None,  # Patterns don't supersede
    'content': '...',
}
```

---

## Supersession Detection

```python
def detect_supersession(new_chunk, collection):
    """Detect if new chunk supersedes existing."""
    similar = search(
        query=new_chunk.content,
        filters={'section_type': new_chunk.section_type},
        threshold=0.85,
        limit=5
    )

    if similar:
        for candidate in similar:
            prompt = f"Does '{new_chunk.title}' replace '{candidate.title}'?"
            if user_confirms(prompt):
                return candidate.id
    return None

def mark_supersession(old_chunk_id, new_chunk_id):
    """Update metadata without re-indexing."""
    qdrant.update_payload(
        chunk_id=old_chunk_id,
        payload={'superseded_by': new_chunk_id}
    )
    qdrant.update_payload(
        chunk_id=new_chunk_id,
        payload={'supersedes': old_chunk_id}
    )
```

---

## Serving Strategy

```python
def serve_chunk(chunk_id, force_impl=False):
    """Serve pattern or implementation based on state."""
    chunk = qdrant.retrieve(chunk_id)

    # Force flag: always serve implementation
    if force_impl:
        return chunk

    # Superseded with pattern: serve pattern
    if chunk.payload.get('superseded_by') and chunk.payload.get('has_pattern'):
        pattern_id = chunk.payload['pattern_chunk_id']
        pattern_chunk = qdrant.retrieve(pattern_id)
        return pattern_chunk

    # Default: serve implementation
    return chunk
```

---

## CLI Interface

```bash
# Default query (serves pattern if superseded)
imem search "JWT authentication"

# Force implementation view
imem search "JWT authentication" --full-resolution

# Explicitly query patterns only
imem search "authentication" --pattern-only

# Flip specific chunk to pattern view
imem pattern-flip <chunk-id>
```

---

## Indexing Pipeline

```python
def index_decision(file_path):
    """Index both implementation and pattern."""
    # Index implementation
    impl_chunk = create_chunk(file_path)
    impl_id = qdrant.upsert(impl_chunk)

    # Check for pattern variant
    pattern_path = file_path.replace('.md', '.pattern.md')
    if os.path.exists(pattern_path):
        pattern_chunk = create_chunk(pattern_path)
        pattern_chunk.payload['source_impl_id'] = impl_id
        pattern_chunk.payload['layer'] = 'pattern'
        pattern_id = qdrant.upsert(pattern_chunk)

        # Link chunks
        qdrant.update_payload(
            chunk_id=impl_id,
            payload={
                'pattern_chunk_id': pattern_id,
                'has_pattern': True
            }
        )
```

---

## Query Filters

```bash
# Implementation layer only
imem search "auth" --layer implementation

# Pattern layer only
imem search "auth" --layer pattern

# Both layers
imem search "auth"  # Default

# Superseded chunks (archaeological)
imem search "auth" --include-superseded --full-resolution
```

---

## Performance

**Supersession:** O(1) metadata update
**Serving decision:** O(1) metadata check
**Pattern retrieval:** O(1) chunk lookup
**Re-indexing required:** 0

No performance degradation from supersession tracking.
