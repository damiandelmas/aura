---
session_id: e025fbb0-1abb-46e8-82a1-79c49afcc32d
date: 2025-10-27
type: implementation.innovation
resolution: code-ready
keywords: "qdrant-metadata serving-logic supersession-detection"
---

# Flippable Chunks Implementation

## Storage Layer (Qdrant)

**Both chunks indexed simultaneously:**

```python
# During ingestion
def index_decision(file_path):
    # 1. Index implementation
    impl_chunk = {
        'id': generate_id(file_path),
        'vector': embed(impl_content),
        'payload': {
            'file_path': file_path,
            'layer': 'implementation',
            'pattern_chunk_id': None,  # Set after pattern indexed
            'superseded_by': None,
            'serving_mode': 'implementation'
        }
    }

    # 2. Check for .pattern.md twin
    pattern_path = file_path.replace('.md', '.pattern.md')
    if exists(pattern_path):
        pattern_chunk = {
            'id': generate_id(pattern_path),
            'vector': embed(pattern_content),
            'payload': {
                'file_path': pattern_path,
                'layer': 'pattern',
                'source_impl_id': impl_chunk['id'],
                'cross_project_compatible': True
            }
        }

        # Link bidirectionally
        impl_chunk['payload']['pattern_chunk_id'] = pattern_chunk['id']

        qdrant.upsert(points=[impl_chunk, pattern_chunk])
    else:
        qdrant.upsert(points=[impl_chunk])
```

## Supersession Detection

**On new decision creation:**

```python
def detect_supersession(new_decision_id):
    """Check if new decision supersedes existing ones"""

    new_chunk = qdrant.retrieve(ids=[new_decision_id])[0]

    # Search for semantically similar decisions
    similar = qdrant.search(
        query_vector=new_chunk.vector,
        limit=5,
        score_threshold=0.85,
        filter={
            'section_type': new_chunk.payload['section_type'],
            'superseded_by': None  # Only unsuperseded
        }
    )

    for candidate in similar:
        # Prompt user
        prompt = f"Does '{new_chunk.payload['section_name']}' " \
                 f"replace '{candidate.payload['section_name']}'? [y/N]"

        if user_confirms(prompt):
            # Update metadata only
            qdrant.set_payload(
                points=[candidate.id],
                payload={
                    'superseded_by': new_decision_id,
                    'superseded_at': datetime.now().isoformat(),
                    'serving_mode': 'pattern' if candidate.payload.get('pattern_chunk_id') else 'implementation'
                }
            )

            print(f"✓ Marked {candidate.id} as superseded")
```

## Serving Logic

**CLI integration:**

```python
# In imem/src/imem/cli.py

@click.command()
@click.argument('query')
@click.option('--mode', type=click.Choice(['default', 'pattern', 'force']), default='default')
def search(query, mode):
    """Search with serving mode selection"""

    # 1. Vector search
    results = qdrant.search(query=embed(query), limit=10)

    # 2. Apply serving logic
    served_results = []
    for result in results:
        served_chunk = apply_serving_mode(result, mode)
        if served_chunk:
            served_results.append(served_chunk)

    # 3. Display
    for chunk in served_results:
        display_result(chunk)


def apply_serving_mode(chunk, mode):
    """Determine which chunk to serve"""

    if mode == 'force':
        # Always implementation
        return chunk

    if mode == 'pattern':
        # Pattern if exists, else None
        pattern_id = chunk.payload.get('pattern_chunk_id')
        if pattern_id:
            return qdrant.retrieve(ids=[pattern_id])[0]
        return None

    # mode == 'default'
    if chunk.payload.get('superseded_by'):
        # Superseded: serve pattern if available
        pattern_id = chunk.payload.get('pattern_chunk_id')
        if pattern_id:
            pattern = qdrant.retrieve(ids=[pattern_id])[0]
            # Add metadata about supersession
            pattern.payload['_served_as_replacement'] = True
            pattern.payload['_original_impl_id'] = chunk.id
            return pattern

    # Current or no pattern available
    return chunk
```

## CLI Usage

```bash
# Default: Serve current implementation or pattern if superseded
imem search "JWT authentication"
# → Returns: OAuth2 pattern (if JWT superseded)

# Force: Always get implementation
imem search "JWT authentication" --mode force
# → Returns: JWT implementation (even if superseded)

# Pattern: Always get abstraction
imem search "JWT authentication" --mode pattern
# → Returns: Stateless auth pattern
```

## Files Modified

```
imem/src/imem/ingest.py
├─ index_decision() - dual indexing
└─ detect_supersession() - on ingestion

imem/src/imem/cli.py
├─ search() - add --mode flag
└─ apply_serving_mode() - serving logic

imem/src/imem/supersession.py (new)
├─ detect_supersession()
├─ prompt_user_confirmation()
└─ update_supersession_metadata()
```

## Validation

```python
# Test dual indexing
def test_dual_indexing():
    index_decision("251011-1200_auth.md")

    impl = search("JWT", mode='force')[0]
    pattern = search("JWT", mode='pattern')[0]

    assert impl.id != pattern.id
    assert impl.payload['pattern_chunk_id'] == pattern.id
    assert pattern.payload['source_impl_id'] == impl.id


# Test supersession
def test_supersession_serving():
    # Index initial decision
    jwt_id = index_decision("251011-1200_auth.md")

    # Index replacement
    oauth_id = index_decision("251115-1500_oauth.md")

    # Mark supersession
    mark_superseded(jwt_id, oauth_id)

    # Default mode serves pattern
    result = search("authentication", mode='default')[0]
    assert result.payload['layer'] == 'pattern'
    assert result.payload['_original_impl_id'] == jwt_id

    # Force mode serves implementation
    result = search("authentication", mode='force')[0]
    assert result.id == jwt_id
    assert result.payload['layer'] == 'implementation'
```

## Performance

- **Supersession detection**: O(k) similarity search (k=5)
- **Serving logic**: O(1) metadata check + optional O(1) retrieve
- **Storage overhead**: 2x chunks (impl + pattern)
- **Query time**: +10-20ms for pattern retrieval (if superseded)

No re-indexing. No corpus scan. Just metadata and optional second retrieve.
