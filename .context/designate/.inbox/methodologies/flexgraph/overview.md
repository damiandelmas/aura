# FlexGraph Methodology

**Graph construction from Typed Vector Store.**

## Overview

FlexGraph is a methodology for building graphs from typed, metadata-rich chunks.

**Two modes:** Ephemeral and Persistent.

## Core Principle

**Shared Foundation:**
- Typed chunks serve as structured input
- Metadata guides construction (implicit or explicit)

**Difference:**
- **Ephemeral:** Metadata → edges
- **Persistent:** Typed chunks → AI → graph

## Ephemeral Mode (Runtime)

Runtime graph materialization from metadata predicates.

### Flow

```
Query → k results with metadata
  ↓
Materialize edges from predicates (session_id, timestamp, file_path, etc.)
  ↓
Compute k² implicit edges
  ↓
Run algorithms (PageRank, communities)
  ↓
Serve with topology context
  ↓
Discard graph
```

### Properties
- **Automatic:** No AI needed, pure metadata queries
- **Fast:** O(k²) edge computation on query-scoped subgraphs
- **Contextual:** Different graph per query intent
- **No overhead:** No storage, ephemeral composition

### Use Cases
- Find related chunks via session genealogy
- Temporal chains (what came before/after)
- Community detection in query results
- PageRank authority scoring

## Persistent Mode (AI-Guided)

AI-guided knowledge graph construction using typed chunks as structured input. Stored for repeated traversal.

### Flow

```
Query typed foundation (via FlexSchema)
  ↓
AI agent sees structured chunks:
  - All typed (Decision, Precedent, Pattern, etc.)
  - All have CORE coordinates
  - Rich metadata visible
  ↓
AI extracts entities + relationships (5-10 LLM calls total)
  ↓
Store in Neo4j or explicit graph structure
  ↓
Queryable via graph traversal
```