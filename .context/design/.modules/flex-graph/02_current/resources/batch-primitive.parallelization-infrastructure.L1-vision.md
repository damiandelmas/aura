# Batch Primitive: Parallelization Infrastructure

**Session:** a86bc733-c4e3-4d88-b17f-2f9e330ca11a
**Level:** Vision (L1)
**Date:** 2025-10-27

## The Core Insight

batch is not a domain primitive (like search or siblings).
batch is an infrastructure primitive (like async or cache).

It parallelizes ANY CLI operations via single bash call.

## The Problem

Sequential CLI execution:
```bash
r1=$(imem search "auth" --decisions)
r2=$(imem search "auth" --failures)
r3=$(imem siblings <result-id>)
```

Total time: t1 + t2 + t3 (sequential)
Bash overhead: 3 process spawns
Parsing: 3 separate outputs

## The Solution

Parallel execution via JSON config:
```bash
imem batch '{
  "parallel": [
    {"op": "search", "query": "auth", "filters": {"decisions": true}},
    {"op": "search", "query": "auth", "filters": {"failures": true}},
    {"op": "siblings", "result_id": "abc123"}
  ]
}'
```

Total time: max(t1, t2, t3) + overhead (parallel)
Bash overhead: 1 process spawn
Parsing: 1 structured JSON output

## The Pattern

batch is to CLI primitives what asyncio is to Python functions:
- Takes multiple operations
- Executes in parallel
- Returns combined results

Not domain logic. Infrastructure.

## Why This Matters

For Claude Code orchestration:
- Reduce latency (3 ops @ 100ms = 110ms vs 300ms)
- Single bash call (observable, atomic)
- Structured output (JSON parseable)
- Composable (any primitives)

## The Architectural Choice

Could have:
- Left parallelization to Claude Code (bash &)
- Made each primitive internally async
- No batch command

Why batch wins:
- Observable (single logged operation)
- Atomic (all ops in one transaction)
- Discoverable (Claude knows it exists)
- Language-agnostic (bash-composable)

## The Generic Power

batch works with ANY future primitive:

Current primitives: search, siblings, filter, graph build, graph apply
Future primitives: export, import, validate, summarize, etc.

batch doesn't care. It just parallelizes.

## The Sugar Layer

"queries" format = batch specialized for common case:

```json
{
  "queries": [
    {"text": "auth", "filters": {"decisions": true}},
    {"text": "auth", "filters": {"failures": true}}
  ],
  "combine": true,
  "graph": {"algorithm": "pagerank"}
}
```

Sugar for: multi-search + merge + graph ranking.

90% of batch usage. Concise syntax.

Generic "parallel" format available for other 10%.

## The Innovation

Not "multi-query search" but "generic parallelization infrastructure for any CLI primitives."

Enables Claude Code to compose operations efficiently.
Reduces latency without complexity.
Observable, atomic, discoverable.

Infrastructure, not feature.
