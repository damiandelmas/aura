---
schema_version: "v3_adaptive"
type: "implementation.granular-chunking"
status: "completed"
keywords: "trace formatter imem chunking metadata filtering conversations tools thinking"
timestamp: "2025-11-08T16:36:00-0700"
session_id: "0f556f6f-115c-4d23-ab6c-f612c52c7fe6"
---

# Granular Conversation Chunking

## Request
> "audit my shit. tell me whats good brother."

Initial question about Claude Code observability tools evolved into comprehensive audit of TRACE implementation, revealing that tool usage and thinking data existed in JSONL but wasn't being indexed separately, causing "pollution" when searching conversations.

## Overview
Implemented granular chunking for conversation archaeology - splitting messages into separate vectors for text, thinking, and tools. Previously, searching conversations returned everything mixed together. Now each component (message text, extended thinking, tool usage, code patches) becomes its own top-level section and vector, enabling precise filtering at query time without pollution.

## Decisions

### Split at H2 Not H3
- **Context**: MarkdownNodeParser chunks at H2 boundaries by default
- **Solution**: Make each component type its own H2 section instead of H3 subsections
- **Rationale**: Creates separate vectors automatically without parser reconfiguration
- **Example**: `## Message 2: ASSISTANT` + `## Message 2 Extended Thinking` + `## Message 2 Tools`

### Query-Time Filtering Not Index-Time
- **Context**: User concerned about "pollution" - tool data appearing in narrative searches
- **Solution**: Index everything but filter during search with metadata
- **Alternatives**: Could have created separate collections per type, but adds complexity
- **Benefit**: Single index, flexible queries, no re-indexing needed

### Preserve Thinking Blocks
- **Context**: Extended thinking exists in JSONL but was ignored
- **Solution**: Extract and index thinking as separate chunks
- **Why**: Captures Claude's reasoning process, valuable for understanding decision patterns
- **Metadata**: Tagged as `chunk_type: 'thinking'` for filtering

## Implementation

### Architecture
1. JSONL parsing extracts content blocks → text, thinking, tools identified
2. Formatter creates separate H2 sections → each becomes distinct vector
3. Ingest enriches metadata → chunk_type, role, message_num tagged
4. Search filters by metadata → users query specific component types
5. Results return targeted data → no pollution, clean separation

### Code Signatures

**Enhanced Content Extraction** (`trace/src/aura_trace/retrieval.py`)
```python
# Separate content blocks by type
for block in content_blocks:
    if block['type'] == 'thinking':
        thinking_blocks.append(block.get('thinking'))
    elif block['type'] == 'tool_use':
        tool_uses.append(block)

return {'text': text_parts, 'thinking': thinking_blocks, 'tools': tool_uses}
```

**Granular H2 Formatting** (`trace/src/aura_trace/formatter.py`)
```markdown
## Message {n}: {ROLE}
{message_text}

## Message {n} Extended Thinking
{thinking_blocks}

## Message {n} Tools
{tool_usage_details}

## Code Patch {n}
{diff_content}
```

**Metadata Enrichment** (`imem/src/imem/ingest.py`)
```python
# Pattern matching for chunk types
if 'Extended Thinking' in header:
    metadata['chunk_type'] = 'thinking'
elif 'Tools' in header:
    metadata['chunk_type'] = 'tools'
elif 'Code Patch' in header:
    metadata['chunk_type'] = 'patch'
elif match := re.match(r'Message \d+: (USER|ASSISTANT)', header):
    metadata['chunk_type'] = 'message'
    metadata['role'] = match.group(1).lower()
```

**CLI Filtering** (`imem/src/imem/cli.py`)
```bash
# New search options
--chunk-type {message|thinking|tools|patch}
--role {user|assistant}

# Filter construction
if chunk_type:
    filters['chunk_type'] = chunk_type
if role:
    filters['role'] = role
```

## Patterns

### Component Separation Pattern
- **Pattern**: Split complex data into semantic components with distinct metadata
- **When**: Content has multiple facets that need independent querying
- **Approach**: Create separate H2 sections, let parser chunk naturally, enrich with type metadata
- **Benefit**: Flexible filtering without complex parser configuration

### Metadata-Driven Filtering
- **Pattern**: Index everything, filter at query time using metadata tags
- **When**: Users need different views of the same underlying data
- **Approach**: Tag chunks during ingestion, expose filters in CLI
- **Anti-Pattern**: Don't create separate indexes/collections per type - adds operational complexity

## Audit

### Modified
- `trace/src/aura_trace/retrieval.py` - Extract thinking blocks and tool usage from content blocks
- `trace/src/aura_trace/formatter.py` - Generate separate H2 sections for message components
- `imem/src/imem/ingest.py` - Pattern matching to detect and tag chunk types
- `imem/src/imem/cli.py` - Add --chunk-type and --role filtering options

### Created
- `test_granular_flow.sh` - End-to-end test script for chunking pipeline

### Configuration
Query examples:
```bash
# Just conversation text
imem search conversations "create files" --chunk-type message

# Just reasoning
imem search conversations "architecture" --chunk-type thinking

# Just tool usage
imem search conversations "Write" --chunk-type tools

# Assistant messages only
imem search conversations "implementation" --role assistant

# Everything (no filter)
imem search conversations "context"
```
