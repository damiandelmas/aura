# Soft-Graph: Runtime Relationship Discovery

**Session:** a86bc733-c4e3-4d88-b17f-2f9e330ca11a
**Level:** Vision (L1)
**Date:** 2025-10-27

## The Geometric Insight

Traditional knowledge graphs: Build edges upfront, traverse at query time
Soft-graphs: Build edges at query time, discard after use

Complexity shift:
- Traditional: O(n²) precomputation, O(1) traversal
- Soft-graph: O(0) precomputation, O(k²) construction (k << n)

## The Pattern

Metadata as latent edges. Queries materialize relationships on-demand.

Edge types emerge from metadata predicates:
- file_path == X → FILE edge (structural)
- session_id == Y → SESSION edge (genealogical)
- timestamp > Z + semantic > 0.7 → TEMPORAL edge (evolutionary)

No storage. No maintenance. Infinite flexibility.

## The Paradigm Shift

Knowledge graphs: Static structure → dynamic queries
Soft-graphs: Dynamic structure ← query intent

Graph adapts to query, not vice versa.

## Why This Matters

Knowledge graph maintenance:
- Rebuild on document change: O(n²)
- Storage overhead: GB for large corpus
- Edge schema changes: Expensive migration

Soft-graph advantages:
- Zero maintenance (no precomputed structure)
- Zero storage (ephemeral graphs)
- Infinite edge types (metadata predicates)
- Query-adaptive (different graph per query)

## The Core Trade-off

Traditional: Slow writes, fast reads
Soft-graph: Fast writes, computed reads

Perfect for git-native institutional memory where documents evolve constantly.

## Architectural Innovation

Not "RAG with knowledge graphs" but "knowledge graphs as query-time views over metadata-enriched chunks."

Relationships discovered, not stored.
