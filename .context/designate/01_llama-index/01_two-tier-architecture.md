---
type: "designate.architecture"
status: "staged"
timestamp: "2025-10-23T19:30:00"
version: "v3.0"
---

# Two-Tier LlamaIndex Architecture

**Staged Execution Plan for AURA's Vector Search System**

_Consolidates design R&D for Phase 5A+B implementation_

---

## Executive Summary

AURA uses LlamaIndex MarkdownNodeParser to provide section-level retrieval across two distinct knowledge tiers:

**Tier 1 (Changelogs):** H3-level chunking (~15 vectors/doc) for surgical retrieval across lifecycle phases
**Tier 2 (Conversations):** H2-level chunking (~5 vectors/conversation) for semantic discovery

Both indexed in Qdrant, both searchable with phase/section filters, maintaining clean microservices separation.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│ SOURCE DATA (File-Based)                                │
├─────────────────────────────────────────────────────────┤
│ Tier 1: Changelogs                                      │
│   .context/design/.changes/*.md     (exploration)       │
│   .context/designate/*.md           (ground truth)      │
│   .context/develop/.changes/*.md    (validated)         │
│   .context/document/*.md            (stable)            │
│                                                          │
│ Tier 2: Conversations                                   │
│   ~/.claude/projects/*/*.jsonl      (raw)               │
│   → TRACE exports to structured markdown                │
└─────────────────┬───────────────────────────────────────┘
                  │
                  │ Read & Parse
                  ▼
┌─────────────────────────────────────────────────────────┐
│ PARSING LAYER (LlamaIndex)                             │
├─────────────────────────────────────────────────────────┤
│ MarkdownNodeParser                                      │
│                                                          │
│ Tier 1 Chunking:                                        │
│   H1 → Document root                                    │
│   H2 → Section parent (Decisions, Implementation)       │
│   H3 → Individual items (1 vector each)                 │
│                                                          │
│ Tier 2 Chunking:                                        │
│   H1 → Conversation root                                │
│   H2 → Section (User Messages, Code Changes, Tools)     │
│   (1 vector per H2)                                     │
└─────────────────┬───────────────────────────────────────┘
                  │
                  │ Generate embeddings (E5-Large-v2)
                  ▼
┌─────────────────────────────────────────────────────────┐
│ INDEX LAYER (Qdrant Vector Database)                   │
├─────────────────────────────────────────────────────────┤
│ Collection: institutional_memory                        │
│                                                          │
│ Points (Vectors):                                       │
│   - Vector: 1024D E5-Large embedding                    │
│   - Payload: Rich metadata (see schema below)           │
│                                                          │
│ Indexed Fields:                                         │
│   - source: 'changelog' | 'conversation'                │
│   - phase: 'design' | 'designate' | 'develop' | 'doc'   │
│   - section_type: Header path from markdown             │
│   - session_id: For conversations                       │
└─────────────────┬───────────────────────────────────────┘
                  │
                  │ Semantic search + filtering
                  ▼
