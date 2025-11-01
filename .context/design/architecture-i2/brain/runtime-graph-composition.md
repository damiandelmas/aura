---
session_id: "090c7e16-cb85-45e5-a1f0-8dd53f191a40"
---

# BRAIN: Runtime Graph Composition

**The control plane for document space.**

---

## Overview

Metadata index = implicit knowledge graph.

BRAIN exposes this graph via runtime APIs. No separate graph storage. Metadata predicates (file_path, session_id, timestamp) ARE traversable edges. Query the index, materialize relationships on demand.

**The shift:** Not "build a graph DB" but "query metadata as graph."

---

## The Foundation

Template + frontmatter create typed chunks with indexed metadata.

**Every chunk has:**

**Type system metadata (from template):**
- section_type: "Decision" (from H2 parent)
- section_name: "Use JWT" (from H3 header)
- Fields: context, solution, rationale (guaranteed when present)

**Document properties (from frontmatter):**
- category: "implementation" (resolved from type field)
- session_id: "b4078811..." (genealogy link)
- timestamp: "2025-10-30T00:00:00-0700"
- keywords: ["cli", "refactor"]

**All indexed. All queryable.**

---

## The Implicit Graph

Indexed metadata = traversable edges. Zero edge storage.

**Relationship queries:**
```
Siblings: filter(file_path=X.file_path) → O(log n)
Genealogy: filter(session_id=X.session_id) → O(log n)
Temporal: filter(timestamp>X.timestamp, semantic>0.85) → O(log n)
```

**Traditional knowledge graph:**
```
Precompute edges: O(n²) at write-time
Store edges: Millions of rows
Query edges: O(1) lookup
```

**IMEM implicit graph:**
```
Precompute edges: O(0) - nothing to build
Store edges: Zero - metadata already indexed
Query edges: O(log n) - metadata index lookup
```

**Same traversal capability. Zero storage overhead.**

---

## Runtime Composition API

AI agents compose graphs from metadata queries.

**API:**
```json
imem graph compose '{
  "queries": [
    {"text": "authentication", "filters": {"section_type": "Decision"}},
    {"text": "authentication", "filters": {"section_type": "Failure"}}
  ],
  "edges": ["sibling", "genealogy", "temporal"],
  "algorithm": "pagerank",
  "top": 10
}'
```

**Execution:**
1. Execute 2 vector queries (3-5 query budget)
2. Materialize edges from metadata:
   - file_path matches → sibling edge
   - session_id matches → genealogy edge
   - timestamp + semantic → temporal edge
3. Build NetworkX graph (ephemeral, in-memory)
4. Run PageRank algorithm
5. Return top 10 nodes by score
6. Discard graph

**Property:** Zero storage. Graph exists during query, disappears after.

**Scope flexibility:**
- Query-scoped: Materialize k² edges on results (fast, adaptive)
- Corpus-scoped: Compute full n² graph when needed (feasible with indexed metadata)
- Hybrid: Precompute expensive metrics, materialize on-demand for queries

---

## Graph-Aware Serving

**Topology informs presentation.**

Query graph to detect each chunk's position:
- Temporal position (current vs evolved)
- Authority (connectivity, PageRank)
- Lifecycle (active vs isolated)
- Confidence (validated vs speculative)

**Serve chunks with graph context:**

AI sees relationships programmatically, not inferred. Template selection driven by detected topology. Structure conveys graph position.

**The ability:** Use graph algorithms to contextualize chunks intelligently for AI comprehension.

---

## BRAIN: The Control Plane

**Manager of document space runtime/control/map.**

### Runtime Infrastructure

**Graph composition API:**
- Expose metadata as queryable graph
- Materialize relationships on-demand
- Run algorithms (PageRank, communities, shortest path)

**Schema introspection:**
- Expose complete metadata landscape before query
- AI asks: "What can I filter on? What relationships exist?"
- BRAIN responds with schema map
- Zero guessing, full discovery

### Storage Layer

**Entity resolution:**
- Canonical term mapping (jwt → auth.jwt)
- Enables better edge detection
- Storage: Normalized entity map

**Presets:**
- Saved composition patterns
- Observable usage → preset generation
- Storage: Proven query patterns

**Persistent graphs:**
- Reference topology (optional)
- Ephemeral graphs compare against stable baseline
- Storage: Canonical subgraphs (when valuable)

### Intelligence

**Pre-computed metrics:**
- PageRank scores stored as chunk metadata
- Authority accessible without recomputation

**Usage tracking:**
- Which compositions recur
- Which graphs get cached
- Which patterns emerge

---

## Schema Introspection

BRAIN exposes metadata landscape before query.

**AI workflow:**
```
1. AI: "What metadata exists?"
2. BRAIN: Returns schema map (all indexed fields)
3. AI: Constructs precise query from schema
4. BRAIN: Executes query
```

**Available metadata:**
- Type system: section_type, section_name, has_context, has_solution
- Document: category, subtype, session_id, timestamp, keywords
- Relationships: file_path (siblings), session_id (genealogy)

**Property:** Self-describing system. AI discovers capabilities programmatically.

---

## Complete Example

**Query: "Find authoritative authentication decisions"**

**Step 1: Schema introspection**
```
AI: imem schema
BRAIN: Returns available filters (section_type, category, etc.)
```

**Step 2: Graph composition**
```
AI: imem graph compose '{
  "queries": [{"text": "authentication", "section_type": "Decision"}],
  "edges": ["sibling", "genealogy"],
  "algorithm": "pagerank",
  "top": 5
}'
```

**Step 3: BRAIN executes**
- Query vector DB: 20 auth decisions
- Materialize edges from metadata (siblings, genealogy)
- Build graph (ephemeral)
- Run PageRank
- Detect topology (authority nodes)

**Step 4: Graph-aware serving**
- Top 5 by PageRank
- Label with graph position (authoritative, current)
- Template selection based on topology
- Return structured context

---

## The Architectural Exploitation

**Traditional systems need:**
- Vector DB + Graph DB (two systems)
- Edge precomputation O(n²)
- Graph maintenance on updates
- Separate serving logic

**IMEM needs:**
- Vector DB with indexed metadata (one system)
- Runtime edge materialization - O(k²) on query results or full corpus graphs when needed
- Zero graph maintenance (implicit edges)
- Topology-aware serving (graph position → context)

**Everything exploits what template + frontmatter already created.**