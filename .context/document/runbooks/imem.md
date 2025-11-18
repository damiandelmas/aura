# IMEM - Semantic Search for Institutional Memory

**For AI agents.**

IMEM provides semantic search across changelogs and conversations using Qdrant vector database with Nomic Embed v1.5 (default) or E5-Large-v2 (legacy).

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

# Check what's indexed
imem introspect --status
imem introspect --fields

# Search changelogs (Best: Decisions/Patterns sections)
imem search develop "authentication decisions" --section "Decisions"
imem search develop "retry patterns" --section "Patterns"

# Search conversations (Good: code patches)
imem search conversations "bug fix" --chunk-type patch

# Compositional retrieval (Direct JSON)
imem compose '{"search": {"text": "JWT"}, "discovery": {"siblings": true, "genealogy": true}}'
```

## Quality Hierarchy

**Best:** develop/design docs with `--section Decisions|Patterns|Implementation`
**Good:** Code patches from conversations
**Bad:** User messages (hit or miss)
**Useless:** Thinking chunks (never use `--chunk-type thinking`)

## Introspection (Start Here)

Before querying, discover what's available:

```bash
# Check what's indexed
imem introspect --status
# Shows: 3608 context chunks, 1357 conversation chunks, which phases indexed

# See available filters
imem introspect --fields
# Shows all filterable metadata fields, values, what you can filter on

# System overview
imem introspect
# Shows: primitives, coverage stats, top concepts, quick start examples
```

**Use case:** Run `imem introspect --fields` before writing queries to see available filters

## Service Management

**Start Qdrant:**
```bash
imem service start
# Starts Docker container on port 6334
# Persists data to ~/.context/qdrant_storage/
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
imem search develop "database" --section "Decisions"
imem search develop "API limits" --section "Constraints"
imem search develop "retry logic" --section "Patterns"
```

**Filter by layer:**
```bash
imem search develop "error handling" --layer pattern
# Only searches .pattern.md files (language-agnostic)
```

**Combined filters:**
```bash
imem search develop "async operations" --section "Decisions" --layer pattern
# Decisions from pattern layer only
```

## Searching Conversations

**Basic search:**
```bash
imem search conversations "bug in authentication"
# Searches conversation collection
# Returns messages + patches
```

**Filter by section type:**
```bash
imem search conversations "error handling" --section "User Messages"
# Only searches user messages

imem search conversations "bug fix" --section "Code Patches"
# Only searches code patches
```

**Note:** Conversation chunks are indexed by H2 sections. Use `--section` to filter by section type (e.g., "Message 1: USER", "Code Patch 1: src/cli.py"). For surgical filtering, use compose with discovery primitives.

**Filter by session:**
```bash
imem search conversations "database" --session cb91d93d
# Searches specific conversation only
```

**Combined filters:**
```bash
imem search conversations "auth bug" --section "Code Patches" --session abc123
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

**Index a conversation:**
```bash
imem index-conversation <session-id>
# TRACE export happens automatically - no manual export needed
```

**Search across both:**
```bash
# Find decisions in changelogs
imem search develop "auth decisions" --section "Decisions"

# Find how we discussed it in conversation
imem search conversations "auth discussion" --session <id>
```

## Performance

**Indexing speed:**
- Changelogs: ~100 docs in 30-60 seconds
- Conversations: ~1 conversation per 5-10 seconds (depends on size)

**Search speed:**
- 40-80ms p50, 120ms p99 (500+ doc collections)
- HNSW optimization: m=16, ef_construct=100, on_disk=False

**Storage:**
- Embeddings: ~3KB per section (768-dim Nomic) or ~4KB (1024-dim E5)
- Location: `~/.context/qdrant_storage/`
- Dual collections per project (context + conversation)

## Common Workflows

**"Find all decisions about X"**
```bash
imem search develop "X" --section "Decisions" --limit 20
```

**"What did we decide in conversation Y?"**
```bash
imem search conversations "decision" --session <id>
```

**"Show me all code patches"**
```bash
imem search conversations "code" --section "Code Patches"
```

**"Find language-agnostic patterns"**
```bash
imem search develop "error handling" --section "Patterns" --layer pattern
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
imem search conversations "topic"
```

**"Reconstruct decision narrative with context"**
```bash
# Get decision with genealogy and related patterns
imem compose '{
  "search": {"text": "authentication decision"},
  "discovery": {
    "genealogy": {"direction": "ancestors", "limit": 5},
    "siblings": {"section_types": ["Patterns", "Failures"], "limit": 3},
    "temporal": {"direction": "after", "limit": 3}
  }
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
  "discovery": {"temporal": {"direction": "both", "limit": 5}}
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

**"Filters not working (no section matches)"**
```bash
# Check what sections exist in your conversations
imem search conversations "" --limit 5 --show-metadata