┌─────────────────────────────────────────────────────────┐
│ SEARCH INTERFACE (IMEM CLI)                            │
├─────────────────────────────────────────────────────────┤
│ Phase Filtering:                                        │
│   imem search "query" --in develop                      │
│   imem search "query" --in design                       │
│   imem search "query" --in conversations                │
│                                                          │
│ Section Filtering:                                      │
│   imem search "query" --section "Decisions"             │
│   imem search "query" --section "User Messages"         │
│                                                          │
│ Combined:                                               │
│   imem search "auth" --in develop --section "Decisions" │
└─────────────────────────────────────────────────────────┘
```

---

## Two-Tier Strategy

### Tier 1: Changelogs (Precision)

**Source:** `.context/**/*.md` (design, designate, develop, document)

**Chunking:** H3-level (individual items)

**Vectors per document:** ~15 (varies by complexity)

**Use case:** "What did we decide about JWT authentication?"

**Query pattern:**
```bash
imem search "JWT" --in develop --section "Decisions"
```

**Returns:** Just the H3 sections about JWT decisions, not entire documents

**Why H3-level:**
- Surgical retrieval (find exact decision, not entire changelog)
- Hierarchical context (H3 → H2 → H1 relationships preserved)
- Progressive disclosure (simple docs = fewer vectors, complex = more)

### Tier 2: Conversations (Completeness)

**Source:** TRACE-exported structured markdown from JSONL conversations

**Chunking:** H2-level (major sections)

**Vectors per conversation:** ~5 (User Messages, Assistant Responses, Code Changes, Tools Used, Files Modified)

**Use case:** "What conversations discussed database design?"

**Query pattern:**
```bash
imem search "database" --in conversations --section "Code Changes"
```

**Returns:** Just the "Code Changes" sections from relevant conversations

**Why H2-level:**
- Broader discovery (find relevant conversations)
- Section-specific retrieval (just user questions, or just patches)
- Lower vector count (5 vs 15 for changelogs = faster indexing)

---

## Phase-Based Organization

### Four Lifecycle Phases

**design:** R&D exploration, experimental ideas, planning
- `.context/design/.changes/` - Sequential exploration sessions
- `.context/design/.modules/` - Experimental frameworks (may fail)
- May flow directly to `develop` or consolidate in `designate` first

**designate:** Sprint/implementation plans (staging area)
- `.context/designate/` - Aggregated, consolidated execution plans
- Used when design R&D needs clarification/consolidation before development
- Optional stage: `design → designate → develop` OR `design → develop`
- NOT ground truth (develop is truth), but staged plans for execution

**develop:** Validated changelogs, implementation records
- `.context/develop/.changes/` - What actually happened (user-validated)
- `.context/develop/.modules/` - New proven patterns
- Source of truth for what was built

**document:** Stable, integrated documentation
- `.context/document/` - Current authoritative state

**conversations:** Raw source material
- TRACE-parsed JSONL conversations exported as structured markdown

### Phase Semantics

**Filter by phase to control knowledge lifecycle:**

```bash
# Stable, authoritative docs
imem search "architecture" --in document

# Validated implementations (source of truth)
imem search "auth" --in develop

# Staged execution plans
imem search "sprint" --in designate

# Exploratory R&D and planning
imem search "alternatives" --in design

# Raw discussions
imem search "database" --in conversations
```

---

## Microservices Separation

### TRACE (Conversation Source)

**Owns:** JSONL parsing, conversation data
**Provides:** Structured markdown export
**Does NOT:** Index or search (IMEM's job)

**Workflow:**
```bash
# User triggers indexing
trace --index-all

# Behind the scenes:
# 1. TRACE exports conversation as structured markdown
# 2. TRACE calls: imem index-conversation <markdown-file>
# 3. IMEM parses with LlamaIndex
# 4. IMEM stores in Qdrant
```

### IMEM (Vector Search)

**Owns:** Embedding, indexing, semantic search
**Accepts data from:** Markdown files (changelogs, TRACE exports)
**Does NOT:** Parse JSONL or own source data

**Workflow:**
```bash
# Changelogs (automatic)
imem init --chunked

# Conversations (from TRACE)
imem index-conversation /tmp/conversation-abc123.md --session abc123
```

### Clean Separation

**TRACE = Source of truth** (conversations in JSONL)
**IMEM = Search index** (optimization layer)

**They communicate via structured markdown files** (not direct coupling)

---

## Chunking Strategy by Document Type

### Changelogs: H1 → H2 → H3 Hierarchy

**Template structure** (from 251008-1040):
```markdown
# Changelog Title                    ← H1 (root node)

## Decisions                          ← H2 (section parent)
### Use JWT over Sessions             ← H3 (1 vector)
**Context:** ...
**Solution:** ...
**Trade-offs:** ...

