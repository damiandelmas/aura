---
schema_version: "v3_adaptive"
type: "refactor.cli-collection-routing"
status: "completed"
keywords: "imem registry collections context conversation cli refactor routing lifecycle"
timestamp: "2025-10-29T15:45:00-0700"
session_id: "41f29cf9-c556-4940-a27a-e672fccd82c8"
---

# IMEM CLI Refactor: Collection Routing & Lifecycle Management

## Request
> Review implementation plan for CLI refactor to support dual collections (context vs conversation) with unified verb-noun interface

## Overview
Refactored the command-line interface and registry to support separate collections for context documents (develop/design/document phases) and conversations. Changed from single collection per project to dual collections with routing logic that directs queries to the appropriate collection. Simplified interface from noun-verb command groups to unified verb-noun pattern with source as a positional argument. Added collection lifecycle management tools for visibility and cleanup. Updated all metadata references from 'changelog' to 'context' for semantic clarity.

## Decisions

### Dual Collection Architecture
- **Context**: Single collection couldn't efficiently separate document types
- **Solution**: Two collections per project - `imem_{hash}_context` and `imem_{hash}_conversation`
- **Rationale**: Different content structures require different query patterns and metadata
- **Impact**: Registry schema change requires backward compatibility

### Collection Naming Convention
- **Context**: Need to distinguish collection types in the vector database
- **Solution**: Append `_context` and `_conversation` suffixes to hash-based names
- **Benefit**: Self-documenting collection purpose in database

### CLI Interface Pattern
- **Context**: User suggested `imem search develop "query"` vs `imem search --in develop "query"`
- **Solution**: Source as positional argument, not option flag
- **Rationale**: Matches git/docker patterns, less typing, more intuitive
- **Trade-offs**: Slightly less explicit but cleaner UX

### Metadata Terminology Change
- **Context**: 'changelog' terminology confused with git changelogs
- **Solution**: Renamed all `source: 'changelog'` to `source: 'context'`
- **Benefit**: Clearer semantic meaning for institutional memory context

### Auto-Create Collections
- **Context**: Users got confusing errors when collection didn't exist
- **Solution**: Auto-create collections on first index operation
- **Alternatives**: Require `--force` flag - rejected for poor UX
- **Behavior**: `--force` now means "recreate from scratch" not "create if missing"

### Compose Collection Routing
- **Context**: Compose needs to route to correct collection
- **Solution**: Default to context collection, add `source` field for future conversation support
- **Why Deferred**: Conversations are linear timelines, compose graph features don't apply well

## Implementation

### Architecture
1. Registry tracks dual collections → Returns dict with 'context' and 'conversation' keys
2. CLI helpers determine collection type from source → Call `get_collection_by_type()`
3. Collection auto-created if missing → No user intervention needed
4. Search/compose route to correct collection → Based on source filter

### Code Signatures

**Registry Schema** (`imem/src/imem/registry.py`)
```python
def register_project(self, project_root: Path) -> dict:
    """Register a project and return collection names"""
    hash_suffix = hashlib.md5(project_key.encode()).hexdigest()[:8]

    collections = {
        "context": f"imem_{hash_suffix}_context",
        "conversation": f"imem_{hash_suffix}_conversation"
    }

    self.data["projects"][project_key] = {
        "collections": collections,
        "doc_counts": {
            "context": 0,
            "conversation": 0
        }
    }
```

**Collection Routing** (`imem/src/imem/registry.py`)
```python
def get_collection_by_type(self, project_root: Path, collection_type: str) -> str:
    """Get collection name for a specific type"""
    collections = info.get('collections', {})

    # Backward compatibility
    if not collections and 'collection' in info:
        if collection_type == 'context':
            return info['collection']

    return collections[collection_type]
```

**Unified Index Command** (`imem/src/imem/cli.py`)
```python
@imem.command('index')
@click.argument('source', type=click.Choice([
    'develop', 'design', 'document', 'conversations', 'context'
]))
@click.option('--force', is_flag=True)
@click.option('--limit', type=int)
def index_source(source, force, limit):
    if source == 'conversations':
        _index_conversations(force=force, limit=limit)
    else:
        _index_phase(phase_name=source, force=force, limit=limit)
```

**Search with Source Argument** (`imem/src/imem/cli.py`)
```python
@imem.command()
@click.argument('source', type=click.Choice([
    'develop', 'design', 'document', 'conversations', 'context'
]))
@click.argument('query', nargs=-1, required=True)
def search(source, query, ...):
    # Build filters based on source
    if source == 'conversations':
        filters['source'] = 'conversation'
        collection_name = registry.get_collection_by_type(project_root, 'conversation')
    elif source in ['develop', 'design', 'document']:
        filters['source'] = 'context'
        filters['phase'] = source
        collection_name = registry.get_collection_by_type(project_root, 'context')
```

