---
date: 2025-10-27
type: architecture.implementation
status: planned
keywords: "asyncio json-cli dispatch python implementation"
---

# Architecture: Batch Parallelization Implementation

## Component

**Location:** `imem/src/imem/batch.py`
**Status:** Planned (Phase 6.5)
**Effort:** ~150 lines

---

## Interface

### CLI

```bash
imem batch '{"parallel": [...]}'
```

**Input:** JSON string (single CLI argument)
**Output:** JSON results (stdout)

### JSON Schema

```json
{
  "parallel": [
    {
      "op": "search",
      "query": "authentication",
      "filters": {"decisions": true},
      "limit": 10
    },
    {
      "op": "siblings",
      "result_id": "abc123"
    },
    {
      "op": "graph_apply",
      "graph_id": "g1",
      "algorithm": "pagerank"
    }
  ]
}
```

**Sugar variant (multi-query shorthand):**
```json
{
  "queries": [
    {"text": "auth", "filters": {"decisions": true}},
    {"text": "auth", "filters": {"failures": true}}
  ],
  "combine": true,
  "graph": {"algorithm": "pagerank", "top": 10}
}
```

---

## Implementation

### Core Function

```python
import asyncio
import json
from typing import Any, Dict, List

async def batch_execute(config: Dict) -> Dict[str, Any]:
    """Execute operations in parallel"""

    # Handle sugar format (queries + combine + graph)
    if 'queries' in config:
        return await _execute_query_sugar(config)

    # Handle generic parallel format
    operations = config.get('parallel', [])

    # Dispatch all operations concurrently
    tasks = [_dispatch_operation(op) for op in operations]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    return {
        'results': results,
        'count': len(results),
        'errors': [r for r in results if isinstance(r, Exception)]
    }
```

### Operation Dispatcher

```python
async def _dispatch_operation(op: Dict) -> Any:
    """Dispatch single operation to appropriate handler"""
    op_type = op['op']

    if op_type == 'search':
        return await _async_search(
            op['query'],
            op.get('filters', {}),
            op.get('limit', 10)
        )

    elif op_type == 'siblings':
        return await _async_siblings(op['result_id'])

    elif op_type == 'filter':
        return await _async_filter(op['filters'])

    elif op_type == 'graph_build':
        return await _async_graph_build(op['result_ids'])

    elif op_type == 'graph_apply':
        return await _async_graph_apply(
            op['graph_id'],
            op['algorithm']
        )

    else:
        raise ValueError(f"Unknown operation: {op_type}")
```

### Async Wrappers

```python
async def _async_search(query: str, filters: Dict, limit: int):
    """Async wrapper for search primitive"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: search(query, filters, limit)
    )

async def _async_siblings(result_id: str):
    """Async wrapper for siblings primitive"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: get_siblings(result_id)
    )

# Similar wrappers for filter, graph_build, graph_apply...
```

### Sugar Handler (Multi-Query)

```python
async def _execute_query_sugar(config: Dict) -> Dict[str, Any]:
    """Handle queries + combine + graph sugar"""

    # 1. Execute all queries in parallel
    query_specs = config['queries']
    tasks = [
        _async_search(q['text'], q.get('filters', {}), q.get('limit', 10))
        for q in query_specs
    ]
    results_list = await asyncio.gather(*tasks)

    # 2. Combine if requested
    if config.get('combine'):
        results = _combine_results(results_list)
    else:
        return {'results': results_list}

    # 3. Graph operations if requested
    if config.get('graph'):
        graph_config = config['graph']

        # Build graph
        result_ids = [r.id for r in results]
        graph_id = await _async_graph_build(result_ids)

        # Apply algorithm
        ranked = await _async_graph_apply(
            graph_id,
            graph_config['algorithm']
        )

        # Return top N
        top = graph_config.get('top', 10)
        return {'results': ranked[:top]}

    return {'results': results}
```

---

## CLI Entry Point

