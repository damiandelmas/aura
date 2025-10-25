# Tier 2 Conversation Indexing: Architecture Specification

**Date**: 2025-10-18
**Scope**: Conversation discovery and bidirectional changelog linking
**Status**: Designed but not implemented

---

## Executive Summary

This document specifies the **Tier 2 conversation indexing architecture** that enables bidirectional navigation between conversations and changelogs, completing AURA's two-tier institutional memory system.

**Key Capabilities to Be Built**:
- Semantic conversation discovery via IMEM vector search
- Bidirectional linking: Conversation ↔ Changelog
- Status visibility: Which conversations have been validated into changelogs
- Two-tier search: Changelogs (precision) OR Conversations (completeness)

**Estimated Implementation**: ~135 lines across 6 files, 4-6 hours

---

## 1. Functionality Gained

### Before (Current State)
- ❌ Can't search conversations semantically
- ❌ Can't discover "What conversations discussed database design?"
- ❌ Can't filter "Show me conversations that have changelogs"
- ❌ Don't know which conversations have been validated into changelogs
- ❌ Can't navigate from conversation → changelog (reverse direction)
- ❌ IMEM only searches changelogs, conversations are invisible

### After (Tier 2 Complete)
- ✅ Semantic conversation discovery: "Find conversations about authentication"
- ✅ Bidirectional navigation: Conversation ↔ Changelog (both directions work)
- ✅ Status visibility: See which conversations have changelogs
- ✅ Filtered search: "Show conversations WITH changelogs" or "WITHOUT changelogs"
- ✅ Two-tier search: Search changelogs (precision) OR conversations (completeness)
- ✅ Complete institutional memory: Nothing is lost, everything is discoverable

---

## 2. System Components to Modify

### A. Registry System (`.claude/.trace/registry.json`)

**Current Behavior**:
- Tracks session creation (SessionStart hook)
- Stores: `session_id`, `created`, `status`
- Never updated after creation

**Modifications Needed**:
- Update registry AFTER changelog creation
- Add 2 new fields:
  - `has_changelog`: boolean flag
  - `last_changelog`: path to most recent changelog

**Rationale**:
- Fast O(1) lookup: "Does session X have a changelog?"
- Lightweight metadata store (no vector search needed)
- Source of truth for changelog linking

**Implementation Location**: `src/orchestrator/registry.py`

---

### B. TRACE Service (Already Exists - Use As-Is)

**Current Capabilities**:
- Parses `~/.claude/projects/*.jsonl` files
- `get_summary()` extracts metadata (message_count, duration, summary text)
- Exports conversations to markdown

**Usage for Tier 2**:
- `ConversationFinder.list_all()` → Discover all conversations
- `ConversationRetrieval.get_summary()` → Get 200-500 word summary + metadata
- No changes needed, just consumption

**Why No Changes**:
- Already implemented ✅
- Returns exactly what we need for indexing
- Battle-tested (29+ sessions parsed successfully)

---

### C. IMEM Ingestion Pipeline (`aura-v2/src/aura/services/imem/`)

**Current Behavior**:
- Ingests markdown files (changelogs, documents)
- Generates embeddings (E5-large model)
- Stores in Qdrant with minimal metadata
- Only indexes files, not conversations

**Modifications Needed**:
- Add new ingestion path: `ingest_conversation_summary()`
- Read from TRACE (summary text)
- Read from Registry (has_changelog, changelog_path)
- Combine into single payload
- Store in Qdrant with `type: 'conversation'`

**New Payload Structure**:
```json
{
  "type": "conversation",
  "session_id": "abc123-def456",
  "summary": "200-500 word conversation summary from TRACE",
  "message_count": 42,
  "duration_minutes": 35,
  "start_time": "2025-10-18T19:55:00",
  "has_changelog": true,
  "changelog_path": ".context/develop/.changes/251018-1955_abc123.md"
}
```

**Why This Design**:
- Enables semantic search on conversation summaries
- Bidirectional link stored in searchable metadata
- Lightweight (1 vector per conversation, not 10K-100K words)

**Implementation Location**: `aura-v2/src/aura/services/imem/modular_ingest.py`

---

### D. IMEM Search API (`aura-v2/src/aura/services/imem/`)

