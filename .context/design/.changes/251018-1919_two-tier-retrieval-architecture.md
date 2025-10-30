# Two-Tier Retrieval Architecture: Changelogs + Conversations

**Date:** 2025-10-18 19:19
**Type:** Architecture Documentation
**Status:** Active Design

---

## Overview

AURA implements a **two-tier knowledge retrieval system** that indexes both validated changelogs and raw conversations, with bidirectional linking between them. This provides both **precision** (curated, structured knowledge) and **completeness** (full source material).

```
┌─────────────────────────────────────────────────────────┐
│ USER CONVERSATION                                       │
│ (Raw, noisy, incomplete patches)                        │
└─────────────────┬───────────────────────────────────────┘
                  │
                  │ /log:develop
                  ▼
┌─────────────────────────────────────────────────────────┐
│ TRACE: Conversation Archaeology                         │
│ - Finds JSONL files in ~/.claude/projects/             │
│ - Parses conversations                                  │
│ - Exports to markdown                                   │
│ - Provides context to ChangelogAgent                    │
└─────────────────┬───────────────────────────────────────┘
                  │
                  │ Conversation context
                  ▼
┌─────────────────────────────────────────────────────────┐
│ CHANGELOGAGENT (Brother spawned via claude -p)         │
│ - Receives full conversation context                    │
│ - Uses RAG-optimized template                           │
│ - Creates structured changelog                          │
│ - User validates                                        │
└─────────────────┬───────────────────────────────────────┘
                  │
                  │ Validated changelog
                  ▼
┌─────────────────────────────────────────────────────────┐
│ DUAL INDEXING SYSTEM                                    │
│                                                         │
│ ┌─────────────────────┐  ┌────────────────────────┐   │
│ │ TIER 1: CHANGELOGS  │  │ TIER 2: CONVERSATIONS  │   │
│ │                     │  │                        │   │
│ │ • Section-level     │  │ • Summary-level        │   │
│ │ • ~15 vectors/doc   │  │ • 1 vector/doc         │   │
│ │ • H1→H2→H3 chunks   │  │ • Simple indexing      │   │
│ │ • User validated    │  │ • Semantic discovery   │   │
│ │ • RAG-optimized     │  │ • Source material      │   │
│ │                     │  │                        │   │
│ │ Metadata:           │  │ Metadata:              │   │
│ │ • session_id ───────┼──┼→ session_id            │   │
│ │ • section_type      │  │ • has_changelog        │   │
│ │ • category          │  │ • changelog_path ──────┼───┤
│ │ • timestamp         │  │ • duration             │   │
│ └─────────────────────┘  └────────────────────────┘   │
│                                                         │
│         IMEM: Vector Search Engine (Qdrant + E5)       │
└─────────────────────────────────────────────────────────┘
                  │
                  │ Semantic search with type filtering
                  ▼
┌─────────────────────────────────────────────────────────┐
│ RETRIEVAL LAYER                                         │
│                                                         │
│ Query: "auth design decisions"                          │
│                                                         │
│ ┌─────────────────────┐  ┌────────────────────────┐   │
│ │ Search changelogs   │  │ Search conversations   │   │
│ │ type='changelog'    │  │ type='conversation'    │   │
│ │ section='decision'  │  │ (semantic match)       │   │
│ │                     │  │                        │   │
│ │ Returns:            │  │ Returns:               │   │
│ │ • Validated         │  │ • Relevant sessions    │   │
│ │ • Structured        │  │ • With summaries       │   │
│ │ • With session_id   │  │ • Link to changelog    │   │
│ └─────────────────────┘  └────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                  │
                  │ Bidirectional navigation
                  ▼
┌─────────────────────────────────────────────────────────┐
│ USER WORKFLOWS                                          │
│                                                         │
│ • Changelog → session_id → Full conversation            │
│ • Conversation → changelog_path → Validated knowledge   │
│ • Brother spawning for intelligent querying             │
└─────────────────────────────────────────────────────────┘
```

---

## System Components

### TRACE: Conversation Archaeology

**Purpose:** Parse Claude Code's internal storage and provide conversation data.

