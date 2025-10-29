# Batch Primitive: Architecture Pattern

**Session:** a86bc733-c4e3-4d88-b17f-2f9e330ca11a
**Level:** Architecture Pattern (L2a)
**Date:** 2025-10-27

## System Topology

```
JSON Config (operations specification)
    ↓
Operation Dispatcher (routing)
    ↓
Parallel Execution (asyncio/threading)
    ↓
Result Collection
    ↓
JSON Response (structured output)
```

## Interface Design

### Sugar Format ("queries")

```json
{
  "queries": [
    {"text": "auth security", "filters": {"decisions": true}},
    {"text": "auth implementation", "filters": {"layer": "implementation"}}
  ],
  "combine": true,
  "graph": {"algorithm": "pagerank", "top": 10}
}
```

**Semantics:**
- Execute searches in parallel
- Merge results if `combine: true`
- Build graph and apply algorithm if `graph` specified
- Return top N ranked results

**Use case:** 90% of batch operations (multi-query + ranking)

### Generic Format ("parallel")

```json
{
  "parallel": [
    {"op": "search", "query": "auth", "filters": {...}},
    {"op": "siblings", "result_id": "abc123"},
    {"op": "filter", "filters": {"session": "xyz"}},
    {"op": "graph_apply", "graph_id": "g1", "algorithm": "pagerank"}
  ]
}
```

**Semantics:**
- Execute any operations in parallel
- Return array of results (one per operation)

**Use case:** 10% of batch operations (mixed primitive types)

## Dispatch Algorithm

```
1. Parse JSON config
2. Detect format (queries vs parallel)
3. For each operation:
   - Map to function: "search" → search(), "siblings" → get_siblings()
   - Extract parameters from config
   - Validate operation exists
4. Execute operations in parallel (asyncio.gather)
5. Collect results
6. If "queries" format with "combine" or "graph":
   - Post-process (merge, build graph, rank)
7. Return JSON response
```

## Parallelization Strategy

### Option 1: asyncio (Python async)

```python
async def execute_operations(ops):
    async def run_op(op):
        if op['op'] == 'search':
            return await async_search(op['query'], op.get('filters'))
        # ... dispatch other ops

    return await asyncio.gather(*[run_op(op) for op in ops])
```

**Pros:** Native Python, efficient I/O
**Cons:** Requires async versions of primitives

### Option 2: ThreadPoolExecutor

```python
from concurrent.futures import ThreadPoolExecutor

def execute_operations(ops):
    with ThreadPoolExecutor(max_workers=len(ops)) as executor:
        futures = []
        for op in ops:
            if op['op'] == 'search':
                futures.append(executor.submit(search, op['query'], op.get('filters')))
            # ... dispatch other ops

        return [f.result() for f in futures]
```

**Pros:** Works with existing sync functions
**Cons:** Thread overhead

**Recommendation:** ThreadPoolExecutor for v1 (works with existing code)

## Operation Registry

```python
OPERATION_REGISTRY = {
    'search': search,
    'siblings': get_siblings,
    'filter': filter_metadata,
    'graph_build': build_graph,
    'graph_apply': apply_algorithm,
    # Future primitives auto-registered
}

def dispatch(op_spec):
    """Generic operation dispatcher"""
    op_name = op_spec['op']
    if op_name not in OPERATION_REGISTRY:
        raise ValueError(f"Unknown operation: {op_name}")

    func = OPERATION_REGISTRY[op_name]
    params = extract_params(op_spec, func)
    return func(**params)
```

Extensible: New primitives just register themselves.

## Response Format

### Queries Format Response

```json
{
  "results": [
    {
      "id": "abc123",
      "content": "...",
      "score": 0.94,
      "metadata": {...}
    }
  ],
  "count": 10,
  "strategy": "queries",
  "operations": [
    {"op": "search", "query": "auth security", "count": 15},
    {"op": "search", "query": "auth implementation", "count": 12},
    {"op": "graph_build", "node_count": 27},
    {"op": "graph_apply", "algorithm": "pagerank"}
  ]
}
```

### Parallel Format Response

```json
{
  "results": [
    {
      "op": "search",
      "output": {"count": 10, "results": [...]}
    },
    {
      "op": "siblings",
      "output": {"count": 5, "results": [...]}
    }
  ],
  "strategy": "parallel",
  "operations": 2
}
```

## Performance Characteristics

| Scenario | Sequential | Batch (Parallel) | Speedup |
|----------|------------|------------------|---------|
| 3 searches @ 100ms | 300ms | ~110ms | 2.7x |
| 5 searches @ 80ms | 400ms | ~90ms | 4.4x |
| Search + siblings @ 100ms | 200ms | ~110ms | 1.8x |

Overhead: ~10ms for dispatch + collection

## Error Handling

```
If any operation fails:
  Option 1: Fail entire batch (atomic)
  Option 2: Return partial results (best-effort)

Recommendation: Best-effort by default, atomic mode optional

Response includes success/failure per operation:
{
  "results": [...],
  "errors": [
    {"op": "siblings", "result_id": "invalid", "error": "Not found"}
  ]
}
```

## Observability

```
Usage log:
{
  "timestamp": "2025-10-27T15:00:00",
  "operation": "batch",
  "format": "queries",
  "operations": [
    {"op": "search", "duration_ms": 95},
    {"op": "search", "duration_ms": 102},
    {"op": "graph_build", "duration_ms": 45},
    {"op": "graph_apply", "duration_ms": 38}
  ],
  "total_duration_ms": 112,
  "speedup": "2.5x vs sequential"
}
```

Enables pattern mining: "80% of batch calls use 2-3 searches + pagerank"

## CLI Interface

```bash
# Queries format (sugar)
imem batch '{"queries": [...], "combine": true, "graph": {...}}'

# Parallel format (generic)
imem batch '{"parallel": [{"op": "search", ...}, {"op": "siblings", ...}]}'

# From file
imem batch @query-config.json

# Pipe from stdin
echo '{"queries": [...]}' | imem batch
```

## Integration with Slash Commands

```markdown
# .claude/commands/multi-angle-search.md

Search from multiple angles and rank by authority.

Usage: /multi-angle-search <topic>

Executes:
  imem batch '{
    "queries": [
      {"text": "<topic>", "filters": {"decisions": true}},
      {"text": "<topic>", "filters": {"patterns": true}},
      {"text": "<topic>", "filters": {"failures": true}}
    ],
    "combine": true,
    "graph": {"algorithm": "pagerank", "top": 5}
  }'

Returns top 5 most authoritative results across all angles.
```

## Architectural Properties

**Generic:** Works with any primitive (current + future)
**Parallel:** Reduces latency via concurrent execution
**Observable:** Single logged operation (not N separate logs)
**Atomic:** All-or-nothing option for transactional consistency
**Extensible:** New primitives auto-supported via registry

## The Key Design Decision

Not "multi-query wrapper" but "parallelization infrastructure."

Domain primitives: search, siblings, filter, graph ops
Infrastructure primitive: batch

Orthogonal concerns. Clean separation.
