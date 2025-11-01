# Entity Resolution: Living Vocabulary

**Feature Status:** Designed, not implemented

---

## The Problem

Keywords drift over time ("jwt", "JWT", "jwt-tokens", "auth.jwt"). Searches miss variations. Manual curation is unsustainable.

---

## The Concept

Instead of rewriting history, maintain a living map that resolves variations to canonical forms at query time.

**Architecture:**
```
Immutable Layer: Changelogs stay as written ("jwt", "JWT", whatever)
Resolution Layer: Map variants → canonical (all variations → "auth.jwt")
Query Layer: Expand search ("auth.jwt" → search for ALL variants)
```

**The Value:**
- Changelogs are archaeological artifacts (never modified)
- Searches find everything despite inconsistent naming
- Entity map evolves independently from content

---

## Pipeline (Conceptual)

### Stage 1: Structured Extraction

Parse frontmatter from all changelogs → collect types, keywords, timestamps
Output: Raw entity lists from structured fields

### Stage 2: Content Extraction

AI reads changelog content → extracts technical terms, frameworks, file patterns
Seeded by: Stage 1 entities (knows what to look for)
Output: Enriched entity lists from unstructured content

### Stage 3: Canonicalization

AI clusters variations → creates canonical mappings

Examples:
- "jwt" + "JWT" + "jwt-tokens" → canonical: "auth.jwt"
- "implementation.auth" + "feature.auth-system" → canonical: "type.implementation-auth"

Output: Entity resolution map

### Query-Time: Expansion

User searches "implementation.auth" → expands to all variations → returns complete results

---

## Key Principles

**Write naturally (freeform):** Authors use natural language, don't enforce terminology

**AI discovers patterns (periodic):** Weekly LLM batch job clusters terms

**Query gets everything (automatic):** Resolution happens transparently at query time

**No validation, no enforcement, just emergence.**

---

## Implementation Approach

**Entity Map Storage:**
```json
{
  "canonical_entities": {
    "auth.jwt": ["jwt", "JWT", "jwt-tokens", "JWT authentication"],
    "caching.redis": ["redis", "Redis", "redis-cache"],
    "architecture.variant-system": ["variant-system", "variant system", "prompt variants"]
  }
}
```

**Query Expansion:**
```python
def search(query):
    canonical = entity_map.resolve(query)  # "jwt" → "auth.jwt"
    variants = entity_map.get_variants(canonical)  # All historical spellings
    results = qdrant.search(query=canonical, expand=variants)
```

**Update Frequency:** Weekly LLM batch (~$0.01 per run)

---

## Related Concepts

See: [VISION.md](./VISION.md) - Principle #1: Living Vocabulary
See: [adaptive-updates.md](./adaptive-updates.md) - Weekly LLM processing
