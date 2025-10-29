---
date: 2025-10-27
type: architecture.implementation
status: planned
keywords: "jinja2 template-rendering field-extraction python"
---

# Architecture: Template Serve-Time Implementation

## Components

**Location:** `imem/src/imem/serve.py`
**Status:** Planned (Phase 6.5)
**Effort:** ~100 lines

---

## Template Library

### Template Storage

```
imem/templates/
├── decision.md.j2          # Decision explanation
├── pattern.md.j2           # Pattern abstraction
├── timeline.md.j2          # Chronological trace
├── authority.md.j2         # PageRank ranked
└── bridge.md.j2            # Centrality ranked
```

### Decision Template (Jinja2)

```jinja2
{# imem/templates/decision.md.j2 #}

# DECISION: {{ primary.section_name }}

## Primary Decision ({{ primary.file_path }})
{{ render_decision_fields(primary) }}

{% if siblings %}
---
## RELATED SECTIONS (Same Changelog)
Found {{ siblings|length }} related sections from same document:

{% for sibling in siblings %}
### {{ sibling.section_type }}: {{ sibling.section_name }}
{{ sibling.content }}

{% endfor %}
{% endif %}

{% if genealogy %}
---
## CONVERSATION ORIGIN (Session {{ primary.session_id }})
This decision originated from:

{{ render_conversation(genealogy) }}
{% endif %}

{% if pattern %}
---
## PATTERN ABSTRACTION (Cross-Project Reusable)
Language-agnostic pattern from .pattern.md:

{{ pattern.content }}
{% endif %}

{% if temporal %}
---
## EVOLUTION (Later Refinements)
{% for t in temporal %}
- {{ t.timestamp }}: {{ t.section_name }}
  {{ t.content[:200] }}...

{% endfor %}
{% endif %}
```

### Timeline Template

```jinja2
{# imem/templates/timeline.md.j2 #}

# DECISION TIMELINE: {{ decision.section_name }}

## Current State ({{ decision.timestamp }})
{{ render_decision_fields(decision) }}

{% if earlier %}
---
## EARLIER (Before Decision)

{% for chunk in earlier|sort(attribute='timestamp') %}
### [{{ chunk.phase }}] {{ chunk.section_name }} ({{ chunk.timestamp }})
{{ chunk.content }}

{% endfor %}
{% endif %}

{% if later %}
---
## LATER (After Decision)

{% for chunk in later|sort(attribute='timestamp') %}
### [{{ chunk.phase }}] {{ chunk.section_name }} ({{ chunk.timestamp }})
{{ chunk.content }}

{% endfor %}
{% endif %}
```

---

## Field Extraction

### Core Function

```python
import re
from typing import Dict, Optional

def extract_field(content: str, field_marker: str) -> Optional[str]:
    """Extract template field from content

    Args:
        content: Markdown content
        field_marker: Field name (e.g., '**Context**')

    Returns:
        Field content or None
    """
    # Pattern: **FieldName**: content until next ** or section end
    pattern = rf'{re.escape(field_marker)}:\s*(.+?)(?=\n-\s*\*\*|\n##|\Z)'

    match = re.search(pattern, content, re.DOTALL)
    if match:
        return match.group(1).strip()

    return None

def extract_decision_fields(chunk) -> Dict[str, str]:
    """Extract all decision fields using template knowledge"""
    content = chunk.payload['content']

    return {
        'context': extract_field(content, '**Context**'),
        'solution': extract_field(content, '**Solution**'),
        'rationale': extract_field(content, '**Rationale**'),
        'alternatives': extract_field(content, '**Alternatives**')
    }

def render_decision_fields(chunk) -> str:
    """Render decision fields as formatted markdown"""
    fields = extract_decision_fields(chunk)

    output = []
    if fields['context']:
        output.append(f"**Context**: {fields['context']}")
    if fields['solution']:
        output.append(f"**Solution**: {fields['solution']}")
    if fields['rationale']:
        output.append(f"**Rationale**: {fields['rationale']}")
    if fields['alternatives']:
        output.append(f"**Alternatives**: {fields['alternatives']}")

    return '\n\n'.join(output)
```

---

## Template Rendering Engine

### Core Implementation