### Implement Rate Limiting            ← H3 (1 vector)
**Context:** ...
**Solution:** ...

## Implementation                     ← H2 (section parent)
### Token Validation Middleware       ← H3 (1 vector)
**Code Signature:**
```python
def verify_token(request):
    ...
```
```

**Result:** Each H3 = 1 vector with complete context (Context + Solution + Trade-offs combined)

**Why not per-field chunking:** Query "JWT decision" needs full decision context, not isolated "Solution" field

### Conversations: H2 Sections

**TRACE structured export:**
```markdown
# Conversation: abc123               ← H1 (root node)

## User Messages                      ← H2 (1 vector)
- "How do we implement JWT?"
- "What about session cookies?"

## Assistant Responses                ← H2 (1 vector)
Here's the approach...
[Full assistant responses]

## Code Changes                       ← H2 (1 vector)
### auth/middleware.py
```diff
+ def verify_token(request):
```

## Tools Used                         ← H2 (1 vector)
- Edit: 12×
- Bash: 5×

## Files Modified                     ← H2 (1 vector)
- auth/middleware.py
- tests/test_auth.py
```

**Result:** Each H2 section = 1 vector (~5 vectors per conversation)

**Why H2 not H3:** Conversations are less structured than changelogs; H2 provides sufficient granularity

---

## Metadata Enrichment

### LlamaIndex Auto-Extracted

**From MarkdownNodeParser:**
- `header_path`: "Decisions > Use JWT over Sessions"
- `header_level`: 3 (for H3)
- `node_type`: "heading"
- `parent_node_id`: UUID of parent H2

### Custom Added at Index Time

**For all documents:**
- `source`: 'changelog' | 'conversation'
- `section_type`: Extracted from header_path
- `section_level`: Same as header_level
- `content`: Node text
- `file_path`: Source file location

**For changelogs only:**
- `phase`: 'design' | 'designate' | 'develop' | 'document'
- `category`: Extracted from frontmatter `type` field (e.g., "implementation")
- `subtype`: Extracted from `type` after dot (e.g., "security")
- `timestamp`: From frontmatter

**For conversations only:**
- `session_id`: UUID from TRACE
- `start_time`: Conversation start timestamp
- `duration_minutes`: Conversation length
- `message_count`: Total messages
- `has_changelog`: Boolean (linked to Tier 1)
- `changelog_path`: Link to validated changelog (if exists)

---

## Bidirectional Linking

### Changelog → Conversation

**Frontmatter includes:**
```yaml
---
session_id: abc123def456
---
```

**User workflow:**
```bash
# Reading changelog, see session_id
cat .context/develop/.changes/251023-1930_abc123.md

# Jump to source conversation
trace --session abc123 --export full.md
```

### Conversation → Changelog

**Metadata includes:**
```python
{
    'has_changelog': True,
    'changelog_path': '.context/develop/.changes/251023-1930_abc123.md'
}
```

**User workflow:**
```bash
# Search conversations
imem search "auth" --in conversations

# Result shows: has_changelog: ✅
# Click changelog_path to see validated knowledge
```

---

## Progressive Disclosure

### Changelog Complexity Varies Naturally

**Simple changelog** (44 lines):
- ~6 nodes (1 root + 2 H2 + 3 H3)
- Minimal work → minimal vectors

**Complex changelog** (171 lines):
- ~25 nodes (1 root + 5 H2 + 19 H3)
- Complex work → more vectors

**No manual tuning needed:** Document complexity naturally determines vector count

### Conversation Sections Consistent

**All conversations:** ~5 vectors (H2 sections)
- User Messages
- Assistant Responses
- Code Changes
- Tools Used
- Files Modified

**Sections may be empty** (e.g., no code changes), but structure is consistent

---

## Query Patterns Enabled

### 1. Phase-Scoped Discovery

```bash
# Find validated decisions
imem search "JWT" --in develop