# Conversations are chunked by H2 headers
# Section names like "Message 1: USER", "Code Patch 1: src/cli.py"
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
- Named vectors: "nomic-embed-text-v1.5" (default) or "e5-large-v2" (legacy)
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

**Start with introspection:**
- Run `imem introspect --fields` to see available filters
- Check `imem introspect --status` for coverage stats
- Understand what's indexed before querying

**Phrase queries semantically:**
- Good: "authentication implementation"
- Better: "user authentication and session management"
- Best: "secure token validation patterns"

**Use section filters for quality:**
- `--section "Decisions"` for architectural choices
- `--section "Patterns"` for reusable solutions
- `--section "Failures"` for what didn't work
- `--chunk-type patch` for code changes only (avoid `thinking`)

## Compositional Retrieval (Advanced)

### Discovery Primitives

Four orthogonal primitives compose via declarative JSON for surgical knowledge retrieval:

**siblings** - Related sections from same document
- Parameters: `section_types`, `order_by`, `limit`, `has_rationale`, `has_alternatives`
- Example: Get top 3 Failures with rationale
- Config: `{"siblings": {"section_types": ["Failures"], "limit": 3, "has_rationale": true}}`
- Backward compatible: `{"siblings": true}` still works (converts to dict internally)
- **Coverage:** 100% (requires `file_path` metadata)
- **Empty result when:** Target is only section in file (expected behavior)

**genealogy** - Origin conversation via session_id linking
- Reconstructs discussion that led to decision
- Config: `{"genealogy": {"direction": "ancestors", "limit": 5}}`
- **Coverage:** Low initially (5% typical)
- **Action needed:** Run `imem index-all-conversations` to index missing sessions
- **Expected:** Near 100% coverage after full indexing (~10 min)

**temporal** - Evolution chain via timestamp + semantic similarity
- Parameters: `direction` ("after", "before", "both")
- Finds how approach changed over time
- Config: `{"temporal": {"direction": "after", "limit": 3}}`
- **Threshold:** 0.65 similarity (lowered from 0.85 to match typical 0.6-0.7 evolution scores)
- **Coverage:** 54% context chunks, 100% conversations
- **Missing timestamps:** Chunks without timestamps still returned (no time filtering)

**cross_phase** - Related decisions across phases
- Links design → develop → document
- Config: `{"cross_phase": {"phase": "develop"}}`
- **Syntax:** Must use dict format `{"phase": "develop"}`, not boolean
- **Coverage:** 100% (requires `phase` metadata)

### Multi-Source Composition

Cross-collection queries in single call:

```bash
# Cross-phase batch (develop + design)
imem compose '{
  "search": {
    "queries": [
      {"text": "routing", "filters": {"source": "context", "phase": "develop"}, "limit": 2},
      {"text": "routing", "filters": {"source": "context", "phase": "design"}, "limit": 2}
    ]
  }
}'

# Context + related decisions (siblings)
imem compose '{
  "search": {
    "text": "FlexGraph primitives",
    "filters": {"source": "context", "phase": "develop"},
    "limit": 1
  },
  "discovery": {
    "siblings": {"limit": 3, "section_types": ["Decisions", "Patterns"]}
  }
}'

# Trace conversation origins (genealogy)
imem compose '{
  "search": {"text": "routing decision", "filters": {"phase": "develop"}, "limit": 1},
  "discovery": {"genealogy": {"direction": "ancestors", "limit": 5}}
}'

# Track evolution (temporal)
imem compose '{
  "search": {"text": "routing", "limit": 1},
  "discovery": {
    "temporal": {"direction": "both", "limit": 3}
  }
}'
```

### When to Use What

**Use `imem search`** when:
- Simple keyword lookup
- Single source/phase filter
- Just need top results

**Use `imem compose`** when:
- Cross-phase queries (design + develop)
- Need graph relationships (siblings, genealogy, cross_phase)
- Multi-source batch queries
- Tracing decision lineage

### Discovery-Driven Approach

System exposes primitives and compose JSON interface without prescribing patterns. Patterns emerge through usage rather than premature codification. Honest empty JSON preferred over confident falsehoods.

## See Also

- `/trace` - Export conversations for indexing
- `/log:develop` - Create indexed changelogs
