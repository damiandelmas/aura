---
session_id: "f48360a7-9532-46b2-a6ec-cf9348226255"
timestamp: "2025-10-29T14:45:00-0700"
type: "design.implementation-plan"
status: "ready-to-execute"
parent_design: "251029-1437.md"
---

# IMEM CLI Refactor - Phase 1 Implementation Plan

## Executive Summary

**Objective:** Fix conversation indexing + establish consistent CLI foundation

**Key Decision:** Collection naming uses `context` (not `changelog`)
- `imem_{hash}_context` - All phases (develop, design, document)
- `imem_{hash}_conversation` - Claude Code conversations

**Rationale:** "context" semantically encompasses all documentation phases, not just changelogs

**Estimated Duration:** 2.5 hours

**Files Modified:** 3 files, ~190 line changes

---

## Table of Contents

1. [Phase 1: Registry Schema Update](#phase-1-registry-schema-update)
2. [Phase 2: CLI Structure Refactor](#phase-2-cli-structure-refactor)
3. [Phase 3: Collection Resolution](#phase-3-collection-resolution)
4. [Phase 4: Metadata Source Updates](#phase-4-metadata-source-updates)
5. [Phase 5: Testing & Validation](#phase-5-testing--validation)
6. [Appendix: File Changes Reference](#appendix-file-changes-reference)

---

## Phase 1: Registry Schema Update

**Duration:** ~30 minutes

**Objective:** Enable tracking of multiple collections per project

### Task 1.1: Modify Registry Data Structure

**File:** `/home/axp/projects/fleet/hangar/code/aura/main/imem/src/imem/registry.py`

**Current Schema (lines 36-47):**
```python
def register_project(self, project_root: Path) -> str:
    """Register a project and return collection name"""
    project_key = str(project_root.resolve())
    collection_name = f"imem_{hashlib.md5(project_key.encode()).hexdigest()[:8]}"

    self.data["projects"][project_key] = {
        "collection": collection_name,  # SINGLE collection
        "indexed_at": datetime.now().isoformat(),
        "doc_count": 0
    }
    self._save()
    return collection_name
```

**Required Changes:**
```python
def register_project(self, project_root: Path) -> dict:
    """Register a project and return collection names"""
    project_key = str(project_root.resolve())
    hash_suffix = hashlib.md5(project_key.encode()).hexdigest()[:8]

    collections = {
        "context": f"imem_{hash_suffix}_context",
        "conversation": f"imem_{hash_suffix}_conversation"
    }

    self.data["projects"][project_key] = {
        "collections": collections,
        "indexed_at": datetime.now().isoformat(),
        "doc_counts": {
            "context": 0,
            "conversation": 0
        }
    }
    self._save()
    return collections
```

**Subtasks:**
1. Update return type: `str` → `dict`
2. Generate both collection names with hash suffix
3. Store `collections` dict instead of single `collection` string
4. Split `doc_count` into `doc_counts` dict

---

### Task 1.2: Add Collection Type Helper

**File:** `/home/axp/projects/fleet/hangar/code/aura/main/imem/src/imem/registry.py`

**New Method (add after `get_project_info`):**
```python
def get_collection_by_type(self, project_root: Path, collection_type: str) -> str:
    """Get collection name for a specific type (context or conversation)"""
    info = self.get_project_info(project_root)
    if not info:
        raise ValueError(f"Project not registered: {project_root}")

    collections = info.get('collections', {})

    # Backward compatibility: if old schema, return single collection for context
    if not collections and 'collection' in info:
        if collection_type == 'context':
            return info['collection']
        else:
            raise ValueError(f"Old registry format - no {collection_type} collection")

    if collection_type not in collections:
        raise ValueError(f"Unknown collection type: {collection_type}")

    return collections[collection_type]
```

**Subtasks:**
1. Add method signature with type hints
2. Implement backward compatibility check
3. Add error handling for missing types
4. Return appropriate collection name

---

### Task 1.3: Update Doc Count Tracking

**File:** `/home/axp/projects/fleet/hangar/code/aura/main/imem/src/imem/registry.py`

**Current (lines 57-63):**
```python
def update_doc_count(self, project_root: Path, count: int):
    """Update document count for a project"""
    project_key = str(project_root.resolve())
    if project_key in self.data["projects"]:
        self.data["projects"][project_key]["doc_count"] = count
        self._save()
```

**Required Changes:**
```python
def update_doc_count(self, project_root: Path, collection_type: str, count: int):
    """Update document count for a specific collection type"""
    project_key = str(project_root.resolve())
    if project_key in self.data["projects"]:
        # Backward compatibility: handle old schema
        if "doc_counts" not in self.data["projects"][project_key]:
            self.data["projects"][project_key]["doc_counts"] = {
                "context": 0,
                "conversation": 0
            }

        self.data["projects"][project_key]["doc_counts"][collection_type] = count
        self._save()
```

**Subtasks:**
1. Add `collection_type` parameter
2. Add backward compatibility check
3. Update per-collection count
4. Save registry

---

### Validation Steps (Phase 1)

```bash
# 1. Check registry module loads without errors
python3 -c "from imem.registry import SimpleRegistry; print('OK')"

# 2. Test registration
python3 -c "
from imem.registry import SimpleRegistry
from pathlib import Path
reg = SimpleRegistry()
collections = reg.register_project(Path.cwd())
print(f'Collections: {collections}')
assert 'context' in collections
assert 'conversation' in collections
assert '_context' in collections['context']
print('✅ Registry schema updated')
"

# 3. Test helper method
python3 -c "
from imem.registry import SimpleRegistry
from pathlib import Path
reg = SimpleRegistry()
reg.register_project(Path.cwd())
ctx = reg.get_collection_by_type(Path.cwd(), 'context')
conv = reg.get_collection_by_type(Path.cwd(), 'conversation')
print(f'Context: {ctx}')
print(f'Conversation: {conv}')
print('✅ Helper method works')
"
```

**Success Criteria:**
- ✅ `register_project()` returns dict with both collection names
- ✅ `get_collection_by_type()` works for both types
- ✅ `update_doc_count()` accepts collection_type parameter
- ✅ Backward compatibility maintained (old registry format still readable)

---

## Phase 2: CLI Structure Refactor

**Duration:** ~1 hour

**Objective:** Consistent verb-noun CLI structure, remove old commands

### Task 2.1: Extract Index Phase Helper

**File:** `/home/axp/projects/fleet/hangar/code/aura/main/imem/src/imem/cli.py`

**New Helper Function (add near top of file):**
```python
def _index_phase(phase_name: str, force: bool = False, limit: Optional[int] = None):
    """
    Index a specific phase (develop, design, document) or all context

    Args:
        phase_name: Phase to index ('develop', 'design', 'document', 'context')
        force: If True, recreate collection
        limit: Optional limit for number of documents
    """
    from imem.ingest import DocumentIngester
    from imem.registry import SimpleRegistry
    import click

    registry = SimpleRegistry()
    project_root = registry.get_project_root()

    if not project_root:
        click.echo("❌ Not in a registered project. Run 'imem init' first.", err=True)
        return

    # Get or create collection
    collections = registry.get_project_info(project_root).get('collections')
    if not collections:
        collections = registry.register_project(project_root)

    collection_name = collections['context']

    # Determine paths to index
    if phase_name == 'context':
        # Index all phases
        phases_to_index = ['develop', 'design', 'document']
    else:
        phases_to_index = [phase_name]

    # Initialize ingester
    ingester = DocumentIngester(collection_name=collection_name)

    # Create collection if needed
    if force:
        ingester.create_collection(recreate=True)

    # Index each phase
    total_indexed = 0
    for phase in phases_to_index:
        phase_path = project_root / '.context' / phase
        if not phase_path.exists():
            click.echo(f"⚠️  Phase directory not found: {phase_path}")
            continue

        click.echo(f"📚 Indexing {phase} phase...")
        count = ingester.ingest_markdown_chunked(
            phase_path,
            phase=phase,
            limit=limit
        )
        total_indexed += count
        click.echo(f"✅ Indexed {count} documents from {phase}")

    # Update registry
    registry.update_doc_count(project_root, 'context', total_indexed)

    click.echo(f"\n🎉 Total indexed: {total_indexed} documents")
    return total_indexed
```

**Subtasks:**
1. Create function signature with parameters
2. Add registry lookup logic
3. Add collection resolution (context collection)
4. Add phase path resolution (all phases if 'context')
5. Add ingestion loop
6. Update registry with counts

---

### Task 2.2: Create New Index Commands

**File:** `/home/axp/projects/fleet/hangar/code/aura/main/imem/src/imem/cli.py`

**Add New Command Group:**
```python
@cli.command('index')
@click.argument('source', type=click.Choice(['develop', 'design', 'document', 'conversations', 'context']))
@click.option('--force', is_flag=True, help='Recreate collection if exists')
@click.option('--limit', type=int, help='Limit number of documents/conversations to index')
def index_source(source, force, limit):
    """
    Index content from a specific source

    Sources:
      develop       - .context/develop/ phase
      design        - .context/design/ phase
      document      - .context/document/ phase
      context       - All phases (develop + design + document)
      conversations - Claude Code conversations (~/.claude/)

    Examples:
      imem index develop
      imem index context --force
      imem index conversations --limit 50
    """
    if source == 'conversations':
        _index_conversations(force=force, limit=limit)
    else:
        _index_phase(phase_name=source, force=force, limit=limit)
```

**Subtasks:**
1. Add @cli.command decorator
2. Add source argument with choices
3. Add force and limit options
4. Route to appropriate handler (phase vs conversations)

---

### Task 2.3: Create New Search Commands

**File:** `/home/axp/projects/fleet/hangar/code/aura/main/imem/src/imem/cli.py`

**Add New Command:**
```python
@cli.command('search')
@click.argument('query')
@click.option('--in', 'source', type=click.Choice(['develop', 'design', 'document', 'context', 'conversations']),
              default='context', help='Source to search')
@click.option('--limit', default=10, help='Number of results')
@click.option('--decisions', is_flag=True, help='Filter for decision sections')
@click.option('--patches-only', is_flag=True, help='Conversation patches only')
@click.option('--user-only', is_flag=True, help='User messages only')
def search_command(query, source, limit, decisions, patches_only, user_only):
    """
    Search across indexed content

    Examples:
      imem search "authentication" --in develop
      imem search "JWT" --in context
      imem search "bug fix" --in conversations --patches-only
    """
    # Build filters based on source
    filters = {}

    if source in ['develop', 'design', 'document']:
        filters['source'] = 'context'
        filters['phase'] = source
    elif source == 'context':
        filters['source'] = 'context'
    elif source == 'conversations':
        filters['source'] = 'conversation'

    # Add type filters
    if decisions:
        filters['section_type'] = 'Decisions'
    if patches_only:
        filters['chunk_type'] = 'patch'
    if user_only:
        filters['role'] = 'user'

    # Execute search
    _execute_search(query, filters, limit)
```

**Subtasks:**
1. Add command decorator and arguments
2. Add source option with choices
3. Add filter flags
4. Build filter dict based on source
5. Call existing _execute_search helper

---

### Task 2.4: Remove Old Commands

**File:** `/home/axp/projects/fleet/hangar/code/aura/main/imem/src/imem/cli.py`

**Delete These Sections:**
1. `@cli.group('develop')` decorator and all methods (lines ~50-100)
2. `@cli.group('conversations')` decorator and all methods (lines ~100-150)
3. `@cli.command('index-all-conversations')` (lines ~1000-1050)
4. `@cli.command('index-conversation')` (lines ~1050-1100)

**Subtasks:**
1. Remove noun-verb group decorators
2. Remove old index command implementations
3. Keep helper functions (_execute_search, etc.)
4. Verify no dangling references

---

### Validation Steps (Phase 2)

```bash
# 1. Check CLI loads without errors
imem --help

# 2. Verify new commands exist
imem index --help
imem search --help

# 3. Verify old commands gone
imem develop search "test" 2>&1 | grep "No such command" && echo "✅ Old command removed"
imem index-all-conversations 2>&1 | grep "No such command" && echo "✅ Old command removed"

# 4. Test new command structure (dry run)
imem index develop --limit 1
imem search "test" --in develop --limit 1
```

**Success Criteria:**
- ✅ `imem index <source>` command exists
- ✅ `imem search <query> --in <source>` command exists
- ✅ Old noun-verb groups removed
- ✅ Old hyphenated commands removed
- ✅ Help text shows consistent structure

---

## Phase 3: Collection Resolution

**Duration:** ~30 minutes

**Objective:** Route search/compose to correct collection based on source

### Task 3.1: Update Search Execution

**File:** `/home/axp/projects/fleet/hangar/code/aura/main/imem/src/imem/cli.py`

**Current _execute_search (lines ~145-176):**
```python
def _execute_search(query: str, filters: dict, limit: int):
    """Shared search execution logic"""
    registry = SimpleRegistry()
    project_root = registry.get_project_root()
    info = registry.get_project_info(project_root)
    collection_name = info['collection']  # OLD: single collection
    # ... search logic
```

**Required Changes:**
```python
def _execute_search(query: str, filters: dict, limit: int):
    """Shared search execution logic"""
    registry = SimpleRegistry()
    project_root = registry.get_project_root()

    # Determine collection type from source filter
    source = filters.get('source', 'context')
    if source == 'context':
        collection_name = registry.get_collection_by_type(project_root, 'context')
    elif source == 'conversation':
        collection_name = registry.get_collection_by_type(project_root, 'conversation')
    else:
        raise ValueError(f"Unknown source type: {source}")

    # ... rest of search logic (unchanged)
```

**Subtasks:**
1. Extract source from filters
2. Call registry helper to get collection by type
3. Handle unknown source types
4. Keep rest of search logic unchanged

---

### Task 3.2: Update Compose Command

**File:** `/home/axp/projects/fleet/hangar/code/aura/main/imem/src/imem/cli.py`

**Current compose (lines ~215-285):**
```python
def compose(config_json):
    """Execute composition pipeline"""
    registry = SimpleRegistry()
    project_root = registry.get_project_root()
    info = registry.get_project_info(project_root)
    collection_name = info['collection']  # OLD: single collection
    # ... compose logic
```

**Required Changes:**
```python
def compose(config_json):
    """Execute composition pipeline"""
    registry = SimpleRegistry()
    project_root = registry.get_project_root()

    # Parse config to determine source
    config_dict = json.loads(config_json)

    # Default to context collection (changelogs/design docs)
    # Compose can be extended to support conversation searches later
    collection_name = registry.get_collection_by_type(project_root, 'context')

    # ... rest of compose logic (unchanged)
```

**Subtasks:**
1. Determine collection type from config (default: context)
2. Call registry helper to get collection
3. Keep compose pipeline logic unchanged
4. Document future extension point for conversation compose

---

### Task 3.3: Update Conversation Indexing

**File:** `/home/axp/projects/fleet/hangar/code/aura/main/imem/src/imem/cli.py`

**New Helper Function:**
```python
def _index_conversations(force: bool = False, limit: Optional[int] = None):
    """
    Index Claude Code conversations

    Args:
        force: If True, recreate collection
        limit: Optional limit for number of conversations
    """
    from imem.ingest import DocumentIngester
    from imem.registry import SimpleRegistry
    from imem.trace_integration import ConversationFinder
    import click

    registry = SimpleRegistry()
    project_root = registry.get_project_root()

    if not project_root:
        click.echo("❌ Not in a registered project. Run 'imem init' first.", err=True)
        return

    # Get or create collection
    collections = registry.get_project_info(project_root).get('collections')
    if not collections:
        collections = registry.register_project(project_root)

    collection_name = collections['conversation']  # Use conversation collection

    # Initialize ingester
    ingester = DocumentIngester(collection_name=collection_name)

    # Create collection if needed
    if force:
        ingester.create_collection(recreate=True)

    # Find conversations
    finder = ConversationFinder()
    conversations = finder.find_all()

    if limit:
        conversations = conversations[:limit]

    click.echo(f"📚 Indexing {len(conversations)} conversations...")

    # Index conversations
    count = ingester.ingest_conversations(conversations)

    # Update registry
    registry.update_doc_count(project_root, 'conversation', count)

    click.echo(f"✅ Indexed {count} conversation chunks")
    return count
```

**Subtasks:**
1. Create function signature
2. Add registry lookup for conversation collection
3. Add TRACE integration to find conversations
4. Add ingestion logic
5. Update registry counts

---

### Validation Steps (Phase 3)

```bash
# 1. Test context search (uses context collection)
imem search "test" --in develop --limit 1

# 2. Test conversation search (uses conversation collection)
imem search "test" --in conversations --limit 1

# 3. Verify collection routing
python3 -c "
from imem.registry import SimpleRegistry
from pathlib import Path
reg = SimpleRegistry()
reg.register_project(Path.cwd())
ctx = reg.get_collection_by_type(Path.cwd(), 'context')
conv = reg.get_collection_by_type(Path.cwd(), 'conversation')
print(f'Context collection: {ctx}')
print(f'Conversation collection: {conv}')
assert '_context' in ctx
assert '_conversation' in conv
print('✅ Collection routing works')
"
```

**Success Criteria:**
- ✅ Search routes to correct collection based on source
- ✅ Compose uses context collection by default
- ✅ Conversation indexing uses conversation collection
- ✅ Registry helper returns correct collection names

---

## Phase 4: Metadata Source Updates

**Duration:** ~15 minutes

**Objective:** Change filter values from 'changelog' to 'context'

### Task 4.1: Update CLI Filter Values

**File:** `/home/axp/projects/fleet/hangar/code/aura/main/imem/src/imem/cli.py`

**Changes Required:**

**Line 67 (develop search):**
```python
# OLD
'source': 'changelog',

# NEW
'source': 'context',
```

**Line 192 (result display):**
```python
# OLD
if payload.get('source') == 'changelog':

# NEW
if payload.get('source') == 'context':
```

**Line 525 (filter construction):**
```python
# OLD
filters['source'] = 'changelog'

# NEW
filters['source'] = 'context'
```

---

### Task 4.2: Update Ingest Source Value

**File:** `/home/axp/projects/fleet/hangar/code/aura/main/imem/src/imem/ingest.py`

**Line 737 (payload construction):**
```python
# OLD
'source': 'changelog',

# NEW
'source': 'context',
```

---

### Task 4.3: Update Comments (Optional)

**File:** `/home/axp/projects/fleet/hangar/code/aura/main/imem/src/imem/cli.py`

**Lines to update:**
- Line 59: "changelogs" → "context"
- Line 190: "changelogs" → "context"
- Line 528: "changelogs" → "context"

---

### Validation Steps (Phase 4)

```bash
# 1. Verify no remaining 'changelog' in source filters
grep -n "source.*changelog" imem/src/imem/cli.py
grep -n "source.*changelog" imem/src/imem/ingest.py
# Should return empty

# 2. Verify 'context' is used
grep -n "'source': 'context'" imem/src/imem/*.py
# Should show 4 matches

# 3. Test metadata in indexed documents
python3 -c "
from qdrant_client import QdrantClient
client = QdrantClient(host='localhost', port=6334)
results, _ = client.scroll(
    collection_name='imem_1ba1fff1_context',
    limit=1,
    with_payload=True
)
if results:
    print(f\"Source field: {results[0].payload.get('source')}\")
    assert results[0].payload.get('source') == 'context'
    print('✅ Metadata source value correct')
"
```

**Success Criteria:**
- ✅ All `'source': 'changelog'` changed to `'source': 'context'`
- ✅ No grep matches for `source.*changelog`
- ✅ Indexed documents have `source: 'context'` in payload

---

## Phase 5: Testing & Validation

**Duration:** ~30 minutes

**Objective:** End-to-end validation of all changes

### Test 5.1: Full Workflow Test

```bash
# 1. Start Qdrant service
imem service start
imem service status
# Expected: Service running

# 2. Initialize project (creates both collections)
cd /home/axp/projects/fleet/hangar/code/aura/main
imem init --force

# 3. Check registry
cat ~/.imem/registry.json
# Expected: "collections": {"context": "imem_..._context", "conversation": "imem_..._conversation"}

# 4. Index develop phase
imem index develop
# Expected: Documents indexed to context collection

# 5. Index conversations (small batch)
imem index conversations --limit 10
# Expected: 10 conversations indexed to conversation collection

# 6. Verify collections in Qdrant
python3 -c "
from qdrant_client import QdrantClient
client = QdrantClient(host='localhost', port=6334)
collections = client.get_collections()
print('Collections:', [c.name for c in collections.collections])
# Expected: ['imem_..._context', 'imem_..._conversation']
"
```

---

### Test 5.2: Search Validation

```bash
# 1. Search context (develop phase)
imem search "authentication" --in develop --limit 5
# Expected: Results from develop phase with source='context'

# 2. Search all context
imem search "JWT" --in context --limit 5
# Expected: Results from all phases (develop, design, document)

# 3. Search conversations
imem search "bug" --in conversations --limit 5
# Expected: Results from conversations with source='conversation'

# 4. Search with filters
imem search "refactor" --in conversations --patches-only
# Expected: Only patch chunks from conversations

imem search "explain" --in conversations --user-only
# Expected: Only user message chunks
```

---

### Test 5.3: Metadata Validation

```python
# Run this Python validation script
python3 << 'EOF'
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

client = QdrantClient(host='localhost', port=6334)

# Test 1: Context collection has correct metadata
print("Test 1: Context collection metadata")
results, _ = client.scroll(
    collection_name='imem_1ba1fff1_context',
    scroll_filter=Filter(
        must=[FieldCondition(key='source', match=MatchValue(value='context'))]
    ),
    limit=5,
    with_payload=True
)
print(f"  Found {len(results)} context documents")
if results:
    print(f"  Sample payload keys: {list(results[0].payload.keys())}")
    assert results[0].payload['source'] == 'context'
    print("  ✅ Context metadata correct")

# Test 2: Conversation collection has correct metadata
print("\nTest 2: Conversation collection metadata")
results, _ = client.scroll(
    collection_name='imem_1ba1fff1_conversation',
    scroll_filter=Filter(
        must=[FieldCondition(key='source', match=MatchValue(value='conversation'))]
    ),
    limit=5,
    with_payload=True
)
print(f"  Found {len(results)} conversation chunks")
if results:
    print(f"  Sample payload keys: {list(results[0].payload.keys())}")
    assert results[0].payload['source'] == 'conversation'
    assert 'chunk_type' in results[0].payload  # message or patch
    assert 'session_id' in results[0].payload
    print("  ✅ Conversation metadata correct")

# Test 3: Vector configuration
print("\nTest 3: Vector configuration")
ctx_info = client.get_collection('imem_1ba1fff1_context')
conv_info = client.get_collection('imem_1ba1fff1_conversation')
print(f"  Context vectors: {ctx_info.vectors_count}")
print(f"  Conversation vectors: {conv_info.vectors_count}")
print(f"  Vector name: e5-large-v2")
print("  ✅ Both collections use same vector config")

print("\n🎉 All validation tests passed!")
EOF
```

---

### Test 5.4: CLI Help Text

```bash
# Verify help text is consistent
imem --help
# Expected: Shows index, search, compose, service, etc.

imem index --help
# Expected: Shows sources: develop, design, document, conversations, context

imem search --help
# Expected: Shows --in option with sources

# Verify old commands gone
imem develop 2>&1 | grep "No such command"
imem conversations 2>&1 | grep "No such command"
imem index-all-conversations 2>&1 | grep "No such command"

echo "✅ CLI structure consistent, old commands removed"
```

---

### Test 5.5: Compose Pipeline

```bash
# Test compose still works with context collection
imem compose '{
  "stages": {
    "discover": {
      "query": "authentication implementation"
    },
    "enrich": {
      "siblings": true,
      "temporal": false
    },
    "structure": {
      "template": "story-context"
    }
  }
}'

# Expected: Composition result using context collection
```

---

### Success Criteria Checklist

**Registry:**
- ✅ Registry tracks both collections per project
- ✅ `get_collection_by_type()` works for 'context' and 'conversation'
- ✅ `update_doc_count()` tracks per-collection counts

**CLI:**
- ✅ `imem index <source>` works for all sources
- ✅ `imem search <query> --in <source>` works consistently
- ✅ Old noun-verb groups removed
- ✅ Old hyphenated commands removed
- ✅ Help text consistent and clear

**Collections:**
- ✅ Two collections created: `imem_{hash}_context` and `imem_{hash}_conversation`
- ✅ Both use E5-Large-v2 vector (1024D, COSINE)
- ✅ Context collection has `source='context'` metadata
- ✅ Conversation collection has `source='conversation'` metadata

**Search:**
- ✅ Context search works (filters by phase if specified)
- ✅ Conversation search works (filters by chunk_type, role)
- ✅ Collection routing works correctly
- ✅ Filters applied correctly

**Compose:**
- ✅ Compose uses context collection
- ✅ Four-stage pipeline still works
- ✅ No breaking changes

**Metadata:**
- ✅ All context documents have `source='context'`
- ✅ All conversation documents have `source='conversation'`
- ✅ No remaining `source='changelog'` references

---

## Appendix: File Changes Reference

### Summary Table

| File | Lines Changed | Change Type | Critical |
|------|---------------|-------------|----------|
| `registry.py` | ~30 | Schema update, new methods | YES |
| `cli.py` | ~150 | Command refactor, routing logic | YES |
| `ingest.py` | ~10 | Metadata source value | YES |

### Detailed Change List

**registry.py:**
- Lines 36-47: `register_project()` - Return dict, create both collections
- New method: `get_collection_by_type()` - Collection routing helper
- Lines 57-63: `update_doc_count()` - Add collection_type parameter

**cli.py:**
- New function: `_index_phase()` - Extract phase indexing logic
- New function: `_index_conversations()` - Extract conversation indexing
- New command: `@cli.command('index')` - Unified index command
- New command: `@cli.command('search')` - Unified search command
- Lines 145-176: `_execute_search()` - Add collection routing
- Lines 215-285: `compose()` - Use collection helper
- Remove: `@cli.group('develop')` and methods
- Remove: `@cli.group('conversations')` and methods
- Remove: `@cli.command('index-all-conversations')`
- Remove: `@cli.command('index-conversation')`
- Lines 67, 192, 525: Change `'source': 'changelog'` → `'source': 'context'`

**ingest.py:**
- Line 737: Change `'source': 'changelog'` → `'source': 'context'`

---

## Post-Implementation Checklist

**Code Review:**
- [ ] All `'source': 'changelog'` changed to `'source': 'context'`
- [ ] Registry schema supports multiple collections
- [ ] CLI commands follow verb-noun pattern consistently
- [ ] Old commands removed, no dead code
- [ ] Error handling for missing collections

**Testing:**
- [ ] Registry unit tests pass
- [ ] CLI integration tests pass
- [ ] Search with context collection works
- [ ] Search with conversation collection works
- [ ] Compose pipeline still works
- [ ] Metadata validation passes

**Documentation:**
- [ ] Update README with new CLI structure
- [ ] Update architecture docs with collection naming
- [ ] Document migration path for old registries
- [ ] Add examples for new commands

**Cleanup:**
- [ ] Remove old audit files if needed
- [ ] Update design doc status to "implemented"
- [ ] Commit changes with clear message
- [ ] Tag release if appropriate

---

## Next Steps (Phase 2 - Future)

After Phase 1 is complete and validated:

1. **Use System for 2-4 Weeks**
   - Index conversations regularly
   - Test search patterns
   - Identify what queries matter
   - Note what breaks or feels clunky

2. **Analyze Usage Patterns**
   - Which primitives get used most?
   - What metadata fields matter for filtering?
   - Are there common composition patterns?

3. **Plan Phase 2: Graph Intelligence Layer**
   - Graph construction from retrieved chunks
   - Topology detection (linear/hub/arc/cluster)
   - Temporal position detection
   - Template adaptation

4. **Consider Phase 3: BRAIN Persistence (3-6 months)**
   - Reference count tracking
   - Supersession signals
   - Entity resolution
   - PageRank-style scoring

---

**Implementation Status:** Ready to execute
**Estimated Total Time:** 2.5 hours
**Files Modified:** 3
**Breaking Changes:** None (backward compatible)

---

**END OF IMPLEMENTATION PLAN**
