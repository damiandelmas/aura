---
session_id: ca22384b-3a6d-4821-8b70-2aa1a89ea4ba
date: 2025-10-27
level: architecture-implementation
innovation: creation-time-schema
---

# Creation-Time Schema: Implementation Specification

## Template Structure

**Template files:**
```
.context/
├─ develop/
│   └─ .template.md
├─ design/
│   └─ .template.md
└─ document/
    └─ .template.md
```

**develop/.template.md example:**
```markdown
---
phase: develop
layer: implementation
type: changelog.implementation
---

# [Date] - [Title]

## Decisions
### [Decision Title]
- **Context**: (REQUIRED - Why this decision arose)
- **Solution**: (REQUIRED - What was decided)
- **Rationale**: (REQUIRED - Why this approach)
- **Alternatives**: (OPTIONAL - Other options considered)

## Constraints
### [Constraint Title]
- **Description**: (REQUIRED - What the limitation is)
- **Impact**: (REQUIRED - How it affects the system)

## Failures
### [Failure Title]
- **Issue**: (REQUIRED - What went wrong)
- **Root Cause**: (REQUIRED - Why it happened)
- **Resolution**: (REQUIRED - How it was fixed)
```

## Validation Schema

**Field requirements by section type:**

```python
# imem/src/imem/validation.py

SECTION_SCHEMAS = {
    'Decisions': {
        'required': ['Context', 'Solution', 'Rationale'],
        'optional': ['Alternatives', 'Constraints']
    },
    'Constraints': {
        'required': ['Description', 'Impact'],
        'optional': ['Mitigation']
    },
    'Failures': {
        'required': ['Issue', 'Root Cause', 'Resolution'],
        'optional': ['Prevention']
    },
    'Patterns': {
        'required': ['Context', 'Solution', 'Rationale'],
        'optional': ['Alternatives', 'Applicability']
    }
}
```

## Validation Logic

**Document parsing and validation:**

```python
from typing import Dict, List, Optional
import re

class TemplateValidator:
    """Validate document compliance with template"""

    def validate_document(self, file_path: str) -> ValidationResult:
        """Parse and validate document structure"""

        with open(file_path) as f:
            content = f.read()

        # Parse H2 sections
        sections = self.parse_sections(content)

        # Validate each section
        errors = []
        warnings = []

        for section in sections:
            section_type = section['type']  # e.g., "Decisions"
            subsections = section['subsections']  # H3 blocks

            for subsection in subsections:
                result = self.validate_subsection(
                    section_type,
                    subsection
                )

                errors.extend(result.errors)
                warnings.extend(result.warnings)

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    def validate_subsection(
        self,
        section_type: str,
        subsection: Dict
    ) -> ValidationResult:
        """Check required fields present"""

        schema = SECTION_SCHEMAS.get(section_type)
        if not schema:
            return ValidationResult(valid=True)  # Unknown section, allow

        errors = []
        warnings = []

        # Check required fields
        for required_field in schema['required']:
            if not self.has_field(subsection['content'], required_field):
                errors.append(
                    f"{subsection['title']}: Missing required field '{required_field}'"
                )

        # Check optional fields (warnings only)
        for optional_field in schema['optional']:
            if not self.has_field(subsection['content'], optional_field):
                warnings.append(
                    f"{subsection['title']}: Missing optional field '{optional_field}'"
                )

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    def has_field(self, content: str, field_name: str) -> bool:
        """Check if markdown content has field"""
        pattern = rf"- \*\*{field_name}\*\*:"
        return re.search(pattern, content) is not None

    def parse_sections(self, content: str) -> List[Dict]:
        """Extract H2 sections with H3 subsections"""
        # Implementation of markdown parsing
        ...
```

## Ingestion Integration

**Reject invalid documents:**

```python
# imem/src/imem/ingest.py

def ingest_changelog(file_path: str, strict: bool = True):
    """Ingest changelog with template validation"""

    # 1. Validate template compliance
    validator = TemplateValidator()
    result = validator.validate_document(file_path)

    if not result.valid:
        if strict:
            # Reject and abort
            print(f"❌ Validation failed for {file_path}")
            for error in result.errors:
                print(f"  - {error}")
            raise ValueError("Template compliance required in strict mode")
        else:
            # Warn but continue
            print(f"⚠️  Warnings for {file_path}")
            for warning in result.warnings:
                print(f"  - {warning}")

    # 2. Parse and extract metadata
    chunks = parse_changelog(file_path)

    # 3. Enrich with validation metadata
    for chunk in chunks:
        chunk.payload['template_compliant'] = result.valid
        chunk.payload['has_context'] = has_field(chunk, 'Context')
        chunk.payload['has_solution'] = has_field(chunk, 'Solution')
        chunk.payload['has_rationale'] = has_field(chunk, 'Rationale')
        chunk.payload['has_alternatives'] = has_field(chunk, 'Alternatives')

    # 4. Index to Qdrant
    qdrant_client.upsert(collection_name=collection, points=chunks)

    print(f"✓ Indexed {len(chunks)} chunks from {file_path}")
```

## CLI Commands

```bash
# Initialize project with templates
aura init /path/to/project
# Deploys: .context/develop/.template.md, etc.

# Validate document before ingestion
imem validate /path/to/changelog.md
# Returns: Validation errors/warnings

# Ingest with strict validation (default)
imem init --strict
# Rejects documents with validation errors

# Ingest with warnings only
imem init --warn
# Logs warnings but continues
```

## Template Distribution

**Project initialization:**

```python
# aura/src/aura/init.py

def init_project(project_root: str):
    """Deploy templates to project"""

    templates_source = Path(__file__).parent / 'templates'
    project_context = Path(project_root) / '.context'

    # Copy templates
    for phase in ['develop', 'design', 'designate', 'document']:
        template_file = templates_source / phase / '.template.md'
        dest_dir = project_context / phase
        dest_dir.mkdir(parents=True, exist_ok=True)

        shutil.copy(template_file, dest_dir / '.template.md')

        print(f"✓ Deployed template: .context/{phase}/.template.md")

    print("\n📋 Templates deployed. Use them for new changelogs.")
```

## Metadata Queries

**Deterministic filtering enabled:**

```python
# Query documents with complete context
results = qdrant_client.query(
    collection_name=collection,
    query_vector=embed("authentication"),
    query_filter=Filter(must=[
        FieldCondition(key='has_context', match=MatchValue(value=True)),
        FieldCondition(key='has_rationale', match=MatchValue(value=True)),
        FieldCondition(key='template_compliant', match=MatchValue(value=True))
    ])
)

# This works reliably because:
# - All indexed documents passed validation
# - Metadata fields guaranteed present
# - No probabilistic extraction
```

## Migration Strategy

**Handling template evolution:**

```python
# Version templates
template_version = "v3"  # In frontmatter

# During ingestion
chunk.payload['template_version'] = extract_version(file_path)

# During query
query_filter = Filter(must=[
    FieldCondition(
        key='template_version',
        match=MatchAny(any=['v3', 'v4'])  # Accept recent versions
    )
])
```

## Validation Performance

- **Parse + validate**: ~10-20ms per document
- **No runtime cost**: Validation at ingestion only
- **Query benefit**: Deterministic filtering (no false positives)
