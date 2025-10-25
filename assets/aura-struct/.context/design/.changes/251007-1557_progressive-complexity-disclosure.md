---
type: "design"
timestamp: "2025-10-07T15:57:00-07:00"
---

# Progressive Complexity Disclosure Pattern

## Question
> "How should we organize .document/ layer - start with full schemas/business-logic/architecture split, or evolve naturally?"

## Key Insight
**Start simple. Refactor when pain emerges, not preemptively.**

## Pattern

### Default (Start Here)
```
.document/architecture/
├── 01_context-and-state.md
├── 02_decision-framework.md
├── 03_mental-models.md
└── 04_operational-guide.md
```

### Refactor Triggers

**Extract schemas/ when:**
- AI agents modify immutable facts (rate, team, agreements)
- Ground truth gets accidentally changed
- Signal: "We can't just change that - Jesse agreed to X"

**Extract business-logic/ when:**
- Workflows become complex, need isolation
- Proven patterns emerge
- Signal: "The HOW is drowning out the WHY"

## Outcome
Keep 4 docs in `architecture/` initially. Let complexity reveal itself naturally. Same principle as code: don't optimize until you feel the pain.

## References
- NPTA ground-truth/ (schemas example)
- Barbar business-logic/ (workflows example)
- YAGNI principle (You Ain't Gonna Need It)
