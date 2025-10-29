---
session_id: "66becaa8-1157-4119-bf8d-e701359011fd"
timestamp: "2025-10-28T12:34:00-0700"
---

# Architectural Decisions: Soft-Graph Documentation Consolidation

Decisions from conversation 251028-1234 consolidating 69 exploratory vision files into actionable architecture docs.

---

## Taxonomy Clarification: Methodology vs System vs Capabilities
**Quote:** "help me think of the actual taxonomy of what we're sorting — IE methodology (soft graph), 'implementation?' 'use case' 'architecture' 'project'? for IMEM"
**Why:** Soft-Graph = methodology (portable pattern), IMEM = system (implementation), Innovations = capabilities (what enables the system)—clear abstraction hierarchy prevents category confusion

---

## Three-Document Target Structure
**Quote:** "we want to delineate between the tiers of architecture we're building — soft graph, imem, etc"
**Why:** Consolidate 69 files into 3 purposeful docs: soft-graph-methodology.md (pattern), imem-architecture.md (how IMEM uses it), imem-roadmap.md (sequenced implementation)—actionable over exploratory

---

## Duplicate Merging: 18 Topics → 7 Capabilities
**Quote:** [Analysis showing: 2 batch variants, 3 template schema variants, 3 cross-project variants, etc.]
**Why:** Same insights explored multiple times across sessions—merge to canonical versions (batch, template-continuity, pattern-layer, runtime-graphs, flippable-chunks, soft-metadata, BRAIN)

---

## Archive to _resources/ Not Delete
**Quote:** "consolidate existing files in /resources/ into root of 03_additional"
**Why:** Preserve genealogy—all 69 exploration files moved to _resources/ subfolder for "how did we get here" context, while consolidated docs serve as working references

---

## Timestamped Files as Authoritative Sources
**Quote:** [Observing 251027-* files represent refined session outputs]
**Why:** 251027-1715 (batch), 251027-1716 (runtime-graphs), 251027-1717 (template-serve), 251027-1718 (BRAIN) = latest thinking—prioritize over earlier explorations when consolidating

---

## Roadmap as Sequencing Artifact
**Quote:** [Proposed structure showing Phase 6-8 (MVP), V2, Endstate tiers]
**Why:** imem-roadmap.md captures implementation sequence—what to build when, dependencies between capabilities, MVP vs endstate delineation

---

## Essential-Arch.md Preservation Decision Deferred
**Quote:** "lets ignore essential arch and soft graph.md for now"
**Why:** Existing 50-line summary may overlap with new consolidated docs—revisit after consolidation to determine keep vs fold vs supersede

---

## Document-Level Edge Discovery Recognition
**Quote:** [Analysis of soft-graph.md showing chunk-level AND document-level edges]
**Why:** Soft-graph operates at two granularities: chunk (siblings/genealogy/temporal) and document (filename chronology, phase continuity)—both valid, different purposes

---

## Capability Tiering: MVP → V2 → Endstate
**Quote:** [Grouping innovations into implementation phases]
**Why:** Runtime graphs + template enforcement = MVP tier, pattern layer + batch = V2 tier, BRAIN annotation = endstate—realistic sequencing based on dependencies and validation needs
