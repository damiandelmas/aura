---
schema_version: "v3_adaptive"
type: "architecture.trace"
status: "stable"
keywords: "trace conversation retrieval jsonl claude-code memory archaeology"
---

# TRACE Architecture

## Purpose

TRACE provides conversation archaeology for Claude Code sessions. The system parses JSONL conversation files stored by Claude Code, extracts structured data (messages, patches, tool usage, file operations), and presents this information through a CLI interface. TRACE enables AI agents and developers to retrieve conversation history, analyze code changes, and export formatted timelines for indexing or reference. The architecture separates discovery (finding conversations), retrieval (parsing JSONL), formatting (output generation), and command routing (CLI).

## Components

TRACE consists of four core components:

**ConversationFinder** (`finder.py`) - Filesystem-based conversation discovery service. Locates JSONL conversation files by scanning `~/.claude/projects/` directory structure. Provides search capabilities by session ID (full or partial match), content markers (keyword search), and date ranges (file modification time). Returns file paths sorted by modification time (newest first). Operates across all Claude projects, not limited to current working directory.

**ConversationRetrieval** (`retrieval.py`) - JSONL parsing and data extraction service. Loads conversation files line-by-line, parses JSON entries into `ConversationEntry` dataclasses. Extracts five data types: messages (user/assistant dialogue with metadata), patches (structured diffs from file edits), file operations (create/edit/delete actions), tool usage (tool invocations with inputs/results), and metadata (session info, timing, counts). Provides `get_timeline()` method as single source of truth, unifying all conversation events in chronological order. Supports filtering via `RetrievalOptions` (message limits, tool filters, content types).

**ConversationFormatter** (`formatter.py`) - Single-format output generator for all consumers. Transforms timeline data into chronological markdown with numbered H2 sections (Message 1, Message 2, Patch 1, etc.). Each H2 section becomes a LlamaIndex chunk, optimized for semantic search and AI agent consumption. Format serves four use cases: AI agents (primary), IMEM indexing, file exports, and terminal display. Provides specialized formatters for metadata, messages, patches, files, and tools while maintaining consistent markdown structure.

**CLI** (`cli.py`) - Command-line interface with three main commands. `trace list` displays available conversations with filtering by marker and limit. `trace show` displays conversation content to terminal (messages, patches, chronicle, metadata, files, tools). `trace export` saves content to files in markdown or JSON format. CLI orchestrates finder (discovery), retrieval (parsing), and formatter (output) components without implementing business logic.

Supporting elements:

**`__init__.py`** - Public API surface exposing `ConversationRetrieval`, `ConversationEntry`, `RetrievalOptions`, and `ConversationFinder` for programmatic use.

**`setup.py`** - Package configuration defining `aura-trace` as installable Python package with `trace` console script entry point.

## Data Flow

Conversation access follows a three-layer pipeline:

**Discovery Layer** - User invokes CLI command with session identifier or search criteria. `ConversationFinder` scans `~/.claude/projects/` filesystem to locate matching JSONL files. Returns `Path` objects pointing to conversation files. Supports three access patterns: session ID lookup (exact/partial), marker search (content grep), and list all (sorted by mtime).

**Retrieval Layer** - `ConversationRetrieval.load_conversation()` reads JSONL file line-by-line. Parses each JSON object into `ConversationEntry` dataclass capturing type, timestamp, session_id, uuid, parent_uuid, cwd, message, tool_use_result, thinking_metadata, and raw_data. Extraction methods (`get_messages()`, `get_patches()`, `get_file_operations()`, `get_tool_usage()`, `get_metadata()`) traverse entries and build structured datasets. `get_timeline()` merges all event types into single chronological list, serving as authoritative data source.

**Formatting Layer** - `ConversationFormatter.format()` receives timeline list and generates markdown output. Creates H2 sections for each event with sequential numbering. Messages become "## Message N: ROLE" with text content. Patches become "## Code Patch N: filepath" with diff blocks. Specialized formatters handle metadata (key-value display), files (operation list), and tools (usage counts). Output flows to terminal (click.echo) or files (Path.write_text).

**CLI Orchestration** - Click command handlers connect layers. `list` calls finder methods and displays results. `show` chains finder → retrieval → formatter → terminal. `export` chains finder → retrieval → formatter → file. Each command implements routing logic without duplicating parsing or formatting code.