**Responsibilities:**
- Discover JSONL files in `~/.claude/projects/`
- Parse conversations (messages, tools, files, patches)
- Extract structured summaries
- Export to markdown for agent consumption
- No vector search (just filesystem + grep)

**Key Operations:**
```bash
trace --recent 5              # List recent conversations
trace --session abc123        # Load specific conversation
trace --marker "auth"         # Find by content
trace --export context.md     # Export for agent
```

**Data Extraction:**
```python
summary = {
    'summary': 'Discussion about PostgreSQL schema...',
    'session_id': 'abc123def456',
    'working_directory': '/path/to/project',
    'message_count': 45,
    'start_time': datetime(...),
    'duration_minutes': 32.5
}
```

### IMEM: Vector Search Engine

**Purpose:** Semantic search across documents and conversations using vector embeddings.

**Tech Stack:**
- **Vector DB:** Qdrant (production-grade, Docker)
- **Embeddings:** E5-large (1024-dimensional vectors)
- **Indexing:** LlamaIndex MarkdownNodeParser
- **Search:** Cosine similarity + metadata filtering

**Responsibilities:**
- Ingest markdown documents
- Generate embeddings (E5-large)
- Store in Qdrant with rich metadata
- Semantic search with filtering
- Hybrid scoring (semantic + recency + complexity)

**Two Collections:**

**Collection 1: Changelogs**
```python
{
    'type': 'changelog',
    'phase': 'develop',  # design/designate/develop/document
    'section_type': 'decision',  # decision/constraint/pattern/implementation
    'category': 'architecture',
    'session_id': 'abc123def456',  # LINK TO CONVERSATION
    'timestamp': '2025-10-18T...',
    'conversation_file': '~/.claude/projects/.../abc123.jsonl'
}
```

**Collection 2: Conversations**
```python
{
    'type': 'conversation',
    'session_id': 'abc123def456',
    'start_time': '2025-10-18T...',
    'duration': 32.5,
    'message_count': 45,
    'working_directory': '/path/to/project',
    'file_path': '~/.claude/projects/.../abc123.jsonl',
    'has_changelog': True,  # LINK TO CHANGELOG
    'changelog_path': '.develop/.changes/251018-1538_abc123.md'
}
```

### ChangelogAgent: Transformation Pipeline

**Purpose:** Transform raw conversations into RAG-optimized changelogs.

**Process:**
1. Spawned via `claude -p` (brother agent)
2. Receives full conversation context (via TRACE export)
3. Uses RAG-optimized template (H1→H2→H3 structure)
4. Applies progressive disclosure (2-6 fields per item)
5. User validates output
6. Changelog saved to `.context/develop/.changes/`

**Key Properties:**
- **Intelligence-first:** LLM transforms noise → signal (no regex)
- **Context-aware:** Has full conversation, knows what happened
- **Structured output:** H1→H2→H3 hierarchy for section-level retrieval
- **User validation:** Ground truth status

### PULSE: Document Maintenance

**Purpose:** Maintain living documents based on validated changelogs.

**Responsibilities:**
- Reads changelogs from `.context/develop/.changes/`
- Updates documents in `.context/document/`
- Ensures documents reflect current state
- Re-triggers IMEM indexing after updates

**Role in Architecture:**
- Consumes changelogs (Tier 1 data)
- Produces maintained documents (also Tier 1)
- Does NOT interact with raw conversations (Tier 2)

---

## The Two-Tier Strategy

### Tier 1: Changelogs (High-Fidelity Knowledge)

**What Gets Indexed:**
- Files from `.context/design/.changes/`, `.context/develop/.changes/`, `.context/document/`
- Validated by user via `/log:develop`
- RAG-optimized structure (H1→H2→H3)
- Section-level chunking (~15 vectors per document)

**Indexing Strategy:**
```python
# LlamaIndex MarkdownNodeParser
# Chunks at H3 level (surgical retrieval)

Document → H1 (parent)
         → H2 (category)
           → H3 (item) ← ONE VECTOR
           → H3 (item) ← ONE VECTOR
         → H2 (category)
           → H3 (item) ← ONE VECTOR
```

