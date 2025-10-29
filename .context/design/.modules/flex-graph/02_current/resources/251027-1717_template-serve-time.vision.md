---
date: 2025-10-27
type: vision.innovation
status: current
keywords: "template-as-schema serve-time-structure relationship-labeling prompt-engineering"
---

# Vision: Template-as-Schema at Serve Time

## Core Insight

Templates traditionally: Define structure at write time (schema enforcement).

AURA innovation: Templates operate at THREE lifecycle stages:
1. **Write time:** Enforce structure (Context/Solution/Rationale fields)
2. **Query time:** Enable filtering (guaranteed metadata presence)
3. **Serve time:** Structure presentation (relationship-aware assembly)

**Third role unlocked: Prompt engineering at retrieval layer.**

---

## The Three Roles

### Role 1: Write-Time Enforcement (Traditional)

```markdown
## Decisions
### Use JWT Authentication
- **Context**: (problem statement)
- **Solution**: (what was chosen)
- **Rationale**: (why this approach)
- **Alternatives**: (what else was considered)
```

**Result:** Structured content with guaranteed fields.

### Role 2: Query-Time Filtering (Vector DB Enhancement)

```python
# Template guarantees these fields exist
results = search("auth", filters={
    'has_context': True,      # ← Guaranteed by template
    'has_alternatives': True  # ← Guaranteed by template
})
```

**Result:** Deterministic metadata queries.

### Role 3: Serve-Time Structuring (New Innovation)

```markdown
# DECISION: Use JWT Authentication

## Primary Decision (develop/.changes/251018-1200_auth.md)
**Context**: Sessions don't scale beyond single server
**Solution**: Stateless JWT tokens with claims
**Rationale**: Enables horizontal scaling without session store
**Alternatives**: OAuth (too complex), API keys (less secure)

---

## RELATED CONSTRAINTS (Same Changelog)
Found 2 constraints from same document:

### Token Expiry Mandatory
**Description**: JWTs can't be revoked
**Impact**: Security risk if stolen
**Mitigation**: Short expiry (15min) + refresh tokens

---

## CONVERSATION ORIGIN (Session cb91d93d)
**User Question**: "How to handle auth for API that needs to scale?"
**Discussion**: Evaluated sessions, JWT, OAuth2
**Outcome**: JWT chosen for stateless scaling
```

**Result:** Relationship-labeled, interpretable context.

---

## The Presentation Problem

**Without template structuring:**

```
Results:

Chunk 1: Use JWT Authentication - Context: Sessions don't scale...

Chunk 2: Token Expiry Mandatory - Description: JWTs can't be revoked...

Chunk 3: User asked: "How to handle auth for API that needs to scale?"
```

**Issues:**
- Flat list (no relationship labels)
- Model must infer structure
- Wastes tokens on parsing relationships
- Ambiguous connections

---

**With template structuring:**

```markdown
# DECISION: Use JWT Authentication

## Primary Decision
[Structured fields from template]

## RELATED CONSTRAINTS (Same File)
[Sibling chunks with same file_path]

## CONVERSATION ORIGIN (Session Match)
[Chunks with matching session_id]
```

**Benefits:**
- Explicit relationship labels
- Model sees HOW chunks relate
- Efficient token usage (no parsing needed)
- Interpretable presentation

---

## The Geometry: Template-Driven Assembly

```
Query: "Explain JWT decision"
    ↓
Search Layer: Find decision chunk
    ↓
Relationship Layer: Discover related chunks
    ├─ siblings (same file)
    ├─ genealogy (same session)
    └─ pattern (abstraction layer)
    ↓
Template Selection: Choose DECISION_TEMPLATE
    ↓
Assembly: Structure chunks with labels
    ├─ Primary Decision section
    ├─ Related Constraints section
    ├─ Conversation Origin section
    └─ Pattern Abstraction section
    ↓
Prompt Rendering: Markdown output
    ↓
Claude receives: Interpretable context
```

**Shape:** Query intent → template selection → relationship-labeled assembly

---

## Template Library Pattern

```
TEMPLATES = {
    'decision': DECISION_TEMPLATE,     # Primary + constraints + origin
    'pattern': PATTERN_TEMPLATE,       # Abstraction + implementations
    'timeline': TIMELINE_TEMPLATE,     # Chronological with phase labels
    'authority': AUTHORITY_TEMPLATE,   # Ranked by PageRank
    'bridge': BRIDGE_TEMPLATE          # Centrality-ranked connectors
}
```

**Query intent drives template selection:**