```python
from jinja2 import Environment, FileSystemLoader, Template
from pathlib import Path
from typing import Dict, Any, List

TEMPLATE_DIR = Path(__file__).parent / 'templates'

# Initialize Jinja2 environment
jinja_env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    trim_blocks=True,
    lstrip_blocks=True
)

# Register custom functions
jinja_env.globals['render_decision_fields'] = render_decision_fields
jinja_env.globals['render_conversation'] = render_conversation

def render_template(
    template_name: str,
    context: Dict[str, Any]
) -> str:
    """Render template with context

    Args:
        template_name: Template file (e.g., 'decision.md.j2')
        context: Template variables

    Returns:
        Rendered markdown
    """
    template = jinja_env.get_template(template_name)
    return template.render(**context)
```

---

## Serve Function

### High-Level Interface

```python
def serve_with_template(
    primary_chunk,
    relationships: Dict[str, List] = None,
    template: str = 'decision'
) -> str:
    """Serve chunks with template structuring

    Args:
        primary_chunk: Main result chunk
        relationships: Related chunks
            - siblings: Same file chunks
            - genealogy: Same session chunks
            - pattern: Pattern layer variant
            - temporal: Evolution chunks
        template: Template name

    Returns:
        Structured markdown prompt
    """
    relationships = relationships or {}

    # Build context for template
    context = {
        'primary': primary_chunk,
        'siblings': relationships.get('siblings', []),
        'genealogy': relationships.get('genealogy', []),
        'pattern': relationships.get('pattern'),
        'temporal': relationships.get('temporal', [])
    }

    # Render with template
    rendered = render_template(f'{template}.md.j2', context)

    return rendered
```

---

## Integration with Retrieval Modes

### Mode 2: Explain (with template)

```python
def explain(query: str, filters: Dict = None) -> str:
    """Explain decision with complete context

    Uses DECISION_TEMPLATE for structured serving
    """
    # 1. Search for decision
    results = search(query, filters={'section_type': 'Decisions', **(filters or {})})
    if not results:
        return "No decisions found"

    primary = results[0]

    # 2. Discover relationships
    relationships = {
        'siblings': get_siblings(primary.id),
        'genealogy': filter_by_session(primary.payload['session_id']),
        'pattern': find_pattern_variant(primary.payload['file_path'])
    }

    # 3. Serve with template
    return serve_with_template(
        primary_chunk=primary,
        relationships=relationships,
        template='decision'
    )
```

### Mode 3: Trace (with template)

```python
def trace(query: str) -> str:
    """Trace decision timeline

    Uses TIMELINE_TEMPLATE for chronological serving
    """
    # 1. Find decision
    results = search(query, filters={'section_type': 'Decisions'})
    if not results:
        return "No decisions found"

    decision = results[0]

    # 2. Discover temporal relationships
    relationships = {
        'earlier': filter_by_timestamp(
            before=decision.payload['timestamp'],
            session_id=decision.payload['session_id']
        ),
        'later': filter_by_timestamp(
            after=decision.payload['timestamp'],
            semantic_similar=decision.id
        )
    }

    # 3. Serve with timeline template
    return serve_with_template(
        primary_chunk=decision,
        relationships=relationships,
        template='timeline'
    )
```

---

## CLI Interface

```python
# imem/src/imem/cli.py

@develop.command()
@click.argument('query')
@click.option('--limit', default=1)
def explain(query, limit):
    """Explain decision with complete context

    Example:
        imem develop explain "JWT authentication"
    """
    result = explain_with_template(query)
    click.echo(result)

@develop.command()
@click.argument('query')
def trace(query):
    """Trace decision timeline

    Example:
        imem develop trace "database schema"
    """
    result = trace_with_template(query)
    click.echo(result)
```

---

## Template Customization

### Custom Template Example

```python
# User can provide custom templates

def serve_with_custom_template(
    primary_chunk,
    relationships,
    template_content: str
) -> str:
    """Render with inline template string"""

    # Parse template
    template = Template(template_content)

    # Build context
    context = {
        'primary': primary_chunk,
        **relationships
    }

    return template.render(**context)
```

### Usage

```python
custom_template = """
# {{ primary.section_name }}

## Summary
{{ primary.content[:500] }}

## Related
{% for s in siblings %}
- {{ s.section_name }}
{% endfor %}
"""

result = serve_with_custom_template(
    primary_chunk=chunk,
    relationships={'siblings': siblings},
    template_content=custom_template
)
```

---

## Field Registry Pattern

### Extensible Field Definitions

