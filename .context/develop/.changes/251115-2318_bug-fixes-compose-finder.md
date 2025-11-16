---
schema_version: "v3_adaptive"
type: "bug-fix.indexing"
status: "completed"
keywords: "compose collection-routing conversation-indexing project-folder-matching"
timestamp: "2025-11-15T23:18:00-0700"
session_id: "08a69e59-12d9-4984-ad66-f06aec5b4af1"
---

# Bug Fixes: Compose Routing + Project Folder Matching

## Request
> "Help our brother out. Figure out whats going on with the bug."

User reported conversation indexing selecting wrong project folder (8 conversations from npta-shopify instead of 488 from aura).

## Overview

Fixed two blocking bugs: (1) compose failing on conversation collections due to incorrect `_impl` suffix assumption, (2) project folder matching using substring match causing wrong folder selection. Compose now handles single-collection mode for conversations, and folder matching uses exact path reconstruction from folder names.

## Decisions

### Fallback to Base Collection Name
- **Context**: Compose assumed all collections have `_impl` suffix
- **Problem**: Conversations use single collection (no impl/pattern split), compose failed with 404
- **Solution**: Check if `_impl` collection exists, fallback to base name if not
- **Rationale**: Conversations don't need dual collections (only changelogs use pattern extraction)

### Path Reconstruction Over Substring Match
- **Context**: Project folder fallback matched by `if "main" in folder_name`
- **Problem**: Matched first alphabetically (npta-shopify-main before aura-main)
- **Solution**: Convert folder name to path (`-home-axp-projects-foo` → `/home/axp/projects/foo`), exact match
- **Rationale**: Claude folder names ARE paths with `-` separator

## Implementation

**Compose Collection Routing** (`imem/src/imem/compose.py`)
```python
# Before: Always assumed _impl suffix
query_collection = f"{collection_name}_impl"

# After: Check existence, fallback to base
impl_collection = f"{collection_name}_impl"
if client.collection_exists(impl_collection):
    query_collection = impl_collection
else:
    query_collection = collection_name  # Conversations
```

**Project Folder Matching** (`trace/src/aura_trace/finder.py`)
```python
# Before: Substring match (wrong)
if project_name.lower() in project_folder.name.lower():
    return project_folder

# After: Path reconstruction (exact)
if folder_name.startswith('-'):
    reconstructed_path = Path('/' + folder_name[1:].replace('-', '/'))
    if reconstructed_path == project_path:
        return project_folder
```

## Patterns

### Collection Existence Checks Before Query
- **Pattern**: Don't assume collection naming conventions, check existence
- **When**: Systems with multiple collection strategies (dual vs single)
- **Benefit**: Graceful handling of different collection types

## Audit

### Modified
- `imem/src/imem/compose.py` - Added collection existence check, fallback logic
- `trace/src/aura_trace/finder.py` - Replaced substring match with path reconstruction

### Verified
- Compose works with conversations: `imem compose '{"source": "conversations", ...}'`
- Folder matching finds correct project: 488 conversations (not 8)
- Incremental indexing skips existing sessions correctly
