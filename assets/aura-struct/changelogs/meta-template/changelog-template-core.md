# Changelog Template - Core Pattern

## Universal Structure

```yaml
---
schema_version: "v3_adaptive"
type: "[domain].[category]"
status: "[completed|in-progress|archived]"
keywords: "[searchable-terms]"
timestamp: "[ISO-8601]"
---

# [What Changed/Decided/Discovered]

## Request
> "[Original trigger/question]"

## Overview
[Executive summary in 2-3 sentences]

## [OUTCOMES - domain-specific name]
### [Outcome Name]
- **Context**: What led here
- **Solution/Conclusion**: What was decided
- **Rationale**: Why this way
- **Alternatives**: What else considered (optional)
- **Implications**: What this means forward

## [EXECUTION - domain-specific name]
[How to apply/implement/what happens next]

## Constraints
### [Discovered Limitation]
- **What**: Description
- **Impact**: How affects things
- **Workaround**: How to work within it
- **Why Non-Obvious**: Why wasn't apparent initially (optional)

## Patterns
### [Reusable Pattern]
- **Pattern**: General principle
- **When**: Conditions where applies
- **Approach**: How to apply
- **Why**: Underlying reason
- **Benefit**: Value of using
- **Anti-Pattern**: What NOT to do (optional)

## [VALIDATION - domain-specific name]
[Evidence, audit, context, measurements]
```

## Domain Translations

| Component | CODE | BUSINESS | IDEATION | PHILOSOPHY |
|-----------|------|----------|----------|------------|
| OUTCOMES | Implementation | Decisions | Insights | Conclusions |
| EXECUTION | Code Changes | Action Plans | Next Steps | Applications |
| VALIDATION | Files Changed | Audit | Evidence | Arguments |

## Core Principles

1. **User-Validated** - Created/confirmed by user
2. **Searchable** - Keywords enable discovery  
3. **Reusable** - Patterns extract wisdom
4. **Complete** - Validation provides full context
5. **Temporal** - Timestamp anchors when
6. **Categorized** - Type enables filtering

## Required Sections

- Metadata (YAML)
- Request
- Overview
- Constraints
- Patterns

## Optional Sections

- Failures (what didn't work)
- Alternatives (what else considered)
- Timeline (when things happened)
- References (external sources)
