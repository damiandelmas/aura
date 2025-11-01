# FlexGraph Methodology

**Core methodology for building AI-native memory systems that learn from usage**

*Status: Foundational principles validated, full system under development*

---

## What FlexGraph Is

FlexGraph is the complete methodology for building memory systems where AI agents are both:
- **Content creators** (write structured documents)
- **Primary users** (query and compose knowledge)

**Not just:** Query-time graph construction
**But:** The entire stack from content creation → knowledge persistence → intelligent retrieval → self-improvement

---

## The Foundation: Template-as-Schema

**Core Principle:** AI agents write structured content, guaranteeing metadata compliance.

**FlexGraph approach:**
```
AI writes via template → Schema enforcement → 100% metadata accuracy → Deterministic operations
```

**Why this matters:**
- Enables guaranteed metadata (no probabilistic extraction)
- Foundation for all downstream intelligence

**Example:**
```markdown
## Decision
- Context: (required field, always present)
- Solution: (required field, always present)
- Rationale: (optional field, known present/absent)
```

**Result:** Can query `WHERE has_rationale=true` deterministically

See: [business-logic/AI-FIRST-USER.md](../business-logic/AI-FIRST-USER.md)

---

## The Six Pillars

FlexGraph combines six architectural principles into a unified system:

### 1. Entity Resolution

**Problem:** Terms drift over time ("jwt", "JWT", "jwt-tokens")

**FlexGraph Solution:**
- Source stays as written (immutable)
- Resolution map evolves separately
- Queries expand at runtime (find all variants)

**Enables:** Complete recall despite inconsistent terminology

See: [the-brain/entity-resolution.md](../design/.modules/the-brain/entity-resolution.md)

---

### 2. Schema Introspection

**Problem:** Future AI sessions can't discover system capabilities

**FlexGraph Solution:**
- System introspects itself
- Returns schema + examples programmatically
- AI agents query capabilities, not docs

**Enables:** Zero-friction onboarding for brother agents

See: [the-brain/schema-introspection.md](../design/.modules/the-brain/schema-introspection.md)

---

### 3. Knowledge Graph

**Problem:** Recomputing edges every query is wasteful when relationships are stable

**FlexGraph Solution:**
- Metadata = edge predicates (file_path → siblings, session_id → genealogy)
- Persist graph structure in lightweight store
- Query-time reads graph instead of computing it

**Enables:** Graph algorithms (PageRank, centrality) + fast traversal

See: [the-brain/knowledge-graph.md](../design/.modules/the-brain/knowledge-graph.md)

---

### 4. BRAIN Persistence

**Problem:** Not all metadata ages the same

**FlexGraph Solution:**
- Layer 1: Static metadata (what was created, never changes)
- Layer 2: Learned metadata (what usage reveals, changes continuously)
- Layer 3: Composed views (assembled at query time, ephemeral)

**Update frequencies:**
- Real-time: reference_count, last_accessed (~1ms)
- Nightly: PageRank, centrality (~5min batch)
- Weekly: Entity resolution, supersession detection (LLM)

**Enables:** Continuous learning without rewriting history

See: [the-brain/brain-persistence.md](../design/.modules/the-brain/brain-persistence.md)
See: [the-brain/adaptive-updates.md](../design/.modules/the-brain/adaptive-updates.md)

---

### 5. Graph-Informed Templates

**Problem:** Template structure affects AI comprehension

**FlexGraph Solution:**
- Graph discovers relationships (centrality, temporal chains, failures)
- Templates adapt structure to match relationships
- AI comprehends context from presentation

**Example:**
- High centrality + temporal chain → Evolution template
- Many failures + decision → Anti-pattern template

**Enables:** Context-aware assembly where structure conveys meaning

See: [the-brain/graph-templates.md](../design/.modules/the-brain/graph-templates.md)

---

### 6. Adaptive Learning

**Problem:** Batching everything weekly wastes real-time signals, updating everything real-time is costly

**FlexGraph Solution:**
- Stratify by cost/latency/value
- Real-time: Cheap, high-signal operations
- Batch: Expensive algorithms run offline
- LLM: Costly analysis runs infrequently

**Enables:** Continuous learning without per-query penalty

See: [the-brain/adaptive-updates.md](../design/.modules/the-brain/adaptive-updates.md)

---

## How They Fit Together

```
┌─────────────────────────────────────────────────────────────┐
│ Template-as-Schema (Foundation)                            │
│ AI agents write structured docs → 100% metadata            │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ Immutable Source (Primary Storage)                         │
│ Changelogs as written + vectors                            │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌──────────────────────┬──────────────────────┬───────────────┐
│ Knowledge Graph      │ BRAIN Persistence    │ Entity Map    │
│ (Relationships)      │ (Learned Metadata)   │ (Vocabulary)  │
│                      │                      │               │
│ Persistent edges     │ Real-time stats      │ Term variants │
│ Graph algorithms     │ Batch metrics        │ LLM clustering│
└──────────────────────┴──────────────────────┴───────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ Compositional Primitives (Discovery Layer)                 │
│ siblings · genealogy · temporal · cross_phase               │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ Query-Time Composition (Flexible Assembly)                 │
│ AI agents compose primitives → Graph-informed templates    │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ Observable Usage (Self-Improvement)                        │
│ Track patterns → Capture proven compositions → Presets     │
└─────────────────────────────────────────────────────────────┘
```

**Each layer enables the next. Remove any piece and the system degrades.**

---

## Compositional Primitives + Observable Usage

**Core Innovation:** Don't prescribe query types. Provide primitives, observe usage, capture patterns.

