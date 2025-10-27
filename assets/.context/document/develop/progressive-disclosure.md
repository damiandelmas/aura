# Progressive Disclosure Methodology

## Core Principle

**The template adapts to the work, not vice versa.**

Use fields and sections that add value. Skip what doesn't.

## Natural Variation

### Within Same Changelog

```markdown
## Decisions

### Decision 1: Simple Choice (2 fields)
- **Context**: Port 6333 conflicted with MongoDB
- **Solution**: Changed to 6334

### Decision 2: Complex Choice (5 fields)
- **Context**: Rate limiting needed to prevent abuse
- **Solution**: Implemented Upstash Redis sliding window
- **Alternatives**: In-memory (rejected - not persistent), database (rejected - too slow)
- **Rationale**: Redis provides persistence + speed
- **Implications**: All API routes need rate limit middleware

### Decision 3: Standard Choice (3 fields)
- **Context**: Email validation failing on edge cases
- **Solution**: Used library zod for schema validation
- **Alternatives**: Custom regex (rejected - incomplete coverage)
```

**This is correct.** Complexity follows decisions, not template rules.

## Field Progression

### Decisions

**Always use:**
- **Context** - Why this decision point arose
- **Solution** - What was chosen

**Add when valuable:**
- **Alternatives** - Other options considered (with rejection reasons)
- **Rationale** - Technical reasoning if not obvious
- **Trade-offs** - What was sacrificed or compromised
- **Implications** - Future impact or when to revisit

**Variation:**
- Simple decisions: 2 fields
- Standard decisions: 3-4 fields
- Complex decisions: 5-6 fields

### Constraints

**Always use:**
- **What** - The limitation discovered
- **Discovery** - How it was found
- **Workaround** - How it was handled
- **Impact** - What this affects

**Add when valuable:**
- **Why Non-Obvious** - If it wasn't documented/expected
- **Testing** - How the workaround was validated

**Variation:**
- Standard constraints: 4 fields
- Detailed constraints: 6 fields

### Failures

**Always use:**
- **Attempted** - What was tried
- **Why Failed** - What broke or didn't work
- **Lesson** - What was learned

**Add when valuable:**
- **Hypothesis** - Why you thought it would work
- **Failure Mode** - How exactly it failed
- **Discovery** - How you found out
- **Alternative** - What you did instead

**Variation:**
- Simple failures: 3 fields
- Detailed failures: 7 fields

### Patterns

**Always use:**
- **Pattern** - The reusable solution
- **When** - When to apply this pattern
- **Approach** - How to implement it
- **Benefit** - What you gain

**Add when valuable:**
- **Why** - Rationale if not obvious
- **Anti-Pattern** - What NOT to do
- **Occurrences** - Where else this appears

**Variation:**
- Standard patterns: 4 fields
- Detailed patterns: 7 fields

## Section Inclusion

### Always Include

- **Request** - User quote/trigger
- **Overview** - Language-agnostic narrative
- **Audit** - File operations

### Include When Relevant

| Section | Include When |
|---------|-------------|
| **Decisions** | Strategic choices made with alternatives |
| **Constraints** | Limitations or blockers discovered |
| **Failures** | Approaches didn't work (prevents repeating) |
| **Implementation** | Technical details worth preserving |
| **Patterns** | Reusable insights emerged |

### Skip When

- Section adds no value beyond what's documented
- Information is obvious or trivial
- Content would just repeat other sections

## Complexity Spectrum

### Minimal (40-60 lines)

**Example:** Bug fix, config change
```
Request + Overview + 1 Decision (2 fields) + Audit
```

**Real example:** PH Domain Exclusion (44 lines)

### Simple (55-80 lines)

**Example:** Small feature, UI refinement
```
Request + Overview + 2-3 Decisions (variable fields) + Implementation + Audit
```

**Real examples:**
- Composer Bar Refinements (58 lines)
- Mobile Subdomain Redirect (75 lines)

### Standard (110-130 lines)

**Example:** Typical feature with discoveries
```
Request + Overview + Multiple Decisions + Constraints + Implementation + Audit
```

**Real examples:**
- Vercel Deployment (114 lines)
- Security Guardrails (128 lines)

