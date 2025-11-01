# Batch Composition: Parallel Orchestration

**Feature Status:** Designed, not implemented

---

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
         (50ms)          (50ms)          (50ms)
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
Input: Single JSON config
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

**3x performance improvement from parallelism.**

---

## Compositional Topology

**Without batch:**
```
CLI call 1 → Result 1
CLI call 2 → Result 2    } Manual
CLI call 3 → Result 3    } orchestration
Combine manually
```

**With batch:**
```
Single call → Internal orchestration → Unified result
```

**Shift:** Orchestration moves from user space to system space.

---

## The Value

**Latency:** Single round-trip (not N)
**Parallelism:** Internal (not sequential)
**Overhead:** Zero developer orchestration

**Result:** Performance + simplicity.

---

## Related Concepts

See: [../business-logic/COMPOSITIONAL-PRIMITIVES.md](../business-logic/COMPOSITIONAL-PRIMITIVES.md) - Primitive composition
See: [../business-logic/AI-FIRST-USER.md](../business-logic/AI-FIRST-USER.md) - Single atomic calls
