---
schema_version: "v3_adaptive"
type: "bug-fix.discovery-primitives"
status: "completed"
keywords: "compose temporal-discovery genealogy threshold cross-collection routing"
timestamp: "2025-11-17T15:55:00-0700"
session_id: "34194c23-4034-4697-b026-9e9d9a1c4725"
---

# IMEM Compose Discovery Primitive Fixes

## Request
> "Test our system. Give me a lineage of COMPOSE.py"
> "do more tests"
> "threshold must be MUCH lower. we're often only getting .6 or .7"

## Overview
Fixed two discovery primitive bugs preventing temporal and genealogy retrieval. Lowered temporal similarity threshold from 0.85 to 0.65 to match typical cross-time evolution scores. Fixed genealogy cross-collection routing bug that searched wrong collection for conversation chunks.

## Decisions

### Lower Temporal Threshold to 0.65
- **Context**: Temporal discovery returned 0 results with 0.85 threshold
- **Solution**: Lowered to 0.65 to match typical evolution scores (0.6-0.7 range)
- **Result**: 0 → 9 temporal results for Phase 6 query

### Fix Genealogy Cross-Collection Routing
- **Context**: Genealogy searched same collection instead of conversation collection
- **Solution**: Extract base name via `split('_context')[0]` to route to `{base}_conversation`
- **Alternative**: Previous logic used `.replace('_impl', '')` which left `_context` in path
- **Result**: 0 → 5 genealogy results for matching session_ids

## Implementation

### Code Signatures

**Temporal Threshold** (`imem/src/imem/primitives/discovery.py:224`)
```python
score_threshold=0.65,  # Lower threshold for temporal evolution (typical scores 0.6-0.7)
```

**Genealogy Collection Routing** (`imem/src/imem/primitives/discovery.py:146-147`)
```python
base_name = collection_name.split('_context')[0]
conversation_collection = f"{base_name}_conversation"
```

## Audit

### Modified
- `imem/src/imem/primitives/discovery.py` - Lowered temporal threshold (2 locations), fixed genealogy routing logic

### Test Results
| Primitive | Before | After |
|-----------|--------|-------|
| Temporal discovery | 0 results | 9 results |
| Genealogy | 0 results | 5 results |
| Siblings filtering | ✅ 14→7 | ✅ (unchanged) |
| Multi-source routing | ✅ | ✅ (unchanged) |
