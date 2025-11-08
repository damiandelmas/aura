---
session_id: "034ba596-240e-4bc3-b71a-2194dafd9656"
---

# CORE: Universal Dimensional Foundation

**The coordinate system that makes FlexSchema universal.**

FlexSchema methodology: Observation → Clustering → Emerged types. CORE provides the 6D space in which clustering happens, enabling cross-domain pattern transfer and instant semantic richness.

---

## The Six Dimensions

**1. Interrogative:** WHO | WHAT | WHERE | WHEN | WHY | HOW
What fundamental questions does this chunk answer?

**2. Valence:** GOOD | BAD | NEUTRAL
What's the outcome orientation?

**3. Abstraction:** CONCRETE | ABSTRACT | META
What's the level of generality?

**4. Epistemic:** KNOWN | HYPOTHETICAL | UNKNOWN
What's the certainty state?

**5. Temporal:** PAST | PRESENT | FUTURE
What's the time position?

**6. Structural:** ATOMIC | COMPOSITE | RELATIONAL
What's the compositional nature?

---

## Architecture

### Index Time
```
Chunk → CORE classifier → 6D coordinates
Store: chunk + vector + metadata + CORE coords
```

### Serve Time
```
Query → Retrieve chunks with CORE coords
CORE coords + Domain template → Resolve to domain type
CORE coords + Project context → Qualification
```

### Domain Resolution
Domain templates define type signatures as CORE coordinate patterns.

**Software domain:**
- Decision: what=0.8, why=0.7, valence=good, epistemic=known
- Pattern: why=0.9, how=0.85, abstraction=abstract, structural=relational
- Failure: what=0.75, why=0.8, valence=bad, temporal=past

**Legal domain:**
- Statute: what=0.9, valence=neutral, abstraction=abstract, epistemic=known
- Precedent: what=0.85, why=0.75, who=0.7, temporal=past
- Argument: why=0.95, epistemic=hypothetical, structural=relational

Same CORE dimensions, different type mappings per domain.

---

## Benefits

### Bootstrap Without Corpus
First document gets full semantic typing through CORE coordinates. No waiting for 1000 documents to cluster.

### Cross-Domain Transfer
Pattern discovered in software (what+why+bad+past = "Failure") transfers to legal (what+why+bad+past = "Breach") through shared coordinates.

### Confidence-Aware Resolution
Epistemic dimension tracks certainty. When confidence low, system widens type (Decision | Pattern) rather than incorrectly narrowing.

### AI-Augmented Construction
**Traditional KG:** 50 LLM calls per doc, extracting entities/relationships from raw text.

**CORE-enabled:** 1 call per doc for CORE. Then AI agent queries typed chunks: "Find all Precedents" returns 50 chunks pre-typed. Agent extracts entities from structured set (5 calls total).

Result: Structured input makes extraction 50x cheaper and more accurate.

---

## Implementation Approaches

### Option 1: Lightweight LLM
Use Claude/GPT-4 to classify chunks. Output JSON with 6D scores.

### Option 2: Small Trained Model
Train ~10M parameter model on labeled chunks. <1ms inference, no API cost.

### Option 3: Hybrid
LLM for bootstrap/validation, small model for production inference.

---

## Relationship to Current System

**Current:** Template structure (H2/H3 parsing) → section_type metadata → emergent schema through usage

**CORE:** Universal coordinates → explicit typing → designed schema transferable across domains

**Not replacement.** CORE adds explicit semantic layer to template structure.

**Template:** Enforces creation-time structure (H2 = type, H3 = instance)
**CORE:** Adds universal semantic coordinates (interrogative, valence, etc.)

Together: Structural and semantic richness.

---

## Implementation Status

**Current:** Template system provides implicit CORE structure through H2/H3 parsing. Types emerge through template compliance.

**CORE classifier:** Would make the coordinate system explicit, enabling:
- Bootstrap without corpus (first doc fully typed)
- Cross-domain transfer (shared coordinate foundation)
- Confidence-aware resolution (epistemic dimension)
- AI-augmented construction (structured input for agents)

**Relationship:** Template system = implicit CORE. CORE classifier = explicit CORE. Both implement FlexSchema principles.

---

## References

- [Hindley-Milner Conversation](../tiny-models/Claude-Hindley-Milner type system explained.md) — Intellectual foundation
- [00_NAMESPACE.md](../00_NAMESPACE.md) — Term definitions
- [00_architecture-vision.md](../vision/00_architecture-vision.md) — System overview
- [parameter-space/20_parameter-space-taxonomy.md](../parameter-space/20_parameter-space-taxonomy.md) — Current implementation