**Search Patterns:**
```bash
# Surgical section retrieval
imem search "JWT implementation" --type changelog --section decision

# Category filtering
imem search "auth" --category security --phase develop

# Time-based
imem search "schema" --after 2025-10-01
```

**Characteristics:**
- ✅ User validated (ground truth)
- ✅ Structured for retrieval (H1→H2→H3)
- ✅ Language-agnostic patterns (code signatures, not implementations)
- ✅ Progressive disclosure (complexity matches work)
- ✅ Low noise (40% reduction from raw conversations)
- ❌ Curated (some details omitted)

### Tier 2: Conversations (Source Material)

**What Gets Indexed:**
- Conversation summaries from `~/.claude/projects/*.jsonl`
- NOT full transcripts (too noisy, 10K-100K words)
- Just summaries (200-500 words)
- One vector per conversation

**Indexing Strategy:**
```python
# Simple summary-level indexing
# One vector per conversation (semantic discovery)

Conversation → Summary (200-500 words) → ONE VECTOR
```

**Search Patterns:**
```bash
# Semantic discovery
imem search "database design" --type conversation

# Find source material
imem search "auth exploration" --type conversation --recent-days 30
```

**Characteristics:**
- ✅ Complete source material (full conversation available on demand)
- ✅ Semantic discovery (find relevant discussions)
- ✅ All alternatives explored (dead ends, iterations)
- ✅ Full patches and tool usage
- ❌ Noisy (tool calls, back-and-forth)
- ❌ No validation (raw material)
- ❌ Not RAG-optimized (simple summary indexing)

---

## Bidirectional Linking

### Changelog → Conversation

**Use Case:** "I'm reading a validated decision, but want to see the original discussion."

**Flow:**
1. User reads changelog section
2. Sees `session_id` in metadata
3. Runs: `trace --session abc123 --export context.md`
4. Gets full conversation context
5. Optional: Spawn brother to query conversation

**Metadata in Changelog:**
```yaml
---
session_id: abc123def456
timestamp: 2025-10-18T15:38:00
conversation_file: ~/.claude/projects/.../abc123.jsonl
---
```

### Conversation → Changelog

**Use Case:** "I found a relevant conversation, has it been validated into a changelog?"

**Flow:**
1. IMEM search returns conversation
2. Metadata shows `has_changelog: true`
3. User clicks `changelog_path`
4. Jumps to validated knowledge

**Metadata in Conversation:**
```python
{
    'has_changelog': True,
    'changelog_path': '.develop/.changes/251018-1538_abc123.md'
}
```

---

## Data Flow

### Creation Flow (Conversation → Changelog)

```
1. User works with Claude Code
   ↓
2. Conversation created (~/.claude/projects/abc123.jsonl)
   ↓
3. User runs: /log:develop
   ↓
4. TRACE exports conversation to markdown
   ↓
5. ChangelogAgent (claude -p) receives:
   - Full conversation context
   - RAG-optimized template
   ↓
6. Changelog created (.develop/.changes/251018-1538_abc123.md)
   ↓
7. User validates
   ↓
8. IMEM indexes changelog (section-level, ~15 vectors)
   ↓
9. (Optional) Index conversation summary (1 vector)
   ↓
10. Bidirectional link established (session_id ↔ changelog_path)
```

### Search Flow (Dual Retrieval)

```
User query: "Find auth design decisions"
   ↓
┌──────────────────────┬───────────────────────┐
│                      │                       │
│ Search Tier 1        │  Search Tier 2        │
│ (Changelogs)         │  (Conversations)      │
│                      │                       │
│ type='changelog'     │  type='conversation'  │
│ section='decision'   │  (summary match)      │
│                      │                       │
│ Returns:             │  Returns:             │
│ • Validated          │  • Relevant sessions  │
│ • Structured         │  • Summaries          │
│ • session_id link    │  • changelog link     │
└──────────────────────┴───────────────────────┘
   ↓                       ↓
   │                       │
   └───────┬───────────────┘
           │
           ▼
    User picks result
           │
           ▼
    ┌──────────────────┐
    │ Changelog?       │ → View validated knowledge
    │ Conversation?    │ → TRACE exports → Brother queries
    └──────────────────┘
```

