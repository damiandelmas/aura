---
schema_version: "v3_adaptive"
type: "architecture.trace"
status: "stable"
keywords: "trace conversations jsonl archaeology parsing chronicle"
---

# TRACE Architecture

## Purpose

TRACE is a conversation archaeology tool that parses Claude Code conversation JSONL files and provides structured queries for both humans and AI agents. It enables retrieving conversation context, code changes, tool usage, and chronological timelines.

The system provides global session discovery across projects, structured data extraction from conversation files, and formatted output optimized for both terminal display and AI processing. It serves as the primary interface for accessing historical conversation data and integrates with vector search systems for institutional memory.

**Path**: `trace/src/aura_trace/`
**CLI**: `trace`
**Architecture**: 3-layer (finder → retrieval → formatter)

## Components

**Finder** (`finder.py`) - Locates conversation JSONL files globally by scanning `~/.claude/projects/*/conversations/` directories. Provides search by session ID (supports partial matching with minimum 8 characters), content markers (keyword filtering), and modification time sorting. Returns file paths sorted by recency.

Key methods:
- `list_all()` - Returns all conversation files across projects
- `find_by_session_id(id: str)` - Locates specific session by ID
- `find_by_marker(keyword: str)` - Filters conversations by content

**Retrieval** (`retrieval.py`) - Parses conversation JSONL files into structured data. Extracts messages, code patches, metadata, file operations, and tool usage. Provides unified chronological timeline by merging messages and patches by timestamp.

Key methods:
- `load_conversation(path: Path)` - Loads and parses JSONL file
- `get_timeline(entries)` - Chronologically merged messages and patches
- `get_messages(entries)` - User and assistant text messages
- `get_patches(entries)` - Code diffs with timestamps
- `get_metadata(entries)` - Session timing, counts, working directory
- `get_file_operations(entries)` - Deduplicated file operations
- `get_tool_usage(entries)` - Tool usage counts by type

**Formatter** (`formatter.py`) - Converts Python data structures to markdown with granular H2-level separation. Generates independent H2 sections for each message component (text, thinking, tools, patches) enabling surgical vector retrieval. Optimized for AI agents and LlamaIndex MarkdownNodeParser chunking.

Key methods:
- `format_timeline(timeline, session_id)` - Complete timeline markdown with granular H2 sections per component
- `format_messages(messages)` - Messages-only view
- `format_patches(patches)` - Code changes view
- `format_files(file_ops)` - File operations summary
- `format_tools(tool_usage)` - Tool usage statistics
- `format_metadata(metadata)` - Session metadata display

Granular formatting structure:
- Main message text → `## Message {num}: {role}`
- Extended thinking → `## Message {num} Extended Thinking`
- Tool usage → `## Message {num} Tools`
- Code patches → `## Code Patch {num}: {file_path}`

**CLI** (`cli.py`) - User-facing command interface with subcommand structure. Orchestrates finder, retrieval, and formatter components. Provides discovery, display, and export operations.

Subcommands:
- `trace list` - Discover conversations globally
- `trace show [content] [session-id]` - Display to terminal
- `trace export [content] [session-id]` - Save to file

## Data Flow

**Discovery Layer** - User invokes list command. Finder scans all project directories for conversation files. Returns session IDs sorted by modification time.

```
User: trace list
  ↓
finder.list_all() → List[Path]
  ↓
Display session IDs
```

**Query Layer** - User requests specific content type. Finder locates session file by ID. Retrieval loads and parses JSONL into structured data. Formatter generates markdown. Output flows to terminal or file.

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

**Export Layer** - User specifies output file. System follows query layer pattern. Formatter includes metadata header. Output writes to specified path.

```
User: trace export chronicle <session-id> -o file.md
  ↓
finder.find_by_session_id() → Path
  ↓
retrieval.load_conversation() → entries
  ↓
retrieval.get_timeline() → timeline
retrieval.get_metadata() → metadata
  ↓
formatter.format(timeline, session_id, metadata) → markdown
  ↓
Write to file
```

**Chronicle Timeline Pattern** - Interleaves messages and patches by timestamp to create chronological narrative with granular component separation. Retrieval extracts both data streams, tags with type and timestamp, merges and sorts chronologically.

```python
# Conceptual flow
messages = extract_messages(entries)  # tag with 'message' type
patches = extract_patches(entries)    # tag with 'patch' type
timeline = merge_and_sort([messages, patches], key='timestamp')
```

Output format creates separate H2 sections for each message component enabling vector search filtering:
- **Main message text** (`## Message {num}: {role}`) - User/assistant conversation content
- **Extended thinking** (`## Message {num} Extended Thinking`) - Internal reasoning blocks
- **Tool usage** (`## Message {num} Tools`) - Tool invocations and parameters
- **Code patches** (`## Code Patch {num}: {file_path}`) - Diffs with context

Granular H2-level separation enables surgical retrieval: query "what was discussed" returns only message text, query "what tools were used" returns only tool sections, query "code changes to auth.py" returns only relevant patches.

## Integration Points

**Filesystem Access** - Reads conversation files from `~/.claude/projects/*/conversations/*.jsonl` directories. Requires read permissions. No write operations to source data. Lazy loading ensures only queried files are parsed.

