# IMEM - Semantic Search for Institutional Memory

IMEM provides semantic search across changelogs and conversations using Qdrant vector database and E5-Large-v2 embeddings.

## Core Concept

IMEM indexes two sources with dual collections per project:
- **Context collection** (`.context/develop/.changes/`, `.context/document/`) - What you built and documented
- **Conversation collection** (TRACE exports) - How you got there

Uses:
- **Nomic Embed v1.5**: 768-dim embeddings, 8k context (default for new collections)
- **E5-Large-v2**: 1024-dim embeddings (legacy, auto-detected for existing collections)
- **Qdrant**: Fast vector search with HNSW optimization (<100ms queries)
- **Template-aware chunking**: H3 sections for changelogs, H2 for conversations
- **Content filtering**: <20 char filter skips empty H2 parent headers
- **Rich metadata**: Filter by phase, layer, section type, chunk type, role, file path

## Quick Start

```bash
# Start Qdrant service
imem service start

# Index changelogs
imem init

# Index conversations
imem index-conversation <session-id>

# Search changelogs
imem develop search "authentication decisions" --decisions

# Search conversations
imem conversations search "bug fix" --patches-only

# Compositional retrieval (FlexGraph)
imem compose '{"search": {"text": "JWT"}, "discovery": {"siblings": true, "genealogy": true}}'
```

## Service Management

**Start Qdrant:**
```bash
imem service start
# Starts Docker container on port 6334
# Persists data to ~/.qdrant/storage
```

**Check status:**
```bash
imem service status
# Shows: running/stopped, port, container ID
```

**Stop/Restart:**
```bash
imem service stop
imem service restart
```

## Indexing

### Changelogs (.context/)

**Initialize project:**
```bash
imem init
# Creates dual collections: imem_<hash>_context and imem_<hash>_conversation
# Indexes .context/develop/, .context/document/, .context/designate/
# HNSW-optimized with Nomic v1.5 embeddings
# Chunks at H3 boundaries (decisions, constraints, patterns)
# Auto-creates collections on first use (no --force needed initially)
```

**Force re-index:**
```bash
imem init --force
# Recreates collections from scratch
# Note: --force now means "recreate" not "create if missing"
```

**Include design phase:**
```bash
imem init --include-design
# Also indexes .context/design/ (excluded by default)
```

### Conversations (TRACE exports)

**Index single conversation:**
```bash
imem index-conversation <session-id>
# Uses full or partial session ID (min 8 chars)
# Exports via TRACE → chunks at H2 → indexes
```

**Index multiple conversations:**
```bash
imem index-all-conversations --limit 10
# Batch index recent conversations
# --recent N: Most recent N conversations
# --min-size KB: Skip small conversations
```

**Dry run:**
```bash
imem index-all-conversations --limit 10 --dry-run
# Preview what would be indexed
```

## Searching Changelogs

### Unified Search Interface

**Search with source argument:**
```bash
imem search develop "authentication pattern"
# Searches context collection, phase=develop
# Returns H3 decision/constraint/pattern sections

imem search context "database"
# Searches all context sources (develop/design/document)

imem search conversations "bug fix"
# Searches conversation collection
```

**Filter by section type:**
```bash
imem search develop "database" --decisions
imem search develop "API limits" --constraints
imem search develop "retry logic" --patterns
```

**Filter by layer:**
```bash
imem search develop "error handling" --pattern
# Only searches .pattern.md files (language-agnostic)
```

**Combined filters:**
```bash
imem search develop "async operations" --decisions --pattern
# Decisions from pattern layer only
```

## Searching Conversations

**Basic search:**
```bash
imem search conversations "bug in authentication"
# Searches conversation collection
# Returns messages + patches
```

**Filter by chunk type:**
```bash
imem search conversations "error handling" --messages-only
# Only searches message text (excludes code patches)

imem search conversations "bug fix" --patches-only
# Only searches code patches (excludes messages)
```

**Filter by role:**
```bash
imem search conversations "how do I" --user-only
# Only searches user messages

imem search conversations "implementation approach" --assistant-only
# Only searches assistant responses
```

**Filter by file:**
```bash
imem search conversations "error" --file src/cli.py
# Only searches patches for src/cli.py
```

**Filter by session:**
```bash
imem search conversations "database" --session cb91d93d
# Searches specific conversation only
```

**Combined filters:**
```bash
imem search conversations "auth bug" --patches-only --session abc123
# Code patches about auth bugs in specific conversation
```

## What Gets Indexed

### Changelogs

**Included:**
- `.context/develop/.changes/*.md` (ground truth - what happened)
- `.context/document/**/*.md` (stable reference docs)
- `.context/designate/.changes/*.md` (planned work)
- `.context/develop/.changes/*.pattern.md` (language-agnostic patterns)