**Auto-Create Logic** (`imem/src/imem/cli.py`)
```python
collection_exists = ingester.client.collection_exists(collection_name)

if force and collection_exists:
    click.echo(f"🔄 Recreating collection...")
    ingester.client.delete_collection(collection_name)
    collection_exists = False

if not collection_exists:
    click.echo(f"📦 Creating collection...")
    ingester.client.create_collection(
        collection_name=collection_name,
        vectors_config={"e5-large-v2": VectorParams(...)}
    )
```

**Collection Lifecycle** (`imem/src/imem/cli.py`)
```python
@imem.group()
def collections():
    """Manage collections and lifecycle"""
    pass

@collections.command('list')
def collections_list():
    # Show registered vs orphaned collections
    all_collections = client.get_collections().collections
    imem_collections = [c for c in all_collections if c.name.startswith('imem_')]

    registered = set()
    for project_path, info in registry.list_projects().items():
        if 'collections' in info:
            registered.add(info['collections']['context'])
            registered.add(info['collections']['conversation'])
```

## Constraints

### Conversation Finder API
- **What**: ConversationFinder returns List[Path] not metadata objects
- **Discovery**: During implementation of `_index_conversations()`
- **Workaround**: Extract session_id from filename, use TRACE retrieval/formatter to convert JSONL to markdown
- **Impact**: Requires temp file for ingestion pipeline

### EnhancedModularIngest API
- **What**: Ingester processes single files, not directories
- **Discovery**: Expected batch method didn't exist
- **Workaround**: Loop over files explicitly in helper functions
- **Why Non-Obvious**: Existing commands hid this loop inside other functions

### 404 Errors During Indexing
- **What**: Files processed but batch upload failed if collection missing
- **Discovery**: User saw confusing "✅ Indexed" message with 404 errors
- **Workaround**: Auto-create collection before indexing
- **Impact**: Better UX, no `--force` needed for first run

## Patterns

### Progressive Collection Creation
- **Pattern**: Check existence, auto-create if missing, recreate if forced
- **When**: Any operation requiring a collection
- **Approach**: Single try-except block handles all cases
- **Benefit**: User never sees collection errors, smooth first-run experience

### Collection Type Routing
- **Pattern**: Map source to collection type, get collection name from registry
- **When**: Search, index, or compose operations
- **Approach**: Central routing logic in registry, CLI just passes type
- **Benefit**: Single source of truth, easy to extend with new collection types

### Backward Compatible Schema Evolution
- **Pattern**: Check for new format, fall back to old format
- **When**: Reading registry data
- **Approach**: Try new schema first (`collections` dict), fall back to old (`collection` string)
- **Benefit**: Existing projects continue working during migration

### Source as First-Class Concept
- **Pattern**: Source (develop/design/conversations) drives collection routing and filtering
- **When**: All CLI commands
- **Approach**: Positional argument determines collection and filters
- **Occurrences**: index, search, status commands

## Audit

### Created
- `imem/src/imem/cli.py` - Helper functions `_index_phase()` and `_index_conversations()`
- `imem/src/imem/cli.py` - Collection lifecycle commands group with `list` and `clean` subcommands

### Modified
- `imem/src/imem/registry.py` - Changed `register_project()` to return dict instead of string
- `imem/src/imem/registry.py` - Added `get_collection_by_type()` method for routing
- `imem/src/imem/registry.py` - Updated `update_doc_count()` to accept collection_type parameter
- `imem/src/imem/cli.py` - Added unified `index` command with source argument
- `imem/src/imem/cli.py` - Updated `search` command to accept source as positional argument (not option)
- `imem/src/imem/cli.py` - Updated `compose` command to use collection routing
- `imem/src/imem/cli.py` - Fixed `status` command to handle dual collection format
- `imem/src/imem/cli.py` - Updated `_execute_search()` for collection routing
- `imem/src/imem/ingest.py` - Changed metadata from `source: 'changelog'` to `source: 'context'`

### Configuration
- Registry schema changed from single `collection` string to `collections` dict with `context` and `conversation` keys
- Doc counts changed from single `doc_count` integer to `doc_counts` dict with per-type counts

### New Commands
- `imem index <source>` - Unified indexing for all sources
- `imem search <source> "query"` - Source as positional argument
- `imem collections list` - Show registered and orphaned collections
- `imem collections clean [--dry-run]` - Remove orphaned collections

### Behavioral Changes
- Collection auto-creation on first use (no `--force` needed)
- `--force` flag now means "recreate from scratch" not "create if missing"
- Search defaults to showing both collection types in status command
- Old commands (noun-verb groups) still exist for backward compatibility
