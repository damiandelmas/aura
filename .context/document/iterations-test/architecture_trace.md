---
schema_version: "v3_adaptive"
type: "architecture.trace"
status: "stable"
keywords: "trace conversations jsonl archaeology parsing chronicle"
timestamp: "2025-10-24T15:40:00-0700"
---

# TRACE Architecture

## Purpose

TRACE is a conversation archaeology tool that parses Claude Code conversation JSONL files and provides structured queries for both humans and AI agents. It enables retrieving conversation context, code changes, tool usage, and chronological timelines.

**Path**: `trace/src/aura_trace/`
**Lines**: ~900 lines (cleaned from 1,242)
**CLI**: `trace`
**Architecture**: 3-layer (finder → retrieval → formatter)

---

## Core Capabilities

### 1. Global Session Discovery
```bash
trace list                    # All conversations across projects
trace list --marker "keyword" # Filter by content
trace list --limit 10         # Limit results
```

Scans `~/.claude/projects/*/conversations/*.jsonl` globally, sorts by modification time.

### 2. Structured Queries (Subcommands)
```bash
trace show metadata <session-id>   # Session info (timing, counts)
trace show messages <session-id>   # Just user/assistant messages
trace show patches <session-id>    # Just code changes
trace show chronicle <session-id>  # Complete timeline
trace show files <session-id>      # File operations
trace show tools <session-id>      # Tool usage counts
```

### 3. Export to File
```bash
trace export chronicle <session-id> -o context.md
trace export messages <session-id>
trace export patches <session-id>
trace export metadata <session-id>  # JSON format
```

Exports structured markdown with H2 sections for LlamaIndex chunking.

---

## Components

### `finder.py` - Session Discovery
**Purpose**: Find conversation JSONL files globally

**Key Methods**:
```python
list_all() -> List[Path]
find_by_session_id(id: str) -> Path
find_by_marker(keyword: str) -> List[Path]
```

**Features**:
- Scans all projects in `~/.claude/projects/`
- Supports partial session ID matching (min 8 chars)
- Sorts by modification time (newest first)

### `retrieval.py` - JSONL Parsing
**Purpose**: Parse conversation files and extract structured data

**Key Methods**:
```python
load_conversation(path: Path) -> List[Dict]
get_timeline(entries, include_messages=True, include_patches=True) -> List[Dict]
get_messages(entries) -> List[Dict]
get_patches(entries) -> List[Dict]
get_metadata(entries) -> Dict
get_file_operations(entries) -> List[Dict]
get_tool_usage(entries) -> List[Dict]
```

**Data Extraction**:
- Timeline (chronologically merged messages + patches)
- Messages (user + assistant text)
- Patches (code diffs with timestamps)
- Metadata (timing, counts, working directory)
- File operations (deduplicated)
- Tool usage (counts by tool type)

### `formatter.py` - Markdown Generation
**Purpose**: Convert Python data structures to markdown

**Key Methods**:
```python
format(timeline, session_id, metadata) -> str           # Timeline markdown
format_messages(messages) -> str                        # Messages only
format_patches(patches) -> str                          # Patches only
format_files(file_ops) -> str                           # File operations
format_tools(tool_usage) -> str                         # Tool usage
format_metadata(metadata) -> str                        # Metadata display
```

**ONE FORMAT FOR EVERYTHING**:
- Optimized for AI agents and LlamaIndex
- Creates H2 sections for each message/patch
- Numbered (Message 1, Message 2, Patch 1, etc.)
- Chronological order preserved

**Output Format**:
```markdown
# Conversation: abc123

**Duration:** 42min | **Messages:** 156

## Message 1: USER
How do we implement auth?

## Message 2: ASSISTANT
Here's the approach...

## Code Patch 1: auth/middleware.py
```diff
+ def verify_token(request):
```

## Message 3: USER
What about sessions?
```

### `cli.py` - Command Interface
**Purpose**: User-facing CLI with subcommand structure

**Subcommands**:
- `trace list` - Discovery
- `trace show [content] [session-id]` - Display to terminal
- `trace export [content] [session-id]` - Save to file

**Clean Data Flow**:
```python
# All commands follow same pattern:
entries = retrieval.load_conversation(path)
data = retrieval.get_X(entries)
output = formatter.format_X(data)
click.echo(output)
```

---

## Architecture

### 3-Layer Design

```
┌─────────────────────────────────────────┐
│              CLI (cli.py)               │
│         User Interface Layer            │
└────────────┬────────────────────────────┘
             │
             ├─> finder.py ──────> Find .jsonl files
             │
             ├─> retrieval.py ───> Parse → Python data
             │
             └─> formatter.py ───> Python data → Markdown
```

**Clean Separation of Concerns**:
- **Finder**: I/O (finding files)
- **Retrieval**: Parsing (JSONL → data)
- **Formatter**: Presentation (data → markdown)
- **CLI**: User interface (orchestrates all 3)

### Data Flow

**Discovery Flow**:
```
User: trace list
  ↓
finder.list_all() → List[Path]
  ↓
Display session IDs
```

**Query Flow**:
```
User: trace show chronicle <session-id>
  ↓
finder.find_by_session_id() → Path
  ↓
retrieval.load_conversation() → entries
  ↓
retrieval.get_timeline() → timeline
  ↓
formatter.format() → markdown
  ↓
Display to terminal
```

**Export Flow**:
```
User: trace export chronicle <session-id> -o file.md
  ↓
finder.find_by_session_id() → Path
  ↓
retrieval.load_conversation() → entries
  ↓
retrieval.get_timeline() → timeline
  ↓
retrieval.get_metadata() → metadata
  ↓
formatter.format(timeline, session_id, metadata) → markdown
  ↓
Write to file
```