```python
# Field extraction registry
FIELD_EXTRACTORS = {
    'decisions': {
        'context': ('**Context**:', r'(.+?)(?=\n-\s*\*\*|\n##|\Z)'),
        'solution': ('**Solution**:', r'(.+?)(?=\n-\s*\*\*|\n##|\Z)'),
        'rationale': ('**Rationale**:', r'(.+?)(?=\n-\s*\*\*|\n##|\Z)'),
        'alternatives': ('**Alternatives**:', r'(.+?)(?=\n-\s*\*\*|\n##|\Z)')
    },
    'constraints': {
        'description': ('**Description**:', r'(.+?)(?=\n-\s*\*\*|\n##|\Z)'),
        'impact': ('**Impact**:', r'(.+?)(?=\n-\s*\*\*|\n##|\Z)'),
        'mitigation': ('**Mitigation**:', r'(.+?)(?=\n-\s*\*\*|\n##|\Z)')
    },
    'patterns': {
        'problem': ('**Problem**:', r'(.+?)(?=\n-\s*\*\*|\n##|\Z)'),
        'solution': ('**Solution**:', r'(.+?)(?=\n-\s*\*\*|\n##|\Z)'),
        'trade_off': ('**Trade-off**:', r'(.+?)(?=\n-\s*\*\*|\n##|\Z)')
    }
}

def extract_fields_by_type(chunk) -> Dict[str, str]:
    """Extract fields based on section type"""
    section_type = chunk.payload['section_type'].lower()
    extractors = FIELD_EXTRACTORS.get(section_type, {})

    fields = {}
    for field_name, (marker, pattern) in extractors.items():
        value = extract_field(chunk.payload['content'], marker)
        fields[field_name] = value

    return fields
```

---

## Performance Characteristics

**Template rendering:**
- Decision template: ~5ms
- Timeline template: ~10ms (chronological sort)
- Field extraction: ~1ms per field

**Total overhead:** 10-20ms per serve operation

**Bottleneck:** None (negligible compared to search/graph)

---

## Error Handling

```python
def serve_with_template_safe(
    primary_chunk,
    relationships,
    template
) -> str:
    """Serve with fallback on template errors"""

    try:
        return serve_with_template(primary_chunk, relationships, template)
    except Exception as e:
        # Fallback: Return raw chunks
        logger.warning(f"Template rendering failed: {e}")
        return _render_raw_fallback(primary_chunk, relationships)

def _render_raw_fallback(primary, relationships):
    """Simple fallback rendering"""
    output = [f"# {primary.payload['section_name']}\n"]
    output.append(primary.payload['content'])

    if relationships.get('siblings'):
        output.append("\n## Related Sections\n")
        for s in relationships['siblings']:
            output.append(f"### {s.payload['section_name']}\n")
            output.append(s.payload['content'])

    return '\n'.join(output)
```

---

## Testing Strategy

```python
# test_serve.py

def test_decision_template():
    """Test decision template rendering"""
    chunk = create_test_chunk(section_type='Decisions', content="""
### Use JWT Authentication
- **Context**: Sessions don't scale
- **Solution**: Stateless tokens
- **Rationale**: Horizontal scaling
- **Alternatives**: OAuth (too complex)
    """)

    result = serve_with_template(chunk, template='decision')

    assert '# DECISION: Use JWT Authentication' in result
    assert '**Context**: Sessions don\'t scale' in result
    assert 'RELATED SECTIONS' not in result  # No siblings provided

def test_field_extraction():
    """Test template field extraction"""
    content = """
- **Context**: Problem statement here
- **Solution**: Implementation approach
- **Rationale**: Why this works
    """

    context = extract_field(content, '**Context**')
    assert context == 'Problem statement here'

    solution = extract_field(content, '**Solution**')
    assert solution == 'Implementation approach'
```

---

## Dependencies

```python
# requirements.txt
jinja2>=3.1.0
```

---

## Summary

**Implementation:**
- ~100 lines (serve.py)
- Jinja2 templates
- Field extraction via regex
- Template registry pattern

**Templates:**
- decision.md.j2 (explanation)
- timeline.md.j2 (chronological)
- authority.md.j2 (PageRank)
- bridge.md.j2 (centrality)

**Integration:**
- explain() mode uses DECISION_TEMPLATE
- trace() mode uses TIMELINE_TEMPLATE
- Custom templates supported

**Overhead:** 10-20ms per serve (negligible)

**Next:** See `.pattern.md` for language-agnostic principle.
