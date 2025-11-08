# TRACE - Conversation Archaeology

**For AI agents.** Find, export, and analyze Claude Code conversations.

## Overview

TRACE searches `~/.claude/projects/` for conversation intelligence:

**What it does:**
- Find sessions by content/keyword
- Export chronicles for agent handoff
- Track code evolution across sessions
- Format conversations for vector search

**Architecture:**
- 3-layer: Finder → Retrieval → Formatter
- Chronicle format: H2-section markdown (LlamaIndex-ready)
- Lazy loading: Fast discovery, parse on-demand

**Use cases:**
- Agent handoff (export context for next Claude)
- Find past conversations ("what session had X?")
- Review code changes from sessions
- IMEM vector search integration

## Workflows

**When you need to find a session:**
1. User shows conversation snippet
2. Extract unique phrase (2-4 words)
3. Use: `trace list --marker "unique phrase"`
4. Returns session ID

**When you need to load past session as context:**
1. Find session ID (if needed)
2. Use: `trace show chronicle <id>` or `/trace-show <id>`
3. Chronicle outputs to stdout → Claude reads → context loaded

**When you need to export for handoff:**
1. Find session ID (if needed)
2. Export chronicle: `trace export chronicle <id> -o context.md`
3. Chronicle contains complete timeline (messages + patches)

**When you need to review code changes:**
1. See what changed: `trace show files <id>`
2. See exact diffs: `trace show patches <id>`
3. Understand evolution from conversation to code

## Slash Commands

<!-- BUILD SOURCE: This section compiles to ~/.claude/commands/aura/trace/*.md -->

**trace-find** - Find session by conversation snippet
**Args:** <unique-text>
**Action:** Find TRACE Session
**Verb:** Search conversations for
```bash
trace list --marker "$ARGUMENTS"
```
**Examples:**
```
/trace-find "Extracted Brand Information"
/trace-find "simplified sys prompt"
```
**Tip:** Use 2-4 word unique phrases from assistant messages

**trace-show** - Load session context into current conversation
**Args:** <session-id>
**Action:** Load TRACE Context
**Verb:** Load session
```bash
trace show chronicle <session-id>
```
**Examples:**
```
/trace-show 0a535859
/trace-show dc3d19c9
```
**Tip:** Outputs chronicle to stdout - Claude reads and loads context immediately

**trace-export** - Export chronicle for agent handoff
**Args:** [session-id]
**Action:** Export TRACE Chronicle
**Verb:** Export session
```bash
trace list
trace export chronicle <session-id> -o context.md
```
**Examples:**
```
/trace-export
/trace-export 0a535859
```
**Tip:** Chronicle contains complete timeline (messages + patches), H2-section markdown for vector search

**trace-changes** - Review code evolution from session
**Args:** <session-id>
**Action:** Review TRACE Changes
**Verb:** Review code evolution for
```bash
trace show files <session-id>
trace show patches <session-id>
```
**Examples:**
```
/trace-changes 0a535859
/trace-changes dc3d19c9
```
**Tip:** Shows files modified + exact diffs with timestamps

## Reference

### Discovery Commands

**List sessions:**
```bash
trace list                      # All sessions (sorted by time)
trace list --marker "keyword"   # Filter by content
trace list --limit 10           # Limit results
```

**Session ID format:**
- Full UUID: `a1acf43d-ed61-475b-b38d-942d33673efc`
- Partial: Minimum 8 characters
- Get IDs: `trace list`

### Display Commands

Pattern: `trace show <content-type> <session-id>`

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

### Export Commands

Pattern: `trace export <content-type> <session-id> [-o FILE]`

**Export chronicle:**
```bash
trace export chronicle <session-id> -o context.md  # Specify output
trace export chronicle <session-id>                # Auto-named: <id>.md
```

**Export other content:**
```bash
trace export messages <session-id> -o messages.md
trace export patches <session-id> -o patches.md
trace export metadata <session-id> -o metadata.json
```

**Export use cases:**
- Agent context preparation
- Documentation generation
- Conversation analysis
- Vector search indexing
- IMEM integration

### Chronicle Format

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

### Integration

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

### Architecture

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

### Performance

- `list` is fast (filesystem scan)
- `list --marker` is slower (grep through files)
- Default limit: 20 results

### Project Detection

- Auto-detects from current directory
- Searches `~/.claude/projects/{project-hash}/conversations/`
- Works from any subdirectory

### Troubleshooting

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

### Installation

```bash
cd trace && pip install -e .
```

### See Also

- `.context/document/architecture_trace-i2.md` - Full architecture
- `.context/document/architecture_imem-i2.md` - Vector search integration
