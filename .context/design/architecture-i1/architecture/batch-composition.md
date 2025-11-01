# Batch Composition: Parallel Orchestration

## Architectural Position

**Batch = compositional peer, not abstraction layer.**

```
Primitives          Batch
├─ search       →   Orchestrates
├─ filter           primitives
├─ graph            internally
└─ siblings         (parallel)
```

Same architectural level. Different execution model.

---

## The Geometry

**Sequential:**
```
Query 1 → Wait → Query 2 → Wait → Query 3 → Wait
Total: N × latency
```

**Parallel:**
```
Query 1 ──┐
Query 2 ──┤→ Internal parallelism → Results
Query 3 ──┘
Total: max(latency)
```

**Property:** Single round-trip vs N round-trips.

---

## Dataflow

```
Input: Single config
  ↓
Parse composition
  ↓
Execute primitives IN PARALLEL
  ↓
Combine results (if requested)
  ↓
Apply graph operations (if requested)
  ↓
Output: Unified results
```