---
schema_version: "v3_adaptive"
type: "architecture.trace"
status: "stable"
keywords: "trace conversations jsonl archaeology parsing chronicle"
timestamp: "2025-10-23T20:45:00-0700"
---

# TRACE Architecture

## Purpose

TRACE is a conversation archaeology tool that parses Claude Code conversation JSONL files and provides structured queries for both humans and agents. It enables retrieving conversation context, code changes, tool usage, and chronological timelines.

**Path**: `trace/src/aura_trace/`
**Lines**: 1,242 lines (33% of codebase)
**CLI**: `trace`
**Code Quality**: ⭐ Highest in codebase (80%+ type hints, dataclasses, comprehensive docstrings)

---

## Core Capabilities

### 1. Global Session Discovery
```bash
trace --list              # All conversations across projects
trace --list --recent 10  # 10 most recent
```

Scans `~/.claude/projects/*/conversations/*.jsonl` globally, sorts by modification time.

### 2. Structured Queries
```bash
trace --session abc123 --metadata     # Session info (timing, counts)
trace --session abc123 --messages     # Just user/assistant messages
trace --session abc123 --patches      # Just code changes
trace --session abc123 --files        # File operations
trace --session abc123 --tools        # Tool usage counts
```

### 3. Chronological Timeline
```bash
trace --session abc123 --chronicle
```

Interleaves messages and patches in chronological order - complete story for agents.

### 4. Agent-Friendly Export
```bash
trace --session abc123 --chronicle --output context.md
```

Exports structured markdown with H2 sections for LlamaIndex chunking.

---

## Components

### `finder.py` - Session Discovery
**Purpose**: Find conversation JSONL files globally

**Key Features**:
- Scans all projects in `~/.claude/projects/`
- Supports partial session ID matching (min 8 chars)
- Sorts by modification time (newest first)
- Extracts session metadata from file

**Data Class**:
```python
@dataclass
class ConversationInfo:
    session_id: str
    file_path: Path
    size: int
    modified_time: datetime
    project_path: str
```

### `retrieval.py` - JSONL Parsing
**Purpose**: Parse conversation files and extract structured data

**Key Features**:
- Dataclass-based extraction (type-safe)
- Comprehensive docstrings (90%+ coverage)
- Logging instead of print statements
- Handles malformed JSONL gracefully

**Extracts**:
- Summary (timing, counts, working directory)
- Messages (user + assistant)
- File operations (deduplicated)
- Tool usage (counts by tool type)
- Code patches (with timestamps)

**Data Class**:
```python
@dataclass
class ConversationEntry:
    type: str                    # 'user', 'assistant', 'tool_use', etc.
    session_id: Optional[str]
    timestamp: Optional[str]
    message: Optional[Dict]
    # ... other fields
```

### `query.py` - Agent Formatting
**Purpose**: Format conversation data for agent consumption

**Key Methods**:
```python
def prepare_for_agent(file_path) -> Dict:
    """Complete conversation data for agent memory"""

def export_structured_markdown(file_path) -> str:
    """H2-sectioned markdown for IMEM indexing"""
```

**Structured Export Format**:
```markdown
# Conversation: abc123

## User Messages
- "How do we implement auth?"
- "What about JWT?"

## Assistant Responses
Here's the approach...

## Code Changes
### auth/middleware.py
```diff
+ def verify_token(request):
```

## Tools Used
- Edit: 12×
- Bash: 5×

## Files Modified
- auth/middleware.py (modified)
```

### `cli.py` - Command Interface
**Purpose**: User-facing CLI with backwards-compatible flags

**Flag Naming**:
- `--metadata` - Session info (renamed from `--summary`)
- `--messages` - Text only (renamed from `--conversation`)
- `--chronicle` - Complete timeline (messages + patches chronological)
- `--output` - Write to file (alias for `--export`)

**Deprecation Handling**:
- Old flags still work but show warnings
- Migration guidance provided
- Zero breaking changes

---

## Data Flow

### Discovery Flow
```
1. User: trace --list
2. Scan ~/.claude/projects/*/conversations/*.jsonl
3. Extract file stats (size, mtime)
4. Parse first few lines for session_id
5. Sort by mtime (newest first)
6. Return session list with metadata
```

### Query Flow
```
1. User: trace --session abc123 --chronicle
2. finder.py: Find file by partial ID match
3. retrieval.py: Parse JSONL line by line
4. Extract: messages, patches, files, tools
5. query.py: Build chronological timeline
6. Output: Interleaved messages + patches
```

### Export Flow
```
1. User: trace --session abc123 --chronicle --output context.md
2. query.py: export_structured_markdown()
3. Build H2-sectioned markdown:
   - ## User Messages
   - ## Assistant Responses
   - ## Code Changes
   - ## Tools Used
   - ## Files Modified
4. Write to file
5. IMEM can index this file for search
```

---

## Session Detection

### Partial ID Matching
```bash
# Full ID
trace --session 5d8e69ea-8014-4e2a-9481-368685fb3a1f

# Partial (min 8 chars)
trace --session 5d8e69ea   # Works!
```

**Algorithm**:
1. List all conversations
2. Filter where `session_id.startswith(partial_id)`
3. Return first match
4. Error if multiple matches (rare)

