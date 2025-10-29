---
session_id: ca22384b-3a6d-4821-8b70-2aa1a89ea4ba
date: 2025-10-27
level: architecture-implementation
innovation: dual-layer-architecture
---

# Dual-Layer Architecture: Implementation Specification

## File Naming Convention

```
Implementation: YYMMDD-HHMM_title.md
Pattern: YYMMDD-HHMM_title.pattern.md

Detection:
if file_path.endswith('.pattern.md'):
    layer = 'pattern'
else:
    layer = 'implementation'
```

## Dual Indexing

```python
def index_decision(file_path: str):
    """Index both implementation and pattern if exists"""

    # 1. Index implementation
    impl_chunk = parse_and_embed(file_path)
    impl_chunk.payload['layer'] = 'implementation'

    # 2. Check for pattern twin
    pattern_path = file_path.replace('.md', '.pattern.md')

    if Path(pattern_path).exists():
        pattern_chunk = parse_and_embed(pattern_path)
        pattern_chunk.payload['layer'] = 'pattern'
        pattern_chunk.payload['source_impl_id'] = impl_chunk.id

        # Bidirectional link
        impl_chunk.payload['pattern_chunk_id'] = pattern_chunk.id

        # Index both
        qdrant.upsert(points=[impl_chunk, pattern_chunk])
    else:
        # Implementation only
        qdrant.upsert(points=[impl_chunk])
```

## Query Filtering

```python
# Implementation only (default)
results = qdrant.search(
    query=embed("authentication"),
    query_filter=Filter(must=[
        FieldCondition(key='layer', match=MatchValue(value='implementation'))
    ])
)

# Pattern only
results = qdrant.search(
    query=embed("authentication"),
    query_filter=Filter(must=[
        FieldCondition(key='layer', match=MatchValue(value='pattern'))
    ])
)

# Both layers
results = qdrant.search(query=embed("authentication"))
```

## CLI Interface

```bash
# Default: Implementation layer
imem search "authentication"

# Pattern layer only
imem search "authentication" --pattern

# Pattern layer, all projects
imem search "authentication" --pattern --all-projects

# Navigate from implementation to pattern
imem pattern-view <impl-chunk-id>
```

## Pattern Extraction Agent

```python
def extract_pattern(impl_file_path: str) -> str:
    """Agent-assisted pattern extraction"""

    with open(impl_file_path) as f:
        impl_content = f.read()

    # LLM prompt
    prompt = f"""
    Extract language-agnostic pattern from this implementation:

    {impl_content}

    Remove:
    - Framework names
    - Library references
    - Code snippets (replace with pseudocode if needed)
    - File paths
    - Language-specific idioms

    Preserve:
    - Context (why this arose)
    - Solution principle (abstractly)
    - Rationale
    - Constraints
    - Alternatives
    """

    pattern_content = llm.generate(prompt)

    # Save pattern twin
    pattern_path = impl_file_path.replace('.md', '.pattern.md')
    with open(pattern_path, 'w') as f:
        f.write(pattern_content)

    return pattern_path
```

## Bidirectional Navigation

```python
# From implementation to pattern
def get_pattern(impl_chunk_id: str) -> Optional[Chunk]:
    impl = qdrant.retrieve(ids=[impl_chunk_id])[0]
    pattern_id = impl.payload.get('pattern_chunk_id')

    if pattern_id:
        return qdrant.retrieve(ids=[pattern_id])[0]
    return None

# From pattern to implementation
def get_implementation(pattern_chunk_id: str) -> Chunk:
    pattern = qdrant.retrieve(ids=[pattern_chunk_id])[0]
    impl_id = pattern.payload['source_impl_id']
    return qdrant.retrieve(ids=[impl_id])[0]
```

## Storage

**No duplication:**
- Implementation: .md file in git
- Pattern: .pattern.md file in git
- Both indexed as separate vectors
- Metadata links them

**Overhead:**
- 2x chunks (one per layer)
- Different embeddings (pattern ≠ implementation content)
- Minimal metadata (~100 bytes per link)
