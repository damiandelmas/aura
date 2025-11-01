---
schema_version: "v3_adaptive"
type: "implementation.storage-architecture"
status: "completed"
keywords: "dual-collection flippable-index impl-pattern-separation semantic-space-isolation"
timestamp: "2025-11-01T01:04:00-0700"
session_id: "4073f617-cac9-43a2-9362-de4411e42744"
source_changelog: "251101-0104_dual-collection-flippable-index.md"
---

# Dual Collection Storage: Implementation and Pattern Separation

## Request
> "we still need to separate pattern from impl in vector store tho?"

## Overview
Implemented dual-collection architecture, separating implementation and pattern chunks into distinct storage collections. This eliminates near-duplicate chunks in the same collection, creates clean semantic spaces, and enables future cross-collection pattern aggregation. Modified ingestion to route chunks based on file naming convention, updated indexing to create both collections, and added query routing to select the correct collection.

## Decisions

### Dual Collections Over Single Collection with Metadata
- **Context**: Single collection contained both content types causing semantic pollution and duplication
- **Solution**: Two collections per context: one for implementation-specific content, one for language-agnostic patterns
- **Rationale**: Physical separation prevents near-duplicate vectors in same space, enables clean cross-context pattern queries
- **Benefit**: Zero duplicates per collection, obvious routing, simple to understand

### File Naming Convention for Layer Detection
- **Context**: Need to determine which collection receives chunks at index time
- **Solution**: Check file extension pattern to identify content type
- **Rationale**: Simple, explicit, works with existing file structure
- **Benefit**: No metadata parsing required, routing decision is obvious

### Collection Suffix Naming Convention
- **Context**: Need consistent naming for dual collections
- **Solution**: Append type suffixes to base collection identifier
- **Rationale**: Clear, discoverable, follows existing naming patterns
- **Benefit**: Easy to identify collection purpose from name

## Architecture

### Storage Topology
1. Index time → Parse content → Route to collection based on file type
2. Default routing → Standard files to implementation collection
3. Pattern files → Alternative file type to pattern collection
4. Query routing → Selection based on query intent or flags

### Flow
```
File Detection
    ↓
Determine Layer (filename check)
    ↓
Route to Collection (suffix-based)
    ↓
Index Content
```

### Query Routing
```
Query Request
    ↓
Check Intent/Flags
    ↓
Select Collection (impl or pattern)
    ↓
Execute Search
```

## Implementation

### Architectural Flow

**Layer Detection**
```pseudocode
1. Check file path for pattern marker
2. If pattern marker present:
   - Return pattern layer designation
3. Else:
   - Return implementation layer designation
```

**Collection Routing**
```pseudocode
1. Determine layer from file detection
2. If layer equals pattern:
   - Route to pattern collection (base + pattern suffix)
3. Else:
   - Route to implementation collection (base + impl suffix)
4. Execute ingest to determined collection
```

**Dual Collection Creation**
```pseudocode
1. Define implementation collection name (base + impl suffix)
2. Define pattern collection name (base + pattern suffix)
3. For each collection:
   - Check if collection exists in storage
   - If not exists or force recreation:
     - Create collection with vector configuration
     - Initialize with schema
4. Complete initialization
```

**Query Routing**
```pseudocode
1. Check query configuration for intent flags
2. If cross-context flag enabled:
   - Route to pattern collection
3. Else:
   - Route to implementation collection
4. Execute query on selected collection
```

## Patterns

### Dual Collection Storage Strategy
- **Pattern**: Physically separate collections for different content types with semantic overlap
- **When**: Need clean semantic spaces and want to prevent near-duplicate pollution
- **Approach**: Route at index time based on file naming convention, query routes based on intent
- **Benefit**: Each collection has clean semantic space, cross-collection queries possible

### File Convention Based Routing
- **Pattern**: Use file naming conventions to determine storage routing without metadata parsing
- **When**: Have different content types that follow consistent naming patterns
- **Approach**: Simple string matching on file paths at ingestion time
- **Benefit**: Fast, deterministic, no metadata dependency

## Audit

### Modified
- Ingestion system: Added file-based layer detection, changed to use base collection identifier, added collection routing logic
- Indexing system: Added dual collection creation during index operations
- Query system: Added routing based on intent flags to select appropriate collection
- Removed layer field from chunk metadata (collection name now encodes this information)

### Configuration
Collections automatically created as pairs during indexing. Routing determined by file naming convention at index time and by query flags at search time.
