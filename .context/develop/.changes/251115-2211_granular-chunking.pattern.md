---
schema_version: "v3_adaptive"
type: "implementation.granular-chunking"
status: "completed"
keywords: "document-indexing conversation-visibility granular-chunking metadata-filtering vector-search"
timestamp: "2025-11-15T22:11:00-0700"
session_id: "0f556f6f-115c-4d23-ab6c-f612c52c7fe6"
source_changelog: "251115-2211_granular-chunking.md"
---

# Granular Conversation Chunking

## Request
> "audit my shit. tell me whats good brother."

User requested comprehensive audit of conversation logging system against observability tools to understand what conversation data is being captured and what's missing.

## Overview

Audited conversation parsing capabilities against external observability platforms, identifying gaps in message visibility and chunking strategy. Implemented granular header-level separation of message components (text, extended reasoning, tools, patches) to enable precise filtering during vector search. Added metadata extraction for chunk type and role, plus query filters to retrieve specific conversation aspects without content pollution. This transforms the system from retrieving monolithic message chunks to supporting surgical queries like "show only tool usage" or "exclude reasoning blocks."

## Decisions

### Separate H2 Sections for Each Component
- **Context**: Original formatter placed all message content (text, reasoning, tools) under single H2 header
- **Problem**: Vector search returned everything together - no way to retrieve just conversation text without tool details
- **Solution**: Split each component into separate H2 sections that become independent vector chunks
- **Rationale**: Document parser splits at H2 boundaries, so H2 granularity = vector granularity
- **Benefit**: Can search for "what was discussed" (text only) vs "what tools were used" (tools only)

### Metadata-Based Filtering Over Structural Changes
- **Context**: Need to filter search results by chunk type and role
- **Solution**: Extract chunk_type and role during ingestion, add as search index payload metadata
- **Alternatives**: Could have used separate collections per chunk type (rejected - adds complexity)
- **Implementation**: Added metadata extraction during ingestion, exposed via query filters

### Keep Tools/Reasoning Visible by Default
- **Context**: User asked if tool visibility would "pollute" conversation results
- **Solution**: Made tool/reasoning visibility opt-in via query flags rather than hiding by default
- **Rationale**: Institutional memory use case values completeness - users can filter out noise when needed

## Implementation

### Architecture
1. Conversation data source → Retrieval extracts messages, tools, reasoning, patches
2. Formatter creates separate H2 sections for each component type
3. Document parser splits markdown at H2 boundaries → separate vectors
4. Ingestion extracts metadata (chunk_type, role) from section headers
5. Search interface accepts filters (--chunk-type, --role) to query specific components

### Code Signatures

**Granular Formatter**
```pseudocode
1. Process timeline data structure containing messages
2. For each message in timeline:
   a. Create H2 section header with message number and role identifier
   b. Append message text content
   c. If reasoning/extended thinking exists:
      - Create separate H2 section for reasoning
      - Append reasoning content
   d. If tools were used:
      - Create separate H2 section for tools
      - For each tool invocation:
         - Record tool name
         - Format and append input parameters
3. Return formatted markdown with H2-separated components
```

**Metadata Extraction**
```pseudocode
1. Receive document node from ingestion pipeline
2. Parse H2 section headers using pattern matching
3. For each header pattern identified:
   a. If matches "Message N: ROLE" pattern:
      - Extract role (USER or ASSISTANT)
      - Set chunk_type to 'message'
   b. If contains reasoning identifier:
      - Set chunk_type to 'reasoning'
   c. If contains tools identifier:
      - Set chunk_type to 'tools'
   d. If contains patch identifier:
      - Set chunk_type to 'patch'
4. Return metadata structure with extracted values
```

**Search Filters**
```pseudocode
1. Accept query string from user
2. Accept optional filter parameters:
   - chunk_type (message, reasoning, tools, patch)
   - role (user, assistant)
3. Build filter specification from provided parameters
4. Execute search with query and filter constraints
5. Return filtered results to user
```

## Patterns

### H2-Level Granularity for Vector Chunks
- **Pattern**: Structure documents so each independently useful concept is its own H2 section
- **Why**: Document parsers typically split at H2 boundaries, so H2 boundaries control vector chunk boundaries
- **When**: Any document destined for vector indexing where you want surgical retrieval
- **Benefit**: Prevents "kitchen sink" chunks that contain unrelated information

### Progressive Metadata Enrichment
- **Pattern**: Extract metadata from document structure during ingestion rather than requiring explicit declaration
- **Approach**: Parse section headers with pattern matching to infer chunk_type, role, sequence numbers
- **Occurrences**: Both conversation metadata (this work) and other document metadata (existing patterns)
- **Benefit**: Reduces manual metadata maintenance, structure IS the metadata

## Audit

### Modified
- Formatter module - Split message components into separate H2 sections for granular chunking
- Ingestion module - Added metadata extraction to identify chunk_type and role from headers
- Search CLI interface - Added chunk_type and role filter options to query command

### Created
- End-to-end integration test - Test script for granular chunking pipeline

### Configuration
No environment variables or deployment changes required. Backward compatible - existing indexed conversations will lack new metadata but remain searchable.
