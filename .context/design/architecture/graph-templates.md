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

### Template Selection

```python
def select_template(results, graph_data):
    """Let graph properties determine presentation structure"""

    # High centrality node?
    if graph_data.get('centrality_score') > 0.8:
        return 'authority'  # Present as canonical decision

    # Strong temporal chain?
    if len(results[0].get('temporal', [])) > 3:
        return 'evolution'  # Present as evolution story

    # Lots of failures?
    failure_count = sum(1 for s in results[0].get('siblings', [])
                       if s.payload['section_type'] == 'Failures')
    if failure_count > 2:
        return 'anti-pattern'  # Present as "what not to do"

    # Has genealogy + cross-phase?
    if results[0].get('genealogy') and results[0].get('cross_phase'):
        return 'story'  # Present as complete narrative

    return 'simple'
```

---

## Template Examples

### Evolution Template
(High centrality + temporal chain)

```markdown
# CANONICAL DECISION: JWT Authentication [Authority: 0.91]

⚠️ **Note**: This decision is heavily referenced (23 links) and has evolved
over 6 months. Understanding full context recommended.

## Evolution Timeline
[Temporal chain showing refinements]

## Current State (Authoritative)
[The decision with high PageRank]

## Related Decisions
[Siblings sorted by importance]
```

### Anti-Pattern Template
(Many failures + decision)

```markdown
# DECISION: Caching Strategy

## What We Tried (And Failed)
❌ In-memory LRU (race conditions)
❌ Redis with TTL (cache stampede)
❌ Write-through (consistency issues)

## What Finally Worked
✅ Redis with lease-based locking
- Prevents stampede
- Handles concurrency
- Acceptable consistency trade-offs

## Lessons
[Extracted patterns]
```

---

## Key Terms

- **Graph Intelligence**: Dual purpose (retrieval ranking AND presentation structure)
- **Context-Aware Assembly**: Structure matches discovered relationships
- **aiUX**: Structure = comprehension for AI agents
- **Adaptive Templates**: Not user-selected, graph-selected

---

## The Value

**Graph discovers:** "This is central, evolved over time, has failures"
**Template presents:** Structure showing evolution timeline with failed branches
**AI comprehends:** Full context from structure, not just content similarity

---

## Current Gap

Current implementation:
```python
_render_template(results, template_name)
# Template selected by user via config, not adapted to content
```

Missing:
- Graph data passed to template selection
- Adaptive selection logic
- Context-aware structure based on relationships

---

## Related Concepts

See: [VISION.md](./VISION.md) - Principle #5: Structure as Signal
See: [knowledge-graph.md](./knowledge-graph.md) - Graph analysis provides input
