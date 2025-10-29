---
date: 2025-10-27
type: pattern.reusable
status: current
keywords: "metadata-driven-presentation schema-continuity retrieval-engineering"
---

# Pattern: Metadata-Driven Presentation

## Problem

Retrieval systems return results, but structure is lost.

**Typical scenario:**
- Search returns 5 relevant chunks
- Chunks have relationships (same document, same session, temporal)
- Relationships stored as metadata, not explicit in content
- Model must infer structure from flat list

**Result:** Token waste parsing, relationship ambiguity, comprehension overhead.

---

## Anti-Pattern: Flat Result Serving

```
function serve_results(query):
    results = search(query)

    output = "Results:\n\n"
    for i, result in enumerate(results):
        output += f"{i+1}. {result.content}\n\n"

    return output

# Problems:
# - No relationship labels
# - Model infers connections
# - Wastes tokens on parsing
# - Ambiguous structure
```

---

## Pattern: Metadata-Driven Presentation

### Core Principle

**Metadata relationships → Prompt structure**

If metadata says: `result1.file_path == result2.file_path`
Then prompt says: "These chunks are from the same document"

**Explicit over implicit.**

---

## Implementation

### Step 1: Metadata Schema Definition

```
# At write time: Define metadata structure
Document Metadata:
├─ file_path: string
├─ session_id: string
├─ timestamp: datetime
├─ section_type: enum (Decisions, Constraints, Patterns)
└─ has_context: boolean
└─ has_solution: boolean
└─ has_rationale: boolean
```

**Schema guarantees these fields exist.**

### Step 2: Relationship Discovery

```
function discover_relationships(primary_chunk, all_results):
    relationships = {}

    # Sibling relationship (same file)
    relationships['siblings'] = [
        r for r in all_results
        if r.metadata.file_path == primary_chunk.metadata.file_path
        and r.id != primary_chunk.id
    ]

    # Genealogy relationship (same session)
    relationships['genealogy'] = [
        r for r in all_results
        if r.metadata.session_id == primary_chunk.metadata.session_id
        and r.metadata.source == 'conversation'
    ]

    # Temporal relationship (evolution)
    relationships['temporal'] = [
        r for r in all_results
        if r.metadata.timestamp > primary_chunk.metadata.timestamp
        and semantic_similarity(r, primary_chunk) > 0.85
    ]

    return relationships
```

### Step 3: Template-Driven Assembly

```
function assemble_with_template(primary_chunk, relationships):
    """Structure results using template"""

    output = []

    # Primary section
    output.append("# PRIMARY RESULT")
    output.append(render_with_fields(primary_chunk))

    # Sibling section (if exists)
    if relationships['siblings']:
        output.append("\n## RELATED SECTIONS (Same Document)")
        for sibling in relationships['siblings']:
            output.append(f"### {sibling.section_type}: {sibling.title}")
            output.append(sibling.content)

    # Genealogy section (if exists)
    if relationships['genealogy']:
        output.append("\n## CONVERSATION ORIGIN")
        output.append(render_conversation(relationships['genealogy']))

    # Temporal section (if exists)
    if relationships['temporal']:
        output.append("\n## EVOLUTION (Later Refinements)")
        for t in relationships['temporal']:
            output.append(f"- {t.timestamp}: {t.title}")

    return '\n'.join(output)
```

### Step 4: Field Extraction (Schema Knowledge)

```
function render_with_fields(chunk):
    """Use schema knowledge to extract fields"""

    # Because schema guarantees field markers exist, extraction is deterministic
    fields = {
        'context': extract_between('**Context**:', next_field_or_end),
        'solution': extract_between('**Solution**:', next_field_or_end),
        'rationale': extract_between('**Rationale**:', next_field_or_end)
    }

    # Render structured
    output = []
    if fields['context']:
        output.append(f"**Context**: {fields['context']}")
    if fields['solution']:
        output.append(f"**Solution**: {fields['solution']}")
    if fields['rationale']:
        output.append(f"**Rationale**: {fields['rationale']}")

    return '\n\n'.join(output)
```

---

## Template Library Pattern

**Query intent → Template selection:**

```
TEMPLATES = {
    'explain': EXPLANATION_TEMPLATE,    # Primary + related sections
    'timeline': TIMELINE_TEMPLATE,      # Chronological with phase labels
    'authority': AUTHORITY_TEMPLATE,    # Ranked by connectivity
    'bridge': BRIDGE_TEMPLATE           # Connecting concepts
}

function serve(primary, relationships, intent):
    template = TEMPLATES[intent]
    return template.render(primary, relationships)
```

