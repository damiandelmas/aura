---
session_id: "090c7e16-cb85-45e5-a1f0-8dd53f191a40"
---

# FlexGraph Methodology

**Exploiting emergent structure in AI-generated knowledge systems.**

---

## What FlexGraph Is

Methodology for building memory systems where structure creates capability.

**Not:** "Build a graph database then add features"

**But:** "Template + metadata already contains everything. Expose it."

**Core insight:** AI agents writing structured documents create indexed metadata. That metadata enables type-safe queries, implicit graphs, runtime composition, and intelligent serving. Don't build these separately—exploit what's already there.

---

## The Foundation

**Template-as-Type-System:**

AI agents write markdown following templates. Template structure defines semantic types. LlamaIndex preserves hierarchy. Result: typed chunks with indexed metadata.

```
AI writes template → H2/H3 structure → LlamaIndex chunks → Typed vectors
                  ↓
            Indexed metadata (file_path, session_id, timestamp, section_type)
                  ↓
        Everything downstream exploits this
```

**Frontmatter adds document properties:** category, session_id, timestamp, keywords.

**Every chunk has:** Type metadata (section_type) + Document properties (both indexed).

**This is the foundation. Everything else exploits it.**

---

## Four Architectural Exploitations

### 1. Type-Safe Vector Queries

**Exploit:** Template structure becomes queryable type system.

```
H2: Decisions → Decision type (collection)
H3: Use JWT → Decision instance

Query: section_type='Decision' + vector_similarity("auth")
→ Type-safe fuzzy search
```

**What it enables:**
- Deterministic filtering (not probabilistic extraction)
- Progressive type instantiation (simple vs complex work)
- Guaranteed field structure (Context, Solution when type present)

**Exploitation:** Structure you already enforced becomes query precision.

---

### 2. Implicit Knowledge Graph

**Exploit:** Indexed metadata predicates ARE traversable edges.

```
file_path indexed → Sibling edges O(log n)
session_id indexed → Genealogy edges O(log n)
timestamp + semantic → Temporal edges O(log n)
```

**No edge storage. Metadata index IS the graph.**

**What it enables:**
- Graph traversal without precomputation
- Relationship queries without separate graph DB
- New edge types = new metadata fields

**Exploitation:** Metadata you already indexed is a knowledge graph. Just query it.

---

### 3. Runtime Graph Composition

**Exploit:** Materialize subgraphs from query results on-demand.

```
1. Vector search → 20 results (k=20)
2. Query metadata → Materialize edges O(k²) = 400 edges
3. Build NetworkX graph (ephemeral)
4. Run algorithms (PageRank, communities, paths)
5. Discard graph

Traditional: O(n²) precomputation, n=10,000 → 100M edges
FlexGraph: O(k²) materialization, k=20 → 400 edges
```

**What it enables:**
- Graph algorithms without graph storage
- Query-adaptive topology (different graph per query)
- 40,000× fewer edges to compute

**Exploitation:** Don't precompute corpus-wide. Compute on result set.

---

### 4. Graph-Aware Serving

**Exploit:** Use topology to contextualize chunks for AI comprehension.

```
Query graph → Detect position (temporal, authority, lifecycle)
              ↓
        Inform presentation (template selection, labels, structure)
              ↓
        AI sees relationships programmatically
```

**What it enables:**
- Context from structure, not inference
- Topology-driven presentation (linear → timeline, hub → authority)
- Intelligent serving (decaying memories, cross-project patterns)

**Exploitation:** Graph position becomes chunk context at serve-time.

---

## Core Principles

When building FlexGraph implementations:

**1. Preserve**
- Keep source immutable (archaeological integrity)
- Never rewrite history
- Evolution happens separately from source

**2. Learn**
- Accumulate intelligence from usage
- Metadata emerges from behavior
- Observable patterns → captured insights

**3. Expose**
- Make capabilities discoverable (schema introspection)
- Self-describing systems
- AI discovers, doesn't guess

**4. Compose**
- Assemble views at runtime (ephemeral)
- Don't store every derived view
- Query-time composition over precomputation

**5. Adapt**
- Structure matches relationships (graph-informed)
- Template selection from topology
- Context-aware serving

**6. Stratify**
- Update at speeds matching value/cost
- Real-time (usage tracking)
- Periodic (graph metrics)
- Occasional (LLM analysis)

---

## Mental Models

### Storage Philosophy

```
Immutable Source: What was written (never changes)
BRAIN Infrastructure: What's learned (evolves from usage)
Entity Resolution: Term variations (living vocabulary)
```

