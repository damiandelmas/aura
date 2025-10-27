# TRACE - Conversation Archaeology

TRACE provides conversation intelligence for Claude Code sessions. It searches `~/.claude/projects/` to find and query conversations using a semantic verb-noun command structure.

## Core Concept

TRACE is your source of truth for conversation data:
- **Global discovery**: Searches all projects in `~/.claude/projects/`
- **3-layer architecture**: Finder → Retrieval → Formatter
- **Chronicle timeline**: Chronologically merged messages + patches
- **Vector-ready output**: H2-section markdown for LlamaIndex chunking

## Quick Start

```bash
# Discover conversations
trace list
trace list --marker "authentication"

# Display to terminal
trace show chronicle <session-id>
trace show messages <session-id>
trace show patches <session-id>

# Export to file
trace export chronicle <session-id> -o context.md
```

## Discovery Commands

**List all conversations:**
```bash
trace list
# Shows session IDs sorted by modification time
```

**Filter by content:**
```bash
trace list --marker "architecture"
# Finds conversations containing keyword
```

**Limit results:**
```bash
trace list --limit 10
# Show first 10 results only
```

## Display Commands (Terminal Output)

All display commands use: `trace show <content-type> <session-id>`

**Chronicle (complete timeline):**
```bash
trace show chronicle <session-id>
# Chronologically merged messages + patches
# H2-numbered sections alternating between content types
```

**Messages only:**
```bash
trace show messages <session-id>
# User and assistant conversation text
# Filters out tool calls and system noise
```

**Code patches only:**
```bash
trace show patches <session-id>
# Structured diffs with timestamps
# Shows exact changes to files
```

**Session metadata:**
```bash
trace show metadata <session-id>
# Topic, duration, message count, working directory, timestamps
```

**File operations:**
```bash
trace show files <session-id>
# Deduplicated list of files created/edited/deleted
```

**Tool usage:**
```bash
trace show tools <session-id>
# Tool usage counts by type
```

## Export Commands (File Output)

All export commands use: `trace export <content-type> <session-id> [-o FILE]`

**Export chronicle:**
```bash
# Specify output file
trace export chronicle <session-id> -o context.md

# Auto-generate filename (<session-id>.md)
trace export chronicle <session-id>
```

**Export other content types:**
```bash
trace export messages <session-id> -o messages.md
trace export patches <session-id> -o patches.md
trace export metadata <session-id> -o metadata.json
```

**Export use cases:**
- Documentation generation
- Agent context preparation
- Conversation analysis
- Vector search indexing
- IMEM integration

## Chronicle Timeline Pattern

Chronicle merges messages and patches chronologically:

**Structure:**
```markdown
## 1. MESSAGE
**Role**: USER
Content here...

## 2. PATCH
**File**: src/auth.py
--- a/src/auth.py
+++ b/src/auth.py
...

## 3. MESSAGE
**Role**: ASSISTANT
Response here...
```

**Benefits:**
- Complete narrative arc
- H2-section chunking for vector search
- Each section becomes separate Qdrant vector
- Optimized for LlamaIndex MarkdownNodeParser

## Common Workflows

**Discover and view:**
```bash
# 1. Find sessions
trace list --marker "database"

# 2. View complete timeline
trace show chronicle <session-id>
```

**Export for documentation:**
```bash
# 1. Discover
trace list

# 2. Export with metadata
trace export chronicle <session-id> -o analysis.md
```

**Track code evolution:**
```bash
# What files changed
trace show files <session-id>

# Exact changes
trace show patches <session-id>
```

## Integration Points

**IMEM Vector Search:**
```python
from aura_trace.retrieval import ConversationRetrieval
from aura_trace.formatter import ConversationFormatter
from llama_index.node_parser import MarkdownNodeParser

# Load conversation
retrieval = ConversationRetrieval()
formatter = ConversationFormatter()
entries = retrieval.load_conversation(conv_file)
timeline = retrieval.get_timeline(entries)
metadata = retrieval.get_metadata(entries)

# Format as H2-section markdown
markdown = formatter.format(timeline, metadata['session_id'], metadata)

# Index (each H2 section → vector)
nodes = MarkdownNodeParser().get_nodes_from_documents([llama_doc])
```

**Programmatic Access:**
```python
from aura_trace.retrieval import ConversationRetrieval

retrieval = ConversationRetrieval()
entries = retrieval.load_conversation(conv_file)

# Get specific views
timeline = retrieval.get_timeline(entries, include_messages=True, include_patches=True)
messages = retrieval.get_messages(entries)
patches = retrieval.get_patches(entries)
metadata = retrieval.get_metadata(entries)
```

## Architecture Principles

**3-Layer Separation:**
- **Finder**: File discovery (I/O)
- **Retrieval**: JSONL parsing (data)
- **Formatter**: Markdown generation (presentation)

**One Format Philosophy:**
- Single H2-section markdown serves all consumers
- Terminal display, file export, AI agents, vector search
- Human-readable + machine-chunkable

**Lazy Loading:**
- List scans filenames only
- Parsing happens on-demand when queried
- Fast discovery across large histories

**Semantic Commands:**
- Verb-noun pattern: `show messages`, `export patches`
- Self-documenting for AI agents
- Extensible through new content types

## Tips & Tricks

**Session ID format:**
- Minimum 8 characters (partial matching supported)
- Full UUID: `a1acf43d-ed61-475b-b38d-942d33673efc`
- Get IDs: `trace list`

**Performance:**
- `list` is fast (filesystem scan)
- `list --marker` is slower (grep through files)
- Default limit: 20 results

**Project detection:**
- Auto-detects from current directory
- Searches `~/.claude/projects/{project-hash}/conversations/`
- Works from any subdirectory

## Error Handling

**"No conversations found":**
- Verify you're in project directory
- Run `trace list` to see available sessions
- Check `~/.claude/projects/` exists

**"Session not found":**
- Minimum 8 characters required
- Verify ID with `trace list`

**"Cannot export":**
- Check output path is writable
- Verify session ID is correct

## See Also

- `.context/document/architecture_trace-i2.md` - Full architecture
- `.context/document/architecture_imem-i2.md` - Vector search integration
- Installation: `cd trace && pip install -e .`
