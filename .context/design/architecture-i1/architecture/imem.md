# IMEM Architecture Overview

**Memory system for AI coding agents**

---

## Domain

IMEM stores software development memory as structured changelogs.

**Content types:**
- Design decisions (what we chose, why)
- Implementation details (what we built, how)
- Constraints (limitations, trade-offs)
- Failures (what didn't work, lessons)
- Patterns (reusable learnings)

**Created by:** AI agents during development
**Used by:** AI agents for context retrieval

---

## Four-Phase Lifecycle

```
design → designate → develop → document
```

Phases linked by genealogy (session_id), enabling full reasoning chain from idea to implementation.

See: [phase-lifecycle.md](./phase-lifecycle.md)

---

## Architecture Components

**Foundation:**
- [template-as-schema.md](./template-as-schema.md) - Creation-time enforcement (the moat)
- [phase-lifecycle.md](./phase-lifecycle.md) - Four-stage memory evolution

**Infrastructure:**
- [brain-persistence.md](./brain-persistence.md) - Learned metadata substrate
- [knowledge-graph.md](./knowledge-graph.md) - Persistent relationship edges
- [entity-resolution.md](./entity-resolution.md) - Living vocabulary
- [adaptive-updates.md](./adaptive-updates.md) - Multi-speed maintenance

**Intelligence:**
- [intelligence-layers.md](./intelligence-layers.md) - Structural awareness for AI comprehension
- [graph-templates.md](./graph-templates.md) - Topology-driven presentation
- [schema-introspection.md](./schema-introspection.md) - Self-describing capabilities

**Composition:**
- [batch-composition.md](./batch-composition.md) - Parallel primitive orchestration
- [flippable-chunks.md](./flippable-chunks.md) - Dual-layer architecture

---

## Core Principles

**Template-as-Schema:**
Guaranteed metadata from creation-time enforcement (not probabilistic extraction).

**Immutable Source + Learned Intelligence:**
Source preserved as written, intelligence accumulated from usage.

**Compositional Primitives:**
Orthogonal building blocks (siblings, genealogy, temporal) compose freely.

**Usage-Driven:**
System learns from observed patterns, not predictions.

---

## Related Documents

**Methodology:**
- [../methodology/flexgraph.md](../methodology/flexgraph.md) - General methodology
- [../methodology/vision-integration.md](../methodology/vision-integration.md) - How principles compose

**Vision:**
- [../vision/imem.md](../vision/imem.md) - Core principles (6 pillars)

**Business Logic:**
- [../business-logic/AI-FIRST-USER.md](../business-logic/AI-FIRST-USER.md)
- [../business-logic/COMPOSITIONAL-PRIMITIVES.md](../business-logic/COMPOSITIONAL-PRIMITIVES.md)
- [../business-logic/IMMUTABLE-SOURCE.md](../business-logic/IMMUTABLE-SOURCE.md)
- [../business-logic/USAGE-DRIVEN.md](../business-logic/USAGE-DRIVEN.md)

---

**IMEM = Structured changelog memory with guaranteed metadata, persistent relationships, and compositional retrieval.**
