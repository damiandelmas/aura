# Batch Primitive: Implementation Specification

**Session:** a86bc733-c4e3-4d88-b17f-2f9e330ca11a
**Level:** Implementation (L2b)
**Date:** 2025-10-27

## Component: `imem/src/imem/batch.py`

### Core Batch Execution

```python
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any
from datetime import datetime

# Import all primitives
from imem.search import search
from imem.relationships import get_siblings, get_temporal_chain, get_session_chain
from imem.graph_ops import build_graph, apply_algorithm
from imem.filter import filter_metadata


# Operation registry
OPERATION_REGISTRY = {
    'search': search,
    'siblings': get_siblings,
    'temporal': get_temporal_chain,
    'session': get_session_chain,
    'filter': filter_metadata,
    'graph_build': build_graph,
    'graph_apply': apply_algorithm,
}


def batch_execute(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute multiple operations in parallel.

    Supports two formats:
    1. "queries" format (sugar for multi-search + combine + graph)
    2. "parallel" format (generic parallelization)
    """
    start_time = datetime.now()

    # Detect format
    if 'queries' in config:
        result = execute_queries_format(config)
    elif 'parallel' in config:
        result = execute_parallel_format(config)
    else:
        raise ValueError("Config must have 'queries' or 'parallel' key")

    # Add timing metadata
    duration_ms = (datetime.now() - start_time).total_seconds() * 1000
    result['duration_ms'] = duration_ms

    # Log operation
    log_batch_operation(config, result, duration_ms)

    return result


def execute_queries_format(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute multi-query format with optional combine + graph.

    Config:
    {
      "queries": [{"text": "...", "filters": {...}}],
      "combine": true,
      "graph": {"algorithm": "pagerank", "top": 10}
    }
    """
    queries = config['queries']
    combine = config.get('combine', False)
    graph_config = config.get('graph')

    # 1. Execute searches in parallel
    with ThreadPoolExecutor(max_workers=len(queries)) as executor:
        futures = []
        for query_spec in queries:
            future = executor.submit(
                search,
                query_spec['text'],
                filters=query_spec.get('filters', {}),
                limit=query_spec.get('limit', 10)
            )
            futures.append(future)

        # Collect results
        search_results = []
        for future in as_completed(futures):
            search_results.extend(future.result())

    operation_log = [
        {"op": "search", "query": q['text'], "count": len(r)}
        for q, r in zip(queries, [future.result() for future in futures])
    ]

    # 2. Combine if requested
    if combine:
        # Deduplicate by result ID
        seen = set()
        combined = []
        for result in search_results:
            if result.id not in seen:
                seen.add(result.id)
                combined.append(result)
        search_results = combined
        operation_log.append({"op": "combine", "count": len(search_results)})

    # 3. Graph operations if requested
    if graph_config:
        # Build graph
        graph_id = build_graph([r.id for r in search_results], collection_name)
        operation_log.append({"op": "graph_build", "graph_id": graph_id, "node_count": len(search_results)})

        # Apply algorithm
        algorithm = graph_config['algorithm']
        ranked_ids = apply_algorithm(graph_id, algorithm)
        operation_log.append({"op": "graph_apply", "algorithm": algorithm})

        # Return top N
        top_n = graph_config.get('top', 10)
        search_results = [load_result(rid) for rid in ranked_ids[:top_n]]

    return {
        'results': [serialize_result(r) for r in search_results],
        'count': len(search_results),
        'strategy': 'queries',
        'operations': operation_log
    }


def execute_parallel_format(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute generic parallel format.

    Config:
    {
      "parallel": [
        {"op": "search", "query": "...", "filters": {...}},
        {"op": "siblings", "result_id": "..."}
      ]
    }
    """
    operations = config['parallel']

    # Execute operations in parallel
    with ThreadPoolExecutor(max_workers=len(operations)) as executor:
        futures = {}
        for i, op_spec in enumerate(operations):
            future = executor.submit(dispatch_operation, op_spec)
            futures[future] = (i, op_spec)

        # Collect results in order
        results = [None] * len(operations)
        errors = []

        for future in as_completed(futures):
            idx, op_spec = futures[future]
            try:
                results[idx] = {
                    'op': op_spec['op'],
                    'output': future.result(),
                    'success': True
                }
            except Exception as e:
                results[idx] = {
                    'op': op_spec['op'],
                    'error': str(e),
                    'success': False
                }
                errors.append({'op': op_spec['op'], 'error': str(e)})

    return {
        'results': results,
        'count': len(results),
        'strategy': 'parallel',
        'errors': errors if errors else None
    }


def dispatch_operation(op_spec: Dict[str, Any]) -> Any:
    """
    Dispatch a single operation to its handler.
    """
    op_name = op_spec['op']

    if op_name not in OPERATION_REGISTRY:
        raise ValueError(f"Unknown operation: {op_name}")

    func = OPERATION_REGISTRY[op_name]

    # Extract parameters based on operation
    if op_name == 'search':
        return func(
            query=op_spec['query'],
            filters=op_spec.get('filters', {}),
            limit=op_spec.get('limit', 10)
        )
    elif op_name == 'siblings':
        return func(result_id=op_spec['result_id'])
    elif op_name == 'temporal':
        return func(
            result_id=op_spec['result_id'],
            direction=op_spec.get('direction', 'forward')
        )
    elif op_name == 'session':
        return func(result_id=op_spec['result_id'])
    elif op_name == 'filter':
        return func(filters=op_spec['filters'])
    elif op_name == 'graph_build':
        return func(result_ids=op_spec['result_ids'])
    elif op_name == 'graph_apply':
        return func(
            graph_id=op_spec['graph_id'],
            algorithm=op_spec['algorithm']
        )
    else:
        raise ValueError(f"Dispatch not implemented for: {op_name}")


def serialize_result(result) -> Dict[str, Any]:
    """Convert result object to JSON-serializable dict"""
    return {
        'id': result.id,
        'content': result.payload.get('content', ''),
        'score': result.score,
        'metadata': result.payload
    }


def log_batch_operation(config: Dict[str, Any], result: Dict[str, Any], duration_ms: float):
    """Log batch operation for observability"""
    import os
    from pathlib import Path

    log_dir = Path.home() / '.context' / 'imem_usage'
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / 'batch.log'

    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'operation': 'batch',
        'format': result.get('strategy'),
        'operations': result.get('operations', []),
        'duration_ms': duration_ms,
        'result_count': result.get('count', 0)
    }

    with open(log_file, 'a') as f:
        f.write(json.dumps(log_entry) + '\n')
```

