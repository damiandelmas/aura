# Existing Claude Code Conversation Management Tools

**Date:** 2025-10-18
**Purpose:** Reference for conversation history management and UI tools
**Context:** Research for AURA conversation indexing and querying system

---

## Summary

Four mature tools exist for managing Claude Code conversation history:

1. **claude-conversation-extractor** - CLI search engine for conversations
2. **claude-code-history-viewer** - Desktop GUI with analytics
3. **claude-code-viewer** - Web-based client with full Claude Code functionality
4. **claude-code-log** - Python CLI for HTML timeline generation
5. **christian-byrne/claude-code-vector-memory** - Vector search with ChromaDB

---

## 1. claude-conversation-extractor (ZeroSumQuant)

**Repository:** https://github.com/ZeroSumQuant/claude-conversation-extractor

### What It Does
CLI tool to export and search Claude Code JSONL conversations with real-time search capabilities.

### Key Features
- **`claude-search`** - Real-time search across all sessions in `~/.claude/projects/`
- **Export to Markdown/HTML** - Clean conversation exports
- **Detailed mode** - Includes tool calls, MCP responses, file operations
- **JSONL parsing library** - Can be imported into other Python projects

### Installation
```bash
# From PyPI (if published)
pip install claude-conversation-extractor

# Or from source
git clone https://github.com/ZeroSumQuant/claude-conversation-extractor
cd claude-conversation-extractor
pip install -e .
```

### Usage Examples
```bash
# Search all conversations
claude-search "authentication design"

# Export specific session
claude-extract --session abc123 --output conversation.md

# Detailed export with tool calls
claude-extract --session abc123 --detailed --output full.md
```

### Python API
```python
from claude_conversation_extractor import parse_jsonl, search_conversations

# Parse a conversation file
conversation = parse_jsonl("~/.claude/projects/.../abc123.jsonl")

# Search across all conversations
results = search_conversations("database schema")
```

### What We Can Use
- ✅ JSONL parsing library (import into TRACE)
- ✅ Search indexing approach
- ✅ Markdown export functionality
- ✅ Session metadata extraction

---

## 2. claude-code-history-viewer (jhlee0409)

**Repository:** https://github.com/jhlee0409/claude-code-history-viewer

### What It Does
Desktop GUI application (Tauri) for browsing and analyzing Claude Code conversations with rich analytics.

### Key Features
- **Project/session tree navigation** - Visual hierarchy of projects and sessions
- **Activity heatmap** - Visual timeline of conversation activity
- **Usage statistics** - Token usage, message counts, tool usage analytics
- **Session browser** - Click to view any conversation
- **Syntax highlighting** - Code blocks rendered properly
- **Cross-platform** - MacOS, Linux, Windows (Tauri-based)

### Installation
```bash
# From releases
# Download binary from GitHub releases

# Or build from source
git clone https://github.com/jhlee0409/claude-code-history-viewer
cd claude-code-history-viewer
npm install
npm run tauri build
```

### Features for Users
- **Visual discovery** - Heatmaps show conversation density over time
- **Analytics dashboard** - Token usage per project, conversation lengths
- **Quick navigation** - Tree view with search
- **Export** - Copy conversations as markdown

### What We Can Use
- ✅ UI/UX patterns for conversation browsing
- ✅ Analytics approach (token tracking, activity patterns)
- ✅ Project/session hierarchy visualization
- ⚠️ Desktop app architecture (if we build UI)

---

## 3. claude-code-viewer (d-kimuson)

**Repository:** https://github.com/d-kimuson/claude-code-viewer

### What It Does
Web-based client that wraps Claude Code CLI with full conversation management and real-time monitoring.

### Key Features
- **Resume sessions from web UI** - Click to continue any conversation
- **Real-time task monitoring** - Watch Claude Code operations live
- **Git diff viewer** - See code changes inline
- **Auto-detects new conversations** - Watches `~/.claude/projects/` for new files
- **WebSocket streaming** - Real-time output from `claude -p`
- **Session management** - Pause, resume, fork conversations

### Architecture
```
Web UI (React/Vue)
    ↓ WebSocket
Node.js Backend
    ↓ Subprocess
claude -p (headless mode)
```

### Installation
```bash
git clone https://github.com/d-kimuson/claude-code-viewer
cd claude-code-viewer
npm install
npm run dev
```

### Usage
```bash
# Start server
npm start

# Open browser
open http://localhost:3000

# Features:
# - Browse all conversations
# - Click to resume any session
# - Watch real-time output
# - Fork conversations from UI
```

### What We Can Use
- ✅ Web UI architecture pattern
- ✅ `claude -p` subprocess wrapper approach
- ✅ Real-time monitoring via WebSocket
- ✅ Session resume/fork UI patterns
- ✅ Git diff integration ideas

---

## 4. claude-code-log (daaain)

**Repository:** https://github.com/daaain/claude-code-log

### What It Does
Python CLI that converts Claude Code JSONL files to interactive HTML timelines.

