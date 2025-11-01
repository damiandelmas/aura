---
schema_version: "v3_adaptive"
type: "implementation.storage-architecture"
status: "completed"
keywords: "dual-collection flippable-index impl-pattern-separation qdrant-routing"
timestamp: "2025-11-01T01:04:00-0700"
session_id: "4073f617-cac9-43a2-9362-de4411e42744"
---

# Dual Collection Storage: Implementation and Pattern Separation

## Request
> "we still need to separate pattern from impl in vector store tho?"

## Overview
Implemented dual-collection architecture for IMEM, separating implementation and pattern chunks into distinct Qdrant collections (project_impl and project_pattern). This eliminates near-duplicate chunks in the same collection, creates clean semantic spaces, and enables future cross-project pattern aggregation. Modified ingestion to route chunks based on filename (.pattern.md → pattern collection), updated CLI to create both collections during indexing, and added search routing to query the correct collection based on user intent.

## Decisions

### Dual Collections Over Single Collection with Metadata
- **Context**: Single collection contained both impl and pattern chunks causing semantic pollution and duplication
- **Solution**: Two collections per project: `{base}_impl` and `{base}_pattern`
- **Rationale**: Physical separation prevents near-duplicate vectors in same space, enables clean cross-project pattern queries
- **Benefit**: Zero duplicates per collection, obvious routing, simple to understand

### File-Based Layer Detection
- **Context**: Need to determine which collection receives chunks at index time
- **Solution**: Check filename for `.pattern.md` extension
- **Rationale**: Simple, explicit, works with existing file structure
- **Implementation**: `if '.pattern.md' in str(file_path): return 'pattern'`

### Collection Name Suffix Convention
- **Context**: Need consistent naming for dual collections
- **Solution**: Append `_impl` and `_pattern` to base collection name
- **Rationale**: Clear, discoverable, follows existing naming patterns
- **Benefit**: Easy to identify collection purpose from name

## Implementation

### Architecture
1. CLI creates both collections during `imem index` → `{base}_impl` and `{base}_pattern`
2. Ingest detects layer from filename → `.pattern.md` or `.md`
3. Route to appropriate collection → `{base}_pattern` or `{base}_impl`
4. Search routes queries → `--layer` flag selects collection
5. Compose routes by context → `cross_project` flag determines collection

### Code Signatures

**File-Based Layer Detection** (`imem/src/imem/ingest.py`)
```python
def _detect_layer(self, file_path, phase):
    """Detect layer (implementation/pattern) based on filename.
    Only develop phase has pattern mirrors."""
    if phase != 'develop':
        return 'implementation'
    if '.pattern.md' in str(file_path):
        return 'pattern'
    else:
        return 'implementation'
```

**Collection Routing** (`imem/src/imem/ingest.py`)
```python
def ingest_markdown_chunked(self, file_path, phase, base_collection):
    layer = self._detect_layer(file_path, phase)

    # Route to separate collections based on layer
    if layer == 'pattern':
        collection_name = f"{base_collection}_pattern"
    else:
        collection_name = f"{base_collection}_impl"
```

**Dual Collection Creation** (`imem/src/imem/cli.py`)
```python
# Create both impl and pattern collections
impl_collection = f"{collection_name}_impl"
pattern_collection = f"{collection_name}_pattern"

for coll_name in [impl_collection, pattern_collection]:
    collection_exists = ingester.client.collection_exists(coll_name)

    if force and collection_exists:
        ingester.client.delete_collection(coll_name)
        collection_exists = False

    if not collection_exists:
        ingester.client.create_collection(
            collection_name=coll_name,
            vectors_config={...}
        )
```

**Search Collection Routing** (`imem/src/imem/cli.py`)
```python
# Route to impl or pattern collection based on layer flag
base_collection = registry.get_collection_by_type(project_root, 'context')
if layer == 'pattern':
    collection_name = f"{base_collection}_pattern"
else:  # layer == 'implementation' or 'both'
    collection_name = f"{base_collection}_impl"
```

**Compose Query Routing** (`imem/src/imem/compose.py`)
```python
# BRAIN Query Routing: Determine which collection to query
if config_dict.get('cross_project'):
    # Cross-project: Query pattern collection
    query_collection = f"{collection_name}_pattern"
else:
    # Same-project: Query impl collection (default)
    query_collection = f"{collection_name}_impl"
```

## Patterns

### Dual Collection Storage Strategy
- **Pattern**: Physically separate collections for different content types with semantic overlap
- **When**: Need clean semantic spaces and want to prevent near-duplicate pollution
- **Approach**: Route at index time based on file naming convention, query routes based on intent
- **Benefit**: Each collection has clean semantic space, cross-collection queries possible

## Audit

### Modified
- `imem/src/imem/ingest.py` - Added filename-based layer detection, changed parameter from `collection_name` to `base_collection`, added collection routing logic
- `imem/src/imem/cli.py` - Added dual collection creation loop in index command, updated search to route based on `--layer` flag
- `imem/src/imem/compose.py` - Added basic query routing based on `cross_project` flag, routes discovery and graph operations to correct collection
- Removed `layer` field from chunk metadata (collection name now determines layer)

### Configuration
Collections automatically created as pairs during indexing. Routing determined by filename at index time (`.pattern.md` vs `.md`) and by `--layer` flag at query time.