---

## CLI Integration

```python
# imem/src/imem/cli.py

@imem.command()
@click.argument('config', default='-')
def batch(config):
    """
    Execute multiple operations in parallel.

    CONFIG can be:
    - JSON string: '{"queries": [...]}'
    - File path: @config.json
    - Stdin: - (default)
    """
    import sys
    from imem.batch import batch_execute

    # Read config
    if config == '-':
        config_str = sys.stdin.read()
    elif config.startswith('@'):
        with open(config[1:]) as f:
            config_str = f.read()
    else:
        config_str = config

    # Parse JSON
    try:
        config_dict = json.loads(config_str)
    except json.JSONDecodeError as e:
        click.echo(f"Invalid JSON: {e}", err=True)
        sys.exit(1)

    # Execute batch
    result = batch_execute(config_dict)

    # Output result
    click.echo(json.dumps(result, indent=2))
```

---

## Usage Examples

### Multi-Query with Ranking

```bash
imem batch '{
  "queries": [
    {"text": "authentication patterns", "filters": {"decisions": true}},
    {"text": "security patterns", "filters": {"patterns": true}}
  ],
  "combine": true,
  "graph": {"algorithm": "pagerank", "top": 5}
}'
```

Response:
```json
{
  "results": [
    {
      "id": "abc123",
      "content": "### Use JWT Authentication",
      "score": 0.94,
      "metadata": {...}
    }
  ],
  "count": 5,
  "strategy": "queries",
  "operations": [
    {"op": "search", "query": "authentication patterns", "count": 10},
    {"op": "search", "query": "security patterns", "count": 8},
    {"op": "combine", "count": 15},
    {"op": "graph_build", "graph_id": "a7f3d2c1", "node_count": 15},
    {"op": "graph_apply", "algorithm": "pagerank"}
  ],
  "duration_ms": 112
}
```

### Generic Parallel Operations

