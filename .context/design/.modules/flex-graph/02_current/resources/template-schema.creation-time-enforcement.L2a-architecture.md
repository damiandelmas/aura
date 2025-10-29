# Template Schema: Architecture Pattern

**Session:** a86bc733-c4e3-4d88-b17f-2f9e330ca11a
**Level:** Architecture Pattern (L2a)
**Date:** 2025-10-27

## Schema Definition

Templates define two tiers:

### Tier 1: Required Fields (MUST be present)

```yaml
Decisions:
  required:
    - Context
    - Solution
  optional:
    - Rationale
    - Alternatives
    - Benefits
    - Drawbacks

Constraints:
  required:
    - Description
    - Impact
  optional:
    - Mitigation
    - Workaround

Failures:
  required:
    - Issue
    - Root Cause
  optional:
    - Resolution
    - Prevention
```

Validation: Required fields missing → reject document

### Tier 2: Structural Requirements

```
H2 (##) → Section type (Decisions/Constraints/Patterns/Implementation)
H3 (###) → Section name
Bold (**field**) → Metadata fields
```

Validation: Structure invalid → reject document

## Validation Algorithm

```
For each H3 section:
  1. Identify parent H2 (section_type)
  2. Extract section name from H3 text
  3. Extract bold fields from section content
  4. Check required fields present
  5. Record optional fields present

If all required fields present:
  → Ingest with metadata
Else:
  → Reject with error specifying missing fields
```

## Metadata Extraction (Deterministic)

```
Input: Template-compliant markdown
Process: Pattern matching (not LLM)
Output: Guaranteed metadata

Example:
## Decisions
### Use JWT Authentication
- **Context**: Session auth doesn't scale
- **Solution**: Migrate to stateless JWT

Extracted metadata:
{
  "section_type": "Decisions",
  "section_name": "Use JWT Authentication",
  "has_context": true,
  "has_solution": true,
  "has_rationale": false,  // Optional field absent
  "content": "...",
  "file_path": "...",
  "timestamp": "..."
}
```

No LLM. No guessing. Regex + string matching.

## Validation Feedback

```
Input document with missing fields:

## Decisions
### Use JSONB
- **Solution**: Store provider data in JSONB column

Validation error:
{
  "valid": false,
  "section": "Use JSONB",
  "section_type": "Decisions",
  "missing_required": ["Context"],
  "message": "Missing required field: Context"
}

Document rejected. User must add Context before ingestion.
```

Immediate feedback → quality improvement.

## Two-Tier Query Model

### Tier 1: Guaranteed Fields

```python
# Always works (required fields guaranteed)
results = search(
    "authentication",
    filters={
        'section_type': 'Decisions',
        'has_context': True,      # ← Always true for Decisions
        'has_solution': True      # ← Always true for Decisions
    }
)
```

### Tier 2: Optional Field Filtering

```python
# Filter by optional field presence
results = search(
    "authentication",
    filters={
        'section_type': 'Decisions',
        'has_alternatives': True  # ← Only returns decisions with alternatives
    }
)

# Query all decisions (regardless of optional fields)
results = search(
    "authentication",
    filters={'section_type': 'Decisions'}
    # No has_alternatives filter → returns all decisions
)
```

Deterministic queries enabled by deterministic metadata.

## Comparison: Post-Hoc vs Creation-Time

### Post-Hoc Extraction (MindsDB/Azure)

```
Ingestion:
  Accept any markdown → LLM extraction → best-effort metadata

Metadata reliability:
  "context": ~80% (LLM sometimes finds it)
  "solution": ~85% (LLM usually finds it)
  "rationale": ~60% (LLM often misses it)

Query reliability:
  filter(has_context=True) → Returns ~80% of docs that have context
  false negatives: 20% of docs with context not returned (LLM missed it)
```

### Creation-Time Enforcement (AURA)

```
Ingestion:
  Validate structure → Enforce required fields → Guaranteed metadata

Metadata reliability:
  "context": 100% (or document rejected)
  "solution": 100% (or document rejected)
  "rationale": 0% or 100% (tracked as has_rationale boolean)

Query reliability:
  filter(has_context=True) → Returns 100% of docs with context
  false negatives: 0% (metadata guaranteed)
```

## Template Evolution

```
v1 Template:
  Decisions required: Context, Solution

v2 Template (future):
  Decisions required: Context, Solution, Impact
  Migration: Existing docs grandfathered, new docs validated to v2

Git diff shows:
  +- **Impact**: High

Structural change visible in version control.
```

Templates versioned like code. Changes tracked. Migration explicit.

## Ingestion Pipeline

```
Markdown File
    ↓
Template Validation
    ↓ (if valid)
Section Extraction (H2/H3 parsing)
    ↓
Metadata Extraction (bold field detection)
    ↓
Required Field Validation
    ↓ (if complete)
Vector Embedding (E5-Large-v2)
    ↓
Qdrant Upsert (with guaranteed metadata)
    ✓ Success

    ↓ (if invalid at any step)
Rejection + Error Feedback
    ✗ Fail
```

Quality gate: Invalid docs don't enter the system.

## Metadata Schema (Qdrant Payload)

```json
{
  "content": "### Use JWT Authentication\n- **Context**: ...",
  "section_type": "Decisions",
  "section_name": "Use JWT Authentication",
  "file_path": "251024-1259_auth.md",
  "session_id": "abc-123-xyz",
  "timestamp": "2025-10-24T12:59:00",
  "phase": "develop",
  "layer": "application",

  // Required field tracking (guaranteed present)
  "has_context": true,
  "has_solution": true,

  // Optional field tracking (may be false)
  "has_rationale": true,
  "has_alternatives": false,
  "has_benefits": false,
  "has_drawbacks": false
}
```

Every field guaranteed present. Optional fields tracked as booleans.

## Interface Contracts

```
ITemplateValidator:
  validate(content: Markdown) → ValidationResult
  extract_metadata(content: Markdown) → Metadata
  check_required_fields(section: Section, schema: Schema) → bool

IIngestionPipeline:
  ingest(file_path: Path) → Result
  reject(file_path: Path, error: ValidationError) → void

IMetadataSchema:
  required_fields: Dict[SectionType, List[Field]]
  optional_fields: Dict[SectionType, List[Field]]
  field_extractors: Dict[Field, Regex]
```

## Architectural Properties

**Deterministic:** Metadata extraction via pattern matching, not LLM
**Reliable:** 100% accuracy or rejection
**Queryable:** Guaranteed fields enable reliable filtering
**Evolvable:** Template versioning + migration support
**Discoverable:** Validation errors guide quality improvement

## The Key Design Decision

Quality at creation, not extraction.

Post-hoc: Accept anything, extract what you can (probabilistic)
AURA: Enforce structure, guarantee metadata (deterministic)

Foundation for soft-graph, bundling, and all query operations.
