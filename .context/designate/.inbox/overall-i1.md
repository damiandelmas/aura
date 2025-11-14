---
session_id: df2a4bb9-d61c-4c7d-8a91-21dcee61290c
session_id-a: e4f01f41-e723-411f-b3b7-92ea48646cb9
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

### 3. CREATE / MANAGE / USE (Core System)
```
CREATE: Entry mechanisms (how artifacts enter)
MANAGE: Universal metadata network (tier wrapping + visibility)
USE: Consumption (retrieval, tools, orchestration)
```

### 4. AUTHORITY EMERGENCE
```
NOT: Sources declare importance
IS: Usage patterns reveal authority
Same source = different authority per project/context
```

---

## The Architecture

```
                    GIT (truth spine)
                         │
                    Validates ↓
                         │
         ┌───────────────┼───────────────┐
         │                               │
    TIER STACK                      CORE SYSTEM
         │                               │
    0: Sources                      CREATE (entry)
         │                               │
    1: Registry ←────┐              MANAGE (metadata network)
         │            │                  │
    2: Qualification  │              USE (consumption)
         │            │                  │
         │       (universal wrapper)     │
         │            │                  │
         └────────────┴──────────────────┘
                      │
              HARMONIOUS LAYERS
                      │
         ┌────────────┼────────────┐
         │            │            │
      PROCESS      IMEM        TRACE
    (four-phase) (memory)   (genealogy)
         │         BRAIN          │
         │      (introspect,      │
         │       compose)         │
         └────────────┴───────────┘
              │
    design → designate → develop → document
```

---

## Harmonious Layers (Exogenous)

**PROCESS (Four-Phase Workflow)**
- Methodology that produces artifacts
- design → designate → develop → document
- Exploits CREATE (outputs feed system)
- Exploited by MANAGE (provides structured metadata)
- Separate but well-integrated
- Harmony, not endogeneity

**IMEM (Institutional Memory)**
- Uses MANAGE (tier wrapping for indexed content)
- Provides BRAIN capabilities (introspect, compose)
- Consumed via USE
- One retrieval method among many

**TRACE (Genealogy)**
- Uses MANAGE (session linkage metadata)
- Consumed via USE
- Enables lineage synthesis

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

**PROCESS** (Harmonious Layer)
```
Four-phase workflow produces artifacts:
design → designate → develop → document
Artifacts enter via CREATE, wrapped by MANAGE, accessed via USE
```

**RETRIEVE** (Type-aware)
```
Query → CORE matching + Context qualification → Serve
```

**COMPOSE** (Graph)
```
Results → Metadata predicates (session_id, timestamp, file_path) → Edges → Topology
```

---

## The Essential Properties

**Property 1: Separation**
- Tiers = data concerns (what exists, how wrapped, who uses)
- CREATE/MANAGE/USE = core system (entry, wrapper, consumption)
- BRAIN = IMEM intelligence (introspect, compose - harmonious layer)
- PROCESS = methodology concerns (how artifacts are produced)
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

**Property 5: Harmony Not Endogeneity**
- PROCESS exploits core (produces artifacts)
- Core exploits PROCESS (gets structured metadata)
- IMEM exploits MANAGE (uses tier wrapping)
- MANAGE exploits IMEM (quality retrieval via BRAIN)
- All harmonious layers: integrated but architecturally separate

---

## The Minimal Truth

**Sources are equal at entry.**

**Facts are inert at registry.**

**Authority emerges through usage.**

**Tiers provide structure.**

**CREATE/MANAGE/USE is the core.**

**Git validates all claims.**

**BRAIN is IMEM's intelligence layer.**

**Context determines meaning.**

**PROCESS (four-phase) is harmonious but separate.**
