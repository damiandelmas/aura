# Graph Ops: Architecture Overview

## The Core Insight

**We have rich metadata at index time.** Unlike systems like Graphiti that use LLM to extract entities and relationships, our metadata (file_path, session_id, timestamp, phase, section_type) already encodes the graph structure.

**Metadata predicates ARE the graph.** No separate edge storage needed.

```
Graphiti:  Text → LLM extracts → Store edges → Query graph DB
IMEM:      Markdown → Parse metadata → SQLite → Runtime composition
                         ↑
                   FREE (already structured)
```

---

## The Four Layers

```
L1: IMPLICIT GRAPH          Metadata predicates = edges           ✅ HAVE
L2: RUNTIME COMPOSITION     NetworkX on k-result subgraphs        🟡 BUILD
L3: CONTEXTUAL ASSEMBLY     Traverse + template = rich context    🟡 BUILD
L4: ENTITY RESOLUTION       Variations → canonical at index       🟡 BUILD
```

---

## Layer 1: Implicit Graph (Metadata Predicates)

**What**: Indexed columns ARE edges. Query them to traverse.

| Predicate | Edge Type | Query Pattern |
|-----------|-----------|---------------|
| `file_path` | Spatial (siblings) | `WHERE file_path = ?` |
| `session_id` | Genealogical | `WHERE session_id = ?` |
| `timestamp` | Temporal | `WHERE timestamp > ? ORDER BY timestamp` |
| `phase` | Lifecycle | `WHERE phase = ?` |
| `section_type` | Type clustering | `WHERE section_type = ?` |

**Intelligence required**: Zero. Data exists at index time.

**Status**: ✅ We have this now.

---

## Layer 2: Runtime Composition (Ephemeral Subgraphs)

**What**: Materialize graph ONLY for k search results. Compute metrics. Discard.

```python
def rank_by_authority(search_results: List[Chunk]) -> List[Chunk]:
    """Build ephemeral graph from k results, compute metrics, discard"""

    # 1. Materialize subgraph (k nodes, ~k² potential edges)
    G = nx.DiGraph()
    for chunk in search_results:
        G.add_node(chunk.id, **chunk.metadata)

        # Add edges via metadata predicates
        siblings = query(f"WHERE file_path = '{chunk.file_path}'")
        for s in siblings:
            G.add_edge(chunk.id, s.id, type='spatial')

        genealogy = query(f"WHERE session_id = '{chunk.session_id}'")
        for g in genealogy:
            G.add_edge(chunk.id, g.id, type='genealogical')

    # 2. Compute graph metrics
    pagerank = nx.pagerank(G)
    centrality = nx.betweenness_centrality(G)

    # 3. Score and rank
    for chunk in search_results:
        chunk.authority = pagerank[chunk.id] * 0.6 + centrality[chunk.id] * 0.4

    # 4. Graph discarded after function returns
    return sorted(search_results, key=lambda c: c.authority, reverse=True)
```

**Why this is 40,000x cheaper than precomputation**:
- Precompute: 10,000 chunks × 10,000 = 100M edge checks
- Runtime: 20 results × 20 = 400 edge checks

**Intelligence required**: Query-time computation (cheap).

**Status**: 🟡 Need to build (`doc-pac_9_authority-scoring`)

---

## Layer 3: Contextual Assembly (Graph-Aware Serving)

**What**: Graph traversal provides CONTEXT. Templates ASSEMBLE it.

Not just:
```
🟢 Use JWT Authentication (confidence: 0.9)
```

But:
```markdown
## Authentication Decision Trail

### What User Wanted (Origin)
💬 From conversation abc123:
> "We need to secure the API endpoints"
> "Users should stay logged in for a day"

### What We Decided
✅ Use JWT Authentication (2025-10-28)
- Context: API needs secure user sessions
- Solution: JWT with 24hr expiration

### How We Built It
```python
# From conversation patch:
def create_jwt(user_id):
    return jwt.encode({'user_id': user_id, 'exp': ...}, SECRET_KEY)
```

### What Happened Next
⚠️ Later modified: Expiration changed to 7 days (251105)
```

**The Assembly Process**:
1. Search: Find Decision about "auth" (k=1)
2. Traverse genealogy: Get conversation chunks via `session_id`
3. Filter user messages: Extract user intent (not AI responses)
4. Traverse siblings: Find Implementation section + code
5. Traverse temporal: Find later modifications
6. Assemble template: User intent → Decision → Code → Evolution

