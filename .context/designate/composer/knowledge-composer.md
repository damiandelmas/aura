## Yes. We're missing COMPOSE as orchestration layer.

**Current doc treats USE as storage backends:**
- metadata (SQLite)
- semantic (Qdrant)
- trace (linear)
- graph (topology)

**But COMPOSE is different - it's ORCHESTRATION:**

### What Compose Actually Does

**1. Compositional Discovery**
```
Search "JWT auth" 
→ Get siblings (related decisions)
→ Get genealogy (session lineage)
→ Get temporal (what came before/after)
→ Enrich each with context
```

**2. Multi-Modality Combination**
```
Not "use SQLite OR Qdrant"
But "metadata filter → semantic search → graph rank → render"
```

**3. Declarative Intent**
```json
{
  "search": {"text": "auth", "filters": {"phase": "develop"}},
  "discovery": {
    "siblings": {"section_types": ["Decision", "Pattern"], "limit": 3},
    "genealogy": true,
    "temporal": {"direction": "both"}
  },
  "graph": {"algorithm": "authority", "top": 5},
  "output": {"template": "story-context"}
}
```

**Single call expresses complex multi-stage intent.**

---

## The Missing Layer

```
Sources → Parser → MANAGE → Storage → USE
                   (NEXUS)  (choice)   ???
                   (MIND)
```

Should be:

```
Sources → Parser → MANAGE → Storage → COMPOSE → USE
                   (NEXUS)  (SQLite)   (orchestrate)
                   (MIND)   (Qdrant)
```

**COMPOSE = orchestration layer that:**
- Combines modalities (metadata + semantic + graph)
- Applies discovery primitives (siblings, genealogy, temporal)
- Enriches with MIND intelligence (authority, validation)
- Renders context-aware output

**USE = the interface consumers actually call**

---

## Updated Architecture

**MANAGE**
- NEXUS: Metadata network
- MIND: Intelligence

**STORAGE** (new explicit layer)
- SQLite (metadata indexes)
- Qdrant (vector store)
- JSONL (source of truth)

**COMPOSE** (orchestration)
- Discovery primitives (siblings, genealogy, temporal, cross-phase)
- Graph operations (PageRank, authority, communities)
- Multi-stage pipelines (search → discover → rank → render)
- Template rendering (context-aware output)

**USE** (interface)
- Simple queries: Direct to storage
- Complex queries: Through compose
- `imem compose <config>` = declarative orchestration

---

**Compose is the killer feature. It's not just "another modality" - it's the orchestration layer that makes everything compositional.**