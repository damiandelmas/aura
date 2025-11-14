---
session_id: 1103bba6-6555-41c8-a893-73234f9e7eb4
---

# The Clearest Definition

A knowledge system that preserves structure during creation instead of extracting it afterward.

**Template-guided AI writes structured documents** → **Metadata creates queryable graph** → **AI agents compose intelligence from typed foundation.**

**Result:** 50x cheaper than extraction-based systems, domain-portable patterns, contextually resolved authority.

---

## Occam's Razor Architecture

### Shape

#### STORAGE (Three Tiers)
```
├─ Tier 0: Raw sources (heterogeneous)
├─ Tier 1: Markdown wrappers (normalized)
└─ Tier 2: Project qualifiers (contextual authority)
```

#### MIND (Orthogonal intelligence)
```
├─ Schema evolution
├─ Entity resolution
├─ Runtime graphs
└─ Temporal validation
```

#### CORE (Semantic layer)
```
└─ 6 dimensions → domain types
```

### Key Points

1. **Structure preservation > extraction**
2. **Metadata = graph** (not separate storage)
3. **Authority at serve time** (contextual, not intrinsic)
4. **Ephemeral composition** (materialize on query)
5. **AI writes = AI reads** (closed loop)

### Dataflow

```
┌─ WRITE ─────────────────────────────────────┐
│ AI follows template                          │
│   → Structured markdown                      │
│   → Frontmatter metadata                     │
│   → CORE typing (optional enhancement)       │
└──────────────────────────────────────────────┘
            ↓
┌─ INDEX ─────────────────────────────────────┐
│ Qdrant stores chunks with:                   │
│   → section_type (from template)             │
│   → session_id, timestamp, file_path         │
│   → CORE coordinates (if added)              │
│   → Embeddings (semantic search)             │
└──────────────────────────────────────────────┘
            ↓
┌─ QUERY ─────────────────────────────────────┐
│ compose() filters:                           │
│   → Semantic (vector similarity)             │
│   → Structural (metadata predicates)         │
│   → Returns typed chunks                     │
└──────────────────────────────────────────────┘
            ↓
┌─ COMPOSE ───────────────────────────────────┐
│ Materialize graph from metadata:             │
│   → session_id matches = genealogy edges     │
│   → timestamp + similarity = temporal edges  │
│   → references = citation edges              │
│ Run algorithms (PageRank, communities)       │
│ Discard ephemeral graph                      │
└──────────────────────────────────────────────┘
            ↓
┌─ SERVE ─────────────────────────────────────┐
│ Qualify by context:                          │
│   → Tier 2 project wrapper                   │
│   → Attention scores                          │
│   → Temporal validation                       │
│ Return with authority labels                  │
└──────────────────────────────────────────────┘
```

**Flow in one line:**

Template → Typed chunks → Indexed metadata → Query foundation → Materialize graph → Contextual serve
