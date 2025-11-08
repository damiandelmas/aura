---
session_id: "fe0004ca-4912-4e0d-9f12-45786c2fd15e"
---

# Temporal Cortex: Code Drift Detection

**Code is truth. Git diffs reveal when documentation diverges from reality.**

---

**Implementation Status:** Git diff detection described below is architectural design. Current implementation uses continuation_count via semantic search to detect temporal position.

---

## The Problem

Changelogs document code at a point in time. Code evolves. Documentation becomes stale.

**Challenge:** Detect when documented implementation no longer matches actual code.

**Traditional approach:**
- Manual reviews (never happen)
- Hope developers update docs (they don't)
- Documentation rots silently

**Need:** Automatic detection when code diverges from documented state.

---

## The Solution

Git diffs of codebase reveal which code files changed. Chunks contain code_signatures referencing those files. Compare documented code against actual code.

```
Code commit (src/auth/jwt.py changed)
    ↓
Query chunks: code_signatures containing "src/auth/jwt.py"
    ↓
Compare chunk's documented code vs actual code
    ↓
Divergence detected → Flag for supersession
```

**Property:** Codebase is ground truth. Documentation automatically marked when stale.

---

## The Mechanism

**Changelogs document implementation:**
```markdown
## Implementation
### Code Signatures
**File:** src/auth/jwt.py
**Code:** async def verify_token(token: str, secret: str)
```

**Git diff shows code evolved:**
```diff
- async def verify_token(token: str, secret: str):
+ async def verify_token(token: str, secret: str, algorithm: str = "HS256"):
```

**System detects drift:**
- Code signature references src/auth/jwt.py
- Git diff shows src/auth/jwt.py modified
- Compare: documented signature vs actual signature
- **Result: Documentation no longer matches reality**

---

## Tiered Supersession by Narrative Radius

**Code drift flagged. Measure impact through narrative distance.**

### Radius 0: Direct Reference

**Chunk documenting the changed code itself.**

```
code_signatures contains changed file
    ↓
serving_mode = "pattern"
    ↓
AI sees: Abstract approach, not outdated code example
```

---

### Radius 1: Sibling Decisions

**Other decision chunks in same changelog.**

```
Same file_path, different section
    ↓
context_hints = [implementation_evolved]
    ↓
AI sees: Full context + awareness code changed
```

---

### Radius 2: Same Changelog

**Other sections (Patterns, Constraints).**

```
Same file_path, distant section_type
    ↓
temporal_framing = [code_evolved]
    ↓
AI sees: Full content + temporal framing
```

**Principle:** Code change ripples through narrative based on proximity.

---

## Why This Works

**Git tracks code evolution for free:**
- Every commit reveals changed files
- Diffs show exact changes
- Zero cost monitoring

**Code signatures link docs to code:**
- Chunks reference specific files/functions
- Query by file path (O(log n) indexed lookup)
- Precise targeting (not semantic guessing)

**Automatic drift detection:**
- Code changes → automatic flag
- No manual review needed
- Real-time (git hook)
- Deterministic (diff comparison, not probabilistic)

---

## The Value

**Documentation stays honest:**

Traditional: Docs rot silently, become misleading
Temporal Cortex: Docs marked when stale, degraded to principles

**Narrative coherence:**

Not binary (delete vs keep). Graded response by narrative distance.

```
Radius 0: Abstract pattern (no stale code)
Radius 1: Full context + drift awareness
Radius 2: Full content + temporal framing
```

**Codebase is always truth. Documentation knows when it's out of sync.**

---

## BRAIN Integration

**Temporal Cortex triggers on code commits:**

```
Write-time: Entity resolution (normalize categories)
Query-time: Observable usage (detect patterns)
Change-time: Temporal Cortex (detect code drift) ← THIS
Background: Topology cache (compute metrics)
```

**Each subsystem independent. Different event triggers.**

---

## Related Concepts

See: [flippable-chunks.md](../flippable-chunks/flippable-chunks.md) - Dual-face storage
See: [decaying-memories.md](../flippable-chunks/decaying-memories.md) - Progressive abstraction
See: [entity-resolution.md](./entity-resolution.md) - Living vocabulary
See: [runtime-graph-composition.md](./runtime-graph-composition.md) - Metadata as edges
