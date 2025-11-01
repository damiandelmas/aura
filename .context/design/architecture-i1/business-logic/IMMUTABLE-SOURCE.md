# Immutable Source

**Core Insight: Source is archaeological record. Intelligence is learned separately.**

---

## What This Means

Source material:
- Written once, never modified
- Preserves exact historical state
- Terms used naturally at time of writing
- Archaeological integrity maintained

Intelligence layer:
- Lives separately from source
- Accumulates from usage patterns
- Updated continuously
- Evolves independently

---

## Why

**Preservation:** Truth about what was thought/decided at that moment

**Evolution:** Terminology/understanding changes without losing history

**Separation:** What was written ≠ what was learned from usage

**Composition:** Assemble contextualized views at query time, don't store them

---

## Core Principles

**Never rewrite history** - Source stays as written, intelligence evolves separately

**Query-time composition** - Context assembled from source + learned intelligence

**Separate persistence** - Immutable store ≠ learned metadata store

**Archaeological integrity** - Future agents see exact historical state

---

## Anti-Patterns

When someone suggests updating old documents for consistency, ask:

**Are we losing historical truth?**
- If terminology changed, map it (don't rewrite)
- If understanding evolved, track it (don't revise)
- If context matters, compose it (don't embed)

**Example:**
- ❌ Update changelog from 2023 to use 2025 terminology
- ✅ Map "jwt" (2023) → "auth.jwt" (canonical) at query time

---

## Implications

Systems must support:
- Immutable primary storage
- Separate learned metadata layer
- Query-time composition and enrichment
- Resolution maps for term evolution

Future sessions will:
- Query source as written
- Receive contextualized view (source + learned intelligence)
- Never see rewritten history

They won't:
- Find content modified for consistency
- Lose historical context to normalization

Preserve truth, compose context.