**Chunking:**
- H3 sections become searchable nodes
- Each decision/constraint/pattern = one vector
- Preserves Context → Solution → Rationale structure

**Excluded:**
- `.context/design/` (unless --include-design)
- Files outside `.context/`
- Non-markdown files

### Conversations

**Source:**
- TRACE conversation exports (chronicle format)
- `~/.claude/projects/*/conversations/*.jsonl`

**Chunking:**
- H2 sections become searchable nodes
- Messages: "Message 1: USER", "Message 2: ASSISTANT"
- Patches: "Code Patch 1: src/cli.py"

**Metadata extracted:**
- `chunk_type`: 'message' or 'patch'
- `role`: 'user' or 'assistant' (for messages)
- `file_path`: 'src/cli.py' (for patches)
- `session_id`: Full UUID

## Metadata Schema

### Changelog Metadata

Extracted from frontmatter + filename:
```yaml
---
schema_version: "v3_adaptive"
type: "implementation.feature"
status: "completed"
keywords: "auth login session"
timestamp: "2025-10-25T10:58:00-0700"
session_id: "abc123..."  # Links to originating conversation
---
```

**Searchable fields:**
- `phase`: develop, document, designate, design
- `layer`: pattern, implementation
- `section_type`: Decisions, Constraints, Failures, Patterns
- `category`: implementation, refactor, bug-fix, etc.
- `status`: completed, in-progress, archived

### Conversation Metadata

Parsed from H2 headers:
```python
"Message 1: USER" → {
    chunk_type: 'message',
    role: 'user'
}

"Code Patch 1: src/cli.py" → {
    chunk_type: 'patch',
    file_path: 'src/cli.py'
}
```

**Searchable fields:**
- `source`: 'conversation'
- `chunk_type`: 'message', 'patch'
- `role`: 'user', 'assistant'
- `file_path`: Path to file (for patches)
- `session_id`: Full UUID

## Integration with TRACE

**Export and index a conversation:**
```bash
# Export conversation to markdown
trace export chronicle <session-id> -o /tmp/conversation.md

# Index it
imem index-conversation <session-id>
# (TRACE export happens automatically)
```

**Search across both:**
```bash
# Find decisions in changelogs
imem develop search "auth decisions" --decisions

# Find how we discussed it in conversation
imem conversations search "auth discussion" --messages-only --session <id>
```

## Performance

**Indexing speed:**
- Changelogs: ~100 docs in 30-60 seconds
- Conversations: ~1 conversation per 5-10 seconds (depends on size)

**Search speed:**
- 40-80ms p50, 120ms p99 (500+ doc collections)
- HNSW optimization: m=16, ef_construct=100, on_disk=False

**Storage:**
- Embeddings: ~4KB per section (1024-dim vectors)
- Location: `~/.qdrant/storage/`
- One collection per project

## Common Workflows

**"Find all decisions about X"**
```bash
imem search develop "X" --decisions --limit 20
```

**"What did we decide in conversation Y?"**
```bash
imem search conversations "decision" --session <id> --messages-only
```

**"Show me all code patches for file.py"**
```bash
imem search conversations "" --file src/file.py --patches-only
```

**"Find language-agnostic patterns"**
```bash
imem search develop "error handling" --patterns --pattern
# Pattern layer only (*.pattern.md files)
```

**"Check collection status"**
```bash
imem collections list
# Shows registered collections (context + conversation per project)
# Plus orphaned collections ready for cleanup
```

**"Search recent work"**
```bash
# Index recent conversations first
imem index-all-conversations --recent 20

# Then search them
imem conversations search "topic"
```

**"Reconstruct decision narrative with context"**
```bash
# Get decision with genealogy and related patterns
imem compose '{
  "search": {"text": "authentication decision"},
  "discovery": {
    "genealogy": true,
    "siblings": {"section_types": ["Patterns", "Failures"]},
    "temporal": {"direction": "after"}
  },
  "output": {"template": "story-context"}
}'
```

**"Find what didn't work (anti-patterns)"**
```bash
# Surgical retrieval of failures with rationale
imem compose '{
  "search": {"text": "error handling"},
  "discovery": {
    "siblings": {
      "section_types": ["Failures"],
      "has_rationale": true,
      "order_by": "timestamp",
      "limit": 5
    }
  }
}'
```

**"Track evolution of approach over time"**
```bash
# Timeline of how solution evolved
imem compose '{
  "search": {"text": "API design"},
  "discovery": {"temporal": {"direction": "both"}},
  "output": {"template": "timeline"}
}'
```

## Troubleshooting

**"Cannot connect to Qdrant"**
```bash
imem service start
docker ps | grep qdrant
```

**"Collection not found"**
```bash
imem init  # Create dual collections and index changelogs
# Auto-creates on first use (no --force needed)
```

