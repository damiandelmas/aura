# Vision Integration: How Business Logic Principles Compose

**Purpose:** Show how core principles integrate together, using IMEM as reference implementation.

**Status:** Conceptual (IMEM not yet FlexGraph-integrated)

---

## The Four Principles

1. **AI-First User** - User is AI agents, not humans
2. **Compositional Primitives** - Building blocks over rigid strategies
3. **Immutable Source** - Source preserved, intelligence learned separately
4. **Usage-Driven** - Learn from behavior, not predictions

**These aren't independent. They compose into a system architecture.**

---

## Integration 1: Compositional Primitives + Usage-Driven

### The Synergy

**Compositional enables flexibility:**
- Orthogonal primitives (siblings, genealogy, temporal, cross_phase)
- Any combination valid
- Infinite compositions possible

**Usage-Driven reveals value:**
- Track which compositions recur
- Proven patterns (10-20 uses) become presets
- System learns what's valuable

**Together = Self-improving flexibility**

### IMEM Vision Example

```python
# Agent composes freely
compose({
  "search": {"text": "auth"},
  "discovery": {
    "genealogy": true,
    "siblings": {"section_types": ["Failures", "Decisions"]},
    "cross_phase": "design"
  }
})

# System tracks usage
usage_log["hash_genealogy_siblings_cross"] += 1

# After 30 uses → captured as preset
if count >= 30:
  create_preset("/explain-decision", config)
```

**Result:** Preset library grows organically from proven need, not designer guesses.

**Domain agnostic:** Any system with compositional primitives can observe usage and capture patterns.

---

## Integration 2: AI-First User + Compositional Primitives

### The Synergy

**AI-First optimizes for:**
- Programmatic construction (no cognitive load)
- Single atomic calls (latency matters)
- Structured output (parseable)

**Compositional provides:**
- Complex queries constructable in one call
- Declarative config (JSON)
- Arbitrary complexity acceptable (AI constructs it)

**Together = Complex operations without latency penalty**

### IMEM Vision Example

**Without integration:**
```python
# 4 round-trips
results = search("auth")              # Call 1
siblings = get_siblings(results[0])   # Call 2
genealogy = get_genealogy(results[0]) # Call 3
output = render(template, data)       # Call 4
# Total: ~320ms (4 × 80ms)
```

**With integration:**
```python
# 1 round-trip
compose({
  "search": {"text": "auth"},
  "discovery": {"siblings": true, "genealogy": true},
  "output": {"template": "story"}
})
# Total: ~120ms
```

**Result:** AI constructs complex query declaratively, system executes atomically.

**Domain agnostic:** Any AI-first system benefits from compositional single-call APIs.

---

## Integration 3: Immutable Source + Usage-Driven

### The Synergy

**Immutable preserves:**
- Archaeological record (what was written)
- Historical truth (exact state at time)
- Source integrity (never rewritten)

**Usage-Driven learns:**
- Reference patterns (which chunks cited)
- Evolution patterns (which supersede others)
- Authority signals (which are central)

**Together = Preserve history, learn intelligence separately**

### IMEM Vision Example

**Source layer (immutable):**
```markdown
## Decision: Use JWT
- Context: Sessions don't scale
- Solution: Stateless tokens
```

**BRAIN layer (learned):**
```sql
brain_stats:
  chunk_id: abc123
  reference_count: 47        -- Updated every query
  last_accessed: 2025-10-31  -- Real-time

brain_metrics:
  chunk_id: abc123
  pagerank_score: 0.91       -- Computed nightly
  superseded_by: null        -- Detected weekly
```

**Query-time composition:**
```markdown
# JWT Authentication [Authority: 0.91, Referenced: 47×]

⚠️ This decision is heavily cited and has evolved over time.

## Decision (Oct 2023)
[Original content unchanged]

## Later Evolution
[Temporal chain from BRAIN metrics]
```

**Result:** Source stays as written, intelligence accumulates from usage.

**Domain agnostic:** Any system can separate immutable content from learned metadata.

---

## Integration 4: All Four Together

### The Complete System