**Separation:** Source stays pure. Intelligence accumulates separately.

### Retrieval Philosophy

```
Semantic: Vector similarity (fuzzy entry)
Structural: Metadata predicates (precise filtering)
Expansive: Entity resolution (term variants)
```

**Fusion:** Combine fuzzy + precise + expansive for complete recall.

### Intelligence Philosophy

```
Type System: Template structure (guaranteed metadata)
Implicit Graph: Metadata index (traversable relationships)
Runtime Composition: Materialize on-demand (ephemeral graphs)
Graph-Aware Serving: Topology informs presentation (intelligent context)
```

**Exploitation:** Each capability exploits what's already there.

### Presentation Philosophy

```
Topology Detection: Graph reveals structure
Template Selection: Structure matches relationships
Context Assembly: AI comprehends from presentation
```

**Intelligence:** Structure aids comprehension, not just retrieval.

---

## When To Use FlexGraph

### Ideal For:

✅ **AI-generated structured content**
- Agents write via templates
- Schema enforcement straightforward
- Guaranteed metadata foundation

✅ **Evolving knowledge bases**
- Constantly growing corpus
- Relationships emerge over time
- Implicit graph > precomputed edges

✅ **Agentic workflows**
- AI agents primary users
- Compositional flexibility needed
- Self-describing systems valuable

✅ **Moderate latency tolerance**
- 80-200ms acceptable
- Runtime composition overhead acceptable
- Query-time intelligence worth it

### Not Ideal For:

❌ **Human-generated unstructured content**
- Can't enforce template compliance
- Post-hoc extraction probabilistic
- Foundation assumption breaks

❌ **Static document corpus**
- One-time ingest, rarely updated
- Precomputed structures amortize well
- Runtime composition overhead wasted

❌ **Fixed relationship schemas**
- Known relationships upfront
- No query-time adaptation needed
- Traditional graph DB simpler

❌ **Millisecond latency requirements**
- High-frequency API calls
- Precomputed structures faster
- Runtime overhead unacceptable

---

## Design Questions

When building features, ask:

**Foundation:**
- Does this exploit existing metadata or add new metadata?
- Is this enforced at creation or derived at runtime?

**Storage:**
- Is this immutable or learned?
- Does it persist or compose at query-time?
- What's the update frequency?

**Intelligence:**
- Does this inform retrieval or presentation?
- Is structure conveying meaning?
- Are we exposing latent capability or building new?

**Evolution:**
- Does this rewrite history or evolve separately?
- What reveals this (creation or usage)?
- How does it adapt over time?

---

## The Complete System

```
Template + Frontmatter
    ↓
Typed chunks with indexed metadata
    ↓
┌─────────────────────────────────────────┐
│ Exploitation 1: Type-safe queries       │
│ Exploitation 2: Implicit graph          │
│ Exploitation 3: Runtime composition     │
│ Exploitation 4: Graph-aware serving     │
└─────────────────────────────────────────┘
    ↓
BRAIN (control plane)
    ├── Runtime: APIs for composition + introspection
    ├── Storage: Entity resolution, presets, optional graphs
    └── Intelligence: Pre-computed metrics, usage tracking
    ↓
Intelligent, compositional, self-improving memory system
```

**One foundation. Four exploitations. Everything emerges from structure.**

---

## The Innovation

**Traditional approach:**
- Vector DB for search
- Graph DB for relationships
- Separate ranking system
- Manual template selection
- Static capabilities

**FlexGraph approach:**
- Vector DB with indexed metadata (one system)
- Metadata index IS the graph
- Runtime composition (materialize on-demand)
- Topology-driven serving (graph-aware)
- Self-describing (schema introspection)

**Difference:** Don't build separate systems. Exploit emergent structure.

---

## Related Concepts

**Architecture:**
- [../database/type-system.md](../database/type-system.md) - Template-as-type-system
- [../database/document-properties.md](../database/document-properties.md) - Frontmatter metadata
- [../brain/runtime-graph-composition.md](../brain/runtime-graph-composition.md) - Implicit graph + composition
- [../flippable-chunks/](../flippable-chunks/) - Dual-collection architecture

**Business Logic:**
- AI-FIRST-USER - AI agents create + consume
- IMMUTABLE-SOURCE - Source never changes
- COMPOSITIONAL-PRIMITIVES - Building blocks over strategies
- USAGE-DRIVEN - Learn from behavior

---

**FlexGraph = Methodology for exploiting emergent structure in AI-generated knowledge systems.**
