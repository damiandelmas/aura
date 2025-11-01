# Flippable Chunks: Dual-Layer Architecture

**Feature Status:** Designed, not implemented

---

## Geometric Concept

**Same node, two faces:**
```
Implementation side ←→ Pattern side
(tech-specific)        (language-agnostic)
```

**The flip:** Metadata toggle, not data change.

---

## Dual-Layer Architecture

**Layer topology:**
```
Implementation Layer          Pattern Layer
    ↓                            ↓
Tech decisions              Abstractions
Framework choices           Principles
Language-specific           Language-agnostic
    ↓                            ↓
Expires (superseded)        Eternal (validated)
```

**Serving logic:** Context determines which face is visible.

---

## Knowledge Evolution

**Traditional flow:**
```
Create → Use → Deprecate → Delete
         (lateral replacement)
```

**IMEM flow:**
```
Create → Use → Supersede → Abstract → Reuse
              (upward evolution)
```

**Property:** Intellectual capital accumulates, doesn't churn.

---

## Cross-Project Topology

**Pattern layer as bridge:**
```
Project A ──→ Pattern X ←── Project B
Project C ──→ Pattern X
Project D ──→ Pattern Y ←── Project E
              ↓
       Cross-project edges
```

**Authority metric:** Validation count = edges from distinct projects.

**PageRank shift:** Runs on pattern layer, not implementation layer.

---

## Observable Intelligence

**System tracks:**
- Flip frequency (implementation → pattern)
- Cross-project pattern reuse
- Composition patterns

**Emergence:** Pattern library grows from usage, not prediction.

---

## The Architecture

**Storage:**
- Single chunk ID
- Two content fields (implementation, pattern)
- Serving mode (metadata flag)

**Query-time:**
- Resolve serving mode from context
- Return appropriate face
- Zero re-indexing

**Graph-level:**
- Pattern edges cross projects
- Implementation edges within project
- Different topologies, same substrate

---

## Related Concepts

See: [knowledge-graph.md](./knowledge-graph.md) - Cross-project edges
See: [brain-persistence.md](./brain-persistence.md) - Validation tracking
See: [../business-logic/USAGE-DRIVEN.md](../business-logic/USAGE-DRIVEN.md) - Observable patterns
