# Template Schema: Implementation Specification

**Session:** a86bc733-c4e3-4d88-b17f-2f9e330ca11a
**Level:** Implementation (L2b)
**Date:** 2025-10-27

## Schema Definition

```python
# imem/src/imem/templates/schema.py

TEMPLATE_SCHEMA = {
    'Decisions': {
        'required': ['Context', 'Solution'],
        'optional': ['Rationale', 'Alternatives', 'Benefits', 'Drawbacks', 'Trade-offs']
    },
    'Constraints': {
        'required': ['Description', 'Impact'],
        'optional': ['Mitigation', 'Workaround', 'Timeline']
    },
    'Failures': {
        'required': ['Issue', 'Root Cause'],
        'optional': ['Resolution', 'Prevention', 'Lessons']
    },
    'Patterns': {
        'required': ['Pattern', 'Use Case'],
        'optional': ['Benefits', 'Trade-offs', 'Examples']
    },
    'Implementation': {
        'required': ['Description'],
        'optional': ['Files', 'Dependencies', 'Configuration']
    }
}


def get_required_fields(section_type: str) -> List[str]:
    """Get required fields for a section type"""
    return TEMPLATE_SCHEMA.get(section_type, {}).get('required', [])


def get_optional_fields(section_type: str) -> List[str]:
    """Get optional fields for a section type"""
    return TEMPLATE_SCHEMA.get(section_type, {}).get('optional', [])
```

---

## Template Validator

```python
# imem/src/imem/templates/validator.py

import re
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class ValidationResult:
    """Result of template validation"""
    valid: bool
    section_type: str
    section_name: str
    missing_required: List[str]
    present_optional: List[str]
    errors: List[str]


class TemplateValidator:
    """
    Validates markdown sections against template schema.
    Enforces required fields, tracks optional fields.
    """

    def __init__(self, schema: Dict):
        self.schema = schema

    def validate_section(self, content: str, section_type: str, section_name: str) -> ValidationResult:
        """
        Validate a single H3 section.

        Args:
            content: Section content (text after H3)
            section_type: Parent H2 section type
            section_name: H3 section name

        Returns:
            ValidationResult with validation outcome
        """
        if section_type not in self.schema:
            return ValidationResult(
                valid=False,
                section_type=section_type,
                section_name=section_name,
                missing_required=[],
                present_optional=[],
                errors=[f"Unknown section type: {section_type}"]
            )

        # Get schema for this section type
        required_fields = self.schema[section_type]['required']
        optional_fields = self.schema[section_type]['optional']

        # Extract bold fields from content
        bold_pattern = r'\*\*([^*]+)\*\*'
        found_fields = set(re.findall(bold_pattern, content))

        # Check required fields
        missing_required = [f for f in required_fields if f not in found_fields]

        # Track optional fields
        present_optional = [f for f in optional_fields if f in found_fields]

        # Validation result
        valid = len(missing_required) == 0
        errors = []

        if missing_required:
            errors.append(f"Missing required fields: {', '.join(missing_required)}")

        return ValidationResult(
            valid=valid,
            section_type=section_type,
            section_name=section_name,
            missing_required=missing_required,
            present_optional=present_optional,
            errors=errors
        )

    def validate_document(self, markdown: str) -> Dict[str, List[ValidationResult]]:
        """
        Validate entire markdown document.

        Returns dict mapping section types to validation results.
        """
        results = {}

        # Parse document structure
        current_h2 = None
        current_h3 = None
        current_content = []

        for line in markdown.split('\n'):
            # H2 header (section type)
            h2_match = re.match(r'^## (.+)$', line)
            if h2_match:
                # Save previous H3 section if any
                if current_h2 and current_h3:
                    content = '\n'.join(current_content)
                    result = self.validate_section(content, current_h2, current_h3)
                    results.setdefault(current_h2, []).append(result)

                current_h2 = h2_match.group(1).strip()
                current_h3 = None
                current_content = []
                continue

            # H3 header (section name)
            h3_match = re.match(r'^### (.+)$', line)
            if h3_match:
                # Save previous H3 section if any
                if current_h2 and current_h3:
                    content = '\n'.join(current_content)
                    result = self.validate_section(content, current_h2, current_h3)
                    results.setdefault(current_h2, []).append(result)

                current_h3 = h3_match.group(1).strip()
                current_content = []
                continue

            # Content lines
            if current_h2 and current_h3:
                current_content.append(line)

        # Save final section
        if current_h2 and current_h3:
            content = '\n'.join(current_content)
            result = self.validate_section(content, current_h2, current_h3)
            results.setdefault(current_h2, []).append(result)

        return results
```

---

## Metadata Extractor