# Find ground truth specs
imem search "schema" --in designate

# Find explorations
imem search "alternatives" --in design
```

### 2. Section-Level Surgical Retrieval

```bash
# Just decisions (not implementation details)
imem search "rate limiting" --section "Decisions"

# Just user questions (not assistant responses)
imem search "database" --in conversations --section "User Messages"

# Just code changes
imem search "middleware" --section "Code Changes"
```

### 3. Combined Filters

```bash
# Validated decisions only
imem search "auth" --in develop --section "Decisions"

# Recent conversation code changes
imem search "JWT" --in conversations --section "Code Changes"
```

### 4. Cross-Tier Discovery

```bash
# Search everything
imem search "authentication"

# Returns: Ranked mix of changelog sections + conversation sections
```

---

## Performance Characteristics

### Indexing Performance

**Changelogs:**
- H3-level chunking: ~15 vectors per document
- Indexing time: ~30 seconds per document (embedding generation)
- Re-indexing: Only changed files (content-hash deduplication)

**Conversations:**
- H2-level chunking: ~5 vectors per conversation
- Indexing time: ~10 seconds per conversation
- Batch indexing: ~30 conversations in 5 minutes

### Search Performance

**Vector search:** <100ms (Qdrant HNSW index)
**Metadata filtering:** <10ms overhead (indexed fields)
**Section retrieval:** Returns 1-3 sections vs entire documents (10-50× smaller)

### Storage Requirements

**Per changelog:** ~75KB (15 vectors × 4KB + metadata)
**Per conversation:** ~25KB (5 vectors × 4KB + metadata)
**100 changelogs + 50 conversations:** ~8.75MB total

---

## Implementation Status

### ✅ Already Implemented (v3.0)

- TRACE JSONL parsing
- TRACE structured markdown export
- IMEM basic indexing
- Qdrant integration
- E5-Large embeddings
- Deduplication

### 🔄 Phase 5A+B (In Progress)

- LlamaIndex MarkdownNodeParser integration
- Section-level chunking (H2/H3)
- Phase extraction from file paths
- Metadata enrichment (phase, section_type)
- CLI filters (--in, --section)
- Conversation indexing pipeline

### ⏳ Future Enhancements

- Hybrid scoring (semantic + recency + complexity)
- Cross-section queries
- Parent-child node traversal
- Code snippet detection across document space

---

## Design Principles

### 1. Form Follows Function

**Changelogs are structured → H3-level chunking**
**Conversations are fluid → H2-level chunking**

Different artifacts get different chunking strategies.

### 2. Separation of Concerns

**TRACE:** Owns conversation data (JSONL)
**IMEM:** Owns search index (vectors)
**Communication:** Via structured markdown (not coupling)

### 3. Progressive Disclosure

**Simple work → fewer vectors**
**Complex work → more vectors**

No manual tuning, complexity emerges naturally from document structure.

### 4. Metadata-Rich Indexing

**Every vector has rich context:**
- What phase (design/develop/document)
- What section (Decisions/Implementation)
- What source (changelog/conversation)
- What relationships (session_id, changelog_path)

Enables surgical, precise queries.

---

## Next Steps

**Phase 5A+B Implementation:**

1. Add LlamaIndex to IMEM dependencies
2. Implement section-level chunking in ingestion
3. Add phase extraction from file paths
4. Implement CLI filters (--in, --section)
5. TRACE structured markdown export
6. Conversation indexing integration

**Estimated effort:** ~125 lines, 4-6 hours

**Result:** Complete two-tier architecture operational with section-level retrieval across all knowledge sources.

---

## References

- `251008-1040_changelog-template-llamaindex-alignment.md` - Template design
- `251007-1801/imem-new-structure.md` - Phase organization
- `251018-2030_imem-vector-search-audit.md` - Gap analysis
- ARCHITECTURE.md - v3.0 microservices specification
