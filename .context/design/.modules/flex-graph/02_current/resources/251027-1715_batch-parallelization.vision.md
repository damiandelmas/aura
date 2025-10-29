---
date: 2025-10-27
type: vision.innovation
status: current
keywords: "parallelization infrastructure primitive composition performance"
---

# Vision: Batch as Parallelization Infrastructure

## Core Insight

batch is not a domain operation (multi-query, search-combine-rank).
batch is infrastructure (execute ANY primitives in parallel).

**Distinction:**
- Domain: What the system does (search, filter, graph operations)
- Infrastructure: How operations execute (sequential vs parallel)

batch belongs to the second category.

---

## The Geometry

**Sequential composition (default):**
```
Operation A → wait → Operation B → wait → Operation C
Total time: tA + tB + tC
```

**Parallel composition (batch):**
```
Operation A ↘
Operation B → combine
Operation C ↗
Total time: max(tA, tB, tC) + ε
```

For independent operations: 3x speedup (3 ops).
For N operations: Nx speedup.

**Shape: Fan-out → fan-in**

---

## Universal Primitive Property

batch works with ANY operation that exposes a function signature:

```
operation(parameters) → result
```

Current operations:
- search(query, filters) → results
- siblings(result_id) → results
- filter(metadata) → results
- graph_build(result_ids) → graph_id
- graph_apply(graph_id, algorithm) → ranked_results

Future operations (automatically supported):
- validate(schema, doc) → compliance
- summarize(text) → summary
- translate(content, lang) → translated

**No code changes needed when adding primitives.**

---

## Interface Philosophy

**Not:** Protocol (MCP with structured params)
- Overhead: Client-server handshake, async coordination
- Rigidity: Schema versioning, backwards compatibility

**Not:** File-based config (write JSON → execute)
- Friction: Two-step process (write, then execute)
- State: Temp files, cleanup needed

**Yes:** JSON as CLI argument
- Simplicity: Single bash call from orchestrator
- Flexibility: Construct JSON inline programmatically
- Observable: Full config captured in single log entry

**Why this works:**
- Claude Code excels at JSON construction
- Bash accepts arbitrary-length string arguments
- Reproducible (JSON is the complete operation spec)

---

## Composition Layer Principle

**Traditional approach:**
```
Code layer:
  ├─ multi_query_with_ranking()  # Wrapper
  ├─ explain_with_context()      # Wrapper
  └─ trace_genealogy()           # Wrapper

Primitives:
  ├─ search()
  ├─ filter()
  └─ graph_apply()
```

Composition at CODE level → N wrappers for N use cases.

**batch approach:**
```
Infrastructure:
  └─ batch(operations)  # Generic parallelizer

Primitives:
  ├─ search()
  ├─ filter()
  └─ graph_apply()

Composition:
  └─ Orchestrator (Claude Code) constructs JSON
```

Composition at PROMPT level → One infrastructure primitive, infinite compositions.

---

## Systems Thinking

**batch is a multiplier:**
- Doesn't change what the system can do
- Changes how efficiently it does it
- Applies universally across all operations

**Analogy:**
- Primitives = verbs (search, filter, rank)
- batch = adverb (do these verbs in parallel)

**Architectural role:**
- Not a feature
- Not a use case
- An execution strategy primitive

---

## Success Criteria

batch succeeds when:
1. Adding new primitives requires zero batch code changes
2. Orchestrator can compose arbitrary operation combinations
3. Performance scales linearly with parallelization
4. Observable (single log entry captures full operation)

batch fails when:
1. Becomes domain-specific (e.g., "multi-query only")
2. Requires per-primitive custom handling
3. Overhead exceeds sequential execution time

---

## Key Property

**Composability:**

Can nest batch operations:
```json
{
  "parallel": [
    {
      "op": "batch",
      "config": {
        "parallel": [
          {"op": "search", "query": "A"},
          {"op": "search", "query": "B"}
        ]
      }
    },
    {"op": "graph_build", "result_ids": "..."}
  ]
}
```

Orchestrator decides composition depth.
Infrastructure executes regardless.

---

## Bottom Line

batch = universal parallelization primitive
- Infrastructure, not domain logic
- Works with any operation signature
- JSON CLI interface (bash-native)
- Composition at prompt level (orchestrator)
- Performance multiplier across system

**Geometric essence: Fan-out/fan-in execution pattern**
**Architectural role: Infrastructure primitive**
**Interface: JSON string as CLI argument**
