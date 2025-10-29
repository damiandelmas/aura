---
date: 2025-10-27
type: vision.innovation
status: endstate
keywords: "accumulated-knowledge soft-decay llm-annotation interpretive-layer"
---

# Vision: BRAIN + LLM Annotation Layer

## Core Insight

Don't delete old knowledge. **Contextualize it.**

Traditional approach: Superseded chunks removed or marked "obsolete"
AURA endstate: Superseded chunks annotated with "evolved" language

**Soft decay over hard deletion.**

---

## The Problem with Deletion

**Scenario:**
```
Oct 2023: Decision "Use Redis for caching"
Oct 2024: Decision "Use Memcached for caching" (supersedes Redis)
```

**Traditional approach:**
```
# Option 1: Delete old decision
search("caching") → Returns only Memcached decision
Lost: Why Redis was chosen initially, what changed

# Option 2: Mark obsolete
search("caching") → Returns both, Redis marked [OBSOLETE]
Problem: Binary flag (obsolete vs current), no nuance
```

**AURA approach:**
```
search("caching") → Returns both with annotations

Memcached decision: [CURRENT] (Oct 2024, 87 references)

Redis decision: [SUPERSEDED] (Oct 2023, 23 references)
└─ Annotation: "This decision was later refined after performance
               testing showed Memcached 3× faster for our access
               patterns. Original context preserved for genealogy."
```

**Genealogy preserved, evolution explained.**

---

## The BRAIN: Accumulated Graph Knowledge

**Persistent storage of relationship metadata:**

```
BRAIN = {
  "chunks": {
    "redis-decision-id": {
      "age_months": 18,
      "reference_count": 23,
      "last_referenced": "2024-09-12",
      "superseded_by": ["memcached-decision-id"],
      "supersession_confidence": 0.89,
      "pagerank_score": 0.72,
      "centrality_score": 0.45
    },
    "memcached-decision-id": {
      "age_months": 0,
      "reference_count": 87,
      "last_referenced": "2024-10-27",
      "supersedes": ["redis-decision-id"],
      "pagerank_score": 0.94,
      "centrality_score": 0.62
    }
  },

  "patterns": {
    "supersession_threshold": 0.85,
    "decay_function": "exponential",
    "authority_boost": 1.2
  }
}
```

**BRAIN learns from usage:**
- Which chunks get referenced → authority
- Which chunks get superseded → decay
- Which patterns emerge → graph structure

---

## The Three Annotation Targets

### Target 1: Chunk Content (Inline)

**Before annotation:**
```markdown
### Use Redis for Caching
- **Context**: Need distributed cache for session data
- **Solution**: Redis cluster with 3 nodes
- **Rationale**: Proven at scale, rich data structures
```

**After LLM annotation:**
```markdown
### Use Redis for Caching

⏳ **Temporal Context**: This decision from October 2023 (18 months old)
may reflect earlier system constraints.

🔄 **Evolution Note**: Later refined in October 2024 after performance
testing revealed Memcached better suited our access patterns. Original
context below preserved for genealogy.

---

- **Context**: Need distributed cache for session data
- **Solution**: Redis cluster with 3 nodes
- **Rationale**: Proven at scale, rich data structures

---

💡 **Why Changed**: Performance analysis showed Memcached 3× faster for
simple key-value access. Redis data structures went unused. See
[memcached-decision] for current approach.
```

### Target 2: Header Labels (Status Badges)

**Before:**
```
# DECISION: Use Redis for Caching
```

**After:**
```
# DECISION: Use Redis for Caching [⏳ SUPERSEDED] [📅 Oct 2023]

*Status: This decision was superseded in Oct 2024. Preserved for context.*
```

### Target 3: Prompt Template Sections

**Before:**
```markdown
## Primary Decision
**Context**: Need distributed cache...
```

**After:**
```markdown
## Primary Decision [Historical]

⚠️ **Interpretive Note**: This decision (18 months old, referenced
23 times) was later refined. While Redis was initially chosen for
rich data structures, subsequent performance analysis led to Memcached
adoption. This document provides valuable context on the original
requirements.

**Context**: Need distributed cache...
```

---

## The Annotation LLM Layer

**Fast, cheap model adds interpretive language:**

```
Query arrives
    ↓
Retrieve chunks (vector search)
    ↓
Lookup BRAIN state (metadata about chunks)
    ↓
LLM annotation pass (Haiku ~$0.0001 per chunk)
    ├─ Read: Chunk content
    ├─ Read: BRAIN context (age, supersession, authority)
    └─ Output: Annotated chunk with soft language
    ↓
Template assembly (structured serving)
    ↓
Claude receives contextualized knowledge
```

---

## Soft Language Philosophy

**Not alarmist:**
```
❌ "OBSOLETE: Do not use"
❌ "DEPRECATED: Will be removed"
❌ "OUTDATED: Ignore this"
```

**But contextual:**
```
✅ "This was later refined..."
✅ "While originally chosen for X, later work showed Y..."
✅ "Preserved for understanding the evolution of thinking..."
```

**Tone:**
- Gentle (not harsh)
- Contextual (why it changed)
- Preservative (genealogy valuable)
- Interpretive (what to make of it now)

---

## The BRAIN Update Cycle

**Continuous learning:**

```
Every query:
├─ Increment reference counts (what gets used)
├─ Update last_referenced timestamps
├─ Compute new authority scores (PageRank/centrality)
└─ Detect supersession patterns (newer + similar)

Every week:
├─ Recompute temporal decay (age → decay function)
├─ Identify canonical patterns (high authority + recent)
└─ Persist BRAIN state

Every month:
└─ Pattern mining (frequent compositions → slash commands)
```