---

## Chronicle Timeline Pattern

**Problem**: Agents need chronological story, not separate data streams.

**Solution**: Interleave messages and patches by timestamp.

**Implementation** (`retrieval.get_timeline()`):
```python
def get_timeline(entries, include_messages=True, include_patches=True):
    timeline = []

    if include_messages:
        for msg in get_messages(entries):
            timeline.append({
                'type': 'message',
                'timestamp': msg.get('_timestamp'),
                'role': msg.get('role'),
                'text': extract_text(msg)
            })

    if include_patches:
        for patch in get_patches(entries):
            timeline.append({
                'type': 'patch',
                'timestamp': patch.get('timestamp'),
                'file': patch.get('file'),
                'diff_lines': patch.get('diff_lines')
            })

    # Sort chronologically
    timeline.sort(key=lambda x: x['timestamp'] or '')
    return timeline
```

**Output**:
```
## Message 1: USER
"How do we implement auth?"

## Message 2: ASSISTANT
"Here's the approach..."

## Code Patch 1: auth/middleware.py
```diff
+ def verify_token(request):
```

## Message 3: USER
"What about sessions?"
```

---

## Integration with IMEM

### IMEM Indexing Pipeline

```
IMEM CLI
  ↓
retrieval.load_conversation() + get_timeline()  ← Get chronological data
  ↓
formatter.format(timeline, session_id, metadata)  ← H2-section markdown
  ↓
LlamaIndex MarkdownNodeParser  ← Chunk by H2
  ↓
Qdrant (institutional_memory)  ← Vector search
```

**IMEM Code** (simplified):
```python
from aura_trace.retrieval import ConversationRetrieval
from aura_trace.formatter import ConversationFormatter

# Load conversation
retrieval = ConversationRetrieval()
entries = retrieval.load_conversation(conv_file)

# Get timeline (messages + patches chronologically)
timeline = retrieval.get_timeline(
    entries,
    include_messages=True,
    include_patches=True,
    include_files=False,
    include_tools=False
)

# Get metadata
metadata = retrieval.get_metadata(entries)

# Format as LlamaIndex-ready markdown
formatter = ConversationFormatter()
markdown = formatter.format(timeline, metadata['session_id'], metadata)

# Index with LlamaIndex
llama_doc = LlamaDocument(text=markdown)
nodes = MarkdownNodeParser().get_nodes_from_documents([llama_doc])
# Each H2 section → separate Qdrant vector
```

**Why H2 Sections**:
- LlamaIndex MarkdownNodeParser chunks at H2 level
- Each section = 1 vector in Qdrant
- Search "code changes" returns just patch sections
- Search "user questions" returns just user message sections

---

## Subcommand Structure (Verb-Noun Pattern)

**Design Philosophy**: Optimized for AI agents with clear verb-noun structure.

**Commands**:
```bash
trace list                      # Discovery
trace show [content] [id]       # Display
trace export [content] [id]     # Save
```

**Benefits for AI Agents**:
- Semantic clarity: `show messages` maps to intent
- Self-documenting: action is explicit
- Extensible: new content types = just add noun

**Example Usage**:
```bash
# List conversations
trace list --marker "authentication"

# Show specific content
trace show messages abc123
trace show patches abc123
trace show chronicle abc123

# Export to file
trace export chronicle abc123 -o context.md
trace export messages abc123    # Auto-generates filename
```

---

## Performance

- **List conversations**: <1ms (filesystem scan)
- **Parse conversation**: ~10-50ms per session (JSONL parsing)
- **Session lookup**: <1ms (partial ID matching)
- **Export markdown**: ~50-100ms (parsing + formatting)

**Optimization**: Lazy loading - only parses when queried, not during listing.

---

## Code Quality

### 1. Clean Architecture
- **3 layers**: Finder → Retrieval → Formatter
- **Single responsibility**: Each module does ONE thing
- **No duplication**: All formatting in formatter.py

### 2. Type Safety
```python
from typing import List, Dict, Any

def get_timeline(
    entries: List[Dict],
    include_messages: bool = True,
    include_patches: bool = True
) -> List[Dict[str, Any]]:
```

### 3. Comprehensive Docstrings
```python
def format(self, timeline: List[Dict[str, Any]],
          session_id: str = None,
          metadata: Dict[str, Any] = None) -> str:
    """Format timeline as chronological markdown

    Args:
        timeline: Chronological list of events from get_timeline()
        session_id: Session identifier (optional)
        metadata: Conversation metadata (optional)

    Returns:
        Markdown string with numbered H2 sections
    """
```

---

## Recent Changes (2025-10-24)

### Cleanup: Removed query.py

**Before** (4 layers):
```
CLI → Finder → Retrieval → Query → Formatter → Output
```

**After** (3 layers):
```
CLI → Finder → Retrieval → Formatter → Output
```

**What Changed**:
- ❌ Deleted `query.py` (redundant wrapper layer)
- ✅ Added formatter methods: `format_messages()`, `format_patches()`, `format_files()`, `format_tools()`
- ✅ Updated IMEM to call retrieval + formatter directly
- ✅ CLI uses formatter methods instead of inline formatting

**Impact**:
- ~400 lines removed
- Cleaner architecture
- No breaking changes
- Same output format

---

## Related Documentation

- **Ecosystem Overview**: [architecture_aura.md](./architecture_aura.md)
- **Vector Search**: [architecture_imem.md](./architecture_imem.md)
