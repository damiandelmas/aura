---
session_id: e025fbb0-1abb-46e8-82a1-79c49afcc32d
date: 2025-10-27
type: vision.innovation
resolution: geometric
keywords: "lazy-discovery metadata-queries zero-precomputation"
---

# Soft-Graph via Metadata: Lazy Relationship Discovery

## The Insight

**Relationships discovered, not predefined.**

Traditional KG: Define edges at write time
Soft-graph: Discover edges at query time via metadata

The power isn't in precomputed structure. It's in dynamic discovery.

## The Geometry

```
Traditional Graph (Neo4j):

Ingestion: Build ALL edges
    Node A ──causes──> Node B
    Node A ──constrains──> Node C
    Node B ──supersedes──> Node D
    [Store 10,000 edges for 1,000 nodes]

Query: Follow precomputed edges (fast)
    Cost: O(edges) - cheap
    Flexibility: Zero (edges are fixed)

AURA Soft-Graph:

Ingestion: Store metadata only
    Chunk A: {file_path: X, session_id: Y, timestamp: Z}
    Chunk B: {file_path: X, session_id: Y, timestamp: Z+1}
    [No edges stored]

Query: Discover relationships via filters
    siblings = filter(file_path == A.file_path)
    genealogy = filter(session_id == A.session_id)
    temporal = filter(timestamp > A.timestamp)

    Cost: O(filter_scan) - slower
    Flexibility: Infinite (any metadata dimension)
```

## The System Property

**Graph emerges from queries, not from structure:**

```
Query "siblings of decision X":
→ Not: Follow pre-built "same_file" edge
→ Instead: Filter WHERE file_path == X.file_path
→ Discovers: All chunks from same document

Query "conversation that created X":
→ Not: Follow pre-built "origin" edge
→ Instead: Filter WHERE session_id == X.session_id AND source == 'conversation'
→ Discovers: Full ideation thread

Query "decisions after X on similar topic":
→ Not: Follow pre-built "supersedes" edge
→ Instead: Filter WHERE timestamp > X.timestamp AND semantic_similarity > 0.85
→ Discovers: Temporal evolution
```

**Zero edges stored. All relationships discovered.**

## The Behavior

**Relationship types via metadata:**

1. **Structural** (file_path)
   - siblings: Same document sections
   - context: Full surrounding content

2. **Genealogical** (session_id)
   - origin: Conversation that created this
   - results: Decisions from this session

3. **Temporal** (timestamp + semantic)
   - earlier: Design docs before implementation
   - later: Refinements after decision
   - superseded: Replacements detected

4. **Abstraction** (naming convention)
   - pattern: .md → .pattern.md twin
   - cross-language: Implementation → agnostic

## Why This Matters

**Adapt without migration.**

New relationship type needed? Just query new metadata dimension.

Traditional KG: Add new edge type → Recompute entire graph → Migrate data
Soft-graph: Add new filter → Query existing metadata → Done

**Example:**

Add "related by author":
- Traditional: Create 50,000 new edges, reindex
- Soft-graph: Query WHERE author == X.author (metadata already there)

Add "related by failure":
- Traditional: Define failure_causes edge, rebuild graph
- Soft-graph: Query WHERE failure_id == X.id (done)

## The Moat

**Flexibility compounds.**

Month 1: Discover relationships via file_path, session_id
Month 6: Add author, keyword, status relationships
Month 12: Add semantic clusters, dependency chains

Traditional KG: Each new relationship = migration
Soft-graph: Each new relationship = new query pattern

**Zero maintenance, infinite extensibility.**
