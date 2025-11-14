---
session_id: "090c7e16-cb85-45e5-a1f0-8dd53f191a40"
---

# Document Properties: Frontmatter Metadata

**Document-wide context inherited by all chunks.**

---

## Overview

Frontmatter provides semantic context applied to entire changelog. Every chunk inherits these properties alongside template metadata.

**Dual metadata:**
- Template → Type system (Decision, Pattern, Failure)
- Frontmatter → Semantic context (category, genealogy, temporal)

---

## Frontmatter Schema

```yaml
schema_version: "v3_adaptive"
type: "category.specific-description"
status: "completed"
keywords: "space-separated terms"
timestamp: "YYYY-MM-DDTHH:MM:SS-0700"
session_id: "uuid-of-conversation"
```

---

## Type Field: Freeform Categories

**AI writes natural descriptions:**
```yaml
type: "refactor.cli-cleanup-and-bugfix"
type: "implementation.security-guardrails"
type: "bug-fix.timeout-handling"
```

**Resolved at document creation (per-document, not batch):**
```
Input: "refactor.cli-cleanup-and-bugfix"
    ↓
Entity resolution (lightweight LLM)
    ↓
Output:
  category: "refactor"
  subtype: "cli-cleanup-and-bugfix"
  original_type: "refactor.cli-cleanup-and-bugfix"  // Preserved
```

**Source immutable, metadata resolved once at write-time.**

---

## Session ID: Genealogy

Bidirectional link to originating conversation:
```yaml
session_id: "b4078811-c691-4ec7-97f5-e0faaf5b7607"
```

Enables: Changelog ↔ Conversation traversal.

---

## Timestamp: Temporal Context

```yaml
timestamp: "2025-10-30T00:00:00-0700"
```

Enables: Before/after queries, evolution detection, recency scoring, timelines.

---

## Keywords: Discovery Tags

```yaml
keywords: "cli refactor cleanup bug-fix registry"
```

Space-separated, natural language. Not normalized (variation aids discovery).

---

## Status: Lifecycle State

```yaml
status: "completed"  # or "in-progress", "archived", "reverted"
```

Currently: Mostly "completed" (limited utility).

Future: MIND could override at runtime (detect supersession → "superseded").

---

## Chunk Inheritance

**Every chunk receives both metadata layers:**

```typescript
{
  // Template metadata (per-chunk)
  section_type: "Decision",
  section_name: "Use JWT",

  // Document properties (inherited)
  category: "implementation",
  subtype: "security-guardrails",
  session_id: "b4078811...",
  timestamp: "2025-10-30T00:00:00-0700",
  keywords: ["security", "authentication"],
  status: "completed",

  embedding: [...]
}
```

---

## The Value

Template provides structural types. Frontmatter provides semantic context.

Together: Type-safe semantic search with genealogy and temporal ordering.

---

## Related Concepts

See: [type-system.md](./type-system.md) - Template metadata
See: [entity-resolution.md](./entity-resolution.md) - Term normalization
See: [phase-lifecycle.md](./phase-lifecycle.md) - Genealogy links