```python
# imem/src/imem/cli.py

@click.command()
@click.argument('config_json', type=str)
def batch(config_json: str):
    """Execute operations in parallel

    Example:
        imem batch '{"parallel": [{"op": "search", "query": "auth"}]}'
    """
    try:
        config = json.loads(config_json)
    except json.JSONDecodeError as e:
        click.echo(f"Invalid JSON: {e}", err=True)
        sys.exit(1)

    # Execute batch
    result = asyncio.run(batch_execute(config))

    # Output JSON
    click.echo(json.dumps(result, indent=2))
```

---

## Performance Characteristics

**Parallelization gain:**
- N independent operations: ~N× speedup
- Overhead: ~10-20ms (asyncio coordination)
- Ideal for: I/O-bound operations (vector search, graph traversal)

**Benchmarks (estimated):**
- 3 searches sequential: 300ms (3 × 100ms)
- 3 searches parallel: 110ms (100ms + 10ms overhead)
- Gain: 2.7× speedup

**Limitations:**
- CPU-bound operations: Limited by GIL (use multiprocessing)
- Dependent operations: Must be sequential (no parallelization)
- Large result sets: Memory overhead (all held concurrently)

---

## Error Handling

```python
async def batch_execute(config: Dict) -> Dict[str, Any]:
    """Execute with per-operation error isolation"""
    operations = config.get('parallel', [])

    # Gather with exceptions (don't fail entire batch)
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Separate successes from failures
    successes = [r for r in results if not isinstance(r, Exception)]
    failures = [
        {'op': operations[i], 'error': str(r)}
        for i, r in enumerate(results)
        if isinstance(r, Exception)
    ]

    return {
        'results': successes,
        'errors': failures,
        'success_count': len(successes),
        'failure_count': len(failures)
    }
```

**Property:** One operation failure doesn't fail entire batch.

---

## Extension Pattern

Adding new primitives:

```python
# 1. Add async wrapper
async def _async_new_operation(param1, param2):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: new_operation(param1, param2)
    )

# 2. Add dispatch case
async def _dispatch_operation(op: Dict) -> Any:
    # ... existing cases ...

    elif op_type == 'new_operation':
        return await _async_new_operation(op['param1'], op['param2'])
```

**Zero changes to batch core logic.**

---

## Dependencies

```python
# Standard library only
import asyncio
import json
from typing import Any, Dict, List
```

No external async frameworks needed.

---

## Testing Strategy

```python
# test_batch.py

async def test_parallel_search():
    """Test multiple searches execute in parallel"""
    config = {
        'parallel': [
            {'op': 'search', 'query': 'auth', 'limit': 5},
            {'op': 'search', 'query': 'cache', 'limit': 5},
            {'op': 'search', 'query': 'db', 'limit': 5}
        ]
    }

    start = time.time()
    result = await batch_execute(config)
    elapsed = time.time() - start

    assert len(result['results']) == 3
    assert elapsed < 0.15  # Parallel should be <150ms
    # Sequential would be ~300ms (3 × 100ms)

async def test_error_isolation():
    """Test that one failure doesn't fail batch"""
    config = {
        'parallel': [
            {'op': 'search', 'query': 'valid'},
            {'op': 'invalid_op', 'query': 'fail'},  # Will raise
            {'op': 'search', 'query': 'also_valid'}
        ]
    }

    result = await batch_execute(config)

    assert result['success_count'] == 2
    assert result['failure_count'] == 1
    assert len(result['errors']) == 1
```

---

## Usage Example (from Claude Code)

```python
# Claude Code constructs JSON inline
config = {
    'queries': [
        {'text': 'authentication', 'filters': {'decisions': True}},
        {'text': 'authentication', 'filters': {'failures': True}}
    ],
    'combine': True,
    'graph': {'algorithm': 'pagerank', 'top': 10}
}

# Single bash call
result = Bash(f"imem batch '{json.dumps(config)}'")

# Parse JSON output
data = json.loads(result)
print(f"Found {len(data['results'])} ranked results")
```

---

## Summary

**Implementation:**
- ~150 lines (batch.py)
- asyncio-based parallelization
- JSON string CLI interface
- Generic operation dispatcher

**Properties:**
- Zero changes when adding primitives
- Per-operation error isolation
- ~Nx speedup for N operations
- Observable (single JSON log entry)

**Next:** See `.pattern.md` for language-agnostic principle.
