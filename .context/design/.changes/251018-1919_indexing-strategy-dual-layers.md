# Indexing Strategy: Dual-Layer Vector Retrieval

**Date:** 2025-10-18 19:19
**Type:** Technical Specification
**Status:** Active Design

---

## Overview

IMEM indexes two distinct artifact types with different strategies:

**Tier 1: Changelogs** - Section-level chunking, RAG-optimized, ~15 vectors per document
**Tier 2: Conversations** - Summary-level indexing, 1 vector per conversation

Both stored in Qdrant, both searchable with metadata filtering, but fundamentally different indexing approaches.

---

## Tier 1: Changelog Indexing (High-Fidelity)

### What Gets Indexed

**Source directories:**
```
.context/design/.changes/      # Design exploration
.context/designate/            # Ground truth specifications
.context/develop/.changes/     # Implementation changelogs (user validated)
.context/document/             # Maintained documentation
```

**File format:** Markdown with H1→H2→H3 hierarchy

**Validation status:** User-approved via `/log:develop` (for develop/.changes/)

### Indexing Strategy: Section-Level Chunking

**Parser:** LlamaIndex MarkdownNodeParser

**Chunking granularity:** H3-level (each H3 section becomes one vector)

**Example document structure:**

```markdown
# PostgreSQL Schema Design for Authentication

**Session:** abc123def456
**Date:** 2025-10-18
**Phase:** Implementation

## Problem Statement

### Business Requirement
User authentication system with role-based access control...
→ VECTOR 1 (metadata: section_type='problem', h2='Problem Statement')

### Technical Constraints
- Must support 10K concurrent sessions
- Sub-100ms auth check latency
→ VECTOR 2 (metadata: section_type='constraint', h2='Problem Statement')

## Solution Architecture

### Core Decision: PostgreSQL over MongoDB
Chose PostgreSQL for ACID guarantees and complex joins...
→ VECTOR 3 (metadata: section_type='decision', h2='Solution Architecture')

### Implementation Pattern
Token-based auth with JWT:
- jwt.encode(payload, secret)
- Middleware: verify_token(request.headers['Authorization'])
→ VECTOR 4 (metadata: section_type='implementation', h2='Solution Architecture')

## Trade-offs Considered

### Alternative 1: MongoDB
Considered document store for flexibility...
Rejected due to: weak consistency, no joins
→ VECTOR 5 (metadata: section_type='alternative', h2='Trade-offs Considered')

### Alternative 2: Redis Sessions
Evaluated in-memory sessions...
Rejected due to: stateful architecture, scaling concerns
→ VECTOR 6 (metadata: section_type='alternative', h2='Trade-offs Considered')
```

**Result:** 6 vectors from one document, each focused on a specific section.

### Metadata Schema

**Each vector (H3 chunk) has rich metadata:**

```python
{
    # Document-level metadata
    'type': 'changelog',
    'phase': 'develop',  # design | designate | develop | document
    'session_id': 'abc123def456',  # LINK TO CONVERSATION
    'timestamp': '2025-10-18T15:38:00',
    'file_path': '.context/develop/.changes/251018-1538_abc123.md',
    'conversation_file': '~/.claude/projects/.../abc123.jsonl',

    # Section-level metadata (enables surgical retrieval)
    'h1_title': 'PostgreSQL Schema Design for Authentication',
    'h2_category': 'Solution Architecture',
    'h3_title': 'Core Decision: PostgreSQL over MongoDB',
    'section_type': 'decision',  # problem | constraint | decision | implementation | alternative | pattern

    # Categorization
    'category': 'database',  # architecture | security | performance | etc.
    'subcategory': 'schema-design',
    'tags': ['postgresql', 'authentication', 'jwt'],

    # Content
    'content': 'Chose PostgreSQL for ACID guarantees...',  # The actual H3 text

    # Hierarchy (for parent-child relationships)
    'parent_h2': 'Solution Architecture',
    'sibling_h3s': ['Implementation Pattern', 'Security Considerations'],

    # Metrics
    'word_count': 150,
    'complexity': 'medium'  # Inferred from field count (2-6 fields)
}
```

