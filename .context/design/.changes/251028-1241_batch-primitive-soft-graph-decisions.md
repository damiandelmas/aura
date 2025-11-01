---
session_id: ""
timestamp: "2025-10-28T12:41:00-0700"
---

# Architectural Decisions: Batch Primitive & Soft-Graph Refinements

Decisions from conversation 251028-1241 refining batch primitive architecture and soft-graph documentation organization.

---

## Batch Primitive = Parallelization Infrastructure
**Quote:** "batch primitive allows you to call any primitive VIA json in parallel with a single bash call"
**Why:** Single bash invocation for parallel operations—3x speed for Claude Code, structured JSON output

**Context:** NOT a multi-query wrapper with graph operations. IS a generic parallelization primitive for ANY CLI operations. Enables Claude Code to execute multiple imem operations (search, siblings, filter, graph) in parallel via single bash call instead of sequential invocations.

**Performance:**
- Sequential: t1 + t2 + t3 (3 separate bash calls)
- Parallel: max(t1, t2, t3) + overhead (1 bash call, internal parallelization)

---

## Template Structure as Inference Layer
**Quote:** [Discussion of template metadata as implicit graph structure]
**Why:** Templates encode relationships at creation time—metadata becomes queryable graph without explicit linking

**Context:** Template compliance enforces structured metadata (type, keywords, status, genealogy, siblings). This metadata IS the soft-graph. Enables deterministic filtering and relationship discovery without post-hoc extraction.

**Key Properties:**
- Creation-time enforcement vs post-hoc extraction
- Deterministic queries (template compliance guarantees)
- Metadata = relationships (siblings, genealogy, temporal)

---

## Runtime Chunk Contextualization via Lightweight LLM
**Quote:** [Discussion of runtime chunk polishing]
**Why:** Zero-cost enhancement—add context at serve time without re-indexing, preserves chunk precision

**Context:** When serving chunks, lightweight LLM can add contextual wrapper (file path, related items, genealogy) without modifying indexed content. Improves retrieval usefulness while maintaining index integrity.

**Options Considered:**
- A: Re-index with context (expensive, degrades precision)
- B: Runtime contextualization (zero-cost, preserves precision)

---

## Documentation Consolidation Over Proliferation
**Quote:** "Honest Take: You're Over-Organizing"
**Why:** Observable usage patterns beat speculative organization—consolidate duplicates, defer structure decisions

**Context:** Found 12+ potentially duplicate documents in soft-graph resources. Instead of creating elaborate filing systems, consolidate proven documents and defer organization decisions until usage patterns emerge.

**Approach:**
- Consolidate duplicates into concise versions
- Keep proven documents (essential-arch.md, soft-graph.md, README.md)
- Defer elaborate organization until patterns validate structure

---

## Template-Driven Graph Assembly
**Quote:** [Discussion of metadata queries building graphs]
**Why:** Query results = graph nodes—metadata relationships enable NetworkX algorithm application without explicit graph construction

**Context:** Don't build object model for graph navigation. Instead: metadata queries discover relationships (siblings, genealogy), results become graph nodes, apply NetworkX algorithms (PageRank, centrality) at runtime.

**Key Insight:** Soft-graph is methodology (metadata = relationships), not implementation (object model with lazy properties). Query primitives + NetworkX = complete graph capabilities.

---

## Soft-Graph as Methodology Not Implementation
**Quote:** "Soft-Graph as Methodology vs Implementation"
**Why:** Approach (metadata relationships) vs code structure (CLI primitives)—methodology guides design without dictating implementation

**Context:** Soft-graph describes HOW AURA thinks about relationships (template metadata, temporal links, genealogy). NOT a class hierarchy or object model. Primitives (search, siblings, filter) + slash commands = soft-graph implementation.

---

## Sequential Edge for Document-Level Continuity
**Quote:** "Yes—Document-Level Sequential Edge"
**Why:** Temporal ordering preserves thought evolution—within-document flow complements cross-document siblings/genealogy

**Context:** Chunks within same document have implicit temporal sequence (section 1 → section 2 → section 3). Enables "next thought" navigation alongside relationship-based discovery. Metadata already captures this via position field.

---