### Key Features
- **Interactive timeline view** - Conversations rendered as timelines
- **Cross-session summary matching** - Links related conversations
- **Batch processing** - Process entire `~/.claude/projects/` directory
- **Token usage tracking** - Per-session and cumulative tracking
- **HTML export** - Beautiful static HTML pages
- **Python library** - Importable for custom processing

### Installation
```bash
pip install claude-code-log

# Or from source
git clone https://github.com/daaain/claude-code-log
cd claude-code-log
pip install -e .
```

### Usage Examples
```bash
# Convert single conversation to HTML
claude-code-log --session abc123 --output timeline.html

# Process entire project
claude-code-log --project ~/.claude/projects/my-app --output-dir ./timelines/

# Extract summaries
claude-code-log --session abc123 --summary-only
```

### Python API
```python
from claude_code_log import ConversationParser, HTMLGenerator

# Parse conversation
parser = ConversationParser("~/.claude/projects/.../abc123.jsonl")
parsed = parser.parse()

# Generate HTML
generator = HTMLGenerator(parsed)
generator.save("timeline.html")
```

### What We Can Use
- ✅ JSONL parsing patterns
- ✅ Summary extraction methods
- ✅ Timeline visualization approach
- ✅ Token usage tracking logic
- ✅ Cross-session linking ideas

---

## 5. christian-byrne/claude-code-vector-memory

**Repository:** https://github.com/christian-byrne/claude-code-vector-memory

### What It Does
Vector search system for Claude Code conversations using ChromaDB with semantic search and hybrid scoring.

### Key Features
- **ChromaDB vector storage** - Persistent vector database
- **Conversation summaries indexed** - Summary-level (not full transcripts)
- **Hybrid scoring** - `0.7 * semantic + 0.2 * recency + 0.1 * complexity`
- **MCP integration** - `/system:semantic-memory-search` command
- **Automatic indexing** - Watches for new conversations
- **Metadata filtering** - By date, duration, message count

### Architecture
```
Conversations (JSONL)
    ↓
Extract summaries (200-500 words)
    ↓
Embed with sentence-transformers
    ↓
Store in ChromaDB
    ↓
Search with hybrid scoring
    ↓
Return top-K sessions
```

### Installation
```bash
git clone https://github.com/christian-byrne/claude-code-vector-memory
cd claude-code-vector-memory
pip install -r requirements.txt
python setup.py install
```

### Usage
```bash
# Index conversations
python -m claude_vector_memory index

# Search
python -m claude_vector_memory search "authentication design"

# In Claude Code (via MCP)
/system:semantic-memory-search authentication design
```

### Hybrid Scoring Implementation
```python
def hybrid_score(result):
    semantic = result['cosine_similarity']  # 0-1

    # Recency (exponential decay)
    days_ago = (now - result['timestamp']).days
    recency = math.exp(-0.1 * days_ago)

    # Complexity (more messages = more context)
    complexity = min(result['message_count'] / 100, 1.0)

    return 0.7 * semantic + 0.2 * recency + 0.1 * complexity
```

### What We Can Use
- ✅ **Hybrid scoring formula** - Proven weights
- ✅ **Summary-level indexing** - Don't index full transcripts
- ✅ **Metadata enrichment** - Duration, message count, tools used
- ✅ **Two-tier retrieval pattern** - Discover via vectors, retrieve full on demand
- ❌ **Don't copy ChromaDB** - We already have Qdrant

---

## Comparison Matrix

| Feature | extractor | history-viewer | code-viewer | code-log | vector-memory |
|---------|-----------|----------------|-------------|----------|---------------|
| **Type** | CLI | Desktop GUI | Web UI | CLI | Vector Search |
| **Tech** | Python | Tauri (Rust+JS) | Node.js | Python | ChromaDB |
| **Search** | Keyword | Keyword | Keyword | Keyword | Semantic |
| **Export** | Markdown/HTML | Copy | Markdown | HTML | None |
| **Analytics** | Basic | Advanced | Medium | Medium | None |
| **UI** | Terminal | Desktop | Browser | Browser (static) | Terminal/MCP |
| **Real-time** | No | No | Yes | No | No |
| **Indexing** | No | No | No | No | Yes (ChromaDB) |
| **Resume** | No | No | Yes | No | No |
| **Parsing** | ✅ Importable | ❌ GUI-only | ⚠️ Node.js | ✅ Importable | ⚠️ Limited |

---

## What AURA Should Adopt

### From claude-conversation-extractor
- ✅ JSONL parsing library (if compatible with TRACE)
- ✅ Real-time search across all sessions
- ✅ Detailed mode (include tool calls, MCP, files)

### From claude-code-history-viewer
- ✅ Activity heatmap visualization
- ✅ Token usage analytics
- ✅ Project/session tree UI pattern
- ⚠️ Desktop app architecture (optional)

### From claude-code-viewer
- ✅ Web UI with resume functionality
- ✅ `claude -p` subprocess wrapper pattern
- ✅ Real-time monitoring via WebSocket
- ✅ Session fork UI