**Current Behavior**:
- Searches Qdrant by vector similarity
- Returns ranked results
- No payload filtering (can't filter by type, metadata)

**Modifications Needed**:
- Support Qdrant `FieldCondition` filters
- Enable metadata filtering: `filter={'type': 'conversation'}`
- Pass filters through to Qdrant search API

**Usage Examples**:
```python
# Search only conversations
imem.search("auth decisions", filters={"type": "conversation"})

# Search conversations with changelogs
imem.search("database", filters={"type": "conversation", "has_changelog": True})

# Search conversations without changelogs (candidates for /log:develop)
imem.search("API design", filters={"type": "conversation", "has_changelog": False})
```

**Implementation Location**: `aura-v2/src/aura/services/imem/modular_search.py`

---

### E. TRACE CLI (`aura-v2/src/aura/cli/trace.py`)

**Current Behavior**:
- Discovers conversations (`--list`, `--recent`)
- Exports conversations (`--export`)
- Shows metadata (`--summary`)
- No indexing functionality

**Modifications Needed**:
- New flag: `--index` (index current conversation into IMEM)
- New flag: `--index-all` (batch index all conversations)
- Integration: Call IMEM ingestion with TRACE summary + Registry lookup

**Usage Examples**:
```bash
# Index a specific conversation
trace --session abc123 --index

# Batch index all discovered conversations
trace --index-all

# Index and show what was stored
trace --session abc123 --index --verbose
```

**Implementation Location**: `aura-v2/src/aura/cli/trace.py`

---

### F. IMEM CLI (`aura-v2/src/aura/cli/imem.py`)

**Current Behavior**:
- `imem search "query"` (searches everything)
- `imem init`, `imem update`, `imem status`
- No type filtering

**Modifications Needed**:
- New flag: `--type [changelog|conversation]`
- New flag: `--has-changelog` (filter conversations with changelogs)
- Pass filters to search API

**Usage Examples**:
```bash
# Search only conversations
imem search "database design" --type conversation

# Search only changelogs
imem search "auth flow" --type changelog

# Find conversations that have been validated
imem search "authentication" --type conversation --has-changelog

# Find orphaned conversations (no changelog yet)
imem search "API changes" --type conversation --no-changelog
```

**Implementation Location**: `aura-v2/src/aura/cli/imem.py`

---

### G. Changelog Workflow (`aura-v2/src/orchestrator/workflows/log_develop.py`)

**Current Behavior**:
- Spawns ChangelogAgent
- Creates changelog file
- Returns success status
- Does NOT update registry

**Modifications Needed**:
- After changelog creation succeeds
- Update registry entry for this session
- Set `has_changelog: true`, `last_changelog: path`

**Why This Matters**:
- Automatically maintains bidirectional link
- No manual step required
- Registry stays synchronized with changelog creation

**Implementation Location**: `aura-v2/src/orchestrator/workflows/log_develop.py`

---

## 3. Data Flow Architecture

### Creation Flow (Changelog → Registry)
```
User runs /log:develop
    ↓
ChangelogAgent creates changelog
    ↓
Workflow updates registry
    ↓
Registry now knows: session X has changelog at path Y
```

### Indexing Flow (TRACE + Registry → IMEM)
```
User runs: trace --index-all
    ↓
TRACE discovers all conversations
    ↓
For each conversation:
    ├─ TRACE.get_summary() → summary, message_count, duration
    ├─ Registry.lookup(session_id) → has_changelog, changelog_path
    ├─ Combine metadata
    └─ IMEM.ingest() → Store in Qdrant
```

### Search Flow (User → IMEM → Results)
```
User: imem search "database design" --type conversation
    ↓
IMEM search with filter: {type: 'conversation'}
    ↓
Qdrant returns matching conversations
    ↓
Results show:
    - Conversation summary
    - Session ID
    - Has changelog? Yes/No
    - Changelog path (if exists)
```

### Navigation Flow (Bidirectional)
```
Changelog → Conversation:
    Read changelog → See session_id → Run: trace --session abc123

Conversation → Changelog:
    Search finds conversation → Metadata shows has_changelog: true
    → Click changelog_path → Read validated knowledge
```

---

## 4. Implementation Breakdown

| Component | Changes | Lines | Effort | Impact |
|-----------|---------|-------|--------|--------|
| Registry | Add 2 fields on update | 10 | 15min | Enables linking |
| TRACE CLI | Add `--index` flag | 30 | 1hr | User can trigger indexing |
| IMEM Ingestion | New conversation pipeline | 50 | 1.5hr | Core indexing logic |
| IMEM Search | Add filter parameter | 20 | 30min | Enables filtered search |
| IMEM CLI | Add `--type`, `--has-changelog` | 20 | 30min | User-facing features |
| Changelog Workflow | Update registry after success | 5 | 15min | Auto-linking |
| **TOTAL** | | **135** | **4-6hr** | **Two-tier complete** |

---

## 5. User-Facing Features Enabled

### Discovery Workflows

**Workflow 1**: Find Conversations
```bash
imem search "database design" --type conversation
# Returns: List of relevant conversations with summaries
```

**Workflow 2**: Filter by Changelog Status
```bash
imem search "authentication" --type conversation --has-changelog
# Returns: Only conversations that have been validated
```

**Workflow 3**: Find Orphaned Conversations
```bash
imem search "API changes" --type conversation --no-changelog
# Returns: Conversations without validation (candidates for /log:develop)
```

**Workflow 4**: Navigate Bidirectionally
```bash
# From changelog → conversation
cat .develop/.changes/file.md  # See session_id
trace --session abc123 --export context.md

# From conversation → changelog
imem search "auth" --type conversation  # See changelog_path in results
cat .develop/.changes/changelog.md
```

---

## 6. Out of Scope (Future Phases)

### Phase 5B (Not in Tier 2)
- ❌ Section-level chunking (H1→H2→H3 for changelogs)
- ❌ LlamaIndex integration
- ❌ ~15 vectors per changelog

### Phase 5C (Not in Tier 2)
- ❌ PULSE orchestration
- ❌ PRUNE orchestration
- ❌ Full pipeline automation

### Phase 6 (Not in Tier 2)
- ❌ Brother querying (trace --ask)
- ❌ Intelligent conversation analysis

**Tier 2 Focus**: Conversation indexing + bidirectional linking only.

---

## 7. Success Criteria

### We Know It Works When:
1. ✅ Can run: `trace --index-all` (indexes all conversations)
2. ✅ Can run: `imem search "query" --type conversation` (returns conversations)
3. ✅ Can run: `imem search "query" --has-changelog` (filters correctly)
4. ✅ Registry shows `has_changelog: true` after `/log:develop`
5. ✅ Search results show `changelog_path` when available
6. ✅ Can navigate: changelog → session_id → conversation
7. ✅ Can navigate: conversation → changelog_path → validated knowledge

### Measurable Outcomes
- 31 conversations in registry → All indexed in IMEM
- 14 changelogs created → 14 sessions show `has_changelog: true`
- Search "database" → Returns both conversations AND changelogs
- Type filtering works → Conversations separate from changelogs

---

## 8. Technical Implementation Details

### 8.1 Registry Update Pattern

```python
# In log_develop.py workflow
def run_log_develop_workflow(...):
    # ... existing ChangelogAgent spawning ...

    result = changelog_agent.run(prompt)

    if result.get('success'):
        # NEW: Update registry after changelog creation
        from orchestrator.registry import update_session
        update_session(session_id, {
            'has_changelog': True,
            'last_changelog': str(changelog_path),
            'last_updated': datetime.now().isoformat()
        })
```

### 8.2 Conversation Indexing Pattern

```python
# In trace.py CLI
@click.option('--index', is_flag=True, help='Index conversation into IMEM')
def trace(..., index):
    if index:
        # Get summary from TRACE
        summary = ConversationRetrieval().get_summary(entries)

        # Check if changelog exists
        registry = load_registry()
        session_data = registry.get(summary['session_id'], {})

        # Ingest into IMEM
        imem.ingest_text(
            content=summary['summary'],
            metadata={
                'type': 'conversation',
                'session_id': summary['session_id'],
                'start_time': summary['start_time'].isoformat(),
                'duration_minutes': summary['duration_minutes'],
                'message_count': summary['message_count'],
                'has_changelog': session_data.get('has_changelog', False),
                'changelog_path': session_data.get('last_changelog')
            }
        )
```

### 8.3 Search Filtering Pattern

```python
# In modular_search.py
from qdrant_client import models

def search(self, query: str, filters: Optional[Dict] = None, **kwargs):
    # NEW: Support Qdrant FieldCondition filters
    qdrant_filter = None
    if filters:
        qdrant_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key=key,
                    match=models.MatchValue(value=value)
                )
                for key, value in filters.items()
            ]
        )

    results = self.client.search(
        collection_name=self.collection_name,
        query_vector=embeddings,
        query_filter=qdrant_filter,  # NEW
        limit=limit
    )
```

### 8.4 CLI Filter Integration

```python
# In imem.py CLI
@click.option('--type', type=click.Choice(['changelog', 'conversation', 'all']),
              default='all', help='Filter by document type')
@click.option('--has-changelog', is_flag=True,
              help='Only show conversations with changelogs')
def search(query, type, has_changelog, ...):
    filters = {}

    if type != 'all':
        filters['type'] = type

    if has_changelog:
        filters['has_changelog'] = True

    results = searcher.search(query, filters=filters, ...)
```

---

## 9. Architecture Principles

### Source of Truth Hierarchy
1. **Conversations** (raw material, parsed by TRACE)
2. **Changelogs** (validated by user, created by brothers)
3. **Documents** (maintained state, updated by PULSE)

### Two-Tier Retrieval Strategy
- **IMEM Tier 1**: Changelogs (section-level, RAG-optimized)
- **IMEM Tier 2**: Conversations (summary-level, discovery-focused)

### Bidirectional Linking
- **Forward**: Changelog → session_id (already exists in YAML frontmatter)
- **Reverse**: Conversation → changelog_path (NEW, stored in Registry + IMEM)

### Registry as Lightweight Cache
- Fast session metadata lookup
- No vector search overhead for simple queries
- Single source of truth for changelog existence

---

## 10. Testing Strategy

### Unit Tests
```python
def test_conversation_indexing():
    # Given a conversation summary from TRACE
    summary = {
        'session_id': 'abc123',
        'summary': '...',
        'message_count': 42,
        'duration_minutes': 35
    }

    # When indexed into IMEM
    imem.ingest_conversation(summary)

    # Then searchable by content
    results = imem.search("summary content", filters={'type': 'conversation'})
    assert len(results) > 0
    assert results[0]['type'] == 'conversation'
```

### Integration Tests
```python
def test_bidirectional_linking():
    # Given a changelog created for session abc123
    workflow_result = run_log_develop_workflow(session_id='abc123')

    # Then registry updated
    registry = load_registry()
    assert registry['abc123']['has_changelog'] == True

    # And conversation search shows link
    results = imem.search("", filters={'session_id': 'abc123', 'type': 'conversation'})
    assert results[0]['changelog_path'] is not None
```

### End-to-End Tests
```bash
# Scenario: User creates changelog, then searches conversations
/log:develop  # Creates changelog
trace --index-all  # Indexes conversations
imem search "auth" --type conversation --has-changelog  # Finds validated conversations
```

---

## 11. Performance Considerations

### Indexing Performance
- **Batch indexing**: 31 conversations × 500 tokens = ~15,500 tokens → ~2 min indexing time
- **Incremental indexing**: Single conversation → ~3-5 seconds
- **Deduplication**: MD5 hash check prevents re-indexing

### Search Performance
- **Type filtering**: Qdrant FieldCondition → negligible overhead
- **Conversation summaries**: 200-500 words → fast embedding generation
- **Registry lookups**: O(1) hash lookup → sub-millisecond

### Storage Requirements
- **Per conversation**: 1 vector (1024D) + ~1KB metadata = ~5KB
- **31 conversations**: ~155KB total
- **Negligible compared to Tier 1**: Changelogs are ~10-100× larger

---

## 12. Migration Path

### Step 1: Update Schema (No Breaking Changes)
```python
# Add new fields to payload, old data unaffected
payload = {
    # Existing fields (keep)
    'information': content,
    'file_path': path,

    # NEW fields (optional for backward compatibility)
    'type': extract_type(content),  # Default: 'document'
    'has_changelog': False  # Default: False
}
```

### Step 2: Backfill Registry
```python
# One-time script to populate has_changelog for existing sessions
for session_id in registry.keys():
    changelog_path = find_changelog_by_session(session_id)
    if changelog_path:
        update_session(session_id, {
            'has_changelog': True,
            'last_changelog': str(changelog_path)
        })
```

### Step 3: Index Existing Conversations
```bash
# Batch index all historical conversations
trace --index-all
```

---

## 13. Future Enhancements (Post-Tier 2)

### Advanced Conversation Features
- Turn-level indexing (index each user/assistant turn separately)
- Conversation threading (link related sessions)
- Topic extraction (auto-tag conversations with keywords)
- Sentiment analysis (track conversational tone)

### Advanced Search Features
- Cross-type queries: "Find conversations AND changelogs about auth"
- Temporal queries: "Recent conversations without changelogs"
- Relevance boosting: Weight recent conversations higher

### Workflow Automation
- Auto-suggest `/log:develop` for high-value conversations
- Detect stale conversations (no changelog after N days)
- Batch changelog generation for selected sessions

---

## 14. Conclusion

**Tier 2 conversation indexing completes AURA's two-tier institutional memory vision:**

- **Tier 1 (Changelogs)**: Surgical, validated, section-level retrieval
- **Tier 2 (Conversations)**: Broad, exploratory, summary-level discovery

**Implementation is straightforward**: 135 lines, 4-6 hours, leveraging existing TRACE infrastructure.

**Key insight**: Bidirectional linking (Conversation ↔ Changelog) transforms AURA from a documentation system into a complete knowledge graph.

**Next steps**: Implement registry updates → conversation indexing → search filtering → CLI integration.
