---
session_id: eee3b7a5-3870-4b50-984c-19eb2e2fa729
date: 2025-10-27
type: vision.innovation
resolution: level-1
keywords: "primitives-over-wrappers runtime-composition observable-intelligence"
---

# Runtime Composition: Intelligence at Query Time

## The Insight

**System provides primitives. AI composes at runtime.**

Traditional: Build wrappers (explain/trace/patterns functions) → rigid modes.

AURA: Expose primitives (search/filter/graph) → infinite compositions.

---

## The Shift

**From:**
```
Framework provides: explain(), trace(), patterns()
User calls: imem.explain("topic")
Result: Pre-defined workflow, black box
```

**To:**
```
System provides: search, filter, graph build/apply
Claude composes: search + filter + filter + graph
Result: Transparent composition, observable, adaptable
```

**The difference:** Intelligence in the orchestrator, not the system.

---

## The Geometry

```
Primitives (kernel space):
├─ search (semantic)
├─ filter (metadata)
├─ graph build/apply
└─ combine (parallel merge)

Compositions (user space):
├─ explain = search + filter(file) + filter(session)
├─ trace = search + filter(session) + filter(temporal)
├─ patterns = search + filter(layer=pattern)
└─ [infinite variations]
```

**Boundary:** Primitives in code. Compositions in markdown/runtime.

---

## The Properties

**Composability:**
- Primitives combine arbitrarily
- No pre-defined workflows
- Claude decides composition per context

**Observability:**
- Every operation logged (bash commands)
- Composition visible in usage.log
- Pattern detection from observed sequences

**Evolvability:**
- Observe frequent compositions
- Generate shortcuts when validated (>10 uses)
- System learns from usage, not prediction

**No premature abstraction:**
- Start with primitives only
- Codify patterns after proven
- Defer wrappers until validated

---

## Why It Matters

**Traditional wrapper approach:**
```python
def explain(query):
    decision = search(query)[0]
    constraints = filter(file=decision.file)
    pattern = filter(file=decision.pattern_file)
    return bundle(decision, constraints, pattern)
```

**Problem:**
- Fixed workflow
- Can't adapt to context
- Black box (not observable)
- Maintenance burden

**Primitive composition:**
```bash
# Claude composes based on context
imem search "JWT" --decisions
imem filter --file-path <result> --constraints
imem filter --session <result.session>
```

**Benefits:**
- Flexible workflow
- Adapts to need
- Transparent (every step visible)
- No maintenance (just primitives)

---

## The Vision

**Week 0:** Primitives only. Claude composes manually.

**Week 8:** Detect patterns in usage.log. 13× sibling queries → validate primitive.

**Week 9:** Generate shortcuts for validated compositions. `/explain` = proven pattern.

**Week 16:** System evolved through observation, not speculation.

**The loop:** Observe → Validate → Codify → Observe.
