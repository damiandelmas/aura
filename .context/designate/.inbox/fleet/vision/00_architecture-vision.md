---
session_id: "034ba596-240e-4bc3-b71a-2194dafd9656"
---

### **Three-Tier Gateway**


```
Tier 0: Raw sources (heterogeneous)
  ↓
Tier 1: Objective registry (normalized markdown wrappers)
  ↓
Tier 2: Subjective qualifiers (per-project gateways)
```

**Key properties:**
- All Tier 0 sources treated equally (official docs = develop logs)
- Authority determined at serve time via Tier 2 context
- Same source has different authority per project

---

### **MIND**


```
┌─ MIND operates ACROSS storage ────────┐
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
- Self-describing system (AI discovers capabilities)

**Pattern:** Observe → Cluster → Emerge → Validate

---

### **Metadata Network**

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
- Intelligence persists across backend changes

**Pattern:** Abstract retrieval → Pluggable backends → Unified serving

---

## Core Methodologies

### **FlexSchema** (Type System Evolution)

Write with natural headers → AI observes patterns → Types emerge → Query using discovered schema

**Enables:** Write naturally, no rigid types, Hindley-Milner for documents

### **FlexGraph** (Runtime Graph Materialization)
**Metadata predicates → Ephemeral graphs**

Index rich metadata → Semantic search returns k chunks → Materialize k-subgraph → Compute O(k²) edges → Run graph algorithms → Serve with topology context

**Enables:** No precomputed graph, context-aware relationships, scalable algorithms

### **Three-Tier Gateway** (Data Organization)
**Objective facts → Subjective qualification**

Encounter source → Create Tier 1 registry → Projects create Tier 2 wrappers → Authority at serve time

**Enables:** Low-friction capture, intellectual capital accumulation, cross-project learning

### **Temporal Truth Validation**
**Code = ground truth**

Documentation claims → Git tracks code changes → Detect drift → Serve based on divergence radius

**Enables:** Honest uncertainty, graceful degradation, validated knowledge

### **Metadata Network Orchestration**

Query intent → Discover sources (Tier 1) → Route to appropriate backend → Execute retrieval → Enrich with MIND intelligence → Serve with qualification