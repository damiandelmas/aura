# Memory System Architecture: Core Principles

*A framework for AI-native knowledge systems that learn from usage*

---

## The Philosophy

**Memory systems should:**
- Preserve history (immutable source)
- Learn from usage (adaptive intelligence)
- Expose capabilities (self-documenting)
- Compose at runtime (ephemeral views)

**Not:**
- Rewrite the past
- Require manual curation
- Hide what's possible
- Store every derived view

---

## 1. Living Vocabulary

**Principle:** Terms drift. Don't fight it. Map it.

**Core Idea:**
```
Source stays as written → Resolution layer evolves → Queries expand automatically
```

**The Insight:**
- Source material uses natural language (inconsistent by nature)
- Resolution map captures term evolution over time
- Query expansion finds everything despite variation
- Vocabulary layer lives separately from content

**Enables:**
- Archaeological integrity (source never modified)
- Complete recall (all variations found)
- Language evolution (map grows with usage)

---

## 2. Self-Describing Systems

**Principle:** Future agents shouldn't guess. Systems should expose capabilities.

**Core Idea:**
```
System introspects itself → Returns schema + examples → Agents discover programmatically
```

**The Insight:**
- Documentation drifts from reality
- Agents need machine-readable capability maps
- Examples teach better than specifications
- Schema generated from live data never lies

**Enables:**
- Zero documentation drift
- Programmatic discovery
- Brother agent onboarding (future sessions learn automatically)

---

## 3. Persistent Relationships

**Principle:** Don't recompute relationships. Persist them.

**Core Idea:**
```
Implicit: Compute edges at query time (slow, ephemeral)
Explicit: Compute edges at write time (fast, queryable)
```

**The Insight:**
- Relationships are stable (file siblings don't change often)
- Graph algorithms need persistent structure
- Query time should read, not compute
- Edges are data, treat them as such

**Enables:**
- Fast graph traversal
- Complex graph algorithms (PageRank, communities)
- Relationship queries (what connects these?)

---

## 4. Stratified Learning

**Principle:** Different intelligence at different speeds.

**Core Idea:**
```
Static Layer:   What was created (never changes)
Learned Layer:  What usage reveals (changes continuously)
Composed Layer: What queries assemble (ephemeral)
```

**The Insight:**
- Not all metadata ages the same
- Separate what's written from what's learned
- Usage patterns reveal authority
- Composition happens at query time, not storage

**Enables:**
- Immutable source + mutable intelligence
- Continuous learning without rewriting history
- Runtime assembly of contextualized views

---

## 5. Structure as Signal

**Principle:** For AI consumers, structure conveys meaning.

**Core Idea:**
```
Graph discovers relationships → Presentation makes them explicit → AI comprehends context
```

**The Insight:**
- Graph intelligence serves retrieval AND presentation
- Structure guides attention (failures first, patterns last)
- Template selection should be adaptive, not fixed
- What you serve affects how it's understood

**Enables:**
- Context-aware assembly
- Relationship-driven presentation
- AI comprehension through structure

---

## 6. Multi-Speed Updates

**Principle:** Update frequency should match value and cost.

**Core Idea:**
```
Real-Time:  Cheap signals (usage tracking)
Periodic:   Expensive computation (graph metrics)
Occasional: Costly analysis (term clustering)
```

**The Insight:**
- Not everything needs real-time updates
- Stratify by cost/latency/value trade-offs
- Reference counts matter immediately (real-time)
- Graph centrality can wait until overnight (batch)
- Entity clustering is weekly at most (LLM cost)

**Enables:**
- Continuous learning without latency penalty
- Expensive operations run offline
- Cost control through update frequency stratification

---

## The Mental Model

### Storage Philosophy
```
Immutable Source:  Archaeological record (never modified)
Learned Layer:     Accumulated intelligence (usage patterns)
Living Vocabulary: Term evolution (resolution map)
```

### Retrieval Philosophy
```
Semantic:     What matches (similarity)
Structural:   What connects (graph relationships)
Expansive:    What's related (term variants)
```

### Intelligence Philosophy
```
Static:   What was created
Learned:  What usage reveals
Composed: What queries assemble
```

### Presentation Philosophy
```
Analysis:  Graph discovers relationships
Selection: Structure matches relationships
Assembly:  Context emerges from structure
```

---

## Design Questions

When building features, ask:

**Persistence:**
- Is this immutable or learned?
- Does it persist or compose at runtime?
- What's the update frequency?

**Intelligence:**
- Does this inform retrieval or presentation?
- Is this for AI or human consumption?
- Does structure convey meaning?

**Evolution:**
- Does this rewrite history or evolve separately?
- What reveals this knowledge (creation or usage)?
- How does this adapt over time?

---

## The Core Insight

**Memory systems for AI should:**

1. **Preserve** - Keep source immutable (archaeological integrity)
2. **Learn** - Accumulate intelligence from usage (reference patterns)
3. **Expose** - Make capabilities discoverable (schema introspection)
4. **Compose** - Assemble views at runtime (ephemeral, not stored)
5. **Adapt** - Structure presentation to relationships (context-aware)
6. **Stratify** - Update at speeds matching value and cost (multi-speed learning)

**Not prescriptive implementation. Guiding principles.**

Use this framework to evaluate architectural decisions, not dictate technical choices.
