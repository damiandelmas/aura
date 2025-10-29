---
session_id: e025fbb0-1abb-46e8-82a1-79c49afcc32d
date: 2025-10-27
type: pattern.innovation
resolution: architectural
keywords: "template-validation fail-fast schema-versioning"
---

# Creation-Time Schema Enforcement Pattern

## Pattern Structure

**Schema as template, enforcement at ingestion.**

### Component Relationship

```
Template file (schema definition):
└─ Defines required fields
   ├─ Section types (Decisions, Constraints)
   ├─ Required fields (Context, Solution, Rationale)
   └─ Optional fields (Alternatives, Implementation)

Validation (at ingestion):
└─ Check template compliance
   ├─ Parse document structure
   ├─ Detect field presence
   └─ Reject if incomplete

Metadata (guaranteed):
└─ Every chunk has deterministic fields
   ├─ has_context: true/false
   ├─ has_solution: true/false
   └─ has_rationale: true/false
```

## Invariants

1. **Template defines contract**
   - Markdown template = schema
   - Version-controlled
   - Human-readable

2. **Validation before indexing**
   - Reject incomplete documents
   - No partial ingestion
   - Fail fast with clear errors

3. **Metadata guaranteed**
   - Field presence deterministic
   - Queries never uncertain
   - Deterministic filtering precision

## Schema Definition

```markdown
# Template: Develop Phase Changelog

## Decisions (required section)

### [Decision Title] (H3 required)

- **Context** (required): Why this decision arose
- **Solution** (required): What was chosen
- **Rationale** (required): Why it was chosen
- **Alternatives** (optional): What was rejected

## Constraints (optional section)

### [Constraint Title]

- **Description** (required): What blocked us
- **Impact** (required): How it affected decisions

## Failures (optional section)

### [Failure Title]

- **Issue** (required): What didn't work
- **Root Cause** (required): Why it failed
- **Resolution** (optional): How we fixed it
```

## Validation Rules

```
Decision section requirements:
- H2: "Decisions"
- H3: Individual decision titles
- Fields: Context (required), Solution (required), Rationale (required)
- Alternatives: Optional but tracked

Constraint section requirements:
- H2: "Constraints"
- H3: Individual constraint titles
- Fields: Description (required), Impact (required)

Failure section requirements:
- H2: "Failures"
- H3: Individual failure titles
- Fields: Issue (required), Root Cause (required)
- Resolution: Optional
```

## Validation Algorithm

```
def validate_document(doc, template_schema):
    """Enforce template compliance before indexing"""

    # 1. Parse document into sections
    sections = parse_markdown_sections(doc)

    # 2. Check each section against schema
    for section in sections:
        section_type = section['h2_title']  # "Decisions", "Constraints"

        if section_type not in template_schema:
            raise ValidationError(f"Unknown section: {section_type}")

        required_fields = template_schema[section_type]['required']

        # Check each H3 subsection
        for subsection in section['h3_subsections']:
            detected_fields = detect_fields(subsection['content'])

            for field in required_fields:
                if field not in detected_fields:
                    raise ValidationError(
                        f"Missing required field '{field}' in "
                        f"{section_type}/{subsection['title']}"
                    )

    return True  # All validations passed
```

## Metadata Extraction

```
After validation passes:

def extract_metadata(doc):
    """Extract guaranteed metadata from validated doc"""

    metadata = {
        'schema_version': doc.frontmatter['schema_version'],
        'phase': detect_phase(doc.file_path),
        'sections': []
    }

    for section in doc.sections:
        for subsection in section.h3_subsections:
            chunk_metadata = {
                'section_type': section.h2_title,
                'section_name': subsection.h3_title,

                # Guaranteed field presence
                'has_context': 'Context' in subsection.content,
                'has_solution': 'Solution' in subsection.content,
                'has_rationale': 'Rationale' in subsection.content,
                'has_alternatives': 'Alternatives' in subsection.content
            }

            metadata['sections'].append(chunk_metadata)

    return metadata
```

## Schema Evolution

```
Schema versioning:

v1.0 (initial):
- Decisions: Context, Solution (required)

v2.0 (added):
- Decisions: + Rationale (required)

v3.0 (added):
- Decisions: + Alternatives (optional)
- New section: Failures

Migration:
- Existing docs marked with schema_version
- Validation uses version-specific rules
- Queries filter by compatible versions
```

## Benefits

- **Deterministic queries**: Filter by field presence
- **No probabilistic extraction**: Humans provide structure
- **Fail fast**: Reject bad docs at creation
- **Version-controlled schema**: Templates in git
- **Self-documenting**: Template is documentation

## When to Use

Use when:
- Metadata reliability critical
- Querying precision required
- Human-in-loop at creation acceptable
- Long-term knowledge management

Avoid when:
- Unstructured content sources
- No control over document creation
- Fully automated ingestion needed
- Probabilistic extraction acceptable
