---
session_id: e025fbb0-1abb-46e8-82a1-79c49afcc32d
date: 2025-10-27
type: vision.innovation
resolution: geometric
keywords: "schema-enforcement deterministic-metadata competitive-moat"
---

# Creation-Time Schema Enforcement

## The Insight

**Schema before content, not after.**

Traditional RAG: Content → Hope → Extract metadata (probabilistic)
AURA: Template → Enforce → Guaranteed metadata (deterministic)

The moat isn't better extraction. It's mandatory structure.

## The Geometry

```
Traditional post-hoc extraction:

Unstructured doc → Chunk → LLM extraction → Maybe metadata
                                                     ↓
                                              Probabilistic
                                              Missing fields
                                              Inconsistent structure

AURA creation-time enforcement:

Template (schema) → Enforce → Document → Chunk → Guaranteed metadata
        ↓                         ↓                      ↓
    Required fields          Complete       Deterministic queries
    Reject violations        Context        Deterministic filtering
```

## The System Property

**Metadata guarantees enable deterministic queries on vectors:**

```
Query impossible in traditional RAG:
"Find all decisions with alternatives considered and rationale"

Traditional result: Maybe 40%, probabilistic extraction fails

AURA result: 100%, template guarantees these fields exist
```

**Deterministic filter chain:**
```
imem search "authentication" \
  --decisions \              # Section type guaranteed
  --has-alternatives \       # Field guaranteed present
  --has-rationale \         # Field guaranteed present
  --phase develop           # Phase guaranteed

Result: Every result has Context, Solution, Rationale, Alternatives
No maybe. No probability. Guaranteed.
```

## The Behavior

**Three enforcement levels:**

1. **Template defines schema**
   - Markdown template specifies required fields
   - Human-readable, git-versioned
   - Self-documenting structure

2. **Validation at creation**
   - Check field presence before indexing
   - Reject incomplete documents
   - Fail fast with clear error

3. **Guaranteed queries**
   - Filter by field presence (has_context: true)
   - Always returns complete chunks
   - No "field might exist" uncertainty

## Why This Matters

**Competitive moat = creation-time enforcement.**

MindsDB, Azure AI Search, e6data:
- All do post-hoc extraction
- LLMs guess at structure
- Probabilistic, lossy, unreliable

AURA:
- Templates enforce structure upfront
- Humans provide context at creation
- Deterministic, complete, reliable

**This is the differentiator.**

Without template enforcement:
- System degrades to post-hoc extraction
- Loses all metadata guarantees
- Becomes traditional RAG (commodity)

With template enforcement:
- Unique architecture
- Deterministic filtering precision on vectors
- Institutional memory with guarantees

## The Moat

**"Template-as-schema" is not a feature. It's the foundation.**

Everything builds on guaranteed metadata:
- Soft-graph relationships (metadata queries)
- Supersession detection (field presence)
- Authority scoring (complete context)
- Cross-project patterns (consistent structure)

Break template enforcement → entire architecture collapses.

**Priority: Non-negotiable before scaling.**
