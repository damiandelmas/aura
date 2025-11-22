---
schema_version: "v3_adaptive"
type: "refactor.qdrant-removal"
status: "completed"
keywords: "qdrant sqlite cleanup phases indexer introspect cli"
timestamp: "2025-11-21T21:24:00-0800"
---

# Qdrant Removal - Phases 3-6 Complete

## Request
> "Execute plan.md" - Complete Qdrant cleanup phases 3-6 from doc-pac.

## Overview
Completed SQLite-first migration by removing all Qdrant dependencies from active code. Rewrote indexer to use VectorStore protocol directly, created pure parser module, rewrote introspect.py for SQLite, unified CLI commands. Legacy code preserved in `legacy/v2/` for reference.

## Decisions

### Extract Parser from Legacy
- **Context**: `compile/indexer.py` depended on `legacy/v2/ingest.py` for parsing
- **Solution**: Created `compile/parser.py` with pure parsing functions extracted from legacy
- **Benefit**: Clean separation, no legacy imports in active path

### Rewrite Introspect for SQLite
- **Context**: `introspect.py` created 5 QdrantClient instances, used `client.scroll()` extensively
- **Solution**: Rewrote to query SQLite directly via `store.store.conn`
- **Rationale**: Per intended architecture - "For discovery queries, write SQL directly. YAGNI."

### Strip Fantasy APIs from Introspect
- **Context**: `get_primitives_info()` and `get_compose_patterns()` documented fake APIs that didn't exist
- **Solution**: Deleted entirely - kept only `introspect()`, `discover_schema()`, `get_coverage_stats()`
- **Rationale**: "Metadata predicates ARE the graph" - no need for primitive wrappers

### Unify CLI Commands
- **Context**: Had `get_qdrant_store()` and duplicate commands (`index` vs `index-metadata`)
- **Solution**: Single `get_store()` returning SQLite, removed `service` command, unified aliases

## Implementation

### Parser Module (`compile/parser.py`)
```python
def parse_markdown_file(file_path, phase=None, collection_name="imem") -> List[Dict]:
    """Pure parsing - returns chunks ready for VectorStore.upsert()"""
    # LlamaIndex MarkdownNodeParser
    # Extracts: phase, section_type, file_path, timestamp, session_id
    # Returns flat chunk structure (not nested metadata)
```

### Introspect Traversal Patterns
```python
result['traversal'] = {
    'note': 'Metadata predicates ARE the graph. Query SQLite directly.',
    'patterns': {
        'same_document': 'SELECT * FROM chunks WHERE file_path = ?',
        'same_conversation': 'SELECT * FROM chunks WHERE session_id = ?',
        'temporal_after': 'SELECT * FROM chunks WHERE timestamp > ? ORDER BY timestamp',
    }
}
```

## Audit

### Created
- `compile/parser.py` - Pure markdown parsing extracted from legacy

### Modified
- `compile/indexer.py` - Uses parser + VectorStore protocol, no legacy imports
- `introspect.py` - Complete rewrite for SQLite, removed fantasy APIs
- `cli/main.py` - Removed `get_qdrant_store()`, unified to `get_store()`
- `cli/commands.py` - Removed `service` command, cleaned options
- `storage/factory.py` - SQLite-only, simplified API
- `storage/__init__.py` - Removed QdrantVectorStore export
- `config.py` - Removed qdrant_host/port/timeout
- `manage/__init__.py` - Removed unused resolver exports
- `compose/orchestrator.py` - Updated comments (SQLite not Qdrant)

### Removed
- `storage/qdrant_backend.py` - Deleted entirely
- `service/__init__.py` - Cleared (was QdrantService export)