### Why Section-Level Chunking?

**Query:** "What database constraints influenced the auth design?"

**Without section chunking:**
```python
# Returns entire changelog document (2000 words)
results = imem.search("database constraints auth design")
# User must read everything to find constraint sections
```

**With section chunking:**
```python
# Returns only H3 sections under "Technical Constraints"
results = imem.search(
    "database constraints auth design",
    filter={'section_type': 'constraint'}
)
# Surgical precision: just the 2-3 constraint items
```

**Benefit:** 10x faster to find specific information.

### Search Patterns for Changelogs

**1. Section-type filtering:**
```python
# Find all decisions about authentication
imem.search("authentication", filter={'section_type': 'decision'})

# Find all constraints (across all changelogs)
imem.search("performance", filter={'section_type': 'constraint'})

# Find implementation patterns
imem.search("JWT", filter={'section_type': 'implementation'})
```

**2. Phase filtering:**
```python
# Search only validated implementations
imem.search("database design", filter={'phase': 'develop'})

# Search ground truth specifications
imem.search("API schema", filter={'phase': 'designate'})

# Search design exploration
imem.search("alternatives considered", filter={'phase': 'design'})
```

**3. Category filtering:**
```python
# Security-related decisions
imem.search("auth", filter={'category': 'security', 'section_type': 'decision'})

# Performance trade-offs
imem.search("latency", filter={'category': 'performance', 'section_type': 'alternative'})
```

**4. Time-based filtering:**
```python
# Recent architecture changes
imem.search("schema", filter={'phase': 'develop', 'after': '2025-10-01'})
```

**5. Hierarchical retrieval:**
```python
# Get parent context
result = imem.search("JWT implementation")
h2_category = result.metadata['parent_h2']  # "Solution Architecture"
# Fetch all H3s under this H2 for full context
```

### Progressive Disclosure in Metadata

**Changelogs adapt field count to complexity:**

**Simple changelog (2 fields):**
```yaml
sections:
  - Problem Statement (1 H3)
  - Solution (1 H3)
# → 2 vectors total
```

**Medium changelog (4 fields):**
```yaml
sections:
  - Problem Statement (2 H3s: Business + Technical)
  - Solution Architecture (3 H3s: Decision + Implementation + Security)
  - Files Changed (1 H3)
# → 6 vectors total
```

**Complex changelog (6 fields):**
```yaml
sections:
  - Problem Statement (3 H3s: Business + Technical + Constraints)
  - Solution Architecture (4 H3s: Decisions + Patterns + Implementation + Testing)
  - Trade-offs (3 H3s: Alternative 1 + Alternative 2 + Rationale)
  - Implementation Details (2 H3s: Code + Integration)
  - Files Changed (1 H3)
  - Future Work (2 H3s: Tech Debt + Enhancements)
# → 15 vectors total
```

**Metadata includes:**
```python
{
    'complexity': 'simple' | 'medium' | 'complex',
    'field_count': 2 | 4 | 6,
    'vector_count': 2-15
}
```

**Search benefit:** Can filter by complexity.
```python
# Find complex implementations (detailed docs)
imem.search("authentication", filter={'complexity': 'complex'})
```

---

## Tier 2: Conversation Indexing (Source Material)

### What Gets Indexed

**Source:** Claude Code conversation files (`~/.claude/projects/*.jsonl`)

**Content indexed:** Summaries only (200-500 words), NOT full transcripts

**Validation status:** Raw material (no user validation)

### Indexing Strategy: Summary-Level

**Parser:** ConversationRetrieval.get_summary()

**Chunking granularity:** One vector per conversation (entire summary)

**Example conversation summary:**