---

## Implementation Status

### Currently Implemented

✅ **TRACE:** Full conversation parsing and export
✅ **IMEM:** Changelog indexing with section-level chunking
✅ **ChangelogAgent:** Brother spawning with template system
✅ **PULSE:** Document maintenance based on changelogs
✅ **Markdown Export:** `trace --export` for agent consumption

### In Progress

🔄 **Conversation Summary Indexing:** `trace --index-all` (Tier 2)
🔄 **Bidirectional Metadata:** Linking session_id ↔ changelog_path
🔄 **Type Filtering:** `imem search --type conversation`

### Future Enhancements

⏳ **Hybrid Scoring:** Semantic + recency + complexity
⏳ **CLI Navigation:** `trace --session abc123 --show-changelog`
⏳ **MCP Tools:** Optional tool wrappers for Claude Code integration

---

## Key Design Principles

### 1. Intelligence-First Transformation

**Raw conversations are noisy:**
- Tool calls and results
- Dead ends explored
- Partial patches (only changed lines)
- Back-and-forth iterations

**ChangelogAgent (LLM) transforms this into:**
- Validated decisions
- Language-agnostic patterns
- Code signatures (not implementations)
- Structured for retrieval

**Never use regex. Always use brothers.**

### 2. Different Artifacts, Different Strategies

**Changelogs:**
- RAG-optimized (H1→H2→H3)
- Section-level chunking
- ~15 vectors per document
- Surgical retrieval

**Conversations:**
- Summary-level indexing
- 1 vector per conversation
- Semantic discovery
- Full text on demand

**Form follows function.**

### 3. Precision AND Completeness

**Not one OR the other. BOTH:**
- Changelogs = Precision (validated, structured)
- Conversations = Completeness (raw, full context)
- Bidirectional linking = Navigate between them

**Trust but verify.**

### 4. Ground Truth Hierarchy

```
Conversations (raw territory)
    ↓ transformation
Changelogs (validated map)
    ↓ maintenance
Documents (current state)
```

**All three indexed by IMEM, with different strategies.**

---

## Comparison to Alternatives

### Christian-Byrne's claude-code-vector-memory

**What they do:**
- Index conversation summaries only
- ChromaDB for vector storage
- Hybrid scoring (semantic + recency + complexity)
- `/system:semantic-memory-search` command

**What they DON'T have:**
- Validated changelogs
- RAG-optimized structure
- User validation workflow
- Brother-based transformation
- Maintained documents

**They index conversations because that's all they have.**

**We have changelogs AND conversations, so we index BOTH, differently.**

### Our Advantage

| Feature | Christian-Byrne | AURA |
|---------|----------------|------|
| Conversation summaries | ✅ Indexed | ✅ Indexed |
| Validated changelogs | ❌ None | ✅ User validated |
| RAG optimization | ❌ Simple | ✅ H1→H2→H3 structure |
| Section-level retrieval | ❌ No | ✅ ~15 vectors/doc |
| Bidirectional linking | ❌ No | ✅ session_id ↔ changelog |
| Document maintenance | ❌ No | ✅ PULSE |
| Intelligence-first | ⚠️ Partial | ✅ Full (claude -p) |

**We're not competing with christian-byrne. We're building on a more sophisticated foundation.**

---

## Summary

**The two-tier retrieval architecture provides:**

1. **Precision:** RAG-optimized changelogs with section-level retrieval
2. **Completeness:** Raw conversations with semantic discovery
3. **Validation:** User-approved ground truth
4. **Traceability:** Bidirectional linking between validated knowledge and source material
5. **Intelligence:** Brother agents transform noise → signal
6. **Flexibility:** Right tool for the job (surgical vs discovery)

**This is not conversations OR changelogs. It's BOTH, indexed differently, linked bidirectionally.**

**Trust (changelogs) but verify (conversations).**
