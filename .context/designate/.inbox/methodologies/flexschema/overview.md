---
session_id: "034ba596-240e-4bc3-b71a-2194dafd9656"
---

# FlexSchema Methodology

**Universal schema library enabling cross-domain type resolution.**

---

## Hypothesis

Pre-defined domain schemas with universal CORE coordinates enable bootstrap and cross-domain pattern transfer.

---

## Components

### 1. Schema Library
Registry of domain-specific schemas (software, legal, business, research).

Each domain defines types with CORE coordinate signatures:
```yaml
# software_development
Decision: {what: 0.8, why: 0.7, valence: good, epistemic: known}
Pattern: {why: 0.9, how: 0.85, abstraction: abstract}
Failure: {what: 0.75, why: 0.8, valence: bad, temporal: past}

# legal
Statute: {what: 0.9, valence: neutral, abstraction: abstract}
Precedent: {what: 0.85, why: 0.75, who: 0.7, temporal: past}
Argument: {why: 0.95, epistemic: hypothetical}
```

### 2. CORE Dimensions
Six universal coordinates classify all knowledge:
- Interrogative, Valence, Abstraction, Epistemic, Temporal, Structural

See: [core-dimensions.md](./core-dimensions.md)

### 3. Resolution Engine
Runtime cross-domain type matching via CORE signatures.

---

## Architecture

### Index Time
```
AI Agent picks schema from library (e.g., software_development)
  ↓
Writes using template
  ↓
Chunks stored with section_type + metadata
```

### Serve Time
```
Query from different domain (e.g., legal project)
  ↓
MIND resolution engine:
  - Reads chunk's section_type="Decision"
  - Looks up software.Decision CORE signature
  - Matches against legal schema templates
  - Finds analog: legal.Precedent
  ↓
Serves: Cross-domain interpretation
```

---

## Implementations

**Current: Template-As-Schema**
- H2/H3 markdown structure
- Implicit CORE (structure implies coordinates)
- Works today

**Future: CORE Classifier**
- Explicit 6D coordinate scoring
- Makes universal foundation visible
- Enables stronger cross-domain transfer

Both produce typed chunks. Both enable FlexSchema resolution.

---

## Benefits

**Bootstrap Without Corpus**
Pick schema, start immediately. No waiting for emergence.

**Cross-Domain Transfer**
Software patterns translate to legal via shared CORE signatures.

**Flexible Resolution**
Same chunk = different type depending on query context.

**Extensible**
Add new domains to library without changing architecture.

---

## Relationship to Other Methodologies

**FlexSchema enables → Typed Vector Store**
Creates rich metadata foundation (section_type + CORE coords)

**Typed Vector Store exploited by → FlexGraph**
Graph construction from typed, metadata-rich chunks

---

## References

- [CORE Dimensions](./core-dimensions.md) — Universal coordinate system
- [FlexGraph](../flexgraph/overview.md) — Graph methodology exploiting typed foundation
- [Hindley-Milner Conversation](../../tiny-models/Claude-Hindley-Milner type system explained.md) — Intellectual origins