```
Session: abc123def456
Duration: 141 minutes
Messages: 591 (297 user + 294 assistant)

Discussion about PostgreSQL schema design for authentication system.
Explored alternatives (MongoDB, Redis sessions) before settling on
PostgreSQL with JWT tokens. Key constraints: 10K concurrent users,
sub-100ms auth latency. Implemented token-based middleware with
refresh strategy. Tested with pytest, deployed to staging.

Tools used: Read (23), Edit (45), Bash (12)
Files modified: auth/middleware.py, auth/models.py, tests/test_auth.py
```

**Result:** 1 vector containing 200-500 word summary.

### Metadata Schema

**Each conversation has:**

```python
{
    # Identifier
    'type': 'conversation',
    'session_id': 'abc123def456',

    # Temporal
    'start_time': '2025-10-18T13:15:00',
    'end_time': '2025-10-18T15:36:00',
    'duration_minutes': 141,

    # Content metrics
    'message_count': 591,
    'user_messages': 297,
    'assistant_messages': 294,
    'tool_uses': 187,
    'file_operations': 89,
    'patch_count': 45,

    # Context
    'working_directory': '/home/user/projects/app',
    'file_path': '~/.claude/projects/.../abc123.jsonl',

    # Bidirectional link
    'has_changelog': True,  # LINK TO CHANGELOG
    'changelog_path': '.context/develop/.changes/251018-1538_abc123.md',

    # Summary content
    'summary': 'Discussion about PostgreSQL schema design...',  # 200-500 words

    # Tools & files (for filtering)
    'tools_used': ['Read', 'Edit', 'Bash'],
    'files_modified': ['auth/middleware.py', 'auth/models.py', 'tests/test_auth.py'],
    'has_patches': True
}
```

### Why Summary-Level (Not Full Conversation)?

**Full conversation size:** 10,000-100,000 words
**Summary size:** 200-500 words
**Reduction:** 20-200x smaller

**Benefits:**

1. **Fast indexing:** 200x less data to embed
2. **Fast search:** Smaller vector space
3. **Lower cost:** Fewer tokens processed
4. **Semantic essence:** Summaries capture key points

**Drawback:** Loses detail

**Solution:** Full conversation available on demand via TRACE.

### Search Patterns for Conversations

**1. Semantic discovery:**
```python
# Find conversations about a topic
imem.search("database design discussions", filter={'type': 'conversation'})

# Returns: List of relevant conversation summaries
```

**2. Time-based discovery:**
```python
# Recent conversations about auth
imem.search("authentication", filter={
    'type': 'conversation',
    'after': '2025-10-01'
})
```

**3. Tool-based filtering:**
```python
# Conversations that modified files
imem.search("schema changes", filter={
    'type': 'conversation',
    'has_patches': True
})
```

**4. Linked changelog check:**
```python
# Find conversations that resulted in changelogs
imem.search("auth implementation", filter={
    'type': 'conversation',
    'has_changelog': True
})
```

**5. Complexity filtering:**
```python
# Long, complex conversations (more context)
imem.search("database", filter={
    'type': 'conversation',
    'duration_minutes > 60',
    'message_count > 100'
})
```

---

## Hybrid Scoring Strategy

### Beyond Semantic Similarity

**Base search:** Qdrant cosine similarity (0-1 score)

**Problem:** Recent but less-relevant results might be more useful than old but highly-relevant ones.

**Solution:** Hybrid scoring combining semantic + recency + complexity.

### Formula (Inspired by christian-byrne)

```python
final_score = (
    0.70 * semantic_similarity +   # Vector cosine similarity
    0.20 * recency_score +         # Time decay
    0.10 * complexity_score        # Content richness
)
```

### Implementation