### Complex (150-171 lines)

**Example:** Major feature with all section types
```
Request + Overview + Multiple Decisions + Constraints + Failures + Implementation + Patterns + Audit
```

**Real examples:**
- Email Update Tool (150 lines)
- Voice Input (159 lines)
- API Simplification (171 lines)

## Field Selection Logic

### Ask: "Does this field add value?"

**Yes → Include it**
```markdown
- **Alternatives**: Tried MiniLM (rejected - 40% accuracy loss vs E5-Large)
```
This prevents repeating the same mistake.

**No → Skip it**
```markdown
- **Alternatives**: N/A
```
Don't write "N/A". Just omit the field.

### Ask: "Is this obvious from context?"

**Not obvious → Include Rationale**
```markdown
- **Rationale**: Redis provides persistence across restarts unlike in-memory solutions
```

**Obvious → Skip Rationale**
If Context + Solution make it clear, Rationale is redundant.

### Ask: "Will this affect future work?"

**Yes → Include Implications**
```markdown
- **Implications**: All new API routes must include rate limit middleware
```

**No → Skip Implications**
One-time fix with no future considerations.

## Real Examples

### Security Guardrails (Progressive Fields)

**Decision 1 (5 fields)** - Complex choice:
- Context, Solution, Alternatives, Rationale, Implications

**Decision 2 (3 fields)** - Standard choice:
- Context, Solution, Alternatives

**Decision 3 (2 fields)** - Simple choice:
- Context, Solution

**Why:** Each decision has different complexity. Template adapts naturally.

### Voice Input (All Section Types)

**Sections used:**
- Request, Overview
- 4 Decisions (varying 2-5 fields each)
- 3 Constraints
- 2 Failures
- Implementation (Architecture + Code Signatures)
- 1 Pattern
- Audit

**Why:** Major feature with discoveries, constraints, and reusable patterns.

### PH Domain Exclusion (Minimal)

**Sections used:**
- Request, Overview
- 1 Decision (3 fields)
- Implementation (Code Signature only)
- Audit

**Why:** Simple bug fix. No constraints or patterns. Minimal but complete.

## LlamaIndex Compatibility

**Progressive disclosure doesn't break parsing:**

- Missing sections → No nodes created (fine)
- Optional fields → Included in node text if present (fine)
- Different field counts → Parser treats as text (fine)

**HTML comments in template:**
```markdown
<!-- Add more fields if relevant:
- **Rationale**: Technical reasoning if not obvious
-->
```

AI sees guidance. Doesn't copy comments to actual changelogs. No pollution.

## Anti-Patterns

### ❌ Rigid Field Requirements
```
"Every decision MUST have exactly 6 fields"
```
**Why wrong:** Simple decisions don't need Alternatives/Trade-offs/Implications.

### ❌ N/A Placeholders
```markdown
- **Alternatives**: N/A
- **Trade-offs**: N/A
```
**Why wrong:** Just omit the fields. Don't write placeholder text.

### ❌ Documenting Everything
```markdown
## Patterns
### Standard Function Call Pattern
- **Pattern**: Call functions to execute logic
- **When**: When you need to run code
```
**Why wrong:** Trivial "pattern" adds no value. Skip the section.

### ❌ Copying Full Code
```markdown
### Implementation
[Paste 200 lines of complete file]
```
**Why wrong:** Use Code Signatures showing key patterns, not exhaustive listings.

## Validation

**Progressive disclosure is working when:**

1. **Same changelog has varying field counts** (2-6 fields per item)
2. **Sections appear only when valuable** (not every changelog has Patterns)
3. **Simple work = short changelogs** (~40-60 lines)
4. **Complex work = detailed changelogs** (~150-170 lines)
5. **No N/A placeholders** (fields are present or absent, not marked N/A)
6. **Complexity matches work** (bug fix isn't 150 lines, major feature isn't 44 lines)

## Philosophy

**Form follows function.**

The template provides structure, not prescription. Complexity emerges from the work itself, not from template compliance.

Simple work deserves simple documentation. Complex work deserves detailed documentation. The template supports both without forcing either.

**Value over completeness.** Document what matters. Skip what doesn't.