### Global Search
TRACE searches **all projects**, not just current directory:
- `~/.claude/projects/project-a/conversations/*.jsonl`
- `~/.claude/projects/project-b/conversations/*.jsonl`
- `~/.claude/projects/project-c/conversations/*.jsonl`

**Benefit**: Resume conversations created in different projects.

---

## Chronicle Timeline Pattern

**Problem**: Agents need chronological story, not separate data streams.

**Solution**: Interleave messages and patches by timestamp.

**Implementation**:
```python
# Build timeline array
timeline = []

for msg in messages:
    timeline.append({
        'type': 'message',
        'timestamp': msg.get('_timestamp'),
        'data': msg
    })

for patch in patches:
    timeline.append({
        'type': 'patch',
        'timestamp': patch.get('timestamp'),
        'data': patch
    })

# Sort chronologically
timeline.sort(key=lambda x: x['timestamp'])

# Output interleaved
for event in timeline:
    if event['type'] == 'message':
        # Format message
    elif event['type'] == 'patch':
        # Format patch
```

**Output**:
```
[09:15] USER: "How do we implement auth?"
[09:16] ASSISTANT: "Here's the approach..."
[09:18] PATCH: auth/middleware.py
        + def verify_token(request):
[09:20] USER: "What about sessions?"
[09:21] ASSISTANT: "We can use..."
```

---

## Structured Markdown Export

TRACE exports conversations in LlamaIndex-compatible format for IMEM indexing.

**Format**:
```markdown
# Conversation: {session_id}

## User Messages
- "Message 1"
- "Message 2"

## Assistant Responses
Full assistant text here...

## Code Changes
### file1.py
```diff
+ new code
```

### file2.py
```diff
- old code
+ new code
```

## Tools Used
- Edit: 12×
- Bash: 5×
- Read: 3×

## Files Modified
- auth/middleware.py (modified)
- tests/test_auth.py (created)
```

**Why H2 Sections**:
- LlamaIndex MarkdownNodeParser chunks at H2 level
- Each section = 1 vector in Qdrant
- Search "tools used" returns just that section

**IMEM Integration**:
```bash
# TRACE exports
trace --session abc123 --output /tmp/conv.md

# IMEM indexes
imem index-conversation abc123
# → Calls TRACE export internally
# → Chunks with LlamaIndex
# → Stores in Qdrant
```

---

## Performance

- **List conversations**: <1ms (filesystem scan)
- **Parse conversation**: ~10-50ms per session (JSONL parsing)
- **Session lookup**: <1ms (partial ID matching)
- **Export markdown**: ~50-100ms (parsing + formatting)

**Optimization**: Lazy loading - only parses when queried, not during listing.

---

## Code Quality Highlights

### 1. Type Safety
```python
@dataclass
class ConversationEntry:
    type: str
    session_id: Optional[str]
    timestamp: Optional[str]
```

**Benefit**: IDE autocomplete, type checking, self-documenting.

### 2. Comprehensive Logging
```python
logger.info(f"Found {len(conversations)} conversations")
logger.debug(f"Parsing entry: {entry.type}")
logger.error(f"Failed to parse JSONL: {e}")
```

**Benefit**: Debuggable, no print statements cluttering output.

### 3. Docstring Coverage
```python
def get_metadata(self, entries: List[ConversationEntry]) -> Dict[str, Any]:
    """Extract conversation summary (timing, counts, working directory).

    Args:
        entries: Parsed conversation entries from JSONL file

    Returns:
        Dict containing session_id, start_time, duration_minutes,
        message_count, working_directory

    Example:
        >>> metadata = retrieval.get_metadata(entries)
        >>> print(metadata['duration_minutes'])
        42.5
    """
```

**Benefit**: Self-documenting, clear contracts, usage examples.

---

## Integration with IMEM

### Bidirectional Linking

**Changelog → Conversation**:
```yaml
# In changelog frontmatter:
session_id: "5d8e69ea-8014-4e2a-9481-368685fb3a1f"
```

Search: `imem search --session 5d8e69ea`
Returns: Changelog sections from that conversation

**Conversation → Changelog**:
```python
# In conversation metadata:
{
    'has_changelog': True,
    'changelog_path': '.context/develop/.changes/...'
}
```

Workflow:
1. Search conversations: `imem search "auth" --in conversations`
2. See: `has_changelog: ✅`
3. Jump to: Validated changelog

---

## Configuration

### Storage Paths
- **Global conversations**: `~/.claude/projects/*/conversations/*.jsonl`
- **Registry**: `.claude/.trace/registry.json` (per-project bookmarks)
- **Exports**: Temporary files (auto-cleaned)

### No Configuration Files
TRACE has zero configuration - works out of the box.

---

## Future Enhancements

### High Priority
- Live watcher (auto-detect new conversations)
- SessionStart hook integration (auto-register)
- Better error messages for malformed JSONL

### Medium Priority
- Conversation search (grep across all conversations)
- Statistics (total messages, average duration)
- Conversation tagging/bookmarking

### Low Priority
- Export to JSON
- Conversation diffing
- Session merging (multi-part conversations)

---

## Related Documentation

- **Ecosystem Overview**: [architecture_aura.md](./architecture_aura.md)
- **Vector Search**: [architecture_imem.md](./architecture_imem.md)
