# AURA: Architectural Shape

## Core Principle

A memory system that learns its own schema from observation rather than enforcing it at write-time.

---

## The Strange Attractor

```
Chaos                                    Coherence
│                                          │
│  ┌─────────────────────────────────┐   │
│  │   Write Freely                  │   │
│  │   (natural variation)           │   │
│  └─────────────────────────────────┘   │
│              ↓                          │
│  ┌─────────────────────────────────┐   │
└─→│   Observe Patterns              │←──┘
   │   (cluster variations)          │
   └─────────────────────────────────┘
               ↓
   ┌─────────────────────────────────┐
   │   Resolve to Canonical          │
   │   (increasing confidence)       │
   └─────────────────────────────────┘
               ↓
   ┌─────────────────────────────────┐
   │   Query with Types              │
   │   (semantic + structural)       │
   └─────────────────────────────────┘
```

---

## Three Layers

### 1. Write Layer: Progressive Disclosure

- Agents write markdown following templates
- Templates define possible types, not required types
- Each document instantiates only valuable types
- No rejection, only varying confidence

### 2. Resolution Layer: Emergent Taxonomy

- Observe corpus → extract section headers
- Cluster variations → discover semantic groups
- Map variations to canonical types
- Confidence scores track resolution quality

### 3. Query Layer: Type + Vector Fusion

- Semantic search (vector similarity)
- Type filtering (canonical names)
- Query expansion (all variants)
- Compositional assembly (siblings, genealogy, temporal, cross-phase)

---

## Dataflow

**Input:**
Natural variation → "Decision:", "Choice:", "We Decided:"

**Transform:**
- Embedding → continuous semantic space
- Clustering → discrete type boundaries
- Resolution → canonical mapping

**Storage:**
- Chunk: `{text, embedding, section_type, confidence, variants}`
- Metadata: `{file_path, session_id, timestamp, parent_headers}`

**Retrieval:**
```
Query("auth decisions")
    → Vector search (semantic: "auth")
    → Type filter (structural: canonical="decision")
    → Expand variants (all decision forms)
    → Compose context (siblings, genealogy)
    → Return with provenance
```

---

## Key Distinctions

| Traditional Vector DB    | AURA                     |
|--------------------------|--------------------------|
| Type-free chunks         | Semantic types           |
| Probabilistic extraction | Deterministic clustering |
| Static schema            | Evolving taxonomy        |
| Single-domain            | Domain-agnostic          |
| Binary (works/fails)     | Confidence gradient      |

---

## The Innovation

**Dual intelligence:**
- Vector embeddings: Pre-trained semantic understanding (continuous, fuzzy)
- Schema evolution: Runtime structural learning (discrete, crisp)

**The attractor:**
- Start anywhere (chaos accepted)
- Converge naturally (patterns emerge)
- Never fully rigid (new types discoverable)
- Always queryable (confidence indicates quality)

---

## What Makes It Strange

- Not document DB (no vectors)
- Not vector DB (types exist)
- Not knowledge graph (ephemeral edges)
- Not type checker (types inferred)

**It's a self-organizing memory with emergent structure.**