```python
from datetime import datetime
import math

def hybrid_score(result, query_time=None):
    """Apply hybrid scoring to search results"""
    query_time = query_time or datetime.now()

    # Base semantic score from Qdrant
    semantic = result.score  # 0-1

    # Recency boost (exponential decay)
    start_time = datetime.fromisoformat(result.payload['start_time'])
    days_ago = (query_time - start_time).days
    recency = math.exp(-0.1 * days_ago)  # Decay factor: 0.1
    # Recent: 1.0, 7 days: 0.5, 30 days: 0.05

    # Complexity boost (more content = more context)
    if result.payload['type'] == 'conversation':
        msg_count = result.payload['message_count']
        complexity = min(msg_count / 100, 1.0)  # Cap at 100 messages
    else:  # changelog
        vector_count = result.payload.get('vector_count', 5)
        complexity = min(vector_count / 15, 1.0)  # Cap at 15 vectors

    return 0.7 * semantic + 0.2 * recency + 0.1 * complexity
```

### Use Cases

**Query:** "authentication design"

**Without hybrid scoring:**
```
Results (by semantic similarity only):
1. Old changelog from 2024-06-15 (score: 0.95)
2. Recent conversation from 2025-10-15 (score: 0.78)
3. Old conversation from 2024-08-20 (score: 0.82)
```

**With hybrid scoring:**
```
Results (hybrid):
1. Recent conversation from 2025-10-15 (hybrid: 0.85)
   - Semantic: 0.78, Recency: 0.95, Complexity: 0.8
2. Old changelog from 2024-06-15 (hybrid: 0.72)
   - Semantic: 0.95, Recency: 0.05, Complexity: 0.6
3. Old conversation from 2024-08-20 (hybrid: 0.68)
   - Semantic: 0.82, Recency: 0.15, Complexity: 0.9
```

**Recent + relevant now wins over old + highly relevant.**

### When to Use

**Enable hybrid scoring for:**
- Time-sensitive queries ("recent auth changes")
- Debugging (recent implementations more relevant)
- Iterative development (building on recent work)

