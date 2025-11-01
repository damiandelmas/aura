# Graph-Informed Template Selection: Adaptive Presentation

**Feature Status:** Designed, not implemented

---

## The Problem

Template structure affects AI comprehension. Currently templates are user-selected, not adapted to content.

**Gap:** Graph discovers relationships, but presentation doesn't reflect them.

---

## The Concept

Graph properties should inform HOW chunks are presented, not just WHICH chunks are returned.

**Graph Intelligence serves TWO purposes:**
1. Retrieval ranking (which chunks to return)
2. Presentation structure (how to present them)

---

## Architecture

### Graph Analysis

```
High PageRank + temporal chain → Evolution template
Many failures + single decision → Anti-pattern template
High centrality + many siblings → Authority template
```

### Selection Logic

**Topology determines structure:**
```
High centrality + temporal chain → Evolution template
Many failures + single decision → Anti-pattern template
High authority + many siblings → Canonical reference template
Linear genealogy chain → Story template
```

**Property:** Presentation structure matches discovered topology.

---

## Structure Examples

### Evolution Structure
**Topology:** High centrality + temporal chain

**Presentation:**
```
Authority signal
    ↓
Evolution timeline (temporal chain)
    ↓
Current authoritative state
    ↓
Related context (siblings)
```

### Anti-Pattern Structure
**Topology:** Multiple failures + single decision

**Presentation:**
```
What failed (failures cluster)
    ↓
What worked (final decision)
    ↓
Extracted lessons (patterns)
```

---

## The Value

**Topology informs structure:**
- Linear chain → Timeline presentation
- Hub pattern → Authority-centered structure
- Failure cluster → Anti-pattern format

**AI comprehends from structure:**
- Not just content similarity
- Relationships visible in presentation
- Temporal/authority context clear

---

## Related Concepts

See: [VISION.md](./VISION.md) - Principle #5: Structure as Signal
See: [knowledge-graph.md](./knowledge-graph.md) - Graph analysis provides input
