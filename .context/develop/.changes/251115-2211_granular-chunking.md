---
schema_version: "v3_adaptive"
type: "implementation.granular-chunking"
status: "completed"
keywords: "trace formatter conversation-visibility granular-chunking metadata-filtering imem-search"
timestamp: "2025-11-15T22:11:00-0700"
session_id: "0f556f6f-115c-4d23-ab6c-f612c52c7fe6"
---

# Granular Conversation Chunking

## Request
> "audit my shit. tell me whats good brother."

User requested comprehensive audit of TRACE implementation against Claude Code observability tools to understand what conversation data is being captured and what's missing.

## Overview

Audited conversation parsing capabilities against external observability platforms, identifying gaps in tool visibility and message chunking strategy. Implemented granular header-level separation of message components (text, thinking, tools, patches) to enable precise filtering during vector search. Added metadata extraction for chunk type and role, plus CLI filters to query specific conversation aspects without content pollution. This transforms the system from retrieving monolithic message chunks to supporting surgical queries like "show only tool usage" or "exclude thinking blocks."

## Decisions

### Separate H2 Sections for Each Component
- **Context**: Original formatter placed all message content (text, thinking, tools) under single H2 header
- **Problem**: Vector search returned everything together - no way to retrieve just conversation text without tool details
- **Solution**: Split each component into separate H2 sections that become independent vector chunks
- **Rationale**: Document parser splits at H2 boundaries, so H2 granularity = vector granularity
- **Benefit**: Can search for "what was discussed" (text only) vs "what tools were used" (tools only)

### Metadata-Based Filtering Over Structural Changes
- **Context**: Need to filter search results by chunk type and role
- **Solution**: Extract chunk_type and role during ingestion, add as Qdrant payload metadata
- **Alternatives**: Could have used separate collections per chunk type (rejected - adds complexity)
- **Implementation**: Added metadata extraction in `_parse_conversation_metadata()`, exposed via CLI filters

### Keep Tools/Thinking Visible by Default
- **Context**: User asked if tool visibility would "pollute" conversation results
- **Solution**: Made tool/thinking visibility opt-in via CLI flags rather than hiding by default
- **Rationale**: Institutional memory use case values completeness - users can filter out noise when needed

## Implementation

### Architecture
1. Conversation file → Retrieval extracts messages, tools, thinking, patches
2. Formatter creates separate H2 sections for each component type
3. Document parser splits markdown at H2 boundaries → separate vectors
4. Ingestion extracts metadata (chunk_type, role) from section headers
5. CLI search accepts filters (--chunk-type, --role) to query specific components

### Code Signatures

**Granular Formatter** (`trace/src/aura_trace/formatter.py`)
```python
# Split message components into separate H2 sections
def format_timeline(timeline, session_id=None):
    # Main message text
    md.append(f"## Message {num}: {role}\n")
    md.append(f"{text}\n\n")

    # Thinking as separate H2
    if thinking:
        md.append(f"## Message {num} Extended Thinking\n")
        md.append(f"{thinking}\n\n")

    # Tools as separate H2
    if tools:
        md.append(f"## Message {num} Tools\n")
        for tool in tools:
            md.append(f"**{tool['name']}**\n")
            # Format inputs...
```

**Metadata Extraction** (`imem/src/imem/ingest.py`)
```python
def parse_conversation_section(self, section_name: str) -> dict:
    """Extract chunk_type and role from H2 headers"""
    metadata = {}

    # Pattern: "Message 4: ASSISTANT"
    if section_name.startswith('Message'):
        metadata['chunk_type'] = 'message'
        if 'USER' in section_name:
            metadata['role'] = 'user'
        elif 'ASSISTANT' in section_name:
            metadata['role'] = 'assistant'

    # Pattern: "Code Patch 1: src/cli.py"
    elif section_name.startswith('Code Patch'):
        metadata['chunk_type'] = 'patch'
        match = re.match(r'Code Patch \d+:\s*(.+)', section_name)
        if match:
            metadata['file_path'] = match.group(1).strip()

    return metadata
```

**CLI Filters** (`imem/src/imem/cli.py`)
```python
@click.option('--chunk-type',
              type=click.Choice(['message', 'thinking', 'tools', 'patch']),
              help='Filter by chunk type (conversations only)')
@click.option('--role',
              type=click.Choice(['user', 'assistant']),
              help='Filter by role (conversations only)')
def search(source, query, ..., chunk_type, role, ...):
    filters = {}
    if chunk_type:
        filters['chunk_type'] = chunk_type
    if role:
        filters['role'] = role

    results = searcher.search(query, filters=filters)
```

## Patterns

### H2-Level Granularity for Vector Chunks
- **Pattern**: Structure markdown so each independently useful concept is its own H2 section
- **Why**: Document parsers typically split at H2, so H2 boundaries control vector chunk boundaries
- **When**: Any markdown destined for vector indexing where you want surgical retrieval
- **Benefit**: Prevents "kitchen sink" chunks that contain unrelated information

### Progressive Metadata Enrichment
- **Pattern**: Extract metadata from document structure during ingestion rather than requiring explicit frontmatter
- **Approach**: Parse H2 headers with regex to infer chunk_type, role, message numbers
- **Occurrences**: Both conversation metadata (this work) and changelog metadata (existing)
- **Benefit**: Reduces manual metadata maintenance, structure IS the metadata

## Audit

### Modified
- `trace/src/aura_trace/formatter.py` - Split message components into separate H2 sections for granular chunking
- `imem/src/imem/ingest.py` - Added `parse_conversation_section()` to extract chunk_type and role from headers
- `imem/src/imem/cli.py` - Added --chunk-type and --role filter options to search command

### Created
- `test_granular_flow.sh` - End-to-end test script for granular chunking pipeline

### Configuration
No environment variables or deployment changes required. Backward compatible - existing indexed conversations will lack new metadata but remain searchable.
