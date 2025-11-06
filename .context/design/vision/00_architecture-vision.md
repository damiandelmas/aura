---
session_id: "034ba596-240e-4bc3-b71a-2194dafd9656"
---

# Aura Architecture Vision

**A self-organizing knowledge orchestration system**

---

## The Core Insight

Traditional knowledge systems impose rigid schemas upfront. Aura inverts this: **write naturally, structure emerges, intelligence accumulates through usage.**

Authority is not declared—it's contextual. Truth is not asserted—it's validated against implementation. Types are not prescribed—they emerge from observation.

---

## Three Concerns, Clean Separation

### **STORAGE (Three-Tier Gateway)**
**Where things live**

```
Tier 0: Raw sources (heterogeneous)
  ↓
Tier 1: Objective registry (normalized markdown wrappers)
  ↓
Tier 2: Subjective qualifiers (per-project gateways)
```

**Key properties:**
- Tiers organize sources, not processing stages
- All Tier 0 sources treated equally (official docs = develop logs)
- Authority determined at serve time via Tier 2 context
- Same source has different authority per project

**Pattern:** Normalize heterogeneous sources → Objective facts → Subjective qualification

---

### **INTELLIGENCE (BRAIN)**
**How we understand**

```
┌─ BRAIN operates ACROSS storage ────────┐
│                                         │
│  FlexSchema: Pattern → emerged types   │
│  FlexGraph: Metadata → implicit edges  │
│  Entity Resolution: Variants → canonical│
│  Introspection: Expose capabilities    │
│  Temporal Cortex: Validate via code    │
│                                         │
└─────────────────────────────────────────┘
```

**Key properties:**
- Intelligence layer independent of storage backend
- Operates on parameter space (metadata per chunk)
- No precomputation—everything emerges at runtime
- Self-describing system (AI discovers capabilities)

**Pattern:** Observe → Cluster → Emerge → Validate

---

### **OPERATIONS (Metadata Network)**
**How we get things**

```
Query → Metadata Network → Route to backend(s)
              ↓
    IMEM | Graphiti | WebFetch | Filesystem
              ↓
        Unified results + context
```

**Key properties:**
- Retrieval-agnostic (swap backends freely)
- IMEM, Graphiti, WebFetch = equal tools
- Retrieval method specified in Tier 1 metadata
- Intelligence persists across backend changes

**Pattern:** Abstract retrieval → Pluggable backends → Unified serving

---

## Core Methodologies

### **FlexSchema** (Type System Evolution)
**CORE → SCHEMA → KNOWLEDGE**

Write with natural headers → AI observes patterns → Types emerge → Query using discovered schema

**Enables:** Write naturally, no rigid types, Hindley-Milner for documents

### **FlexGraph** (Runtime Graph Materialization)
**Metadata predicates → Ephemeral graphs**

Index rich metadata → Semantic search returns k chunks → Materialize k-subgraph → Compute O(k²) edges → Run graph algorithms → Serve with topology context

**Enables:** No precomputed graph, context-aware relationships, scalable algorithms

### **Three-Tier Gateway** (Data Organization)
**Objective facts → Subjective qualification**

Encounter source → Create Tier 1 registry → Projects create Tier 2 wrappers → Attention accumulates → Authority at serve time

**Enables:** Low-friction capture, intellectual capital accumulation, cross-project learning

### **Temporal Truth Validation**
**Code = ground truth**

Documentation claims → Git tracks code changes → Detect drift → Serve based on divergence radius

**Enables:** Honest uncertainty, graceful degradation, validated knowledge

### **Metadata Network Orchestration**
**Universal retrieval interface**

Query intent → Discover sources (Tier 1) → Route to appropriate backend → Execute retrieval → Enrich with BRAIN intelligence → Serve with qualification

**Enables:** Technology independence, future-proof, composable retrieval

---

## The Profound Properties

### **Self-Organizing**
- Schemas emerge from usage patterns
- Entity resolution discovers canonical forms
- Attention density reveals importance
- No manual curation required

### **Retrieval-Agnostic**
- Intelligence layer independent of storage
- Swap Qdrant for Pinecone, add Neo4j
- BRAIN operations work across all backends
- HTTP for knowledge

### **Context-Aware**
- Same source, different authority per project
- barbar's develop log = ground truth (in barbar)
- barbar's develop log = reference example (in npta)
- Purpose + intention determine serve qualification

### **Truth-Validated**
- Code is source of truth
- Documentation validated against implementation
- Drift detected via git diffs
- Graceful degradation when diverged

### **Type-Safe**
- Template structure = type system
- Decision, Pattern, Failure = semantic types
- Fuzzy semantic search + precise type filtering
- First vector database with type system

---

## Implementation

**IMEM:** Typed vector document store implementing FlexGraph methodology internally

**Parameter Space:** ~30-35 metadata dimensions per chunk enabling all intelligence operations

**Template System:** Markdown H2/H3 hierarchy as type declarations with required/optional fields

---

## Future: Universal Semantic Layer (Post-MVP)

### CORE Classification
Every chunk gets 6D coordinates at index. Domain templates map coordinates to types at serve.

**Example:**
```
Coordinates: what=0.85, why=0.75, valence=good, epistemic=known
Software domain: "Decision"
Legal domain: "Holding"
Business domain: "Objective"
```

Same structure, different interpretation per domain.

### AI-Augmented Construction
CORE-enriched chunks enable efficient knowledge graph construction.

**Pattern:** AI agent queries "Find legal precedents about X" → System returns 50 chunks all typed as "precedent" → Agent extracts entities/relationships from structured set (5 LLM calls total vs 50 calls per document).

Structure guides extraction. Cheaper, faster, more accurate.

---

## The Vision Realized

You're not building "a Qdrant-based knowledge system."

You're building a **universal knowledge orchestration layer** that:
- Treats all sources as intellectual capital
- Lets structure emerge from observation
- Determines authority through context
- Validates truth through implementation
- Works across any retrieval backend

**The abstraction is the innovation.**

---

## Related Documents

- [NAMESPACE.md](../00_NAMESPACE.md) — Term definitions
- [three-tier/](../three-tier/) — Storage architecture details
- [flexgraph/methodology.md](../architecture-i2/flexgraph/methodology.md) — Graph construction
- [parameter-space/](../parameter-space/) — Metadata dimensions
- [architecture-i2/brain/](../architecture-i2/brain/) — Intelligence components
- [Hindley-Milner Foundation](../tiny-models/Claude-Hindley-Milner type system explained.md) — Conceptual origins
- [CORE Enhancement](./01_core-enhancement.md) — Detailed design
