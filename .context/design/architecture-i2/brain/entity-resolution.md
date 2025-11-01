---
session_id: "090c7e16-cb85-45e5-a1f0-8dd53f191a40"
---

# Entity Resolution: Living Vocabulary

**Write naturally, search precisely.**

---

## The Concept

AI agents write freeform categories and terms. System resolves to canonical forms.

```
AI writes:
  type: "refactor.cli-cleanup-and-bugfix"
  keywords: "jwt JWT jwt-tokens auth"
    ↓
Resolved: Variations cluster to canonical
  category: "refactor"
  auth.jwt: ["jwt", "JWT", "jwt-tokens"]
    ↓
Query: "jwt" → searches ALL variations
```

**Source immutable. Resolution happens per-document or periodically.**

---

## Three-Layer Flow

```
Immutable Layer: AI writes natural language (no constraints)
    ↓
Resolution Layer: Cluster variations → canonical mapping
    ↓
Query Layer: Expand queries to all known variants
```

**Property:** Archaeological truth preserved, complete recall enabled.

---

## The Value

**Write-time:** AI agents use natural language, no enum constraints.

**Resolution:** Lightweight clustering per-document (type field) or periodic (keywords/terms).

**Query-time:** Queries expand to all variants transparently.

**Result:** Freeform authoring + exhaustive search.

---

## BRAIN Storage

Entity resolution map stored in BRAIN:
```
canonical_form → [variant1, variant2, variant3, ...]
```

Bidirectional lookup:
- Query variant → resolve to canonical
- Query canonical → expand to all variants

---

## Related Concepts

See: [runtime-graph-composition.md](./runtime-graph-composition.md) - BRAIN control plane
