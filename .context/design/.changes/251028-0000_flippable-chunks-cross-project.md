---
session_id: "e025fbb0-1abb-46e8-82a1-79c49afcc32d"
timestamp: "2025-10-28T00:00:00-0700"
---

# Architectural Decisions: Flippable Chunks & Cross-Project Patterns

Decisions from conversation 251028 clarifying pattern-layer supersession mechanism and cross-project intellectual capital transfer.

---

## Flippable Chunk Architecture for Zero-Loss Degradation
**Quote:** "we would have a board of chunks that can be flipped from impl to pattern at runtime (their supersession stored via simple mapping rather than deleting, removing etc or even re-indexing)"
**Why:** No deletion, no re-indexing—supersession sets metadata flag, serving logic chooses which chunk to return (implementation or pattern abstraction)

**Context:** When implementation superseded (JWT → OAuth2), don't delete original—serve pattern layer instead (Stateless Auth Pattern). Enables intellectual capital preservation without code contamination. Metadata flag controls serving mode at query time, no re-indexing needed.

**Key Properties:**
- No deletion (implementation preserved at full resolution)
- No re-indexing (supersession = metadata: `superseded_by`, `serving_mode`)
- Runtime flip (serve pattern or force implementation on demand)
- O(1) chunk retrieval switch (not O(n) content transformation)
- Instant rollback (metadata revert, no data migration)

**Storage:**
```
Both chunks indexed separately:
├─ chunk_abc: 251011-1200_auth.md (implementation)
│   metadata: {superseded_by: chunk_xyz, has_pattern: True}
└─ chunk_abc_pattern: 251011-1200_auth.pattern.md (abstraction)
    metadata: {source_impl: chunk_abc, layer: pattern}

Serving logic:
if chunk.superseded and chunk.has_pattern:
    return pattern_chunk
else:
    return implementation_chunk
```

---

## Cross-Project Intellectual Capital Transfer
**Quote:** "retrieve how we solved problem A from typescript codebase while working on Problem Aa in python codebase without being worried about it 'fitting' to typescript or even worse, a similar python codebase"
**Why:** Pattern layer strips code/frameworks/languages—query patterns across all projects returns pure intellectual capital applicable to any stack

**Context:** Traditional cross-project RAG fails by returning wrong-architecture matches (similar Python project with Django when you need FastAPI) or code-specific solutions (TypeScript JWT library when you need Python approach). Pattern layer queries return language-agnostic principles validated across multiple projects.

**Anti-Contamination Guarantee:**
- Query patterns: Language-agnostic only (no code, no frameworks, no stack)
- Query implementations: Project-specific only (isolated by default)
- Never mix unless explicit override (`--full-resolution` flag)

**Example:**
```bash
# Working in Python FastAPI project
imem search "authentication" --pattern --all-projects

# Returns patterns from:
# - TypeScript project: Stateless Auth Pattern (no JWT lib references)
# - Rust project: Token-Based Auth Pattern (no code snippets)
# - Python project: Session-less Auth Pattern (no Django specifics)

# All applicable, zero contamination
```

**Options Considered:**
- A: Single-project only (safest, but loses cross-project learning)
- B: Implementation cross-project (contamination risk)
- C: Pattern-layer only cross-project (chosen—proven principles, no code leakage)

---

## Pattern Authority via Multi-Project Accumulation
**Quote:** "this enables cross project memory"
**Why:** Pattern appearing in 5 projects = proven approach—graph algorithms on pattern layer reveal intellectual capital accumulation

**Context:** PageRank on pattern-layer nodes across all projects identifies most validated solutions. Cross-project graph construction treats patterns as bridge nodes between project collections.

**Use case:** "What's the most proven approach to provider-agnostic design?" → Pattern validated in TypeScript/Python/Rust projects ranks highest

<!-- Optional: Expand if needed for Phase 11
**Implementation:** Multi-collection graph with pattern nodes, PageRank identifies authority
**Complexity:** High—deferred to Phase 11
-->

---

## Soft-Graph Dual Nature Clarified
**Quote:** "whats the diff between all these?" (relationship discovery vs runtime ranking)
**Why:** Type 1: Metadata queries mimic traversal (no graph exists). Type 2: NetworkX for ranking query results. Both O(k²) not O(n²), both query-time construction

**Context:** Two uses of "graph" in AURA serve different purposes. Type 1 (relationships): Siblings via file_path filter, genealogy via session_id filter—feels like traversal but is database query. Type 2 (ranking): Build NetworkX from query results, apply PageRank/centrality, discard graph.

**Complexity:**
- Traditional KG: O(n²) edges precomputed across all documents
- AURA: O(k²) edges constructed across query results only (k=20-30)
- Difference: 1,000,000 vs 400 operations

---

## Batch Composes Primitives (Peer Commands)
**Quote:** "imem batch, imem search, same level but batch composes search+?"
**Why:** All CLI commands are peers—batch internally calls primitives for parallelism efficiency, not architectural layering

<!-- Straightforward clarification, no expansion needed -->

---

## Missing Metadata Filters Added to Phase 6
**Quote:** [Reviewing changelog metadata showing type/keywords/status fields]
**Why:** Data already captured (type: "refactor.trace-cli", keywords: "api-design", status: "completed") but not exposed as filters—add for composition completeness

**Added primitives:**
```bash
imem filter --type-category <category>
imem filter --keyword <tag>
imem filter --status <state>
```

---

## Progressive Abstraction Workflow
**Quote:** "being able to serve unfitted (pattern insight—intellectual capital) whenever superseded while also being able to retrieve full resolution chunk (impl chunk) upon command"
**Why:** Write implementation first, extract pattern later, system prompts when concepts detected—no upfront overhead

**Context:** Abstraction emerges when value proven, not mandated at creation time. Force flag retrieves original implementation for debugging or historical reference.

---

## Documents 98% Aligned, 2% Polish Applied
**Changes:**
- discovery.md:141: "object model" → "JSON + CLI primitives"
- architecture.md:589: Added "Batch composes primitives internally" note
**Why:** Clarified soft-graph means primitives not classes, batch is peer command not layer

---

## The Board Metaphor
**Concept:** Each decision = double-sided chip (Side A: implementation, Side B: pattern), flipped at runtime based on supersession state
**Why:** Mental model aligns with technical architecture—metadata flip, not data transformation

---

## Positioning as Intellectual Capital Management
**Quote:** "enables no loss in degradation of memory"
**Why:** Not "better RAG" but "intellectual capital management system"—query "how did we solve X?" returns proven principles from any project in any language

**Success criteria:** "Find provider-agnostic patterns across all projects" → returns language-agnostic patterns validated across TypeScript/Python/Rust codebases, validates entire architecture (template enforcement, dual-layer indexing, cross-project queries, anti-contamination)

---

## Implementation Phasing
**Flippable chunks:** Phase 9 (simple—metadata check + conditional retrieval)
**Cross-project patterns:** Phase 11 (moderate—multi-collection query + merge)
**Pattern authority:** Phase 11+ (complex—graph construction across projects)
**Why:** Prioritize validated primitives first, defer cross-project graph until usage proven
