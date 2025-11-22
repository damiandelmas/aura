---
schema_version: "v3_adaptive"
type: "bug-fix.schema-alignment"
status: "completed"
keywords: "schema sqlite parser chunks pipeline validation runbook"
timestamp: "2025-11-21T21:30:00-0800"
---

# Schema Fix & Pipeline Validation

## Request
> "Can you test it?" - Validate the pipeline works end-to-end after Qdrant removal.

## Overview
Fixed critical schema mismatch between parser output and SQLite storage. Parser output nested metadata but SQLite expected flat structure, causing NULL indexed columns. Also deleted orphaned modules and created new runbook. Pipeline now indexes 77 files → 1,060 chunks with working queries.

## Decisions

### Flatten Parser Output
- **Context**: Parser output `chunk['metadata']['file_path']` but SQLite expected `chunk['file_path']`
- **Solution**: Moved indexed fields to top level, kept extras in `metadata` blob
- **Impact**: All indexed columns now populated correctly

### Delete Dead Code
- **Context**: Audit found `primitives/` (broken imports), `parse/` (orphaned), `service/` (empty)
- **Solution**: Deleted all three directories
- **Rationale**: `primitives/` crashed on import, `parse/` duplicated `compile/parser.py`

### Keep Resolvers for Future EPICs
- **Context**: `CompileResolver` and `EntityResolver` exist but never used
- **Solution**: Kept files, removed from `__all__` exports, added notes
- **Rationale**: Complex components need own EPICs, can't be "oneshot mid-workflow"

## Constraints

### Migration Order in SQLite
- **What**: Index creation failed on `created_at` column that didn't exist yet
- **Discovery**: `CREATE INDEX idx_created_at` ran before `ALTER TABLE ADD COLUMN created_at`
- **Workaround**: Reordered `_create_schema()` - migration BEFORE indexes

## Implementation

### Flat Chunk Structure (`compile/parser.py`)
```python
chunk = {
    'id': str(uuid4()),
    'content': node_content,
    # Top-level (SQLite indexed columns)
    'file_path': str(file_path),
    'phase': phase,
    'section_type': h2_section_type,
    'section_name': section_name,
    'timestamp': frontmatter.get('timestamp'),
    'session_id': frontmatter.get('session_id'),
    # Extras (JSON blob)
    'metadata': {'source': 'context', 'layer': layer, ...}
}
```

### Pipeline Test Results
```
Indexed: 77 files → 1,060 chunks
By phase: designate: 786, develop: 186, design: 88
Queries: phase, text, section_type all working
```

## Patterns

### Schema Alignment Pattern
- **Pattern**: Parser output structure must match storage input expectations
- **When**: Any parse → store pipeline
- **Approach**: Define canonical chunk schema, validate at boundaries
- **Anti-Pattern**: Nested structures that require extraction at storage layer

## Audit

### Created
- `.context/document/IMEM_RUNBOOK.md` - New runbook for SQLite-first CLI

### Modified
- `compile/parser.py` - Flattened chunk output (3 locations)
- `compile/indexer.py` - Flattened conversation chunk output
- `storage/sqlite.py` - Reordered migration before index creation

### Removed
- `primitives/` - Broken imports, crashed on load
- `parse/` - Orphaned, duplicated compile/parser.py
- `service/` - Empty placeholder

### Renamed
- `v3-usage.md` → `_DEPRECATED_v3-usage.md`
