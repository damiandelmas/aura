---
session_id: df2a4bb9-d61c-4c7d-8a91-21dcee61290c
---

# Essential Architecture

---

## The Primitives

### 1. PROJECT = GIT REPOSITORY
```
Boundary: .git/
Truth: Commits validate claims
Isolation: Knowledge per-project
```

### 2. THREE-TIER GATEWAY
```
Tier 0: Thing itself (URL, file, repo, anything)
Tier 1: Facts ABOUT thing (source, format, when seen)
Tier 2: Relationship TO thing (how used, by whom, why)
```

### 3. FOUR-PHASE ABSTRACTION
```
design → designate → develop → document
(explore)  (plan)     (implement)  (stable)

```

### 5. MIND (Intelligence Layer)
```
Operations: Schema evolution, entity resolution, graph materialization, validation
Independence: Works regardless of backend (Qdrant/Neo4j/ES/filesystem)
Scope: Operates across all tiers and phases
```

### 6. AUTHORITY EMERGENCE
```
NOT: Sources declare importance
IS: Usage patterns reveal authority
Same source = different authority per project/context
```

---

## The Relationships

```
                    GIT (truth spine)
                         │
                    Validates ↓
                         │
         ┌───────────────┼───────────────┐
         │                               │
    TIER STACK                      PHASE STACK
         │                               │
    0: Sources                    design (fluid)
         │                               │
    1: Registry ←────┐            designate (crystal)
         │            │                  │
    2: Qualification  │            develop (validated)
         │            │                  │
         │       MIND (orthogonal)     document (static)
         │            │                  │
         └────────────┴──────────────────┘
                      │
              TYPE SYSTEM (FlexSchema)
                      │
          CORE (universal) + Templates (domain)
                      │
              GRAPH (FlexGraph)
          Ephemeral | Persistent
```

---

## The Essential Operations

**REGISTER** (Tier 0→1)
```
Source encountered → Metadata captured → Visible
```

**QUALIFY** (Tier 1→2)
```
Project accesses → Usage logged → Authority emerges
```

**VALIDATE** (Git oracle)
```
Document claims → Code implements → Diff computes → Truth grounds
```

**TRANSFORM** (Phase transitions)
```
Abstraction shifts: design→designate, designate→develop, develop→document
Automation lives at crystallization: design→designate
```

**RETRIEVE** (Type-aware)
```
Query → CORE matching + Domain template + Context qualification → Serve
```

**COMPOSE** (Graph)
```
Results → Metadata predicates (session_id, timestamp, file_path) → Edges → Topology
```

---

## The Essential Properties

**Property 1: Separation**
- Tiers = data concerns (what exists, how wrapped, who uses)
- Phases = knowledge concerns (exploration, plan, ground truth, reference)
- MIND = intelligence concerns (understanding, serving, validating)
- All orthogonal

**Property 2: Emergence**
- Authority from usage, not declaration
- Schemas from observation, not prescription
- Graphs from metadata, not precomputation
- Understanding from synthesis, not assertion

**Property 3: Context Determines Meaning**
- Index: Universal facts
- Serve: Contextual interpretation
- Same chunk = different type/authority depending on query context

**Property 4: Git Grounds Everything**
- Repository = project boundary
- Commits = temporal ordering
- Diffs = validation oracle
- History = truth source

**Property 5: Types Without Corpus**
- CORE dimensions universal (work on first document)
- Domain templates pre-defined (bootstrap immediately)
- Cross-domain transfer via shared coordinates

---

## The Minimal Truth

**Sources are equal at entry.**

**Facts are inert at registry.**

**Authority emerges through usage.**

**Types enable structured retrieval.**

**Phases provide abstraction layers.**

**Git validates all claims.**

**MIND operates independently.**

**Context determines meaning.**