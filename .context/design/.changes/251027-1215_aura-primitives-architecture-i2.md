---
session_id: "ca22384b-3a6d-4821-8b70-2aa1a89ea4ba"
timestamp: "2025-10-27T12:15:00-0700"
---

# Architectural Decisions: AURA Primitives & Soft-Graph

Decisions from conversation 251027-1215 refining IMEM architecture from object model to primitive-based composition.

---

## JSON Batch as CLI Argument
**Quote:** "cant we just imem batch 'YOU, CLAUDE CODE — YOU WRITE THE BATCH JSON IN HERE'"
**Why:** Single command simplicity—AI constructs data inline, no temp files or protocol overhead

<!-- Optional: Expand if decision was complex
**Context:** [2-3 sentences if needed]
**Options Considered:** [Brief list if relevant]
**Questions Resolved:** [If uncertainty existed]
-->

---

## Object Model Rejected for Primitives
**Quote:** "What do you think about our operationalization/parameterization?" (while reviewing 01_feedback.md showing 13+ sibling query pain points)
**Why:** Validated primitives (13+ real uses) beat speculative abstractions (200 lines saved, observable compositions)

**Context:** Real usage showed siblings operation needed 13+ times in single session. Object model approach (decision.constraints as lazy-loaded properties) was design speculation with no validated use case. Primitives enable observable composition and slash command capture.

**Options Considered:**
- A: Object model with lazy properties (KnowledgeGraph class, Item base class) - 200 lines, speculative
- B: CLI primitives with explicit composition (imem siblings, imem filter) - 150 lines, validated

---

## Template-as-Schema is THE Moat
**Quote:** "The template as schema is a fundament of this approach"
**Why:** Creation-time enforcement vs post-hoc extraction = uncopyable differentiator enabling deterministic queries

**Context:** MindsDB, Azure AI Search, e6data GraphRAG all use post-hoc extraction (probabilistic metadata). AURA enforces schema at creation time via markdown templates. Guarantees metadata presence enables deterministic filtering (not probabilistic). Entire architecture—metadata guarantees, soft-graph relationships, filtering precision—depends on template compliance.

**Risk:** Templates violated → metadata unreliable → system degrades to post-hoc extraction like competitors

---

## Soft-Graph = Two Distinct Types
**Quote:** "Do we have the same functionality? traversing graph node temporality links?"
**Why:** Relationship discovery (metadata queries) and runtime ranking (algorithms) serve different purposes—both enabled by same metadata foundation

**Context:** Clarifies two different uses of "graph" in AURA. Type 1: Soft-graph navigation via metadata (siblings, genealogy, temporal). Type 2: Runtime ranking via NetworkX algorithms (PageRank, centrality). Same underlying concept (metadata = relationships), different purposes.

**Options Considered:**
- A: Build object model for navigation only (original plan)
- B: Separate primitives for both types (clearer, more composable)

---

## Modes Rejected for Compositions
**Quote:** [Reviewing AI feedback showing EXPLAIN needed 13+ times, composed from 5 primitives each]
**Why:** Observable compositions beat hardcoded wrappers—patterns emerge from usage, captured as slash commands

**Context:** Hardcoded EXPLAIN/TRACE/PATTERNS modes were speculative. Real usage showed Claude composing primitives (search + siblings + filter) into context bundles. Observable compositions can be captured as markdown slash commands.

**Questions Resolved:** How to enable complex retrieval patterns without hardcoding? Answer: Let patterns emerge, capture proven ones as slash commands.

---

## Timeline Acceleration: 3.5 Days Not 6-7
**Quote:** Agreement on primitive approach after roadmap review
**Why:** Validated primitives (450 lines) faster than speculative abstractions (350+ lines)—usage-driven vs design-driven

<!-- Expanded in Object Model decision above -->

---

## Flippable Chunk Architecture for Pattern Serving
**Quote:** "serve unfitted (pattern insight — intellectual capital) whenever superseded while also being able to retrieve full resolution chunk (impl chunk) upon command"
**Why:** Zero-loss degradation—supersession promotes abstraction without deleting implementation, metadata flip not re-indexing

**Context:** When implementation superseded (JWT → OAuth2), don't delete—serve pattern layer instead (Stateless Auth Pattern). Enables cross-project intellectual capital transfer without code contamination. Metadata flag controls serving mode, no re-indexing needed.

**Key Properties:**
- No deletion (implementation still indexed)
- No re-indexing (supersession = metadata flag)
- Runtime flip (serve pattern or implementation on demand)
- Cross-project learning (pattern layer isolation)

---

## Missing Metadata Filters Added
**Quote:** [Reviewing changelog metadata showing type/keywords/status fields]
**Why:** Already captured in frontmatter, not exposed as primitives—add for composition completeness

<!-- Straightforward addition, no expansion needed -->