**The BRAIN gets smarter with usage.**

---

## Annotation Prompt Pattern

```
You are an annotation assistant. Add brief, gentle temporal context
to this knowledge chunk.

CHUNK (Original):
{chunk.content}

BRAIN CONTEXT:
- Age: {age_months} months old
- Superseded by: {superseded_by_ids}
- Supersession confidence: {confidence}
- Reference count: {reference_count}
- Authority score: {pagerank_score}

INSTRUCTIONS:
1. If superseded (confidence > 0.85): Add evolution note
2. If old (>12 months) but unreplaced: Add temporal context
3. If rarely referenced (<5): Add usage note
4. If highly authoritative (pagerank > 0.9): Add canonical note
5. Keep language soft, not alarmist ("refined" not "obsolete")
6. Preserve original content entirely

Output annotated chunk in markdown.
```

**Fast model (Haiku) ~200ms per chunk.**

---

## Authority Annotation Examples

### High Authority (Canonical)

```markdown
⭐ **Canonical Pattern**: This is the most-referenced caching decision
(87 references, 12 months), indicating it represents the established
pattern. Authority score: 0.94 (top 5%).
```

### Low Authority (Niche)

```markdown
💡 **Usage Note**: This decision has been referenced 3 times in the past
year, suggesting it addresses a niche use case. For more commonly applied
patterns, see [top-ranked alternatives].
```

### Bridge Concept (High Centrality)

```markdown
🌉 **Architectural Bridge**: This pattern connects multiple domains
(centrality score: 0.82), indicating it represents a cross-cutting
concern referenced by both auth and caching decisions.
```

---

## The Geometry: Six-Layer Serving

```
Query: "How did we implement caching?"
    ↓
Layer 1: Semantic Search (Qdrant)
    Returns: 5 raw chunks
    ↓
Layer 2: Relationship Discovery (siblings, genealogy, temporal)
    Returns: 15 related chunks
    ↓
Layer 3: Graph Operations (optional)
    Returns: Reranked by PageRank
    ↓
Layer 4: BRAIN Lookup
    Returns: Temporal/supersession/authority state
    ↓
Layer 5: LLM Annotation (Haiku)
    Returns: Chunks with soft decay language
    ↓
Layer 6: Template Assembly
    Returns: Structured, contextualized prompt
    ↓
Claude receives interpretable, genealogy-aware context
```

---

## Success Criteria

BRAIN + annotation succeeds when:
1. Soft language improves comprehension (not clutter)
2. Genealogy preserved (evolution understood)
3. Model benefits from temporal context
4. BRAIN accumulates useful relationship knowledge
5. Annotation cost acceptable (~$0.001 per query)

BRAIN + annotation fails when:
1. Annotations distract from content
2. Soft language too vague (unhelpful)
3. Overhead unacceptable (>500ms)
4. BRAIN knowledge not actionable

---

## Why This Is Endstate (Not MVP)

**Dependencies:**
1. MVP primitives (siblings, graph ops) must work
2. BRAIN must accumulate 3-6 months of usage data
3. Supersession hints must be validated
4. Authority scores must be meaningful
5. Soft language must be refined through iteration

**Complexity:**
- Persistent BRAIN state (JSON storage)
- LLM annotation pass (adds latency)
- Prompt engineering for soft language
- Continuous learning loop
- Multiple annotation strategies

**Timeline:** 12-18 months after MVP launch.

---

## The Power (When Built)

**Query: "How do we handle caching?"**

**Returns:**
```markdown
# CACHING DECISIONS [3 found, ranked by authority]

## 1. Use Memcached for L1 Cache [⭐ CURRENT] [📅 Oct 2024]
*Authority: 0.94 (top pattern, 87 references)*

**Context**: After performance analysis...
**Solution**: Memcached cluster with consistent hashing
**Rationale**: 3× faster than Redis for our access patterns

---

## 2. Use Redis for Caching [⏳ SUPERSEDED] [📅 Oct 2023]

🔄 **Evolution Note**: This decision was later refined (Oct 2024) after
performance testing. Original context preserved for genealogy.

**Context**: Need distributed cache for session data...
**Solution**: Redis cluster with 3 nodes
**Rationale**: Rich data structures, proven at scale

💡 **Why Changed**: Performance analysis showed Memcached 3× faster for
our access patterns (mostly simple key-value). Redis data structures
unused. See [current decision] above.

---

## 3. Evaluated Memcached vs Redis [🗂️ HISTORICAL] [📅 Oct 2023]

⏳ **Historical Context**: Early exploration (18 months old). Decision
ultimately favored Redis initially, then reversed to Memcached. Valuable
for understanding evolution of thinking.

**Options Considered**: (original analysis)...
```

**Interpretable. Contextualized. Genealogy-preserved.**

---

## Bottom Line

**Problem:** Old knowledge becomes noise without context.

**Traditional:** Delete old or mark "obsolete" (hard edges).

**Innovation:** Annotate with soft decay language (gentle context).

**Mechanism:**
1. BRAIN accumulates usage patterns (reference counts, authority, supersession)
2. LLM reads BRAIN context
3. LLM adds interpretive soft language
4. Three targets: Content, headers, templates

**Benefits:**
- Genealogy preserved (evolution understood)
- Soft decay (not binary obsolete/current)
- Interpretive (explains what changed and why)
- Authority-aware (canonical vs niche)

**Geometric essence:** Accumulated knowledge → contextual annotation → interpretable serving

**Timeline:** Endstate (12-18 months post-MVP)

**Key property:** Knowledge never deleted, always contextualized.