**IMEM Vector Search** - Provides markdown output optimized for LlamaIndex MarkdownNodeParser with granular H2-level component separation. Integration pipeline:
1. IMEM calls retrieval methods directly to load conversation data
2. Retrieval provides chronological timeline (messages + patches)
3. Formatter generates H2-section markdown with separate sections per component (text, thinking, tools, patches)
4. LlamaIndex chunks at H2 boundaries (each component becomes independent chunk)
5. Each section becomes separate vector in Qdrant with chunk_type metadata
6. IMEM ingestion extracts chunk_type and role from section headers via `parse_conversation_section()`
7. Metadata stored as Qdrant payload (chunk_type: message/thinking/tools/patch, role: user/assistant)

Granular chunking enables metadata-based filtering during vector search. CLI filters (`--chunk-type message`, `--role assistant`) query specific conversation aspects without content pollution. Surgical retrieval pattern: "show only tool usage" excludes message text and thinking blocks, "exclude thinking" returns only conversation and code.

**Command Framework** - Uses Click for command definition and argument parsing. Declarative decorators define command structure. Commands map to handler functions that orchestrate component interactions.

## Patterns & Principles

**3-Layer Separation of Concerns** - Finder handles I/O (file discovery). Retrieval handles parsing (JSONL to data). Formatter handles presentation (data to markdown). CLI orchestrates all three. Changes to one layer do not affect others. Each layer has single responsibility.

**Unified Data Source** - Timeline method provides complete chronological view. All other access patterns (messages-only, patches-only) filter this unified source. Ensures consistency across operations. Single parsing pass serves all query types.

**One Format Philosophy** - Single markdown format serves all consumers (terminal display, file export, AI agents, vector search). Avoids format proliferation. Granular H2-section structure enables both human readability and machine chunking with surgical filtering. Optimization benefits apply universally. Each component independently useful (message text, thinking, tools, patches) as separate H2 sections.

**Lazy Loading** - Conversations are parsed only when queried, not during listing. Discovery scans filenames only. Parsing happens on-demand. Enables fast listing across large conversation histories.

**Semantic Verb-Noun Commands** - Subcommand structure uses clear action-object pattern. `show messages` and `export patches` map directly to user intent. Self-documenting commands. Optimized for AI agent interpretation. Extensible through new content type nouns.

**H2-Level Granularity for Vector Chunks** - Markdown structure ensures each independently useful concept is its own H2 section. Document parsers split at H2 boundaries, so H2 structure controls vector chunk boundaries. Prevents "kitchen sink" chunks containing unrelated information (message text + tool details + patches). Enables precise filtering during retrieval without content pollution. Metadata extraction from H2 headers (chunk_type, role, message numbers) via regex parsing eliminates manual metadata maintenance where structure IS the metadata.

## Usage

**Installation**
```bash
cd /home/axp/projects/fleet/hangar/code/aura/main/trace
pip install -e .
```

**Discovery Commands**
```bash
# List all conversations
trace list

# Filter by content
trace list --marker "authentication"

# Limit results
trace list --limit 10
```

**Display Commands**
```bash
# Show complete timeline (messages + patches)
trace show chronicle <session-id>

# Show messages only
trace show messages <session-id>

# Show code patches only
trace show patches <session-id>

# Show session metadata
trace show metadata <session-id>

# Show file operations
trace show files <session-id>

# Show tool usage statistics
trace show tools <session-id>
```

**Export Commands**
```bash
# Export to specified file
trace export chronicle <session-id> -o context.md

# Auto-generate filename
trace export messages <session-id>
trace export patches <session-id>

# Export metadata (JSON format)
trace export metadata <session-id>
```

**Programmatic Access**
```python
from aura_trace.retrieval import ConversationRetrieval
from aura_trace.formatter import ConversationFormatter

# Initialize components
retrieval = ConversationRetrieval()
formatter = ConversationFormatter()

# Load conversation
entries = retrieval.load_conversation(conv_file)

# Get timeline (messages + patches chronologically)
timeline = retrieval.get_timeline(
    entries,
    include_messages=True,
    include_patches=True
)

# Get metadata
metadata = retrieval.get_metadata(entries)

# Format as markdown
markdown = formatter.format(timeline, metadata['session_id'], metadata)
```

**Integration Example**
```python
# IMEM indexing pipeline
from aura_trace.retrieval import ConversationRetrieval
from aura_trace.formatter import ConversationFormatter
from llama_index import Document as LlamaDocument
from llama_index.node_parser import MarkdownNodeParser

# Load and format conversation
retrieval = ConversationRetrieval()
formatter = ConversationFormatter()

entries = retrieval.load_conversation(conv_file)
timeline = retrieval.get_timeline(entries, include_messages=True, include_patches=True)
metadata = retrieval.get_metadata(entries)
markdown = formatter.format(timeline, metadata['session_id'], metadata)

# Index with LlamaIndex
llama_doc = LlamaDocument(text=markdown)
nodes = MarkdownNodeParser().get_nodes_from_documents([llama_doc])
# Each H2 section becomes separate Qdrant vector
```