```python
# imem/src/imem/templates/extractor.py

import re
from typing import Dict, Any, List


class MetadataExtractor:
    """
    Extract metadata from template-compliant markdown.
    Uses deterministic pattern matching (not LLM).
    """

    def __init__(self, schema: Dict):
        self.schema = schema

    def extract_section_metadata(self, content: str, section_type: str, section_name: str) -> Dict[str, Any]:
        """
        Extract metadata from a single section.

        Returns metadata dict with:
        - section_type, section_name
        - has_<field> booleans for all required + optional fields
        - content
        """
        required_fields = self.schema[section_type]['required']
        optional_fields = self.schema[section_type]['optional']

        # Extract bold fields
        bold_pattern = r'\*\*([^*]+)\*\*'
        found_fields = set(re.findall(bold_pattern, content))

        # Build metadata
        metadata = {
            'section_type': section_type,
            'section_name': section_name,
            'content': content.strip()
        }

        # Add has_<field> booleans for required fields
        for field in required_fields:
            metadata[f'has_{field.lower().replace(" ", "_")}'] = field in found_fields

        # Add has_<field> booleans for optional fields
        for field in optional_fields:
            metadata[f'has_{field.lower().replace(" ", "_")}'] = field in found_fields

        return metadata

    def extract_document_metadata(self, markdown: str, file_path: str, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Extract metadata for all sections in document.

        Returns list of metadata dicts (one per H3 section).
        """
        sections = []

        # Parse document structure
        current_h2 = None
        current_h3 = None
        current_content = []

        for line in markdown.split('\n'):
            h2_match = re.match(r'^## (.+)$', line)
            if h2_match:
                # Save previous section
                if current_h2 and current_h3:
                    content = '\n'.join(current_content)
                    metadata = self.extract_section_metadata(content, current_h2, current_h3)
                    metadata['file_path'] = file_path
                    if session_id:
                        metadata['session_id'] = session_id
                    sections.append(metadata)

                current_h2 = h2_match.group(1).strip()
                current_h3 = None
                current_content = []
                continue

            h3_match = re.match(r'^### (.+)$', line)
            if h3_match:
                # Save previous section
                if current_h2 and current_h3:
                    content = '\n'.join(current_content)
                    metadata = self.extract_section_metadata(content, current_h2, current_h3)
                    metadata['file_path'] = file_path
                    if session_id:
                        metadata['session_id'] = session_id
                    sections.append(metadata)

                current_h3 = h3_match.group(1).strip()
                current_content = []
                continue

            if current_h2 and current_h3:
                current_content.append(line)

        # Save final section
        if current_h2 and current_h3:
            content = '\n'.join(current_content)
            metadata = self.extract_section_metadata(content, current_h2, current_h3)
            metadata['file_path'] = file_path
            if session_id:
                metadata['session_id'] = session_id
            sections.append(metadata)

        return sections
```

---

## Ingestion Integration

```python
# imem/src/imem/ingest.py (additions)

from imem.templates.schema import TEMPLATE_SCHEMA
from imem.templates.validator import TemplateValidator
from imem.templates.extractor import MetadataExtractor


def ingest_changelog(file_path: str, validate: bool = True) -> Dict[str, Any]:
    """
    Ingest changelog with optional template validation.

    Args:
        file_path: Path to markdown file
        validate: Enforce template compliance (default True)

    Returns:
        Ingestion result with success/failure info
    """
    with open(file_path) as f:
        content = f.read()

    # Template validation
    if validate:
        validator = TemplateValidator(TEMPLATE_SCHEMA)
        validation_results = validator.validate_document(content)

        # Check for failures
        all_valid = True
        errors = []

        for section_type, results in validation_results.items():
            for result in results:
                if not result.valid:
                    all_valid = False
                    errors.append({
                        'section_type': section_type,
                        'section_name': result.section_name,
                        'missing_required': result.missing_required,
                        'errors': result.errors
                    })

        if not all_valid:
            return {
                'success': False,
                'file_path': file_path,
                'errors': errors,
                'message': f"Template validation failed. {len(errors)} section(s) invalid."
            }

    # Extract metadata
    extractor = MetadataExtractor(TEMPLATE_SCHEMA)
    sections = extractor.extract_document_metadata(content, file_path)

    # Embed and upsert to Qdrant
    # (existing embedding logic)
    # ...

    return {
        'success': True,
        'file_path': file_path,
        'sections_ingested': len(sections)
    }
```

---

## CLI Interface

```bash
# Ingest with validation (default)
imem ingest 251024-1259_auth.md

# Skip validation (for legacy docs)
imem ingest 251024-1259_auth.md --no-validate

# Validate without ingesting
imem validate 251024-1259_auth.md
```

