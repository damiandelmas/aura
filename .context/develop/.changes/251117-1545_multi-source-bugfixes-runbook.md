---
schema_version: "v3_adaptive"
type: "bugfix.multi-source-compose"
status: "completed"
keywords: "multi-query aggregation thread-safety discovery-filtering runbook introspection"
session_id: "0bf8bcc5-1fe6-44cb-8bd8-536ba1667b3b"
timestamp: "2025-11-17T15:45:00-0800"
---

# Multi-Source Compose Bugfixes + Usage Runbook

## Request
> "Debug why multi-source routing not working as expected, fix bugs, and create runbook for proper usage"

## Overview
Fixed three critical bugs preventing multi-source compose queries from working correctly. Multi-query aggregation was returning single results due to thread-safety issues with shared encoder instances. Source routing failed with 404 errors because `_impl` suffix wasn't added to context collections. Discovery data wasn't filtered, bloating output with 35+ fields per chunk. Created usage runbook documenting what actually works vs what's useless noise.

## Decisions

### Per-Thread Encoder Instances for Safety
- **Context**: Multi-query parallel execution caused tensor size mismatch exceptions when sharing single encoder instance across threads
- **Solution**: Pass `None` for encoder in parallel tasks, let `_single_search` create thread-local instances
- **Rationale**: SentenceTransformer has internal state that breaks when used concurrently from multiple threads
- **Alternatives**: Use locks (serializes queries, defeats parallelism), single-threaded execution (slow)
- **Implementation**: Lines 143, 257-259 in compose.py

### Add `_impl` Suffix in Per-Query Routing
- **Context**: Multi-source routing looked for `imem_xxx_context` but actual collection is `imem_xxx_context_impl`
- **Solution**: After getting base collection from registry, append `_impl` suffix for context sources
- **Rationale**: Context collections use dual-layer (impl/pattern) architecture, conversations use single collection
- **Implementation**: Lines 128-130, 173-176 in compose.py

### Recursive Filtering for Discovery Data
- **Context**: Primary results filtered to 10 fields, but siblings/temporal/genealogy passed through with full 35+ field payloads
- **Solution**: Extract `_filter_single_chunk()` function, apply recursively to discovery arrays
- **Implementation**: Lines 469-548 in compose.py

## Implementation

### Bugs Fixed

**Bug 1: Multi-Query Returns Single Result**
- **Symptom**: 2 queries → 1 result (should be 2)
- **Cause**: First query throws tensor size mismatch exception, silently caught by `gather(return_exceptions=True)`
- **Fix**: Create per-thread encoder instances (compose.py:143, 257-259)

**Bug 2: Source Filtering Returns 404**
- **Symptom**: `"filters": {"source": "context"}` → Collection not found error
- **Cause**: Routing returns `imem_xxx_context` but collection is `imem_xxx_context_impl`
- **Fix**: Append `_impl` suffix after registry lookup (compose.py:128-130, 173-176)

**Bug 3: Discovery Data Bloat**
- **Symptom**: Each sibling/temporal chunk has 35+ fields instead of filtered 10
- **Cause**: `_filter_results()` only filtered primary results, passed discovery through raw
- **Fix**: Extract filtering logic, apply recursively to nested arrays (compose.py:469-548)

### Code Signatures

**Thread-Safe Encoder Creation** (`compose.py:257-259`)
```python
# Create encoder if not provided (for thread safety in parallel queries)
if encoder is None:
    encoder = SentenceTransformer(config.default_model, trust_remote_code=True)
```

**Context Collection Routing** (`compose.py:128-130`)
```python
elif source == 'context':
    base_collection = registry.get_collection_by_type(project_root, 'context')
    # Context collections have _impl suffix
    query_collection = f"{base_collection}_impl"
```

**Recursive Discovery Filtering** (`compose.py:537-544`)
```python
# Filter primary result
filtered_result = _filter_single_chunk(result)

# Discovery data - apply same filtering recursively
if 'siblings' in result:
    filtered_result['siblings'] = [_filter_single_chunk(s) for s in result['siblings']]
if 'temporal' in result:
    filtered_result['temporal'] = [_filter_single_chunk(t) for t in result['temporal']]
```

## Patterns

### Thread-Local Resource Instances
- **Pattern**: When parallelizing operations, create resource instances per-thread rather than sharing
- **When**: Resource has internal state that isn't thread-safe (encoders, database connections)
- **Approach**: Pass `None` in parallel task spawning, let worker create local instance
- **Benefit**: Avoid race conditions, tensor size mismatches, connection pool exhaustion

### Recursive Structure Cleaning
- **Pattern**: Extract single-item transformation, apply recursively to nested structures
- **When**: Need same filtering/transformation on primary data and nested discovery/metadata
- **Approach**: `_filter_single_chunk()` + list comprehension over nested arrays
- **Benefit**: DRY, consistent output shape, easy to modify filtering rules

## Audit

### Created
- `.context/develop/.modules/IMEM_RUNBOOK.md` - Usage guide documenting what works vs noise

### Modified
- `imem/src/imem/compose.py` - Fixed thread-safety (lines 143, 257-259), source routing (lines 128-130, 173-176), discovery filtering (lines 469-548)
- `imem/src/imem/cli.py` - Restored `_load_preset()` function that was orphaned

### Testing
**Validated multi-source compose working:**
- Multi-query aggregation: 2 queries → 2 results ✓
- Source filtering: context/conversation routing ✓
- Discovery enrichment: siblings filtered to 10 fields ✓
- Cross-phase queries: develop + design + conversations ✓

## Usage Insights

### What Actually Works
**High quality:**
- `imem search develop "topic" --section Decisions`
- `imem search develop "topic" --section Patterns`
- `imem search conversations "topic" --chunk-type patch`

**Useless noise:**
- `imem search conversations "topic" --chunk-type thinking` ❌ Never use

### Introspection First
**AI workflow:**
1. `imem introspect --fields` - See available filters
2. `imem introspect --status` - Check what's indexed
3. `imem search` for single queries
4. `imem compose` for multi-source/discovery

**Why**: Introspection opens the landscape, shows what data exists, what's queryable

## Failures

### Genealogy Returns Empty Arrays
- **What**: Discovery enrichment for genealogy consistently returns `[]`
- **Why**: Cross-collection session_id matching may not be working, or thresholds too strict
- **Status**: Known issue, not blocking (siblings/temporal work fine)

### Conversation Thinking Chunks Useless
- **What**: Thinking chunks are context-free snippets like "Let me fix the path issue"
- **Why**: Thinking is internal reasoning, not standalone knowledge
- **Lesson**: Only use `chunk-type: message` (user requests) or `patch` (code changes)