**Data Structures** - `ConversationEntry` holds raw JSONL data. Timeline events use dicts with common fields (type, timestamp) plus event-specific fields (role/text for messages, file/diff_lines for patches). Retrieval methods return lists of dicts for maximum flexibility.

## Integration Points

**Filesystem Access** - Reads JSONL files from `~/.claude/projects/{project-hash}/` directories. Requires read permissions on user home directory. No write operations to Claude Code data. Respects filesystem ordering (sorts by mtime) and handles file-not-found gracefully.

**Claude Code JSONL Format** - Parses specific schema: each line contains JSON object with `type` (user/assistant/summary), `timestamp` (ISO 8601), `sessionId`, `uuid`, `parentUuid`, `cwd`, `message` (content array), `toolUseResult` (execution output including `structuredPatch` for diffs). Schema understanding embedded in `_parse_entry()` method. Handles missing fields and malformed JSON without crashing.

**Click CLI Framework** - Defines command groups, arguments, and options using decorators. Commands (`list`, `show`, `export`) map to Python functions. Click handles argument parsing, validation, and help text generation. Entry point registered in setup.py as `trace` console script.

**LlamaIndex Document Format** - Generates markdown compatible with LlamaIndex `SimpleDirectoryReader`. H2 sections (## Message N, ## Patch N) serve as natural chunk boundaries. Each chunk contains semantic unit (full message or full patch) for embedding and retrieval. Metadata header provides session context.

**IMEM Integration** - Exports chronicle format (messages + patches in chronological order) for memory system ingestion. `trace export chronicle <session>` produces markdown file ready for IMEM processing. Timeline structure preserves causal relationships and temporal ordering.

**Programmatic API** - Exports core classes via `__init__.py` for direct Python import. External tools can instantiate `ConversationRetrieval`, call `load_conversation()`, and access data via extraction methods. Bypasses CLI for library usage.

**Terminal Output** - Uses click.echo() for stdout writes. Supports color via click styling (emoji prefixes). Formats output for human readability with section headers, indentation, and summary statistics.

**File Export** - Writes markdown (.md) and JSON files to filesystem. Uses pathlib for cross-platform compatibility. Defaults to current directory with auto-generated filenames (`{session}-{content}.md`). Accepts custom output paths via `--output` flag.

## Patterns & Principles

**Single Responsibility Separation** - Each component handles one concern. Finder locates files. Retrieval parses JSONL. Formatter generates output. CLI routes commands. No component implements another component's logic. Changes to search logic affect only finder. Changes to output format affect only formatter.

**Timeline as Source of Truth** - `get_timeline()` method unifies all conversation data in chronological order. All other access patterns (show messages, show patches, export chronicle) filter this timeline. Eliminates duplicate extraction logic. Ensures consistent ordering across outputs. Single method to maintain for chronological correctness.

**One Format Philosophy** - Single markdown format serves all consumers (AI agents, IMEM, terminal, files). Rejects format proliferation (no separate JSON format, CSV format, etc.). H2 sectioning works for both LlamaIndex chunking and human reading. Simplifies maintenance and testing. Format optimization benefits all users simultaneously.

**Dataclass-Based Parsing** - `ConversationEntry` dataclass provides typed structure for JSONL data. Optional fields handle schema variations gracefully. `raw_data` field preserves complete JSON for debugging. Type hints enable IDE support and static analysis. Dataclasses generate `__init__`, `__repr__` automatically.

**Filesystem as Database** - Treats `~/.claude/projects/` as read-only data store. No caching layer. No index files. Direct filesystem traversal on each query. Relies on OS filesystem performance. Sorting by mtime uses filesystem metadata. Simplicity over premature optimization.

**Verb-Noun CLI Structure** - Commands follow `trace <verb> <noun>` pattern: `trace list`, `trace show messages`, `trace export chronicle`. Clear action-object relationship. AI agents parse structure easily. Help text generated from command/argument names.

**Global Search with Local Fallback** - `find_by_session_id()` searches current project first, then expands to all projects if not found. Balances common case (local sessions) with convenience (finding any session). Logging messages indicate search scope changes.

**Structured Patch Extraction** - Extracts `structuredPatch` arrays from tool results. Captures old_start, old_lines, new_start, new_lines, and diff lines. Preserves unified diff format in timeline. Enables reconstruction of file history and change analysis.

**Defensive Parsing** - Wraps JSON parsing in try-except blocks. Logs warnings for malformed entries but continues processing. Returns empty lists rather than raising exceptions. Handles missing timestamps, null fields, and unexpected types. Robustness over strictness.

**Minimal Dependencies** - Requires only `click>=8.0.0` for CLI framework. Uses Python standard library (json, pathlib, datetime, logging, dataclasses) for all other functionality. No external parsing libraries. No database dependencies. Reduces installation complexity and compatibility issues.

**Entry Point Convenience** - Exports both low-level API (`ConversationRetrieval`, `ConversationFinder`) and high-level convenience functions (`get_conversation_data()`, `get_recent_messages()`). Library users choose appropriate abstraction level. CLI and library share implementation without duplication.

## Usage

**Installation**

Install as editable package from repository root:

```bash
cd /path/to/aura/trace
pip install -e .
```

Registers `trace` command in shell. Verify with `trace --help`.

**Discovery Commands**

List all conversations (newest first):

```bash
trace list
trace list --limit 10
```

Find conversations by content marker:

```bash
trace list --marker "architecture"
trace list --marker "refactor"
```

**Display Commands**

Show conversation content to terminal:

```bash
trace show messages <session-id>    # Text messages only
trace show patches <session-id>      # Code changes only
trace show chronicle <session-id>    # Full timeline (messages + patches)
trace show metadata <session-id>     # Session info and statistics
trace show files <session-id>        # File operation summary
trace show tools <session-id>        # Tool usage summary
```

Session ID accepts partial matches (minimum 8 characters):

```bash
trace show messages abc12345        # Matches abc123456789...
```

**Export Commands**

Export to files for processing:

```bash
trace export chronicle <session-id>                    # Auto-named file
trace export chronicle <session-id> --output out.md    # Custom filename
trace export messages <session-id>                     # Messages only
trace export patches <session-id>                      # Patches only
trace export metadata <session-id>                     # JSON metadata
```

Default filename pattern: `{session-12chars}-{content}.md`

**Programmatic Access**

Import and use directly in Python:

```python
from aura_trace import ConversationFinder, ConversationRetrieval
from pathlib import Path

# Find conversation
finder = ConversationFinder()
conv_file = finder.find_by_session_id("abc12345")

# Load and extract data
retrieval = ConversationRetrieval()
entries = retrieval.load_conversation(conv_file)
messages = retrieval.get_messages(entries)
patches = retrieval.get_patches(entries)
timeline = retrieval.get_timeline(entries,
    include_messages=True,
    include_patches=True)

# Get formatted output
from aura_trace.formatter import ConversationFormatter
formatter = ConversationFormatter()
metadata = retrieval.get_metadata(entries)
markdown = formatter.format(timeline, metadata['session_id'], metadata)
```

**IMEM Integration**

Export conversation for memory indexing:

```bash
trace export chronicle <session-id> --output context.md
```

Produces LlamaIndex-compatible markdown with H2 section chunking. Pass output file to IMEM ingestion pipeline.

**Common Workflows**

Find and export recent conversations:

```bash
trace list --limit 5                           # Show 5 newest
trace show chronicle abc12345                  # Preview content
trace export chronicle abc12345 -o session.md  # Save for processing
```

Search for specific topic:

```bash
trace list --marker "authentication"
trace show messages def67890
```

Analyze code changes:

```bash
trace show patches xyz13579
trace export patches xyz13579 --output changes.md
```

**File Locations**

Conversation data: `~/.claude/projects/{project-hash}/{session-id}.jsonl`

Project hash: Derived by Claude Code from git repository path

Session ID: UUID-v4 format (e.g., `abc12345-6789-4abc-8def-0123456789ab`)

**Error Handling**

Session not found: Displays suggestion to run `trace list`

Empty conversation: Returns no results without error

Malformed JSONL: Logs warning and continues parsing remaining lines

Missing files: Returns empty list for finders, exits with error message for show/export
