---
date: 2025-10-27
type: pattern.reusable
status: endstate
keywords: "accumulated-knowledge soft-decay interpretive-layer contextual-annotation"
---

# Pattern: Accumulated Knowledge with Soft Decay

## Problem

Systems accumulate knowledge over time.
Old knowledge becomes noise without context.
Binary states (current/obsolete) lose nuance.

**Typical scenario:**
- Document A: "Use approach X" (2 years old)
- Document B: "Use approach Y" (recent, supersedes X)
- User searches: Gets both A and B
- Problem: No context on why X was chosen, what changed, genealogy lost

---

## Anti-Pattern: Hard Deletion or Binary Flags

### Anti-Pattern 1: Delete Old Knowledge

```
function update_knowledge(new_doc):
    # Find superseded documents
    old_docs = find_similar(new_doc, threshold=0.85)

    # Delete old
    for old in old_docs:
        database.delete(old)

    # Insert new
    database.insert(new_doc)

# Problems:
# - Genealogy lost (why X was chosen initially)
# - Evolution invisible (what changed between X and Y)
# - Context missing (constraints that led to X)
```

### Anti-Pattern 2: Binary Obsolete Flag

```
function mark_superseded(new_doc):
    old_docs = find_similar(new_doc, threshold=0.85)

    for old in old_docs:
        old.status = "OBSOLETE"  # Binary flag
        old.superseded_by = new_doc.id

# Problems:
# - No nuance (obsolete vs evolved vs refined)
# - No explanation (why superseded)
# - Harsh language (sounds like error, not evolution)
```

---

## Pattern: Accumulated Knowledge with Soft Decay

### Core Principle

**Preserve all knowledge. Contextualize with soft language.**

```
function update_knowledge(new_doc):
    # Detect relationships (don't delete)
    old_docs = find_similar(new_doc, threshold=0.85)

    # Store relationship metadata
    for old in old_docs:
        knowledge_graph.add_relationship(
            new_doc, old,
            type='supersedes',
            confidence=similarity(new, old),
            reason=extract_reason(new, old)
        )

    # Both old and new remain searchable
    # Annotation layer adds context at serve time
```

---

## Implementation Pattern

### Step 1: Accumulate Usage Metadata

```
# Persistent knowledge graph state

BRAIN = {
  "nodes": {
    "doc-A": {
      "created": "2023-01-15",
      "age_months": 24,
      "reference_count": 45,
      "last_accessed": "2024-09-20",
      "authority_score": 0.72,  # PageRank
      "superseded_by": ["doc-B"],
      "supersession_confidence": 0.89
    },
    "doc-B": {
      "created": "2025-01-10",
      "age_months": 0,
      "reference_count": 127,
      "last_accessed": "2025-01-27",
      "authority_score": 0.94,
      "supersedes": ["doc-A"]
    }
  }
}

# Update after every query
function on_query_complete(results):
    for result in results:
        BRAIN[result.id].reference_count += 1
        BRAIN[result.id].last_accessed = now()
```

### Step 2: Detect Relationships (Not Delete)

```
function detect_supersession(new_doc, existing_docs):
    """Detect potential supersession relationships"""

    for old_doc in existing_docs:
        # Same topic (semantic similarity)
        similarity = cosine(new_doc.vector, old_doc.vector)

        if similarity > 0.85:
            # Newer supersedes older
            if new_doc.timestamp > old_doc.timestamp:
                BRAIN[old_doc.id].superseded_by.append(new_doc.id)
                BRAIN[old_doc.id].supersession_confidence = similarity

                BRAIN[new_doc.id].supersedes.append(old_doc.id)
```

### Step 3: Annotation at Serve Time

```
function annotate_with_context(doc, brain_state):
    """Add interpretive soft language"""

    annotations = []

    # Supersession annotation
    if brain_state.superseded_by and brain_state.supersession_confidence > 0.85:
        annotations.append({
            'type': 'evolution',
            'text': f"""🔄 **Evolution Note**: This approach was later refined
            in {brain_state.superseded_by[0].created_date}. While originally
            chosen for {extract_reason(doc)}, subsequent work identified
            {extract_improvement(brain_state.superseded_by[0])}. Original
            context preserved for genealogy."""
        })

    # Temporal decay annotation
    if brain_state.age_months > 12:
        annotations.append({
            'type': 'temporal',
            'text': f"""⏳ **Historical Context**: This document from
            {brain_state.age_months} months ago may reflect earlier system
            constraints. Consider whether assumptions still hold."""
        })

    # Authority annotation
    if brain_state.authority_score > 0.9:
        annotations.append({
            'type': 'canonical',
            'text': f"""⭐ **Canonical Pattern**: Most-referenced approach
            ({brain_state.reference_count} references). Authority score:
            {brain_state.authority_score} (top 5%)."""
        })

    # Low usage annotation
    if brain_state.reference_count < 5:
        annotations.append({
            'type': 'niche',
            'text': f"""💡 **Usage Note**: Referenced {brain_state.reference_count}
            times, suggesting niche use case. See [common patterns] for
            mainstream approaches."""
        })

    return annotate_document(doc, annotations)
```

### Step 4: Soft Language Rendering