### From claude-code-log
- ✅ Timeline visualization approach
- ✅ Cross-session linking patterns
- ✅ Token tracking methodology

### From christian-byrne/claude-code-vector-memory
- ✅ **Hybrid scoring formula** (0.7 semantic + 0.2 recency + 0.1 complexity)
- ✅ **Summary-level indexing** (don't index full transcripts)
- ✅ **Rich metadata storage** (duration, messages, tools)
- ✅ **Two-tier retrieval** (discover via vectors, retrieve full on demand)
- ❌ **Don't use ChromaDB** (we already have Qdrant)

---

## AURA's Advantage Over These Tools

### What These Tools DON'T Have

1. **Validated changelogs** - None have user-validated transformation pipeline
2. **RAG-optimized structure** - None have H1→H2→H3 section-level chunking
3. **Brother-based transformation** - None use `claude -p` for intelligent curation
4. **Bidirectional linking** - None link conversations ↔ validated knowledge
5. **Document maintenance** - None have PULSE-like living document updates
6. **Production vector DB** - Most use ChromaDB, we have Qdrant
7. **Intelligence-first** - None use LLMs for transformation (they use regex/scripts)

### AURA's Unique Position

```
christian-byrne: Indexes conversations (that's all they have)
AURA: Indexes conversations AND changelogs (transformation pipeline)

Other tools: Keyword search or basic vectors
AURA: Semantic search + section-level retrieval + hybrid scoring

Other tools: Read-only retrieval
AURA: Intelligent querying via brother agents
```

**We're building institutional memory, not just conversation search.**

---

## Recommended Integration Strategy

### Phase 1: Use Their Parsing (If Needed)
```python
# If claude-conversation-extractor has better parsing
from claude_conversation_extractor import parse_jsonl

# Otherwise, stick with TRACE (we already have this)
from aura.services.trace import ConversationRetrieval
```

### Phase 2: Adopt UI Patterns
```bash
# Study their UIs for best practices:
# - claude-code-history-viewer: Desktop app with analytics
# - claude-code-viewer: Web UI with resume/fork
# - claude-code-log: Timeline visualization

# Build web UI inspired by claude-code-viewer
# Use activity heatmap from history-viewer
# Timeline view from code-log
```

### Phase 3: Implement Hybrid Scoring
```python
# Directly adopt christian-byrne's formula
def hybrid_score(result):
    semantic = result.score  # From Qdrant

    days_ago = (now - result.metadata['start_time']).days
    recency = math.exp(-0.1 * days_ago)

    complexity = min(result.metadata['message_count'] / 100, 1.0)

    return 0.7 * semantic + 0.2 * recency + 0.1 * complexity
```

### Phase 4: Build Brother Querying (Unique to AURA)
```python
# None of these tools have this
@mcp_tool
def query_conversation(session_id: str, question: str):
    """Ask a question to a past conversation via brother agent"""
    md = trace.export_to_markdown(session_id)
    result = subprocess.run(['claude', '-p', f"{question}\n\n{md}"])
    return result.stdout
```

---

## Installation Quick Reference

### To Explore These Tools

```bash
# 1. claude-conversation-extractor (Python CLI)
git clone https://github.com/ZeroSumQuant/claude-conversation-extractor
pip install -e claude-conversation-extractor

# 2. claude-code-history-viewer (Desktop GUI)
# Download from releases: https://github.com/jhlee0409/claude-code-history-viewer/releases

# 3. claude-code-viewer (Web UI)
git clone https://github.com/d-kimuson/claude-code-viewer
cd claude-code-viewer && npm install && npm start

# 4. claude-code-log (Python CLI)
git clone https://github.com/daaain/claude-code-log
pip install -e claude-code-log

# 5. christian-byrne/claude-code-vector-memory (Vector search)
git clone https://github.com/christian-byrne/claude-code-vector-memory
pip install -r claude-code-vector-memory/requirements.txt
```

---

## Summary

### Best for Different Needs

- **Best CLI search:** claude-conversation-extractor
- **Best desktop UI:** claude-code-history-viewer
- **Best web UI:** claude-code-viewer
- **Best visualization:** claude-code-log (timelines)
- **Best vector search:** christian-byrne/claude-code-vector-memory

### What AURA Should Build

**Combine the best of all:**
- CLI search (like extractor)
- Web UI (like code-viewer)
- Vector search (like christian-byrne, but with Qdrant)
- Timeline viz (like code-log)
- **PLUS unique features:**
  - Validated changelogs
  - RAG-optimized structure
  - Brother agent querying
  - Bidirectional linking

**We're not competing with these tools. We're building on top of a more sophisticated foundation (validated knowledge + intelligent transformation).**

---

## Next Steps

1. ✅ Reference these tools for UI/UX patterns
2. ✅ Adopt hybrid scoring from christian-byrne
3. ✅ Consider using extractor's parsing library (if better than TRACE)
4. ✅ Study code-viewer for web UI architecture
5. ✅ Build brother querying (unique to AURA)

**These tools validate the need for conversation management. AURA's transformation pipeline (conversations → validated changelogs) is the differentiator.**