```bash
imem batch '{
  "parallel": [
    {"op": "search", "query": "chunking", "filters": {"decisions": true}},
    {"op": "siblings", "result_id": "abc123"},
    {"op": "filter", "filters": {"session": "xyz789"}}
  ]
}'
```

Response:
```json
{
  "results": [
    {
      "op": "search",
      "output": {"count": 5, "results": [...]},
      "success": true
    },
    {
      "op": "siblings",
      "output": {"count": 3, "results": [...]},
      "success": true
    },
    {
      "op": "filter",
      "output": {"count": 12, "results": [...]},
      "success": true
    }
  ],
  "count": 3,
  "strategy": "parallel",
  "duration_ms": 95
}
```

### From File

```bash
# query-config.json
{
  "queries": [
    {"text": "provider patterns", "filters": {"patterns": true}},
    {"text": "provider implementation", "filters": {"layer": "implementation"}}
  ],
  "combine": true,
  "graph": {"algorithm": "centrality", "top": 3}
}

# Execute
imem batch @query-config.json
```

### From Stdin (Pipe)

```bash
echo '{
  "queries": [{"text": "auth", "filters": {"decisions": true}}]
}' | imem batch
```

---

## In Slash Commands

```markdown
# .claude/commands/authority-search.md

Multi-query search with authority ranking.

Usage: /authority-search <topic>

Executes:
```bash
imem batch '{
  "queries": [
    {"text": "<topic>", "filters": {"decisions": true}},
    {"text": "<topic>", "filters": {"patterns": true}},
    {"text": "<topic>", "filters": {"failures": true}}
  ],
  "combine": true,
  "graph": {"algorithm": "pagerank", "top": 5}
}'
```

Returns top 5 most authoritative results across all section types.
```

---

## Performance Testing

```python
# tests/test_batch_performance.py

import time

def test_batch_speedup():
    """Verify parallel execution is faster than sequential"""

    # Sequential
    start = time.time()
    r1 = search("auth", filters={"decisions": true})
    r2 = search("security", filters={"patterns": true})
    r3 = search("JWT", filters={"failures": true})
    sequential_time = time.time() - start

    # Batch
    start = time.time()
    result = batch_execute({
        "queries": [
            {"text": "auth", "filters": {"decisions": true}},
            {"text": "security", "filters": {"patterns": true}},
            {"text": "JWT", "filters": {"failures": true}}
        ]
    })
    batch_time = time.time() - start

    speedup = sequential_time / batch_time
    assert speedup > 2.0, f"Expected 2x+ speedup, got {speedup:.2f}x"
```

---

## File Structure

```
imem/
├── src/imem/
│   ├── batch.py         (NEW - ~250 lines)
│   └── cli.py           (UPDATE - add batch command)
└── tests/
    └── test_batch.py    (NEW - ~100 lines)
```

---

## Dependencies

```python
# requirements.txt
# (no new dependencies - uses stdlib concurrent.futures)
```

---

## Error Handling

```python
# Best-effort mode (default)
# Returns partial results + error details

{
  "results": [
    {"op": "search", "output": {...}, "success": true},
    {"op": "siblings", "error": "Result not found", "success": false}
  ],
  "errors": [
    {"op": "siblings", "error": "Result not found"}
  ]
}

# Atomic mode (optional)
# Fails entire batch if any operation fails

imem batch --atomic '{"parallel": [...]}'
# → If any op fails, returns error + no results
```

---

## Observability

Log file: `~/.context/imem_usage/batch.log`

```json
{"timestamp": "2025-10-27T15:30:00", "operation": "batch", "format": "queries", "operations": [{"op": "search", "count": 10}, {"op": "graph_apply", "algorithm": "pagerank"}], "duration_ms": 105, "result_count": 5}
```

Pattern mining:
```bash
# Most common batch patterns
cat ~/.context/imem_usage/batch.log | jq '.operations' | jq -s 'group_by(.) | map({pattern: .[0], count: length}) | sort_by(.count) | reverse'
```

---

## The Key Implementation Insight

batch is infrastructure, not domain logic:
- Works with any registered operation
- Parallelizes via ThreadPoolExecutor
- Returns structured JSON
- Logs for observability

Extensible: New primitives auto-supported via OPERATION_REGISTRY.

Domain primitives focus on "what" (search, graph, etc.)
batch focuses on "how" (parallel execution)

Clean separation of concerns.
