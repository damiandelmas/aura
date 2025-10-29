---
session_id: e025fbb0-1abb-46e8-82a1-79c49afcc32d
date: 2025-10-27
type: pattern.innovation
resolution: architectural
keywords: "json-interface parallel-execution internal-composition"
---

# Batch Composition Pattern

## Pattern Structure

**Compositional peer that orchestrates primitives.**

### Component Relationship

```
Batch command:
├─ Peer to other CLI commands (not layer above)
├─ Accepts JSON configuration
└─ Internally orchestrates:
    ├─ search primitive (parallel)
    ├─ combine primitive
    ├─ graph build primitive
    └─ graph apply primitive

Client perspective:
- Single CLI command
- JSON input
- Ranked results output

Internal execution:
- Parse configuration
- Execute searches in parallel
- Compose results
- Apply graph algorithms
- Return final output
```

## Invariants

1. **Parallel execution by default**
   - Multiple queries run concurrently
   - Limited by system resources
   - 3x+ performance vs sequential

2. **JSON as data format, not API**
   - CLI still primary interface
   - JSON = structured configuration
   - Not a web API endpoint

3. **Compositional, not monolithic**
   - Internally uses primitives
   - Primitives remain usable standalone
   - Batch = convenience wrapper

## JSON Schema

```json
{
  "queries": [
    {
      "text": "search query",
      "filters": {
        "decisions": true,
        "phase": "develop",
        "after": "2025-10-01"
      },
      "limit": 10
    }
  ],
  "combine": true | false,
  "graph": {
    "algorithm": "pagerank" | "centrality" | "eigenvector",
    "top": 10
  } | null
}
```

## Execution Flow

```
def batch_execute(config):
    """Execute batch configuration"""

    # 1. Parse queries
    queries = config['queries']

    # 2. Execute in parallel
    with ThreadPoolExecutor(max_workers=len(queries)) as executor:
        futures = [executor.submit(search, q) for q in queries]
        results = [f.result() for f in futures]

    # 3. Combine if requested
    if config.get('combine'):
        all_results = flatten(results)
        deduplicated = deduplicate_by_id(all_results)
    else:
        deduplicated = results

    # 4. Apply graph operations if specified
    if config.get('graph'):
        result_ids = [r.id for r in deduplicated]

        # Build graph
        graph_id = graph_build(result_ids)

        # Apply algorithm
        algorithm = config['graph']['algorithm']
        top = config['graph'].get('top', 10)

        ranked_ids = graph_apply(graph_id, algorithm, top)

        # Reorder results
        id_to_result = {r.id: r for r in deduplicated}
        final_results = [id_to_result[rid] for rid in ranked_ids if rid in id_to_result]

        return final_results

    return deduplicated
```

## Parallelism Strategy

```
Options for parallel execution:

1. Threading (Python):
   - ThreadPoolExecutor
   - Good for I/O-bound (Qdrant queries)
   - GIL not an issue

2. Async/Await:
   - asyncio
   - More complex
   - Better for high concurrency

3. Multiprocessing:
   - Process pool
   - Overkill for network I/O
   - Higher overhead

Recommendation: ThreadPoolExecutor
- Simple implementation
- Adequate performance
- No GIL issues for network calls
```

## Deduplication

```
def deduplicate_by_id(results):
    """Remove duplicate chunks from combined results"""

    seen = set()
    deduplicated = []

    for result in results:
        if result.id not in seen:
            seen.add(result.id)
            deduplicated.append(result)

    return deduplicated
```

## Benefits

- **Performance**: 3x+ via parallelism
- **Convenience**: Single command vs manual orchestration
- **Clean interface**: JSON config vs bash scripting
- **Composability**: Uses existing primitives internally

## Trade-offs

- **Complexity**: More code than simple CLI
- **Debugging**: Harder to debug parallel execution
- **Overhead**: JSON parsing + orchestration logic

## When to Use

Use when:
- Multiple queries needed (multi-perspective)
- Authority ranking required (graph algorithms)
- Performance critical (parallel vs sequential)
- Claude Code orchestrating (clean interface)

Avoid when:
- Single query sufficient
- Sequential execution acceptable
- Simple use cases (use primitives directly)
