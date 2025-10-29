# Query-Adaptive Bundling: Architecture Pattern

**Session:** a86bc733-c4e3-4d88-b17f-2f9e330ca11a
**Level:** Architecture Pattern (L2a)
**Date:** 2025-10-27

## System Topology

```
User Query + Intent
    ↓
Strategy Selection (authority/context/bridge/timeline)
    ↓
Graph Construction (query-specific edges)
    ↓
Algorithm Application (PageRank/siblings/centrality/temporal)
    ↓
Context Assembly (primary + related chunks)
    ↓
Bundled Response
```

## Bundling Strategy Matrix

| User Intent | Graph Strategy | Algorithm | Context Includes |
|-------------|----------------|-----------|------------------|
| "Most authoritative" | Multi-query + combine | PageRank | Top-ranked + siblings |
| "Explain completely" | Single query | Siblings + session | Decision + impl + constraints + origin |
| "Find connections" | Multi-topic | Centrality | Bridge concepts between topics |
| "Show evolution" | Single query | Temporal chain | Original + refinements over time |

## Architecture Components

### 1. Strategy Selector (Intent Detection)

```
Input: User query + context
Output: Bundling strategy specification

Strategies:
- AUTHORITY: Multi-query → combine → PageRank → top N
- CONTEXT: Single query → siblings → session → assemble
- BRIDGE: Multi-topic query → centrality → connecting nodes
- TIMELINE: Single query → temporal → chronological assembly
```

### 2. Graph Constructor (Strategy-Specific)

```
Authority strategy:
  Graph edges: FILE + SESSION (maximize reference detection)

Context strategy:
  No graph needed: Direct metadata queries

Bridge strategy:
  Graph edges: FILE + SESSION + SEMANTIC (maximize connectivity)

Timeline strategy:
  Graph edges: TEMPORAL + SEMANTIC (maximize evolution detection)
```

Different strategies construct different graph structures from same chunks.

### 3. Context Assembler

```
Assemble(primary_chunks, related_chunks, strategy):
  If AUTHORITY:
    Return: Top-ranked chunks + full file context
  If CONTEXT:
    Return: Decision + implementation + constraints + conversation
  If BRIDGE:
    Return: Bridge nodes + paths between topics
  If TIMELINE:
    Return: Original + evolution chain (chronological)
```

## The Key Difference from Knowledge Graphs

### Knowledge Graph Approach

```
Index time:
  ┌─────────────────────────────────────┐
  │ Decision --[CAUSES]--> Constraint   │
  │ Decision --[HAS_IMPL]--> Code       │
  │ Decision --[SUPERSEDES]--> Old      │
  └─────────────────────────────────────┘
  Fixed edges stored

Query time:
  MATCH (d:Decision)-[:CAUSES]->(c:Constraint)
  RETURN d, c

Always returns: Decision + constraints (same structure)
```

### AURA Approach

```
Index time:
  Chunks with metadata (no edges)

Query time (Strategy 1 - Authority):
  1. Multi-query search
  2. Build graph with FILE + SESSION edges
  3. Apply PageRank
  4. Return top-ranked + siblings

Query time (Strategy 2 - Context):
  1. Single query
  2. Get siblings (FILE edges)
  3. Get session (SESSION edges)
  4. Return decision + impl + constraints + origin

Different graphs, different bundling, same chunks.
```

## Bundling Examples (Concrete)

### Example: "LlamaIndex chunking decision"

**Authority bundling:**
```json
{
  "primary": {
    "content": "### Use LlamaIndex MarkdownNodeParser",
    "rank": 1,
    "authority_score": 0.94
  },
  "context": [
    {"content": "### Section Metadata Extraction", "type": "implementation"},
    {"content": "### LlamaIndex Header Path limitation", "type": "constraint"}
  ],
  "strategy": "authority",
  "rationale": "Most-referenced chunking decision with full file context"
}
```

**Context bundling:**
```json
{
  "decision": "### Use LlamaIndex MarkdownNodeParser",
  "implementation": "Section Extraction code...",
  "constraints": "Header Path contains no section information...",
  "origin": "Conversation about enabling section-level retrieval",
  "strategy": "context",
  "rationale": "Complete genealogy from decision to implementation"
}
```

**Bridge bundling:**
```json
{
  "bridges": [
    {
      "content": "### Implement Batch Upsert",
      "connects": ["chunking", "indexing"],
      "centrality_score": 0.89
    }
  ],
  "strategy": "bridge",
  "rationale": "Concepts connecting chunking and indexing workflows"
}
```

**Timeline bundling:**
```json
{
  "original": {
    "content": "### Use LlamaIndex MarkdownNodeParser",
    "timestamp": "2025-10-24T12:59:00"
  },
  "evolution": [
    {
      "content": "### Extract Section Names from Content",
      "timestamp": "2025-10-24T13:05:00",
      "relation": "refinement"
    }
  ],
  "strategy": "timeline",
  "rationale": "Decision evolution over time"
}
```

## Interface Contracts

```
IStrategySelector:
  detect_intent(query: str) → Strategy

IGraphConstructor:
  build_for_strategy(chunks: List, strategy: Strategy) → Graph

IAlgorithmApplier:
  apply(graph: Graph, algorithm: Algorithm) → Rankings

IContextAssembler:
  assemble(primary: Chunks, related: Chunks, strategy: Strategy) → BundledContext
```

## Architectural Properties

**Intent-Adaptive:** Different bundling per query intent
**Algorithm-Flexible:** PageRank, centrality, temporal—chosen at runtime
**Structure-Dynamic:** Graph edges vary by strategy
**Context-Complete:** Returns what's needed, not what's stored

## The Innovation

Knowledge Graphs: Serve predefined relationships
AURA: Serve query-adaptive relationships

Not "chunks + edges" but "chunks + runtime relationship discovery + intent-driven bundling."

Context assembly is computed, not retrieved.
