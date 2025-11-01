# Entity Resolution: Living Vocabulary

**Feature Status:** Designed, not implemented

---

## The Problem

Keywords drift over time ("jwt", "JWT", "jwt-tokens", "auth.jwt"). Searches miss variations. Manual curation is unsustainable.

---

## The Concept

Living map resolves term variations at query-time without rewriting history.

**Three-Layer Topology:**
```
Immutable Layer:  Source as written (natural language drift)
    ↓
Resolution Layer: Canonical mapping (variants → canonical)
    ↓
Query Layer:      Expansion (canonical → all variants)
```

**Property:** Source preserves archaeological truth, resolution enables complete recall.

---

## Pipeline Flow

**Stage 1: Structured Extraction**
```
Source metadata → Entity candidates
```
Output: Raw term lists from guaranteed fields

**Stage 2: Content Extraction**
```
Source content → Technical terms
```
Seeded by Stage 1, enriches with unstructured mentions

**Stage 3: Canonicalization**
```
Term variations → Clustering → Canonical map
```

Example clustering:
- Variations: "jwt", "JWT", "jwt-tokens", "JSON Web Token"
- Canonical: Single normalized form
- Bidirectional: Variant → canonical, canonical → all variants

**Query-Time: Expansion**
```
Query → Resolve to canonical → Expand to all variants → Search
```

---

## Key Principles

**Write naturally:** Authors use freeform language, no terminology enforcement

**Discover patterns:** Periodic batch clustering detects variations

**Expand queries:** Resolution happens transparently at query-time

**Emergence over validation:** No enforcement, just observable patterns

---

## Update Topology

```
Write time:
  Source uses natural language → No enforcement

Background (periodic):
  Cluster term variations → Update canonical map

Query time:
  Resolve term → Expand to variants → Search all
```

**Property:** Map evolves independently from immutable source.

---

## The Value

- **Source preserves natural language** (archaeological truth)
- **Resolution enables complete recall** (all variations found)
- **Map evolves separately** (no source modification)
- **Query-time transparency** (automatic expansion)