**"No results for conversation search"**
```bash
# Conversations not indexed yet
imem index-all-conversations --limit 10

# Check what's indexed
imem collections list
```

**"Wrong collection being searched"**
```bash
# Verify source routing
imem search develop "query"      # → context collection
imem search conversations "query" # → conversation collection
imem search context "query"       # → context collection (all phases)
```

**"Filters not working (--patches-only returns nothing)"**
```bash
# Old conversations don't have new metadata
# Re-index to get chunk_type, role, file_path fields
imem index-all-conversations --limit 100
```

**"Stale changelog results"**
```bash
imem update  # Re-index modified files
# or
imem init --force  # Full re-index
```

## Architecture

**Vector models:**
- Default (new collections): `nomic-ai/nomic-embed-text-v1.5` (768D, 8k tokens)
- Legacy (auto-detected): `intfloat/e5-large-v2` (1024D, 512 tokens)
- Smart fallback: Reads collection vector config to load correct model
- CPU inference (~200ms per batch)

**Qdrant configuration:**
- HNSW index for fast nearest-neighbor search
- Parameters: m=16, ef_construct=100
- Named vector: "e5-large-v2"
- Distance metric: Cosine similarity

**Chunking strategy:**
- **Changelogs**: H3 boundaries (semantic units with Context/Solution/Rationale)
  - Content-length filter: <20 chars → skips empty H2 parent headers
  - Indexes substantive H2 sections (Overview, Request with prose)
- **Conversations**: H2 boundaries (messages and patches)
- Preserves complete decision/message context per chunk

**Metadata enrichment:**
- **Changelogs**: Extract from frontmatter + path + filename
- **Conversations**: Parse from H2 header strings
- Zero manual metadata - all derived from structure

## Tips

**Phrase queries semantically:**
- Good: "authentication implementation"
- Better: "user authentication and session management"
- Best: "secure token validation patterns"

**Use section filters:**
- `--decisions` for architectural choices
- `--patterns` for reusable solutions
- `--failures` for what didn't work

**Combine with TRACE:**
- TRACE: Find conversations by time/content
- IMEM: Semantic search within conversations
- Use both for comprehensive discovery

**Pattern layer:**
- `.pattern.md` files = language-agnostic knowledge
- Use `--pattern` flag to filter to these only
- Useful for cross-project pattern learning

## FlexGraph Compositional Retrieval

### Overview
FlexGraph enables flexible composition of discovery primitives for surgical knowledge retrieval. Instead of prescribing fixed query patterns, four orthogonal primitives compose via declarative JSON.

### Discovery Primitives

**siblings** - Related sections from same document
- Parameters: `section_types`, `order_by`, `limit`, `has_rationale`, `has_alternatives`
- Example: Get top 3 Failures with rationale
- Config: `{"siblings": {"section_types": ["Failures"], "limit": 3, "has_rationale": true}}`
- Backward compatible: `{"siblings": true}` still works (converts to dict internally)

**genealogy** - Origin conversation via session_id linking
- Reconstructs discussion that led to decision
- Config: `{"genealogy": true}`

**temporal** - Evolution chain via timestamp + semantic similarity
- Parameters: `direction` ("after", "before", "both")
- Finds how approach changed over time
- Config: `{"temporal": {"direction": "after"}}`

**cross_phase** - Related decisions across phases
- Links design → develop → document
- Config: `{"cross_phase": true}`

### Compose Pipeline

Four-stage execution:
1. **Search** - Semantic retrieval of base results
2. **Discovery** - Enrich each result with primitive data
3. **Graph** (optional) - Apply PageRank/centrality scoring
4. **Template** - Render with context-aware structure

### Templates

**story-context.j2** - Narrative reconstruction with genealogical indicators
- 🟢 Current thrust (zero later chunks, continuation_count = 0)
- ⚠️ Evolved (1-2 later chunks, continuation_count = 1-2)
- 🔴 Superseded (3+ later chunks, continuation_count >= 3)
- ❌ Failed approaches (from Failures sections, explicit "Don't Suggest" warnings)
- Section order: Failures → Patterns → Decisions
- Temporal position detection: Counts chunks after target timestamp

**timeline.j2** - Evolution timeline showing approach changes

**anti-patterns.j2** - Failed approaches with don't-suggest warnings

### Composition Examples

See Common Workflows section above for practical examples of:
- Narrative reconstruction
- Anti-pattern discovery
- Evolution tracking

### Observable Usage Pattern

System tracks composition patterns by hashing discovery config. Detects recurring usage (10/15/20/30 times) and suggests preset creation as slash commands. Preset library grows organically from proven patterns.

## See Also

- `/trace` - Export conversations for indexing
- `/log:develop` - Create indexed changelogs
