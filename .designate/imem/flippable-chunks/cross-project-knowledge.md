---
session_id: "090c7e16-cb85-45e5-a1f0-8dd53f191a40"
---

# Cross-Project Knowledge: Pattern Bridging

**Learn from other projects without seeing their code.**

---

## The Problem

Want to benefit from solutions discovered in other projects.

**Don't want:**
- Their tech stack (Python vs TypeScript vs Go)
- Their framework choices (Flask vs FastAPI vs Django)
- Their code (different patterns, style, complexity)

**Want:**
- Principles they discovered
- Patterns that worked
- Approaches that failed

**Pattern layer enables this.**

---

## The Solution

Query pattern layer across projects. Query implementation layer within project.

```
Cross-project query:
  Filter: section_type='Pattern', all projects
  Returns: Language-agnostic abstractions only

Within-project query:
  Filter: section_type='Decision', current project
  Returns: Implementation + pattern (both faces)
```

**No code pollution. Patterns bridge, implementations stay isolated.**

---

## Query Modes

**Learning across projects:**
```
Query: "How to handle async processing?"
Scope: All projects
Layer: Pattern only

Returns:
- "Non-blocking I/O with event loop" (Project A)
- "Message queue with worker pool" (Project B)
- "Callback-based concurrency" (Project C)
```

**Implementation for your project:**
```
Query: "Our async processing decisions"
Scope: Current project
Layer: Both (implementation + pattern)

Returns:
- Implementation: Python asyncio specifics
- Pattern: Non-blocking I/O abstraction
```

---

## Pattern Discovery

Cross-project queries filter to pattern layer only.

**Query capability:**
- Semantic search across all projects
- Filter: layer='pattern'
- Returns: Language-agnostic abstractions

**Value emerges from:**
- Pattern reuse across projects
- Shared solutions to common problems
- Observable usage patterns

**Future:** Authority metrics based on pattern similarity and validation count.

---

## Graph Topology

**Future capability:** Cross-project edge detection based on pattern similarity.

```
Project A ──→ "Non-blocking I/O" ←── Project B
Project C ──→ "Non-blocking I/O"

Project D ──→ "Message Queue" ←── Project E

Cross-project edges on pattern layer only
```

**Design goal:** Pattern layer as knowledge bridge between projects.

---

## The Value

**Learn across tech stacks:**
- Python project learns from Go solutions
- See approach, not Go syntax

**Preserve implementation:**
- Your Python code stays queryable
- Their Go code never seen

**Authority from validation:**
- Pattern in 5 projects > pattern in 1
- Validation count = confidence metric

**Result:** Knowledge transfer without code pollution.

---

## BRAIN Integration

**Pattern extraction:**
- Superseded implementation → Pattern abstraction
- Language-specific → Language-agnostic

**Cross-project edges:**
- Pattern similarity across projects
- Validation count tracking

**Query routing:**
- Cross-project scope → Pattern layer filter
- Within-project scope → Both layers available

---

## Related Concepts

See: [flippable-chunks.md](./flippable-chunks.md) - Dual-face architecture
See: [decaying-memories.md](./decaying-memories.md) - Progressive abstraction
See: [../brain/runtime-graph-composition.md](../brain/runtime-graph-composition.md) - Cross-project graph composition