```
function render_annotated(doc, annotations):
    """Render with gentle contextual notes"""

    output = []

    # Header with status
    status_badge = determine_status(annotations)
    output.append(f"# {doc.title} {status_badge}")

    # Annotation section (before content)
    if annotations:
        output.append("\n---\n")
        for annotation in annotations:
            output.append(annotation['text'])
        output.append("\n---\n")

    # Original content (preserved)
    output.append(doc.content)

    return '\n'.join(output)

function determine_status(annotations):
    """Determine status badge from annotations"""

    for annotation in annotations:
        if annotation['type'] == 'evolution':
            return "[⏳ SUPERSEDED]"
        elif annotation['type'] == 'canonical':
            return "[⭐ CURRENT]"
        elif annotation['type'] == 'temporal' and age > 18_months:
            return "[🗂️ HISTORICAL]"

    return ""  # No special status
```

---

## Soft Language Guidelines

**Avoid alarmist:**
```
❌ "OBSOLETE: Do not use"
❌ "DEPRECATED: Will be removed"
❌ "OUTDATED: Ignore this approach"
```

**Use contextual:**
```
✅ "This approach was later refined..."
✅ "While originally chosen for X, subsequent work showed Y..."
✅ "Preserved for understanding the evolution of thinking..."
✅ "Represents earlier system constraints that may have changed..."
```

**Tone principles:**
- Gentle (not harsh)
- Contextual (explains why)
- Preservative (genealogy valuable)
- Interpretive (helps understand current relevance)

---

## When to Use This Pattern

**Use when:**
- Knowledge evolves over time (decisions change)
- Genealogy valuable (why original choice made)
- Context matters (what changed between versions)
- Accumulated metadata available (reference counts, authority)

**Don't use when:**
- Knowledge static (unchanging truths)
- Binary state sufficient (truly obsolete vs current)
- Genealogy irrelevant (only current matters)
- Metadata unavailable (can't track usage/authority)

---

## Trade-off Analysis

### Soft Decay Pattern

**Pros:**
- Genealogy preserved (evolution understood)
- Nuanced (not binary obsolete/current)
- Contextual (explains what changed)
- Authority-aware (canonical vs niche)

**Cons:**
- Complexity (BRAIN state, annotation pipeline)
- Overhead (~200ms per document annotation)
- Maintenance (soft language must be refined)
- Storage (all historical documents retained)

### Hard Deletion

**Pros:**
- Simple (just delete old)
- Fast (no annotation)
- Clean (only current knowledge)

**Cons:**
- Genealogy lost (why X was chosen)
- Evolution invisible (what changed)
- Context missing (constraints/tradeoffs)

---

## Real-World Analogies

**Wikipedia revision history:**
- All versions preserved
- Diffs show what changed
- Context for evolution

**Git commit history:**
- All commits remain
- Can trace feature evolution
- Understand why decisions made

**This pattern:**
- All documents remain searchable
- Annotations provide context
- Genealogy explicitly preserved

---

## Extension: LLM-Generated Annotations

```
function generate_annotation(doc, brain_state):
    """Use LLM to generate contextual language"""

    prompt = f"""Add brief, gentle context to this document.

DOCUMENT (Original):
{doc.content}

CONTEXT:
- Age: {brain_state.age_months} months
- Superseded by: {brain_state.superseded_by}
- Supersession confidence: {brain_state.supersession_confidence}
- Reference count: {brain_state.reference_count}

INSTRUCTIONS:
1. If superseded: Explain what changed and why
2. If old: Note temporal context
3. If rarely referenced: Note niche vs common
4. Use soft language: "refined", "evolved" (not "obsolete")
5. Preserve original content

Output annotated document."""

    # Call cheap/fast LLM (e.g., Haiku)
    return llm_annotate(prompt, model='haiku')
```

**Cost:** ~$0.0001 per annotation
**Benefit:** Contextual language without manual writing

---

## Key Insights

1. **Preserve, don't delete**
   - All knowledge valuable for genealogy
   - Annotation adds context at serve time
   - Soft decay over hard deletion

2. **Accumulate usage metadata**
   - Reference counts → authority
   - Timestamps → temporal decay
   - Similarity + time → supersession

3. **Soft language matters**
   - "Refined" vs "obsolete"
   - Contextual vs alarmist
   - Interpretive vs declarative

4. **Annotation at serve time, not write time**
   - BRAIN evolves with usage
   - Annotations reflect current state
   - Dynamic, not static labels

5. **LLM as annotation layer**
   - Cheap model (Haiku ~$0.0001)
   - Contextual language generation
   - Consistent tone enforcement

---

## Language-Agnostic Implementation Hints

**State storage:**
- JSON (simple, human-readable)
- SQLite (queryable)
- Graph database (relationship-native)

**Annotation:**
- Template-based (fixed patterns)
- LLM-generated (contextual language)
- Hybrid (templates + LLM refinement)

**Soft language:**
- Emoji indicators (⏳ 🔄 💡 ⭐)
- Status badges ([SUPERSEDED] [CURRENT])
- Inline notes (contextual paragraphs)

---

## Bottom Line

**Problem:** Old knowledge becomes noise without context.

**Anti-pattern:** Delete old or mark binary "obsolete".

**Pattern:** Preserve all, accumulate usage metadata, annotate with soft decay language.

**Mechanism:**
1. BRAIN accumulates (reference counts, authority, supersession)
2. Detect relationships (don't delete)
3. Annotate at serve time (contextual language)
4. Render with soft decay (gentle, interpretive)

**Benefits:**
- Genealogy preserved (evolution understood)
- Nuanced (not binary)
- Authority-aware (canonical vs niche)
- Interpretive (helps user understand relevance)

**Trade-off:** Complexity + overhead vs genealogy value.

**Essence:** Soft decay over hard deletion. Context over removal.