### Primitives (Orthogonal Building Blocks)

| Primitive | Returns | Discovery |
|-----------|---------|-----------|
| siblings | Same document chunks | `filter(file_path=X)` |
| genealogy | Origin conversation | `filter(session_id=Y)` |
| temporal | Evolution over time | `semantic + timestamp` |
| cross_phase | Related phase | `filter(phase=Z)` |

**Key property:** Any combination valid (infinite compositions possible)

### Observable Usage

```
1. AI agents compose freely
   └─ genealogy + siblings + cross_phase

2. System tracks patterns
   └─ This composition used 30 times

3. Proven pattern captured
   └─ Becomes /explain-decision preset

4. Preset library grows organically
   └─ Self-improving system
```

**Not prescriptive. Usage-driven.**

See: [business-logic/COMPOSITIONAL-PRIMITIVES.md](../business-logic/COMPOSITIONAL-PRIMITIVES.md)
See: [business-logic/USAGE-DRIVEN.md](../business-logic/USAGE-DRIVEN.md)

---

## When to Use FlexGraph

### Ideal For:

✅ **AI-generated structured content**
- Agents write documents via templates
- Schema enforcement straightforward
- 100% metadata guaranteed

✅ **Evolving knowledge bases**
- Constantly growing corpus
- Relationships emerge over time
- Traditional KG maintenance overhead unacceptable

✅ **Agentic workflows**
- AI agents are primary users
- Compositional flexibility needed
- Self-improving systems valuable

✅ **Moderate latency tolerance**
- 80-200ms query acceptable
- Not millisecond API requirements

### Not Ideal For:

❌ **Human-generated unstructured content**
- Can't enforce template compliance
- Post-hoc extraction necessary (~70% accuracy)
- FlexGraph foundation breaks

❌ **Static document corpus**
- One-time ingest, rarely updated
- Precomputed KG amortizes well
- FlexGraph advantages don't apply

❌ **Fixed relationship schemas**
- Known relationships upfront
- No need for query-time adaptation
- Traditional KG simpler

❌ **Millisecond latency requirements**
- High-frequency API calls
- Precomputed structures faster

---

## Domain Implementations

FlexGraph is a **methodology**, not a product. Different domains apply it differently:

### IMEM (Coding Agents)

**Domain:** Software development changelogs

**Template Structure:**
- Decisions (Context, Solution, Rationale)
- Constraints (Description, Impact, Mitigation)
- Failures (Attempted, Why Failed, Lesson)
- Patterns (Pattern, When, Approach)

**Phases:** design → designate → develop → document

**Use Case:** Coding agent memory (explain decisions, trace evolution, find anti-patterns)

**Status:** In development

---

### WriteMem (Hypothetical)

**Domain:** Long-form writing

**Template Structure:**
- Ideas (Thesis, Evidence, Counter-Argument)
- Drafts (Version, Changes, Rationale)
- Citations (Source, Context, Reliability)

**Phases:** brainstorm → outline → draft → revise

**Use Case:** Writing agent memory (draft evolution, citation network, style analysis)

**Status:** Conceptual example

---

### ResearchMem (Hypothetical)

**Domain:** Academic research

**Template Structure:**
- Hypotheses (Claim, Evidence, Confidence)
- Experiments (Method, Result, Analysis)
- Literature (Paper, Summary, Relevance)

**Phases:** ideate → experiment → analyze → publish

**Use Case:** Research agent memory (literature review, experiment lineage, hypothesis testing)

**Status:** Conceptual example

---

## The Innovation

**Traditional knowledge systems:**
- Build graphs at write time (O(n²))
- Fixed relationship schemas
- Manual curation required
- Static query types
- No learning from usage

**FlexGraph methodology:**
- Template-as-schema foundation (100% metadata)
- Query-time graph construction (O(k²), k << n)
- Living vocabulary (entity resolution)
- Self-describing (schema introspection)
- Persistent relationships + learned metadata (BRAIN)
- Compositional primitives (infinite combinations)
- Observable usage (self-improving)
- Multi-speed updates (adaptive learning)

**Result:** AI-native memory systems that preserve history, learn continuously, and improve from usage.

---

## Core Principles

When building FlexGraph implementations:

**Preserve:** Keep source immutable (archaeological integrity)

**Learn:** Accumulate intelligence separately (usage patterns)

**Expose:** Make capabilities discoverable (schema introspection)

**Compose:** Assemble views at runtime (ephemeral, not stored)

**Adapt:** Structure matches relationships (graph-informed)

**Stratify:** Update at speeds matching value/cost (multi-speed)

**Observe:** Track usage, capture patterns (self-improving)

See: [the-brain/VISION.md](../design/.modules/the-brain/VISION.md) for detailed principles

---

## Related Concepts

**Business Logic:**
- [AI-FIRST-USER.md](../business-logic/AI-FIRST-USER.md) - User is AI agents
- [IMMUTABLE-SOURCE.md](../business-logic/IMMUTABLE-SOURCE.md) - Source never changes
- [COMPOSITIONAL-PRIMITIVES.md](../business-logic/COMPOSITIONAL-PRIMITIVES.md) - Building blocks over strategies
- [USAGE-DRIVEN.md](../business-logic/USAGE-DRIVEN.md) - Learn from behavior

**Technical Details:**
- [.modules/the-brain/](../design/.modules/the-brain/) - Six pillar implementations
- [.modules/flex-graph/](../design/.modules/flex-graph/) - IMEM-specific architecture

---

**FlexGraph = The methodology. IMEM = First implementation.**
