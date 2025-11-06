# Changelog META Template

Universal pattern for documenting changes across CODE, BUSINESS, IDEATION, PHILOSOPHY, etc.

## Core Structure (Domain-Agnostic)

```yaml
---
schema_version: "v3_adaptive"
type: "[domain].[category]"
status: "[completed|in-progress|archived]"
keywords: "[searchable terms]"
timestamp: "[ISO-8601]"
---

# [Title: What Changed/Was Decided/Was Discovered]

## Request
> "[Original trigger: user question, problem statement, why this happened]"

## Overview
[Executive summary: What is this? Why does it matter? What's the key insight?]

## [OUTCOMES]
### [Specific Outcome 1]
- **Context**: [What led to this]
- **[Solution/Conclusion/Discovery]**: [What was decided/found]
- **Rationale**: [Why this approach]
- **[Alternatives/Trade-offs]**: [What else was considered]
- **Implications**: [What this means going forward]

### [Specific Outcome 2]
[Same structure]

## [EXECUTION]
### [Implementation/Application/Next Steps]
[How to actually do this, apply this, or what happens next]

## Constraints
### [Discovered Limitation]
- **What**: [Description of constraint]
- **Impact**: [How this affects things]
- **Workaround**: [How to work within it]
- **Why Non-Obvious**: [Why this wasn't apparent initially]

## Patterns
### [Reusable Pattern Name]
- **Pattern**: [General principle extracted]
- **When**: [Conditions where this applies]
- **Approach**: [How to apply it]
- **Why**: [Underlying reason it works]
- **Benefit**: [Value of using this pattern]
- **Anti-Pattern**: [What NOT to do]

## [VALIDATION]
### [Audit/Evidence/Context]
[Complete context snapshot, evidence, measurements, etc.]
```

---

## Domain Instantiations

### CODE (Technical Changes)
```yaml
type: "code.[refactor|feature|bugfix|architecture]"
```

**OUTCOMES** → **Implementation**
**EXECUTION** → **Code Changes**
**VALIDATION** → **Files Changed**

Example sections:
- Implementation: Technical decisions made
- Code Changes: Actual code modifications
- Files Changed: List of affected files
- Test Coverage: Validation approach

---

### BUSINESS (Strategic Decisions)
```yaml
type: "business.[strategy|negotiation|relationship|operations]"
```

**OUTCOMES** → **Decisions**
**EXECUTION** → **Implementation**
**VALIDATION** → **Audit**

Example sections:
- Decisions: Strategic choices made
- Implementation: Action plans and scripts
- Audit: Evidence, metrics, context

---

### IDEATION (Design Exploration)
```yaml
type: "design.[research|exploration|prototype|architecture]"
```

**OUTCOMES** → **Insights**
**EXECUTION** → **Next Exploration**
**VALIDATION** → **Research Evidence**

Example sections:
- Insights: What was discovered
- Next Exploration: Follow-up questions
- Research Evidence: Sources, data, examples

---

### PHILOSOPHY (Conceptual Insights)
```yaml
type: "philosophy.[ethics|epistemology|ontology|metaphysics]"
```

**OUTCOMES** → **Conclusions**
**EXECUTION** → **Applications**
**VALIDATION** → **Arguments**

Example sections:
- Conclusions: Philosophical positions taken
- Applications: How this applies to practice
- Arguments: Reasoning and evidence

---

## Translation Layer

| META Component | CODE | BUSINESS | IDEATION | PHILOSOPHY |
|----------------|------|----------|----------|------------|
| **OUTCOMES** | Implementation | Decisions | Insights | Conclusions |
| **EXECUTION** | Code Changes | Action Plans | Next Steps | Applications |
| **VALIDATION** | Files Changed | Audit | Evidence | Arguments |

## Required Components (Universal)

1. **Metadata** (YAML) - Always required
2. **Title** - What changed/was decided
3. **Request** - Original trigger
4. **Overview** - Executive summary
5. **Constraints** - Discovered limitations
6. **Patterns** - Reusable insights

## Optional Components (Context-Dependent)

- **Failures** - What didn't work (learning documentation)
- **Alternatives** - What else was considered
- **Timeline** - When things happened
- **References** - External sources

## Core Principles

1. **User-Validated Ground Truth** - Created/confirmed by user, not AI speculation
2. **Searchable** - Keywords enable discovery
3. **Reusable** - Patterns section extracts wisdom
4. **Complete** - Audit/validation provides full context
5. **Temporal** - Timestamp anchors when this happened
6. **Categorized** - Type enables filtering by domain

## Usage Pattern

1. AI encounters significant change/decision/insight
2. Extract into appropriate domain template
3. User validates content
4. File created in `.design/.changes/` or `.develop/.changes/`
5. PULSE reads changelogs → updates `.document/`
