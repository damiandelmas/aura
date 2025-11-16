---
schema_version: "v3_adaptive"
type: "cleanup.compose-routing"
status: "completed"
keywords: "cleanup compose collection-routing test-removal"
timestamp: "2025-11-15T17:21:00-0700"
---

# Cleanup: Compose Routing & Test Removal

## Request
> "assess git staged changes"

## Overview
<details><summary>Removed stale test artifacts and fixed compose collection routing to support conversations (single-collection mode) alongside context docs (dual-collection mode).</summary>

Deleted 2,402 lines of obsolete validation generation code and LlamaIndex experiments. Fixed compose fallback to use base collection name when `_impl` suffix doesn't exist, enabling conversation queries via compose.
</details>

## Decisions

### Remove Validation Set Generator
- **What**: Deleted `.claude/agents/fleet/generate-validation-set.py` + JSON output
- **Why**: Stale experiment, no longer referenced
- **Impact**: -2,125 lines

### Fix Compose Collection Routing
- **Problem**: Hardcoded `_impl` suffix failed for conversations (single collection)
- **Solution**: Check if `_impl` exists, fallback to base name
- **Location**: `imem/src/imem/compose.py:46-53`

## Audit

### Removed
- `.claude/agents/fleet/generate-validation-set.py` (-276 lines)
- `.claude/agents/fleet/validation-set.json` (-1,849 lines)
- `tests/251023-1537/show_sample_nodes.py` (-58 lines)
- `tests/251023-1537/test_llamaindex_pipeline.py` (-198 lines)

### Modified
- `imem/src/imem/compose.py` - Fallback routing for single-collection mode
- `trace/src/aura_trace/formatter.py` - H2 section separation
- `imem/src/imem/ingest.py` - Metadata extraction
- `imem/src/imem/cli.py` - Filter flags

### Created
- `test_granular_flow.sh` - Chunking test harness
- `trace/search_configs.json` - Search config examples
