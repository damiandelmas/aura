# Next Agent TODO: IMEM CLI Refactor + Conversation Metadata Validation

## What We Just Built

### ✅ Completed: Rich Conversation Metadata
**Files modified:**
- `imem/src/imem/ingest.py` - Added `parse_conversation_section()` method (lines 789-821)
- `imem/src/imem/cli.py` - Added rich filtering flags to `conversations search` (lines 102-139)

**New capabilities:**
```bash
imem conversations search "bug" --patches-only
imem conversations search "error" --file src/cli.py
imem conversations search "question" --user-only
imem conversations search "answer" --assistant-only
```

**How it works:**
- Parses TRACE H2 headers: "Message 1: USER" → `{chunk_type: 'message', role: 'user'}`
- Parses patch headers: "Code Patch 1: src/cli.py" → `{chunk_type: 'patch', file_path: 'src/cli.py'}`
- Metadata automatically added during ingestion

---

## TASK 1: Validate Conversation Metadata Works

### Check if indexing completed
```bash
source venv/bin/activate
imem index-all-conversations --limit 10  # (if not already running)
```

### Verify metadata in Qdrant
```python
from qdrant_client import QdrantClient

client = QdrantClient(host="localhost", port=6334)

# Check for new metadata fields
points, _ = client.scroll(
    collection_name="institutional_memory",
    scroll_filter={
        "must": [
            {"key": "source", "match": {"value": "conversation"}},
            {"key": "chunk_type", "match": {"value": "message"}}  # Should work now!
        ]
    },
    limit=5,
    with_payload=True
)

for point in points:
    payload = point.payload
    print(f"chunk_type: {payload.get('chunk_type')}")  # Should show 'message' or 'patch'
    print(f"role: {payload.get('role')}")              # Should show 'user' or 'assistant'
    print(f"file_path: {payload.get('file_path')}")    # Should show path for patches
```

### Test new CLI filters
```bash
# These should work now (after re-indexing)
imem conversations search "authentication" --patches-only
imem conversations search "bug fix" --file src/cli.py
imem conversations search "how do I" --user-only
```

**Expected:** Filters work and return results with correct metadata.

**If filters don't work:** Check logs, verify metadata is present in Qdrant payload.

---

## TASK 2: Refactor CLI for Symmetry

### Problem
Current CLI is asymmetric:

**Search (good):**
- `imem develop search "query"`
- `imem conversations search "query"`

**Index (bad):**
- `imem init` (indexes all phases)
- `imem index-conversation <id>` (single conversation)
- `imem index-all-conversations` (all conversations)

### Goal: Perfect Symmetry

**After refactor:**
```bash
# Phase operations (symmetric)
imem develop search "query"     # Search develop changelogs
imem develop index              # Index develop changelogs

imem document search "query"    # Search document changelogs
imem document index             # Index document changelogs

# Conversation operations (symmetric)
imem conversations search "query" --patches-only
imem conversations index <session-id>
imem conversations index-all --limit 10

# Convenience
imem init [--force]             # Runs: develop.index + document.index
```

### Implementation Steps

**File:** `imem/src/imem/cli.py` (~1092 lines)

#### Step 1: Add `develop.index` command (after line 88)
```python
@develop.command(name='index')
@click.option('--force', is_flag=True, help='Force re-indexing')
def develop_index(force):
    """Index all develop phase changelogs"""
    _index_phase('develop', force=force)
```

#### Step 2: Create `document` group and add `document.index`
```python
@imem.group()
def document():
    """Search document phase (stable reference docs)"""
    pass

@document.command(name='search')
# ... (can add later)

@document.command(name='index')
@click.option('--force', is_flag=True, help='Force re-indexing')
def document_index(force):
    """Index all document phase files"""
    _index_phase('document', force=force)
```

#### Step 3: Extract shared indexing logic
Create helper function `_index_phase(phase_name, force=False)`:
- Takes phase name ('develop', 'document', 'designate')
- Contains all the collection creation + ingestion logic from `init()`
- Returns doc_count

This avoids duplicating ~150 lines of code.

#### Step 4: Move conversation commands
```python
# OLD (line ~806): @imem.command() def index_conversation(...)
# NEW: @conversations.command(name='index')

# OLD (line ~939): @imem.command() def index_all_conversations(...)
# NEW: @conversations.command(name='index-all')
```

Just change the decorator - logic stays the same.

#### Step 5: Update `imem init`
```python
def init(force, vscode, include_design):
    """Initialize and index current project (all phases)"""
    # Setup boilerplate (service, registry, collection)
    # ...

    # Index all phases
    _index_phase('develop', force=force)
    _index_phase('document', force=force)

    if include_design:
        _index_phase('design', force=force)

    # VS Code setup
    # ...
```

#### Step 6: Remove old commands
Delete standalone:
- `@imem.command() def index_conversation()` (moved to conversations.index)
- `@imem.command() def index_all_conversations()` (moved to conversations.index-all)

### Breaking Changes
- ❌ `imem index-conversation <id>` → Use `imem conversations index <id>`
- ❌ `imem index-all-conversations` → Use `imem conversations index-all`

These commands will no longer exist (clean break).

### Testing After Refactor
```bash
# Test phase indexing
imem develop index --force
imem document index --force

# Test conversation indexing
imem conversations index d4c99cb2-1be1-46e1-8f76-30a0f5c30c51
imem conversations index-all --limit 5

# Test init still works
imem init --force

# Verify old commands are gone
imem index-conversation <id>  # Should error
imem index-all-conversations  # Should error
```

---

## Estimated Effort

**Task 1 (Validation):** 10 minutes
- Wait for indexing to complete
- Query Qdrant to verify metadata
- Test CLI filters

**Task 2 (Refactor):** 40-60 minutes
- Extract `_index_phase()` helper: 15 min
- Add `develop.index` and `document.index`: 10 min
- Move conversation commands: 5 min
- Update `init()`: 10 min
- Testing: 15 min

**Total:** ~1 hour

---

## Success Criteria

✅ Conversation metadata includes `chunk_type`, `role`, `file_path`
✅ `imem conversations search --patches-only` works
✅ `imem develop index` and `imem document index` work
✅ `imem conversations index <id>` works
✅ Old commands removed (clean break)
✅ All tests pass

---

## Current State

**Metadata parsing:** ✅ Implemented
**CLI filters:** ✅ Implemented
**Indexing test:** ⏳ Running (10 conversations)
**Validation:** ❌ Pending
**CLI refactor:** ❌ Not started

---

## Questions?

If metadata doesn't show up after indexing:
1. Check ingestion logs for errors
2. Verify `parse_conversation_section()` is being called (line 872 in ingest.py)
3. Check that TRACE formatter outputs correct H2 headers ("Message 1: USER", "Code Patch 1: file.py")

If CLI refactor seems too risky:
- Can keep old commands with deprecation warnings instead of removing
- But clean break is better for long-term maintainability
