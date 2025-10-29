---
date: 2025-10-27
type: vision.innovation
status: current
keywords: "query-adaptive graph-construction ephemeral-graph dynamic-bundling"
---

# Vision: Runtime Graph Bundling

## Core Insight

Knowledge graphs traditionally: Build graph at write time, query fixed structure at read time.

AURA innovation: Build graph at query time, structure adapts to query intent.

**Inversion:**
- Traditional KG: Static graph → dynamic queries
- AURA: Dynamic graph ← query intent

---

## The Problem with Fixed Graphs

**Neo4j approach:**
```
# Write time: Define edges
CREATE (d:Decision {content: "Use JWT"})-[:CAUSES]->(c:Constraint {content: "Can't revoke tokens"})
CREATE (d)-[:SUPERSEDES]->(old:Decision {content: "Use sessions"})
CREATE (d)-[:HAS_PATTERN]->(p:Pattern {content: "Stateless auth"})

# Read time: Query predefined structure
MATCH (d:Decision)-[:CAUSES]->(c:Constraint)
RETURN d, c
```

**Limitations:**
1. **Fixed bundling:** Always return Decision + Constraints (can't change strategy)
2. **Precomputation:** Must define all edges at write time (can't discover new relationships)
3. **Schema rigidity:** Adding new relationship type requires reindexing
4. **Query intent blind:** Same structure regardless of what user needs

---

## The Geometry of Runtime Construction

**Query-First Principle:**

```
Query Intent → Retrieve Chunks → Build Graph → Apply Algorithm → Return Bundled Results
```

**Shape:**
```
Semantic Search (Vector DB)
        ↓
   Candidate Set (20-50 chunks)
        ↓
   Graph Construction (Runtime)
   ├─ Nodes: Chunks
   └─ Edges: Metadata relationships
        ↓
   Algorithm Application
   ├─ PageRank (authority)
   ├─ Centrality (bridges)
   └─ Communities (clusters)
        ↓
   Reranked Results
```

**Key: Graph exists transiently, rebuilt per query.**

---

## Three Bundling Strategies (Same Chunks, Different Graphs)

### Strategy 1: Authority Bundling

**Query intent:** "What's the most authoritative pattern?"

**Graph construction:**
```
Nodes: All results from multi-query
Edges:
  - file_path match (siblings) → weight 0.8
  - session_id match (genealogy) → weight 0.9
  - semantic similarity > 0.85 → weight = similarity

Algorithm: PageRank
Output: Chunks ranked by how many other chunks reference them
```

**Result:** Most-cited knowledge surfaces first.

---

### Strategy 2: Bridge Bundling

**Query intent:** "Find concepts connecting auth and caching"

**Graph construction:**
```
Nodes: Results from "auth" + results from "caching"
Edges:
  - Same as authority bundling

Algorithm: Betweenness Centrality
Output: Chunks that bridge auth ↔ caching subgraphs
```

**Result:** Connector concepts surface (e.g., "token storage" bridges both domains).

---

### Strategy 3: Cluster Bundling

**Query intent:** "Group related security patterns"

**Graph construction:**
```
Nodes: All security-related results
Edges: Semantic similarity only (weight = cosine score)

Algorithm: Community Detection (Louvain)
Output: Chunks grouped into semantic clusters
```

**Result:** Natural groupings emerge (auth cluster, encryption cluster, validation cluster).

---

## Query-Adaptive Property

**Same data, different questions:**

| Query Intent | Graph Algorithm | Bundling Result |
|--------------|-----------------|-----------------|
| "Most authoritative?" | PageRank | Citation-ranked |
| "Connect two topics?" | Centrality | Bridge concepts |
| "Group patterns?" | Community Detection | Semantic clusters |
| "Evolution timeline?" | Topological Sort (temporal edges) | Chronological |

**One architecture, infinite bundling strategies.**

---

## Complexity Advantage

**Traditional KG: O(n²) precomputation**
```
n = 10,000 documents
Edges to precompute: n² = 100,000,000
Index time: Hours to days
```

**AURA: O(k²) runtime construction**
```
k = 20-50 result chunks per query
Edges to compute: k² = 400-2,500
Construction time: 40-100ms
```

**1,000,000× fewer edges to compute.**

Graph on 50 results, not 10,000 documents.

---

## The Ephemeral Property

**Graph lifecycle:**
```
Query arrives
    ↓
Build graph (40ms)
    ↓
Apply algorithm (30ms)
    ↓
Rerank results (10ms)
    ↓
Return to user (80ms total)
    ↓
Graph discarded
```

**By default: Ephemeral.**

Can persist if valuable:
- Session graphs (reuse during conversation)
- Canonical graphs (frequently queried patterns)
- BRAIN graphs (accumulated relationship knowledge)

**But default: Build, use, discard.**

---

## Trade-off Clarity

**What you gain:**
- Flexibility: Algorithm choice at query time
- Adaptability: New relationships emerge from metadata
- Scalability: O(k²) not O(n²)
- Freshness: Always reflects current metadata

**What you sacrifice:**
- Speed: Slower than indexed graph traversal
- Repeatability: Graph rebuilt each time (varies if metadata changes)
- Precomputation: Can't leverage prepared graph analytics

**Ideal for:** AI agent memory, evolving knowledge, query-specific graphs
**Not ideal for:** High-frequency analytics, static relationships, millisecond latency

---

## Metadata as Implicit Edges

**Traditional graphs:** Explicit edges in index
```
(A)-[:SIBLING]->(B)
(A)-[:SUPERSEDES]->(C)
```

**AURA:** Metadata → edges at runtime
```
# Metadata enables edge discovery
A.file_path == B.file_path → sibling edge
A.timestamp > C.timestamp AND semantic(A, C) > 0.85 → supersession edge
A.session_id == D.session_id → genealogy edge
```

**Relationships discovered, not predefined.**

---

## Systems Thinking: Lazy vs Eager

**Eager (traditional KG):**
- Compute all relationships at write time
- Store in index
- Fast read, expensive write

**Lazy (AURA):**
- Compute relationships at read time
- Ephemeral construction
- Flexible read, lightweight write

**Analogy:**
- Eager: Compile (precompute graph)
- Lazy: Interpret (build graph on-demand)

---

## Success Criteria

Runtime graph bundling succeeds when:
1. Query-specific algorithms improve retrieval quality
2. Construction overhead (40-100ms) acceptable for use case
3. New relationship types emerge without reindexing
4. Same chunks produce different insights via different algorithms

Runtime graph bundling fails when:
1. Overhead unacceptable (need <10ms)
2. Fixed bundling sufficient (don't need adaptability)
3. Relationship discovery unreliable (metadata poor quality)

---

## Key Insight: Graph as Query Operator

**Traditional:** Graph is storage layer
```
Storage: Graph database
Query: Traversal over stored graph
```

**AURA:** Graph is ranking layer
```
Storage: Vector database (flat)
Query: Build graph → rank → discard
```

**Graph becomes a QUERY OPERATOR, not a STORAGE FORMAT.**

Like: SQL ORDER BY (operates on results, doesn't store sorted)
Not: SQL Index (precomputed, stored structure)

---

## Bottom Line

**Problem:** Fixed KG bundling can't adapt to query intent.

**Innovation:** Build graph at query time from result sets.

**Benefits:**
- Query-adaptive (authority vs bridges vs clusters)
- O(k²) not O(n²) (1M× fewer edges)
- Ephemeral (build, use, discard)
- Metadata-driven (relationships emerge)

**Geometric essence:** Query → candidates → runtime graph → algorithm → reranked results

**Architectural role:** Graph as query operator, not storage layer

**Trade-off:** Flexibility vs precomputed speed (choose based on use case)