**Same data, different presentation based on intent.**

---

## Schema Continuity Pattern

**Three-stage schema:**

```
Write Time:
├─ Template defines structure
└─ Enforces field presence

Index Time:
├─ Parse template fields
└─ Extract metadata (has_context, has_solution, etc.)

Serve Time:
├─ Use metadata to label relationships
└─ Use schema to extract fields
└─ Structure presentation with template
```

**Schema active at all three stages.**

---

## When to Use This Pattern

**Use when:**
- Metadata captures relationships (file, session, temporal)
- Schema defines structure (template, fields)
- Model benefits from explicit labels (vs inference)
- Query intent varies (different templates)

**Don't use when:**
- Results already structured (e.g., JSON API)
- No metadata relationships (flat data)
- Model prefers raw format (no structure overhead)
- Single presentation format (no template variation)

---

## Trade-off Analysis

### Metadata-Driven Presentation

**Pros:**
- Explicit: Relationships labeled in prompt
- Efficient: No parsing overhead
- Adaptive: Template selection by intent
- Deterministic: Schema guarantees fields

**Cons:**
- Overhead: Template rendering (~10-20ms)
- Complexity: Multiple templates to maintain
- Rigidity: Structure predefined (not free-form)

### Flat Result Serving

**Pros:**
- Simple: No template logic
- Fast: Direct content dump
- Flexible: Model structures as needed

**Cons:**
- Implicit: Model infers relationships
- Inefficient: Wastes tokens on parsing
- Ambiguous: Connection interpretation varies

---

## Real-World Analogies

**SQL result formatting:**
- Database returns: Rows with columns
- Application layer: Formats as table, JSON, or HTML
- Presentation adapts to use case

**API response envelopes:**
- Service returns: Data + metadata
- Client receives: Structured envelope (status, data, pagination)
- Structure makes parsing deterministic

**This pattern:**
- Search returns: Chunks + metadata
- Serve layer: Structures with relationship labels
- Presentation adapts to query intent

---

## Extension: Query-Specific Templates

```
function serve_adaptive(query, results):
    # Detect query intent
    if "explain" in query.lower():
        intent = 'explain'
    elif "timeline" in query.lower() or "trace" in query.lower():
        intent = 'timeline'
    elif "authoritative" in query.lower():
        intent = 'authority'
    else:
        intent = 'default'

    # Select template
    template = TEMPLATES[intent]

    # Discover relationships
    relationships = discover_relationships(results[0], results)

    # Render with template
    return template.render(results[0], relationships)
```

**Query language drives presentation strategy.**

---

## Key Insights

1. **Metadata relationships → Prompt labels**
   - file_path match → "Same Document" section
   - session_id match → "Conversation Origin" section
   - timestamp + semantic → "Evolution" section

2. **Schema enables field extraction**
   - Template enforces structure at write time
   - Deterministic parsing at serve time
   - No guesswork about field presence

3. **Template selection by query intent**
   - Explain → Comprehensive context
   - Timeline → Chronological
   - Authority → Connectivity-ranked

4. **Explicit over implicit**
   - Model sees relationships directly
   - No token waste on parsing
   - Reduced ambiguity

5. **Three-stage schema continuity**
   - Write (enforce) → Index (extract) → Serve (structure)
   - Schema active across lifecycle

---

## Language-Agnostic Implementation Hints

**Template engines:**
- Python: Jinja2
- JavaScript: Mustache, Handlebars
- Go: text/template
- Rust: Tera
- Java: FreeMarker, Thymeleaf

**Field extraction:**
- Regex (universal)
- Markdown parsers (structured)
- Custom DSL parsers

**Metadata storage:**
- JSON payloads
- Database columns
- Document properties

---

## Bottom Line

**Problem:** Retrieval returns flat results, structure implicit.

**Anti-pattern:** Dump chunks, model infers relationships.

**Pattern:** Use metadata to label relationships, template to structure presentation.

**Benefits:**
- Explicit (labeled sections)
- Efficient (no parsing overhead)
- Adaptive (template by intent)
- Deterministic (schema-driven)

**Trade-off:** Template complexity vs flat simplicity.

**Essence:** Metadata relationships → Prompt structure labels.