**Disable for:**
- Historical analysis ("how did we approach X in 2024?")
- Pattern discovery (time doesn't matter)
- Comprehensive search (want all matches, regardless of date)

---

## Dual Collection Strategy

### Qdrant Collections

**Collection 1: `changelogs`**
```python
{
    'collection_name': 'changelogs',
    'vector_size': 1024,  # E5-large embeddings
    'distance': 'Cosine',

    'indexed_fields': [
        'type',           # Always 'changelog'
        'phase',          # design | designate | develop | document
        'section_type',   # problem | decision | constraint | implementation | alternative
        'category',       # architecture | security | performance
        'session_id',     # Link to conversation
        'timestamp'       # ISO format
    ]
}
```

**Collection 2: `conversations`**
```python
{
    'collection_name': 'conversations',
    'vector_size': 1024,  # E5-large embeddings
    'distance': 'Cosine',

    'indexed_fields': [
        'type',           # Always 'conversation'
        'session_id',     # Unique identifier
        'has_changelog',  # Boolean (link exists)
        'changelog_path', # Link to changelog
        'start_time',     # ISO format
        'duration_minutes',
        'message_count'
    ]
}
```

**Why separate collections?**

1. **Different schemas:** Changelogs have section_type, conversations don't
2. **Different querying:** Often search one OR the other, not both
3. **Performance:** Smaller collections = faster search
4. **Metadata filtering:** No type ambiguity

**Searching both:**
```python
# Search changelogs
changelog_results = qdrant.search(
    collection_name='changelogs',
    query_vector=embedding,
    filter={'phase': 'develop'},
    limit=5
)

# Search conversations
conversation_results = qdrant.search(
    collection_name='conversations',
    query_vector=embedding,
    filter={'has_changelog': False},  # Orphaned conversations
    limit=5
)

# Merge and re-rank by hybrid score
all_results = merge_and_rerank(changelog_results, conversation_results)
```

---

## Indexing Workflow

### Tier 1: Changelog Indexing (Existing)

**Trigger:** User runs `/log:develop` → changelog created

**Process:**

```python
# 1. ChangelogAgent creates changelog
changelog_path = '.context/develop/.changes/251018-1538_abc123.md'

# 2. IMEM ingests with LlamaIndex parser
from aura.services.imem import EnhancedModularIngest
from llama_index import MarkdownNodeParser

imem = EnhancedModularIngest()
parser = MarkdownNodeParser()

# Parse into H3-level nodes
nodes = parser.load_data(changelog_path)
# Result: ~15 nodes (H3 sections)

# 3. Embed each node
for node in nodes:
    vector = embedder.encode(node.text)  # E5-large

    # 4. Store in Qdrant
    qdrant.upsert(
        collection_name='changelogs',
        points=[{
            'id': uuid4(),
            'vector': vector.tolist(),
            'payload': {
                'type': 'changelog',
                'phase': extract_phase(changelog_path),
                'session_id': extract_session_id(node.metadata),
                'section_type': infer_section_type(node.h3_title),
                'h2_category': node.h2_title,
                'h3_title': node.h3_title,
                'content': node.text,
                'file_path': str(changelog_path),
                'timestamp': node.metadata['timestamp']
            }
        }]
    )
```

**Status:** ✅ Already implemented

### Tier 2: Conversation Indexing (In Progress)

**Trigger:** `trace --index-all` or `trace --index-recent 10`

**Process:**

```python
# 1. Discover conversations
from aura.services.trace import ConversationFinder, ConversationRetrieval

finder = ConversationFinder()
conversations = finder.list_all()  # or find_recent(n)

# 2. Extract summaries
for conv_file in conversations:
    retrieval = ConversationRetrieval()
    entries = retrieval.load_conversation(conv_file)
    summary_data = retrieval.get_summary(entries)

    # 3. Check if changelog exists
    session_id = summary_data['session_id']
    changelog_path = find_changelog_by_session(session_id)
    has_changelog = changelog_path is not None

    # 4. Embed summary
    summary_text = summary_data['summary']  # 200-500 words
    vector = embedder.encode(summary_text)

    # 5. Store in Qdrant
    qdrant.upsert(
        collection_name='conversations',
        points=[{
            'id': uuid4(),
            'vector': vector.tolist(),
            'payload': {
                'type': 'conversation',
                'session_id': session_id,
                'start_time': summary_data['start_time'].isoformat(),
                'duration_minutes': summary_data['duration_minutes'],
                'message_count': summary_data['message_count'],
                'working_directory': summary_data['working_directory'],
                'file_path': str(conv_file),

                # Bidirectional link
                'has_changelog': has_changelog,
                'changelog_path': str(changelog_path) if changelog_path else None,

                # Content
                'summary': summary_text,

                # Metadata
                'tools_used': extract_tools(entries),
                'files_modified': extract_files(entries),
                'has_patches': len(extract_patches(entries)) > 0
            }
        }]
    )
```

**Status:** 🔄 To be implemented (30 lines of code)

### Bidirectional Link Maintenance

**When changelog is created:**

```python
# Update conversation in Qdrant to link back to changelog
qdrant.update(
    collection_name='conversations',
    filter={'session_id': session_id},
    payload={
        'has_changelog': True,
        'changelog_path': changelog_path
    }
)
```

**When conversation is indexed:**

```python
# Changelog already has session_id (inserted during creation)
# No update needed
```

---

## Storage & Performance

### Tier 1: Changelogs

**Average changelog:**
- Size: 2000 words
- Vectors: ~15 (section-level chunks)
- Vector size: 1024 dimensions (E5-large)
- Storage per changelog: ~60KB vectors + ~10KB metadata

**100 changelogs:**
- Vectors: 1,500
- Storage: ~7MB

**Scalability:** Qdrant handles millions of vectors easily.

### Tier 2: Conversations

**Average conversation:**
- Summary: 300 words
- Vectors: 1 (summary-level)
- Vector size: 1024 dimensions
- Storage per conversation: ~4KB vector + ~2KB metadata

**1,000 conversations:**
- Vectors: 1,000
- Storage: ~6MB

**Scalability:** Trivial for Qdrant.

### Search Performance

**Qdrant benchmarks (1M vectors):**
- Query time: <50ms
- Memory usage: ~4GB
- Disk usage: ~2GB

**Our scale (10K vectors total):**
- Query time: <10ms
- Memory usage: <100MB
- Disk usage: ~50MB

**Performance is not a concern.**

---

## Comparison: Indexing Strategies

| Dimension | Tier 1 (Changelogs) | Tier 2 (Conversations) |
|-----------|---------------------|------------------------|
| **Content size** | 500-2000 words | 200-500 words (summary) |
| **Vectors per item** | ~15 (section-level) | 1 (summary-level) |
| **Chunking strategy** | H3-level (LlamaIndex) | Whole summary |
| **Metadata richness** | High (section_type, h2, h3) | Medium (timing, tools, files) |
| **Validation** | User validated | Raw material |
| **Search precision** | Surgical (section-level) | Broad (semantic discovery) |
| **Use case** | Find specific decisions | Find relevant conversations |
| **Storage per item** | ~60KB | ~4KB |
| **Implementation status** | ✅ Live | 🔄 In progress |

---

## Future Enhancements

### 1. Auto-Indexing on Changelog Creation

**Current:** Manual IMEM re-indexing after changelog creation

**Future:** Automatic indexing via PULSE hook
```python
# When changelog is created
def on_changelog_created(changelog_path):
    imem.index_document(changelog_path)
    print(f"✅ Indexed: {changelog_path}")
```

### 2. Incremental Conversation Indexing

**Current:** `trace --index-all` (full re-index)

**Future:** `trace --index-recent 5` (incremental)
```python
# Only index new conversations
last_indexed_time = get_last_index_time()
new_convs = finder.find_after(last_indexed_time)
index_conversations(new_convs)
```

### 3. Semantic Deduplication

**Current:** No deduplication

**Future:** Detect similar conversations before indexing
```python
# Check if similar conversation already indexed
similar = imem.search(new_summary, threshold=0.95)
if similar:
    print(f"⚠️ Similar conversation already indexed: {similar[0].id}")
    skip_or_merge()
```

### 4. Hybrid Scoring Tuning

**Current:** Fixed weights (0.7 semantic, 0.2 recency, 0.1 complexity)

**Future:** Configurable weights per query
```python
imem.search("auth", weights={'semantic': 0.9, 'recency': 0.1})  # Prioritize relevance
imem.search("recent changes", weights={'recency': 0.6, 'semantic': 0.4})  # Prioritize time
```

---

## Implementation Checklist

### Already Complete

- [x] Tier 1: Changelog section-level indexing
- [x] LlamaIndex MarkdownNodeParser integration
- [x] Metadata extraction (section_type, category, phase)
- [x] Qdrant collection setup
- [x] E5-large embeddings
- [x] Conversation summary extraction (TRACE)
- [x] Markdown export for agents

### In Progress

- [ ] Tier 2: Conversation summary indexing
- [ ] Bidirectional metadata linking
- [ ] Type filtering in search (`--type conversation`)
- [ ] Hybrid scoring implementation

### Future

- [ ] Auto-indexing on changelog creation
- [ ] Incremental conversation indexing
- [ ] Semantic deduplication
- [ ] Configurable hybrid scoring weights

---

## Summary

**The dual-layer indexing strategy provides:**

1. **Surgical precision** via section-level changelog chunking
2. **Semantic discovery** via summary-level conversation indexing
3. **Bidirectional navigation** via session_id linking
4. **Metadata filtering** for precise queries
5. **Hybrid scoring** for time-aware relevance

**Different artifacts get different treatment:**
- Changelogs: RAG-optimized, ~15 vectors, section-level
- Conversations: Simple, 1 vector, summary-level

**Form follows function. Right tool for the job.**