```
AI writes structured docs
    ↓ (IMMUTABLE SOURCE)
Archaeological record preserved
    ↓
AI queries with compositional primitives
    ↓ (COMPOSITIONAL PRIMITIVES + AI-FIRST USER)
Complex queries, single atomic calls
    ↓
System tracks composition patterns
    ↓ (USAGE-DRIVEN)
Proven patterns → presets
    ↓
Intelligence learned separately
    ↓ (IMMUTABLE SOURCE + USAGE-DRIVEN)
Query-time enrichment with BRAIN metadata
```

### IMEM Vision Example

**Write phase:**
```markdown
## Decision: Variant System
- Context: Need extensible prompt variants
- Solution: Plugin registration pattern
```
→ Immutable changelog in Qdrant

**Query phase (Month 1):**
```python
# Agent composes freely
compose({
  "search": {"text": "variant system"},
  "discovery": {"genealogy": true, "siblings": true}
})
# Usage tracked: pattern_genealogy_siblings += 1
```

**Learning phase (Month 3):**
```python
# After 30 uses of genealogy+siblings pattern
create_preset("/explain-decision")

# BRAIN learns from queries
brain_stats["variant_decision"]["reference_count"] = 23
brain_metrics["variant_decision"]["pagerank"] = 0.87
```

**Query phase (Month 4):**
```python
# Agent uses discovered preset
/explain-decision "variant system"

# Returns enriched context:
# - Immutable source (preserved)
# - Genealogy + siblings (composition)
# - Authority signals (BRAIN metrics)
# - Single call (AI-first)
```

**Result:** Self-improving system where AI writes → composes → usage reveals patterns → system learns.

---

## Why This Integration Matters

**Without integration:**
- Compositional alone → flexibility without guidance
- Usage-Driven alone → learns patterns but limited compositions
- AI-First alone → fast but static capabilities
- Immutable alone → preservation but no learning

**With integration:**
- Compositional + Usage-Driven → self-improving flexibility
- AI-First + Compositional → complex operations without latency
- Immutable + Usage-Driven → preserve history, learn intelligence
- All four → adaptive system that learns from behavior while preserving truth

---

## Domain Variations

**IMEM (coding agents):**
- Source: Changelogs (Decisions, Failures, Patterns)
- Primitives: siblings, genealogy, temporal, cross_phase
- Usage: Composition tracking → presets
- BRAIN: reference_count, pagerank, supersession

**WriteMem (hypothetical):**
- Source: Drafts (Ideas, Revisions, Citations)
- Primitives: version_chain, citation_network, style_similarity
- Usage: Revision pattern tracking → presets
- BRAIN: draft_evolution, citation_authority

**ResearchMem (hypothetical):**
- Source: Experiments (Hypotheses, Results, Analysis)
- Primitives: hypothesis_chain, literature_network, method_similarity
- Usage: Research pattern tracking → presets
- BRAIN: experiment_lineage, paper_authority

**Principles stay the same. Manifestation varies by domain.**

---

## Loose Coupling Benefits

**Principles are domain-agnostic:**
- Any AI-generated content can be immutable source
- Any orthogonal operations can be compositional primitives
- Any usage patterns can be tracked and captured
- Any AI agent benefits from single-call composition

**IMEM is one flavor:**
- Specific template structure (Decisions/Failures/Patterns)
- Specific primitives (siblings/genealogy/temporal)
- Specific BRAIN metrics (pagerank/supersession)
- But same principle integration

**Avoids brittleness:**
- Principles survive implementation changes
- IMEM can evolve without breaking principles
- New domains apply same principles differently
- Integration patterns reusable

---

## Related Documents

**Principles:**
- [AI-FIRST-USER.md](../business-logic/AI-FIRST-USER.md)
- [COMPOSITIONAL-PRIMITIVES.md](../business-logic/COMPOSITIONAL-PRIMITIVES.md)
- [IMMUTABLE-SOURCE.md](../business-logic/IMMUTABLE-SOURCE.md)
- [USAGE-DRIVEN.md](../business-logic/USAGE-DRIVEN.md)

**Methodology:**
- [flexgraph.md](./flexgraph.md) - Complete methodology overview

**IMEM Implementation:**
- [architecture_imem-i2.md](../../document/architecture_imem-i2.md) - What exists today (phases 1-5)
- [imem-architecture.md](../implementation/imem-architecture.md) - Vision for FlexGraph integration (phases 6-8)

---

**These principles integrate into a coherent architecture. IMEM shows one way. Other domains will differ in details, same in principles.**
