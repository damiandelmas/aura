---
session_id: ca22384b-3a6d-4821-8b70-2aa1a89ea4ba
date: 2025-10-27
level: architecture-pattern
innovation: creation-time-schema
---

# Creation-Time Schema: Architecture Pattern

## Core Mechanism

**Templates define required structure before document creation:**

1. **Template distribution:** `aura init` deploys templates to `.context/`
2. **User creation:** Documents follow template structure
3. **Ingestion validation:** Reject documents missing required fields
4. **Guaranteed metadata:** All indexed chunks have deterministic fields

**Template structure:**
```markdown
# Template: .context/develop/.template.md

## Decisions
### [Title]
- **Context**: (REQUIRED - Why this decision arose)
- **Solution**: (REQUIRED - What was decided)
- **Rationale**: (REQUIRED - Why this approach)
- **Alternatives**: (OPTIONAL - Other options considered)
- **Constraints**: (OPTIONAL - Discovered limitations)
```

## Validation Architecture

**Three enforcement points:**

**Point 1: Creation (softest)**
- Template provides structure
- User follows or doesn't
- No hard enforcement

**Point 2: Ingestion (critical)**
- Parse document structure
- Detect required fields
- Reject if missing
- Log validation errors

**Point 3: Query (guaranteed)**
- All indexed documents passed validation
- Metadata queries are deterministic
- `filter(has_context=true)` reliable

## Metadata Extraction

**Field detection during parsing:**

```
Parse H3 section: "### Use JWT Authentication"

Check for required subfields:
- **Context**: present → has_context = true
- **Solution**: present → has_solution = true
- **Rationale**: missing → has_rationale = false
- **Alternatives**: present → has_alternatives = true

If required fields missing:
→ Reject document
→ Prompt user to complete template
```

**Resulting metadata:**
```json
{
  "section_type": "Decisions",
  "section_name": "Use JWT Authentication",
  "has_context": true,
  "has_solution": true,
  "has_rationale": false,  // REQUIRED but missing
  "has_alternatives": true,
  "validation_status": "incomplete"  // Reject
}
```

## Template Evolution

**Schema changes over time:**

```
Version 1 Template:
- Context (required)
- Solution (required)

Version 2 Template:
- Context (required)
- Solution (required)
- Rationale (required) ← NEW

Migration:
- Existing documents: Grandfather (validation warnings)
- New documents: Full compliance required
- Metadata: version field tracks template
```

## Competitive Moat

**Why competitors can't copy:**

**MindsDB/Azure approach:**
```
Input: Any document structure
Process: LLM extraction
Result: Probabilistic metadata
```

**AURA approach:**
```
Input: Template-compliant documents only
Process: Deterministic parsing
Result: Guaranteed metadata
```

**Switching cost:**
- MindsDB → AURA: Adopt templates (additive)
- AURA → MindsDB: Lose guarantees (destructive)

**Barrier for competitors:**
- Existing users have unstructured data
- Requiring templates = breaking change
- Migration = high friction

**AURA advantage:**
- Clean start (no legacy)
- Templates = norm from day 1
- Guarantees compound over time

## Template-as-Schema Properties

**Human-readable:**
- Markdown, not JSON
- Self-documenting
- Git-friendly diffs

**AI-friendly:**
- LLMs understand markdown structure
- No special tooling needed
- Context-aware completion

**Version-controlled:**
- Templates in git
- Schema changes visible in commits
- Rollback capability

**Progressive:**
- Start simple (few required fields)
- Add fields as needed
- Backward compatibility via versioning

## Key Architectural Decisions

1. **Reject incomplete documents** (not warn)
   - Ensures metadata reliability
   - Forces compliance

2. **Templates in git** (not database)
   - Version-controlled schemas
   - Human-editable
   - No external tooling

3. **Markdown structure** (not JSON Schema)
   - Readable by humans and LLMs
   - Self-documenting
   - Git-native

4. **Creation-time enforcement** (not post-hoc)
   - Guarantees before indexing
   - Enables deterministic queries
   - Prevents garbage-in-garbage-out