| Query | Template | Structure |
|-------|----------|-----------|
| "Explain X" | DECISION_TEMPLATE | Primary + context |
| "Trace X" | TIMELINE_TEMPLATE | Chronological |
| "Most authoritative X" | AUTHORITY_TEMPLATE | PageRank-ranked |
| "Connect A and B" | BRIDGE_TEMPLATE | Centrality-ranked |

**Same chunks, different presentation based on intent.**

---

## Field Extraction Pattern

**Template schema knowledge enables parsing:**

```python
# Template guarantees these fields exist
def extract_decision_fields(chunk):
    """Parse using template structure knowledge"""
    content = chunk.payload['content']

    return {
        'context': extract_field(content, '**Context**'),
        'solution': extract_field(content, '**Solution**'),
        'rationale': extract_field(content, '**Rationale**'),
        'alternatives': extract_field(content, '**Alternatives**')
    }
```

**Because template enforced structure at write time, parsing deterministic at serve time.**

---

## Relationship Labeling Pattern

**Metadata relationships become prompt sections:**

```python
# Metadata: file_path match
→ Prompt section: "RELATED SECTIONS (Same Changelog)"

# Metadata: session_id match
→ Prompt section: "CONVERSATION ORIGIN (Session X)"

# Naming: .pattern.md suffix
→ Prompt section: "PATTERN ABSTRACTION (Cross-Project)"

# Graph: PageRank score
→ Prompt section: "AUTHORITY RANKING (Most Referenced)"
```

**Soft-graph relationships → Hard prompt labels**

---

## Query-Driven Template Selection

### Example 1: Explanation Query

```python
query_intent = "explain"  # Detected from query or explicit
template = TEMPLATES['decision']

context = {
    'primary': decision_chunk,
    'siblings': get_siblings(decision_chunk.id),
    'genealogy': filter_by_session(decision_chunk.session_id),
    'pattern': find_pattern_variant(decision_chunk.file_path)
}

rendered = template.render(context)
```

**Template knows:**
- How to structure decision fields
- Where to place siblings
- How to label genealogy
- What pattern abstraction means

### Example 2: Timeline Query

```python
query_intent = "trace"
template = TEMPLATES['timeline']

context = {
    'decision': final_decision,
    'earlier': filter_by_timestamp(before=decision.timestamp),
    'later': filter_by_timestamp(after=decision.timestamp)
}

rendered = template.render(context)
# → Chronological timeline with phase labels
```

---

## The Interpretability Gain

**Traditional RAG serving:**

```
Here are 5 relevant chunks:
[chunk 1 text]
[chunk 2 text]
[chunk 3 text]
[chunk 4 text]
[chunk 5 text]
```

**Model task:** Parse relationships, structure context, answer question

**Template-structured serving:**

```markdown
# PRIMARY DECISION
[Structured with field labels]

# CONSTRAINTS (Same Document)
[Labeled as constraints]

# ORIGIN (Conversation)
[Labeled as source discussion]
```

**Model task:** Answer question (relationships already clear)

**Token savings:** ~30-40% (no parsing overhead)
**Accuracy gain:** Fewer misinterpreted relationships

---

## Success Criteria

Template serve-time structuring succeeds when:
1. Model understands relationships without inference
2. Token usage reduced (no relationship parsing)
3. Query intent drives template selection
4. Field extraction leverages write-time schema
5. Presentation adaptable (different templates for different needs)

Template serve-time structuring fails when:
1. Templates add clutter (worse than flat)
2. Rigid templates can't adapt
3. Overhead exceeds benefit
4. Relationship labels don't improve comprehension

---

## Key Property: Schema Continuity

**Write time → Query time → Serve time:**

```
Template enforcement at write
    ↓ (generates)
Guaranteed metadata at query
    ↓ (enables)
Deterministic field extraction at serve
    ↓ (produces)
Structured, interpretable context
```

**Schema flows through entire lifecycle.**

---

## Systems Thinking: Three-Stage Schema

**Most systems:**
```
Write: Schema defines structure
Read: Flat retrieval (no schema)
```

**AURA:**
```
Write: Template enforces structure
Query: Metadata enables filtering
Serve: Template structures presentation
```

**Schema active at all three stages.**

---

## Bottom Line

**Problem:** RAG returns flat chunks, model infers relationships.

**Innovation:** Template schema operates at serve time too.

**Mechanism:**
1. Template knowledge → field extraction
2. Metadata relationships → prompt labels
3. Query intent → template selection

**Benefits:**
- Interpretable (explicit relationship labels)
- Efficient (no parsing overhead)
- Adaptive (different templates per intent)

**Geometric essence:** Schema continuity across lifecycle (write → query → serve)

**Architectural role:** Prompt engineering at retrieval layer

**Result:** Not raw chunks, but INTERPRETED context.