**Different queries want different assemblies**:

| Query Intent | Assembly Directive |
|--------------|-------------------|
| "Current state" | Decision + Code + No supersessions |
| "Why did we decide this?" | Decision + User messages + Alternatives |
| "How has this evolved?" | Temporal chain + Each modification |
| "Full story" | User request → Failures → Solution → Code |

**Intelligence required**: Assembly directive per query type.

**Status**: 🟡 Need to build (`doc-pac_10_discovery-processors`)

---

## Layer 4: Entity Resolution at Index

**What**: Resolve variations → canonical at parse time. Expand at query time.

```
Index time:
  "jwt", "JWT", "jwt-tokens", "json-web-token"
       ↓ Union-Find clustering
  canonical: "jwt" → variants: ["JWT", "jwt-tokens", "json-web-token"]

Query time:
  User searches: "JWT"
       ↓ Expand via resolution map
  Actually queries: "jwt" OR "JWT" OR "jwt-tokens" OR "json-web-token"
```

**Borrowed from Graphiti**: Union-Find with path compression for transitive resolution.

```python
def resolve_entities(pairs: List[Tuple[str, str]]) -> Dict[str, str]:
    """Collapse alias → canonical chains"""
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        if parent[x] != x:
            parent[x] = find(parent[x])  # Path compression
        return parent[x]

    for alias, canonical in pairs:
        parent[find(alias)] = find(canonical)

    return {x: find(x) for x in parent}
```

**Our advantage over Graphiti**:
- Graphiti: LLM extracts entities from text (expensive)
- IMEM: Metadata exists at parse time (free)

**Intelligence required**: Clustering algorithm (cheap, runs at index).

**Status**: 🟡 Need to build (`doc-pac_8_entity-resolution`)

---

## What We DON'T Need

### ❌ Relationships Table

**Why not**: Metadata predicates ARE the edges.

```sql
-- This is unnecessary:
CREATE TABLE relationships (source_id, target_id, type, confidence)

-- Because this already works:
SELECT * FROM chunks WHERE file_path = ?      -- spatial edge
SELECT * FROM chunks WHERE session_id = ?     -- genealogy edge
SELECT * FROM chunks WHERE timestamp > ?      -- temporal edge
```

**The question that kills it**: What intelligence POPULATES the relationships table?
- Heuristics: Brittle
- LLM batch: Expensive
- Human labeling: Doesn't scale

**Verdict**: Premature infrastructure for intelligence that doesn't exist.

### ❌ Graph Database (Neo4j, etc.)

**Why not**: SQLite + runtime composition = same result, simpler stack.

### ❌ Precomputed Authority Scores

**Why not**: 100M edge checks vs 400 edge checks on k results.

---

## The Flow

```
Foundation (Index Time)
├── Parse markdown → structured metadata
├── Entity resolution → canonical mappings
└── Store in SQLite with indexes

Query Time
├── Semantic search → k results
├── Runtime composition → ephemeral subgraph
├── Graph metrics → authority scores
├── Assembly directive → gather related context
└── Template render → rich response

Traversal Predicates (Implicit Edges)
├── file_path     → spatial (siblings)
├── session_id    → genealogical (conversation origin)
├── timestamp     → temporal (evolution chains)
├── phase         → lifecycle (design → develop → document)
└── section_type  → type clustering
```

---

## Cost Comparison

| Operation | Graphiti | IMEM |
|-----------|----------|------|
| Entity detection | LLM call per doc | Parse frontmatter (free) |
| Edge creation | LLM + store | Query metadata (free) |
| Graph traversal | Neo4j query | SQLite WHERE clause |
| Authority scoring | Precomputed globally | Runtime on k results |

**Result**: Graph intelligence at 1/10th the cost.

---

## Walking Skeleton Mapping

| Layer | Doc-Pac | Purpose |
|-------|---------|---------|
| L1: Implicit Graph | ✅ Done | Metadata predicates indexed |
| L2: Runtime Composition | `_9_authority-scoring` | NetworkX on ephemeral subgraphs |
| L3: Contextual Assembly | `_10_discovery-processors` | Traverse + template |
| L4: Entity Resolution | `_8_entity-resolution` | Union-Find at index time |

**Deleted**: `_5_relationships-table` — metadata predicates ARE the graph.
