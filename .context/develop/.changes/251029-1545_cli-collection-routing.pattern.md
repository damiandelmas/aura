---
schema_version: "v3_adaptive"
type: "refactor.cli-collection-routing"
status: "completed"
keywords: "collection-management registry routing lifecycle storage-separation semantic-naming command-interface"
timestamp: "2025-10-29T15:45:00-0700"
session_id: "41f29cf9-c556-4940-a27a-e672fccd82c8"
source_changelog: "251029-1545_cli-collection-routing.md"
---

# Collection Routing & Lifecycle Management Refactor

## Request
> Review implementation plan for unified interface supporting dual collections with content-type based routing

## Overview
Refactored the command interface and registry to support separate collections for distinct content types. Changed from monolithic single collection to dual collections with routing logic that directs queries to the appropriate collection based on content source. Simplified interface from hierarchical command groups to unified pattern with source as a first-class positional argument. Added collection lifecycle management capabilities for visibility and cleanup. Updated metadata terminology for semantic clarity.

## Decisions

### Dual Collection Architecture
- **Problem**: Single collection couldn't efficiently separate different content types
- **Solution**: Multiple collections per project, one per content type
- **Rationale**: Different content structures require different query patterns and metadata
- **Impact**: Storage schema change requires backward compatibility strategy

### Collection Naming Convention
- **Problem**: Need to distinguish collection types in persistent storage
- **Solution**: Append type descriptors to hash-based names
- **Benefit**: Collection purpose becomes self-documenting in storage layer
- **Implementation**: Type suffix appended to base identifier

### CLI Interface Pattern
- **Problem**: Users found explicit flags verbose and unintuitive
- **Solution**: Source becomes positional argument, not option flag
- **Rationale**: Matches established patterns in similar tools, reduces verbosity, more natural
- **Trade-offs**: Slightly less explicit but significantly better user experience

### Metadata Terminology Change
- **Problem**: Legacy terminology conflicted with similar domain concepts
- **Solution**: Rename metadata field to more specific semantic term
- **Benefit**: Clearer meaning in institutional memory context
- **Scope**: Applied consistently across all metadata references

### Automatic Collection Creation
- **Problem**: Users encountered confusing errors when collection didn't exist
- **Solution**: Auto-create collections on first operation requiring the collection
- **Alternatives Considered**: Require explicit creation flag - rejected for poor UX
- **Behavior Shift**: Force flag now means "recreate from scratch" not "create if missing"

### Collection Type Routing
- **Problem**: Multi-collection system needs intelligent routing
- **Solution**: Route queries based on content source to appropriate collection
- **Default Behavior**: When source is ambiguous, route to primary collection type
- **Future Extensibility**: Marker added for potential expansion to new collection types

## Implementation

### Architecture
1. Registry tracks multiple collections per project → Returns structured collection mapping
2. CLI helpers determine collection type from source → Call central routing function
3. Collection auto-created if missing → No user intervention needed
4. Query operations route to correct collection → Based on source filter

### Conceptual Flow

**Collection Registration Process:**
1. Accept project identifier
2. Generate unique hash suffix from project key
3. Create collection name mappings for each content type
4. Store collection names and initialize metadata (document counts per type)
5. Return collection mapping to registry

**Collection Routing Process:**
1. Receive source specification from CLI
2. Map source to collection type
3. Query registry for collection name
4. Return appropriate collection reference

**Backward Compatibility Process:**
1. Attempt to read collection from new schema format
2. If not found, check legacy schema format
3. For legacy single collection, map appropriately based on type request
4. Return mapped collection

**Auto-Creation Pattern:**
1. Check if collection exists in storage
2. If force flag set and exists → delete collection
3. If not exists → create new collection with appropriate configuration
4. Continue with operation

**Collection Lifecycle Discovery Process:**
1. Query storage for all collections matching system prefix
2. Retrieve all registered projects from registry
3. Compute set of expected collections from all projects
4. Compare actual vs expected to identify orphaned collections
5. Display results to user

### Code Conceptualization

**Collection Registry Structure:**
```
Project registration creates:
  ├── Multiple collection names (one per content type)
  ├── Per-collection metadata
  └── Document counts per type

Backward compatible with:
  └── Single collection references from previous version
```

**Routing Logic:**
```
Input: Source identifier
Process:
  1. Map source to content type
  2. Query registry for collection name
  3. Return collection identifier
Output: Collection reference
```

**Unified Command Interface:**
```
Command structure:
  operation <source> [arguments]

Where source:
  - Specifies content type
  - Drives collection routing
  - Applies appropriate filters
  - Determines metadata context
```

**Auto-Creation Workflow:**
```
For each operation:
  1. Check collection existence
  2. Handle force flag (delete if exists)
  3. Create if needed
  4. Return collection or error
```

## Constraints

### API Mismatch: Collection Finder Returns Minimal Data
- **What**: Content discovery mechanism returns file paths only, not full metadata
- **Discovery**: During collection indexing implementation
- **Workaround**: Extract identifiers from filenames, use data retrieval and formatting mechanisms
- **Impact**: Requires intermediate data transformation step

### API Design: Ingestion Expects Single Items
- **What**: Ingestion mechanism processes individual items, not bulk collections
- **Discovery**: Expected batch method didn't exist
- **Workaround**: Explicitly iterate over collection, process each item
- **Why Non-Obvious**: Existing code hid this iteration inside abstraction layers

### Storage Layer: Deferred Collection Error
- **What**: Storage operations fail with not-found errors even after apparent success
- **Discovery**: User received success message but batch operation failed
- **Workaround**: Create collection before attempting any write operations
- **Impact**: Improves user experience, eliminates confusing error states

## Patterns

### Progressive Resource Creation
- **Pattern**: Existence check → conditional creation → conditional recreation
- **When**: Any operation requiring a persistent resource
- **Approach**: Single validation phase handles all cases
- **Benefit**: Operations never encounter missing-resource errors, smooth first-run

### Type-Based Routing
- **Pattern**: Map source to type, retrieve destination from registry, route accordingly
- **When**: Any multi-destination operation
- **Approach**: Centralized routing logic, CLI just specifies type
- **Benefit**: Single source of truth, easy to extend with new types

### Schema Evolution with Compatibility
- **Pattern**: Try new format, gracefully fall back to old format on miss
- **When**: Reading versioned data structures
- **Approach**: Attempt new schema first, fall back to legacy conversion
- **Benefit**: Existing data continues working during migration period

### First-Class Concept Elevation
- **Pattern**: Promote frequently-used parameter from option to positional argument
- **When**: Parameter is always required and high-frequency
- **Approach**: Move from flag to positional position
- **Benefit**: Reduced verbosity, more intuitive command sequences

## Audit

### Architectural Changes
- Registry changed from single collection reference to collection type mapping
- Document count tracking changed from scalar to per-type structure
- Collection routing introduces new decision point in query path

### Interface Changes
- Command structure simplified from hierarchical to unified source-driven pattern
- New collection lifecycle management operations
- Metadata terminology updated for semantic consistency

### New Concepts Introduced
- Collection auto-creation on first use
- Force flag semantic shift to deletion/recreation
- Collection lifecycle visibility

### Behavioral Shifts
- Collections created automatically (no manual setup needed)
- Force flag behavior changed (from creation-if-missing to full recreation)
- Registry returns structured collection mapping instead of single identifier
