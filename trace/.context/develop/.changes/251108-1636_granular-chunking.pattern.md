---
schema_version: "v3_adaptive"
type: "implementation.granular-chunking"
status: "completed"
keywords: "semantic-separation chunking metadata filtering multi-faceted-data indexed-storage query-time-refinement data-archaeology"
timestamp: "2025-11-08T16:36:00-0700"
session_id: "0f556f6f-115c-4d23-ab6c-f612c52c7fe6"
source_changelog: "251108-1636_granular-chunking.md"
---

# Granular Data Chunking

## Request
> Initial audit evolving into comprehensive observability assessment, revealing that distinct content types existed in persistent storage but weren't being indexed separately, causing "pollution" when searching across datasets.

## Overview
Implemented granular chunking for data archaeology - splitting records into separate vectors for distinct content types. Previously, searching records returned all components mixed together. Now each facet (primary content, extended analysis, supplementary data, structural changes) becomes its own top-level section and vector, enabling precise filtering at query time without pollution.

## Decisions

### Split at Structural Boundary Not Nested Level
- **Context**: Document parser chunks at primary boundary level by default
- **Solution**: Make each content type its own primary-level section instead of nested subsections
- **Rationale**: Creates separate vectors automatically without parser reconfiguration
- **Example**: Primary content section + Extended analysis section + Data usage section

### Query-Time Filtering Not Index-Time
- **Context**: User concerned about "pollution" - auxiliary data appearing in primary searches
- **Solution**: Index everything but filter during search with metadata tags
- **Alternatives**: Could have created separate storage collections per type, but adds operational complexity
- **Benefit**: Single index, flexible queries, no re-indexing needed

### Preserve Extended Analysis
- **Context**: Extended analysis exists in persistent storage but was ignored during indexing
- **Solution**: Extract and index analysis as separate chunks
- **Why**: Captures reasoning process, valuable for understanding decision patterns
- **Metadata**: Tagged with `chunk_type` attribute for filtering

## Implementation

### Architecture
1. Raw data parsing extracts content blocks → primary, analysis, auxiliary types identified
2. Formatter creates separate primary-level sections → each becomes distinct vector
3. Ingestion enriches metadata → chunk_type, classification tags applied
4. Search filters by metadata → users query specific content types
5. Results return targeted data → no pollution, clean separation

### Code Signatures

**Enhanced Content Extraction**
```
1. Iterate through content blocks from parsed data
2. Classify each block by type (primary, analysis, auxiliary)
3. Collect classified blocks into typed collections
4. Return structured map with type as key, items as values
```

**Granular Primary-Level Formatting**
```
1. For each record:
   a. Create primary-level section with record identifier
   b. Insert primary content
   c. Create separate section for extended analysis
   d. Insert auxiliary data sections
   e. Create section for structural changes
2. Ensure each section becomes independent document chunk
```

**Metadata Enrichment**
```
1. Parse document structure for section patterns
2. Detect content type from section markers:
   a. If contains "Analysis" keyword → assign analysis type
   b. If contains "Usage" keyword → assign auxiliary type
   c. If contains "Change" keyword → assign structural type
   d. Otherwise → assign primary type
3. Extract classification from pattern matching
4. Attach type metadata to chunk record
```

**Query Interface Enhancement**
```
1. Add filter options for content classification:
   a. Accept content-type parameter
   b. Accept role/actor parameter
   c. Accept sequence number parameter
2. During query construction:
   a. If content-type specified → add type filter to query
   b. If role specified → add role filter to query
3. Return filtered result set
```

## Patterns

### Component Separation Pattern
- **Pattern**: Split complex data into semantic components with distinct metadata
- **When**: Content has multiple facets that need independent querying
- **Approach**: Create separate primary-level sections, let parser chunk naturally, enrich with type metadata
- **Benefit**: Flexible filtering without complex parser configuration

### Metadata-Driven Filtering
- **Pattern**: Index everything, filter at query time using metadata tags
- **When**: Users need different views of the same underlying data
- **Approach**: Tag chunks during ingestion, expose filters in query interface
- **Anti-Pattern**: Don't create separate storage collections per type - adds operational complexity

## Audit

### Modified
- Content extraction layer - Extract analysis blocks and auxiliary data from content blocks
- Document formatting layer - Generate separate primary-level sections for record components
- Ingestion layer - Pattern matching to detect and tag content types
- Query interface layer - Add content-type and role filtering options

### Created
- End-to-end test script for chunking pipeline

### Configuration
Query examples:
```
# Just primary content
search dataset "search term" --chunk-type primary

# Just analysis reasoning
search dataset "search term" --chunk-type analysis

# Just auxiliary data
search dataset "search term" --chunk-type auxiliary

# Specific classification only
search dataset "search term" --role classification

# Everything (no filter)
search dataset "search term"
```
