---
session_id: e025fbb0-1abb-46e8-82a1-79c49afcc32d
date: 2025-10-27
type: vision.innovation
resolution: geometric
keywords: "parallelism composition single-round-trip"
---

# Batch Composition: Parallel Primitive Orchestration

## The Insight

**Batch enables parallelism that sequential CLI cannot.**

Sequential primitives: 3 searches = 3 round trips = 3x latency
Batch composition: 3 searches = 1 round trip = internal parallelism

The power isn't abstraction. It's performance.

## The Geometry

```
Sequential CLI execution:

Query 1: imem search "auth" --decisions
  → Wait for results (50ms)

Query 2: imem search "auth" --failures
  → Wait for results (50ms)

Query 3: imem search "auth" --patterns
  → Wait for results (50ms)

Total latency: 150ms
Parallelism: None (sequential)


Batch composition:

imem batch '{"queries": [
  {"text": "auth", "filters": {"decisions": true}},
  {"text": "auth", "filters": {"failures": true}},
  {"text": "auth", "filters": {"patterns": true}}
]}'

Internal execution: ALL queries run in parallel
Total latency: 50ms (limited by slowest query)

3x performance improvement
```

## The System Property

**Batch = compositional peer, not abstraction layer:**

```
Architecture levels:

Primitives (CLI commands):
├─ imem search
├─ imem siblings
├─ imem filter
├─ imem graph build
└─ imem graph apply

Batch (compositional peer):
└─ imem batch <json>
    ├─ Internally calls: search (parallel)
    ├─ Internally calls: graph build
    ├─ Internally calls: graph apply
    └─ Returns: Final ranked results

Batch sits at same level as primitives
Difference: Orchestrates others internally
```

## The Behavior

**Single JSON interface, complex orchestration:**

```
Input: JSON configuration
{
  "queries": [
    {"text": "auth", "filters": {"decisions": true}, "limit": 10},
    {"text": "auth", "filters": {"failures": true}, "limit": 10}
  ],
  "combine": true,
  "graph": {
    "algorithm": "pagerank",
    "top": 10
  }
}

Internal execution:
1. Parse JSON
2. Execute queries IN PARALLEL (threading/async)
3. Combine results (if combine: true)
4. Build graph from combined results (if graph specified)
5. Apply PageRank
6. Return top 10 by authority

Output: Ranked results
```

## Why This Matters

**Multi-query patterns are common:**

Real usage pattern from session:
- "Find all decisions, failures, patterns for topic X"
- "Rank by authority across all perspectives"
- 3 separate queries + combine + rank

Without batch:
- 3 sequential CLI calls
- Manual result combination
- Manual graph construction
- ~150ms + developer overhead

With batch:
- 1 CLI call
- Automatic parallel execution
- Automatic combination + ranking
- ~50ms + zero overhead

**3x performance, 100% developer efficiency**

## The Moat

**Parallelism without complexity.**

Alternative: Claude Code manually orchestrates
- Execute 3 bash commands sequentially
- Parse 3 result sets
- Combine in Python/bash
- Call graph operations
- Parse final results

Reality: Slow, error-prone, verbose

Batch: Single JSON config, internal optimization
- One command
- Parallel by default
- Clean interface

**Developer experience = competitive advantage**