```python
# imem/src/imem/cli.py

@imem.command()
@click.argument('file_path', type=click.Path(exists=True))
@click.option('--no-validate', is_flag=True, help='Skip template validation')
def ingest(file_path, no_validate):
    """Ingest changelog file into knowledge base"""
    from imem.ingest import ingest_changelog

    result = ingest_changelog(file_path, validate=not no_validate)

    if result['success']:
        click.echo(f"✓ Ingested {result['sections_ingested']} sections from {file_path}")
    else:
        click.echo(f"✗ Validation failed for {file_path}:", err=True)
        for error in result['errors']:
            click.echo(f"  - {error['section_type']}: {error['section_name']}", err=True)
            click.echo(f"    Missing: {', '.join(error['missing_required'])}", err=True)
        sys.exit(1)


@imem.command()
@click.argument('file_path', type=click.Path(exists=True))
def validate(file_path):
    """Validate changelog against template schema"""
    from imem.templates.validator import TemplateValidator
    from imem.templates.schema import TEMPLATE_SCHEMA

    with open(file_path) as f:
        content = f.read()

    validator = TemplateValidator(TEMPLATE_SCHEMA)
    results = validator.validate_document(content)

    all_valid = True
    for section_type, section_results in results.items():
        click.echo(f"\n{section_type}:")
        for result in section_results:
            if result.valid:
                click.echo(f"  ✓ {result.section_name}")
            else:
                click.echo(f"  ✗ {result.section_name}")
                click.echo(f"    Missing: {', '.join(result.missing_required)}")
                all_valid = False

    if all_valid:
        click.echo(f"\n✓ All sections valid")
    else:
        click.echo(f"\n✗ Validation failed")
        sys.exit(1)
```

---

## Example Usage

### Valid Document

```markdown
## Decisions
### Use JWT Authentication
- **Context**: Session-based auth doesn't scale horizontally
- **Solution**: Migrate to stateless JWT tokens with 15min expiry
- **Rationale**: Enables load balancing without sticky sessions
```

```bash
$ imem validate doc.md
Decisions:
  ✓ Use JWT Authentication

✓ All sections valid

$ imem ingest doc.md
✓ Ingested 1 sections from doc.md
```

Metadata extracted:
```json
{
  "section_type": "Decisions",
  "section_name": "Use JWT Authentication",
  "has_context": true,
  "has_solution": true,
  "has_rationale": true,
  "has_alternatives": false,
  "content": "..."
}
```

### Invalid Document

```markdown
## Decisions
### Use JWT Authentication
- **Solution**: Migrate to stateless JWT tokens
```

```bash
$ imem validate doc.md
Decisions:
  ✗ Use JWT Authentication
    Missing: Context

✗ Validation failed

$ imem ingest doc.md
✗ Validation failed for doc.md:
  - Decisions: Use JWT Authentication
    Missing: Context
```

Document rejected until Context added.

---

## Query Examples

### Guaranteed Field Queries

```python
# All decisions have context and solution (guaranteed)
results = search("authentication", filters={
    'section_type': 'Decisions',
    'has_context': True,   # Always true (or rejected at ingestion)
    'has_solution': True   # Always true (or rejected at ingestion)
})
```

### Optional Field Queries

```python
# Only decisions with alternatives considered
results = search("authentication", filters={
    'section_type': 'Decisions',
    'has_alternatives': True  # May be false (optional field)
})

# All decisions (regardless of optional fields)
results = search("authentication", filters={
    'section_type': 'Decisions'
})
```

---

## File Structure

```
imem/
├── src/imem/
│   ├── templates/
│   │   ├── __init__.py
│   │   ├── schema.py       (NEW - ~50 lines)
│   │   ├── validator.py    (NEW - ~150 lines)
│   │   └── extractor.py    (NEW - ~100 lines)
│   ├── ingest.py           (UPDATE - add validation)
│   └── cli.py              (UPDATE - add validate command)
└── tests/
    └── test_templates.py   (NEW - ~200 lines)
```

---

## Testing

```python
# tests/test_templates.py

def test_valid_decision_section():
    """Test valid decision with all required fields"""
    content = """
## Decisions
### Use JWT Auth
- **Context**: Session auth doesn't scale
- **Solution**: Migrate to JWT
"""
    validator = TemplateValidator(TEMPLATE_SCHEMA)
    results = validator.validate_document(content)

    assert len(results['Decisions']) == 1
    assert results['Decisions'][0].valid
    assert results['Decisions'][0].missing_required == []


def test_invalid_decision_missing_context():
    """Test invalid decision missing required Context"""
    content = """
## Decisions
### Use JWT Auth
- **Solution**: Migrate to JWT
"""
    validator = TemplateValidator(TEMPLATE_SCHEMA)
    results = validator.validate_document(content)

    assert len(results['Decisions']) == 1
    assert not results['Decisions'][0].valid
    assert 'Context' in results['Decisions'][0].missing_required


def test_metadata_extraction():
    """Test deterministic metadata extraction"""
    content = """
## Decisions
### Use JWT Auth
- **Context**: Session auth doesn't scale
- **Solution**: Migrate to JWT
- **Rationale**: Enables load balancing
"""
    extractor = MetadataExtractor(TEMPLATE_SCHEMA)
    sections = extractor.extract_document_metadata(content, 'test.md')

    assert len(sections) == 1
    assert sections[0]['section_type'] == 'Decisions'
    assert sections[0]['has_context'] is True
    assert sections[0]['has_solution'] is True
    assert sections[0]['has_rationale'] is True
    assert sections[0]['has_alternatives'] is False
```

---

## The Key Implementation Insight

Validation = pattern matching, not LLM.
- Regex for bold fields
- String matching for field names
- 100% deterministic

Metadata = guaranteed or rejected.
- Required fields enforced at ingestion
- Optional fields tracked as booleans
- Enables reliable queries

Quality at creation, not extraction.
