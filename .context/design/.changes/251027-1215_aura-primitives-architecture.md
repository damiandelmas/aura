# Architectural Decisions: AURA Primitives & Soft-Graph

Decisions from conversation 251027-1215 refining IMEM architecture from object model to primitive-based composition.

---

## JSON Batch as CLI Argument
**Quote:** "cant we just imem batch 'YOU, CLAUDE CODE — YOU WRITE THE BATCH JSON IN HERE'"
**Why:** Single command simplicity—AI constructs data inline, no temp files or protocol overhead

---

## Object Model Rejected for Primitives
**Quote:** "What do you think about our operationalization/parameterization?" (while reviewing 01_feedback.md showing 13+ sibling query pain points)
**Why:** Validated primitives (13+ real uses) beat speculative abstractions (200 lines saved, observable compositions)

---

## Template-as-Schema is THE Moat
**Quote:** "The template as schema is a fundament of this approach"
**Why:** Creation-time enforcement vs post-hoc extraction = uncopyable differentiator enabling deterministic queries

---

## Soft-Graph = Two Distinct Types
**Quote:** "Do we have the same functionality? traversing graph node temporality links?"
**Why:** Relationship discovery (metadata queries) and runtime ranking (algorithms) serve different purposes—both enabled by same metadata foundation

---

## Modes Rejected for Compositions
**Quote:** [Reviewing AI feedback showing EXPLAIN needed 13+ times, composed from 5 primitives each]
**Why:** Observable compositions beat hardcoded wrappers—patterns emerge from usage, captured as slash commands

---

## Timeline Acceleration: 3.5 Days Not 6-7
**Quote:** Agreement on primitive approach after roadmap review
**Why:** Validated primitives (450 lines) faster than speculative abstractions (350+ lines)—usage-driven vs design-driven

---

## Flippable Chunk Architecture for Pattern Serving
**Quote:** "serve unfitted (pattern insight — intellectual capital) whenever superseded while also being able to retrieve full resolution chunk (impl chunk) upon command"
**Why:** Zero-loss degradation—supersession promotes abstraction without deleting implementation, metadata flip not re-indexing

---

## Missing Metadata Filters Added
**Quote:** [Reviewing changelog metadata showing type/keywords/status fields]
**Why:** Already captured in frontmatter, not exposed as primitives—add for composition completeness
