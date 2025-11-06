# .vision/ Pattern - User's Own Words

## Purpose
Capture user's exact statements without AI interpretation. Anti-drift anchor.

## Structure
```
.design/.vision/
└── user-messages.md    # Chronological entries, nothing else
```

## Format
```markdown
## YYMMDD-HHMM
> [user's exact words]

## YYMMDD-HHMM
> [user's exact words]
```

## Example
```markdown
## 251007-1530
> I want to standardize documentation handling across projects using the design/develop/document pattern. For advisory-board, the omega point is my actual life and decisions, not code.

## 251007-1545
> We should allow for natural disclosure of complexity. Start with just document/architecture, only refactor into business-logic and schemas when the mixing creates pain.

## 251007-1557
> For vision I think we'll keep it lean. Just user messages. Simple timestamp and user's message. Nothing else. Keep it lean.
```

## Rules
- ✅ Timestamp + user's exact words
- ❌ NO AI interpretation
- ❌ NO categorization
- ❌ NO summaries
- ❌ NO organization beyond chronological

## When to Capture
- User states core principles
- User clarifies intent after AI misunderstanding
- User defines success/values
- User sets constraints or boundaries
- Any statement user might need to reference later

## How AI Uses It
When AI drifts or needs to understand user's true intent:
1. Read `.vision/user-messages.md`
2. Find user's original words
3. Re-align with user's actual statement
