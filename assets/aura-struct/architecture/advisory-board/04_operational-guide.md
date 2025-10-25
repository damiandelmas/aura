---
schema_version: "1.0"
type: "operational-guide"
audience: "ai-agents"
---

# Operational Guide for AI Agents

## How to Support Decisions

### Understanding Context
1. **Always read first**: `01_context-and-state.md`
2. **Check recent changes**: `.develop/.changes/` (last 5 entries)
3. **Review active patterns**: `.develop/.modules/` (current experiments)
4. **Understand decision trees**: `02_decision-framework.md`

### Research Strategy
**For [scenario type]**:
```
1. Check: [what to look for in context]
2. Search: [what to grep for in .develop/.changes]
3. Review: [which .develop/.modules relevant]
4. Apply: [which decision framework section]
```

**For [scenario type]**:
```
1. Check: [what to look for]
2. Search: [where to search]
3. Consider: [what factors matter]
```

## Common Scenarios

### Scenario: [Type of decision]
**Agent workflow**:
1. Gather context from: [sources]
2. Check constraints: [what limitations apply]
3. Review outcomes: [past similar decisions]
4. Present options: [decision tree format]
5. Document decision: [where to record]

### Scenario: [Type of decision]
**Agent workflow**:
1. Research: [what to investigate]
2. Analyze: [what to compare]
3. Recommend: [how to present]

## What to Search For

### [Domain] decisions
- Keywords: `[term]`, `[term]`, `[term]`
- Files: `.develop/.changes/*[pattern]*`
- Modules: `.develop/.modules/[module-name]/`
- Framework: `02_decision-framework.md` section "[section]"

### [Domain] decisions
- Keywords: `[term]`, `[term]`
- Historical patterns: [where to look]
- Current constraints: [what matters]

## Agent Patterns

### Pattern: Supporting [Activity]
```
1. Context gathering: [what to read]
2. Pattern matching: [what to compare to]
3. Constraint checking: [what limitations exist]
4. Option generation: [how to present choices]
5. Decision capture: [where to document]
```

### Pattern: Supporting [Activity]
```
1. Research phase: [what to investigate]
2. Analysis phase: [what to evaluate]
3. Recommendation phase: [how to advise]
```

## Common Failure Modes

### Anti-pattern: [What doesn't work]
- **Why it fails**: [reason]
- **What to do instead**: [correct approach]
- **How to recognize**: [warning signs]

### Anti-pattern: [What doesn't work]
- **Why it fails**: [reason]
- **What to do instead**: [correct approach]

## Communication Patterns

### When presenting options
- Format: [how to structure]
- Include: [what context needed]
- Exclude: [what's noise]

### When documenting decisions
- Location: `.develop/.changes/[YYMMDD-HHMM]_[description].md`
- Format: [structure to use]
- Extract: [what goes to .document/]

## Continuous Learning

### From each interaction
- Update `01_context-and-state.md` if: [conditions]
- Update `02_decision-framework.md` if: [conditions]
- Update `03_mental-models.md` if: [conditions]
- Create `.develop/.modules/` if: [conditions]

### Pattern recognition
- Watch for: [what signals new pattern]
- Document in: [where to capture]
- Validate by: [how to confirm]
