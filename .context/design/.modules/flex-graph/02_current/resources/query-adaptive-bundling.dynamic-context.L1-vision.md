# Query-Adaptive Bundling: Dynamic Context Assembly

**Session:** a86bc733-c4e3-4d88-b17f-2f9e330ca11a
**Level:** Vision (L1)
**Date:** 2025-10-27

## The Paradigm Inversion

Knowledge Graphs: Serve chunks with context via pre-computed graph linking
- Structure fixed at index time
- Same bundling for every query
- "Here's what we know about X + everything we think is related"

AURA: Serve chunks, determine context at runtime via malleable graph linking
- Structure constructed per query
- Different bundling strategies based on intent
- "Here's what you need about X based on why you're asking"

## The Geometric Insight

Traditional KG: Static graph → dynamic queries
AURA: Dynamic graph ← query intent

Graph structure adapts to query, not vice versa.

## Four Bundling Strategies (Same Chunks, Different Context)

Query: "LlamaIndex section chunking implementation"

### Strategy 1: Authority Bundling (PageRank)
Intent: Find most-referenced decisions

Returns:
- Primary: Most-cited chunking decision
- Context: Other highly-referenced related decisions
- Why: Authority = reference count

### Strategy 2: Context Bundling (Siblings + Session)
Intent: Complete understanding

Returns:
- Primary: Chunking decision
- Context: Implementation + constraints + origin conversation
- Why: Full genealogy from decision → code → rationale

### Strategy 3: Bridge Bundling (Centrality)
Intent: Discover connecting concepts

Returns:
- Primary: Concepts linking chunking ↔ indexing
- Context: Nodes with high betweenness centrality
- Why: Bridge nodes connect disparate topics

### Strategy 4: Timeline Bundling (Temporal)
Intent: Track evolution

Returns:
- Primary: Original decision
- Context: Later refinements + semantic descendants
- Why: Decision genealogy over time

## The Power Difference

Knowledge Graph bundling:
- Fixed: Same edge schema for all queries
- Predefined: Edge types determined at index time
- One strategy: Structure doesn't adapt

AURA bundling:
- Flexible: Different graph per query intent
- Discovered: Relationships materialized at query time
- Infinite strategies: Algorithm selection adapts to need

## Why This Matters

Same institutional knowledge, different access patterns:
- Newcomer: "Show me authoritative patterns" → PageRank
- Developer: "Explain this decision completely" → Siblings + session
- Architect: "Find connecting concepts" → Centrality
- Historian: "How did this evolve?" → Temporal

One knowledge base, infinite views.

## The Architectural Innovation

Not "RAG with bundled context" but "query-intent-driven context assembly via runtime graph construction."

Context is computed, not stored.
Bundling strategy is chosen, not fixed.
