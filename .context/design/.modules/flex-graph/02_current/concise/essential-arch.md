● ● AURA: Essential Architecture

  Foundation: Creation-Time Schema
  - Template enforced at document creation (AI-generated, guaranteed compliance)
  - Required fields: Context, Solution
  - Optional fields: tracked as queryable booleans
  - Result: Deterministic metadata (100% vs ~70% post-hoc extraction)

  Core: Soft-Graph Discovery
  - Edges = metadata queries (not stored structures)
    Chunk-level:
    - file_path → siblings (sections within same file)
    - session_id → genealogy (conversation origin)
    - timestamp + semantic → temporal (evolution)
    Document-level:
    - filename chronology + semantic → sequential work (project narrative)
    - topic keywords + phase → thematic continuity (design → develop → document)
  - O(k²) runtime construction, not O(n²) precomputation
  - Zero maintenance (graphs ephemeral, rebuilt per query)

  Intelligence: Query-Adaptive Bundling
  - Same chunks, different strategies per intent:
    - Authority → PageRank ranking
    - Bridges → Centrality ranking
    - Timeline → Temporal chain
  - Template structure enables field extraction at serve-time
  - Relationship labels from metadata ("CONSTRAINTS (Same File)")

  Infrastructure: Batch Primitive
  - Parallel execution of any CLI operations
  - 3 ops @ 100ms = 110ms (not 300ms)
  - Claude Code orchestrates compositions

  Transfer: Pattern Layer
  - .md → Haiku pass → .pattern.md (remove implementation, keep concept)
  - One-time at creation (~200ms, ~$0.0001)
  - Cross-project knowledge without implementation lock-in

  ---
  The Inversion:
  Traditional KG: Build graph → query structure
  AURA: Query → build ephemeral graph → discard

  Why It Works:
  - Guaranteed metadata (creation enforcement)
  - k << n (query 20, not 10,000)
  - Metadata = latent edges

  MVP: ~1250 lines, 1 week