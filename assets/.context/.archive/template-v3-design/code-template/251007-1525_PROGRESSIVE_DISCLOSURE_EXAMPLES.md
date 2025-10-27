# Progressive Disclosure Examples

This document shows how field counts vary naturally across our trimmed examples.

---

## Security Guardrails (250819-1304)

### Decision 1: Use Official Rate Limiting (5 fields - Complex)
- Context
- Solution
- Alternatives
- Rationale
- Implications

### Decision 2: Upstash Redis Integration (3 fields - Standard)
- Context
- Solution
- Alternatives

### Decision 3: Hard Block Approach (2 fields - Simple)
- Context
- Solution

**Progressive disclosure in action:** Same section, three items with 5/3/2 fields respectively.

---

## Vercel Deployment (250811-1811)

### Decision 1: Fix Execution Order Violation (5 fields - Complex)
- Context
- Solution
- Alternatives
- Rationale
- Implications

### Decision 2: Deploy from Branch (2 fields - Simple)
- Context
- Solution

**Progressive disclosure in action:** Same section, two items with 5/2 fields respectively.

---

## Constraint Examples

### Vercel Deployment - Framework Constraint (4 fields)
- What
- Discovery
- Workaround
- Impact

### Security Guardrails - (Could add with 6 fields if needed)
- What
- Discovery
- Why Non-Obvious
- Workaround
- Impact
- Testing

**Flexibility:** Use 4 fields for straightforward constraints, 6 for complex ones.

---

## Failures Section (New)

### Vercel Deployment - Simple Failure (3 fields)
- Attempted
- Why Failed
- Lesson

**Could be expanded to 6 fields for complex failures:**
- Attempted
- Hypothesis
- Failure Mode
- Discovery
- Lesson
- Alternative

---

## The Pattern

**Within each section, items vary:**
- Simple items: 2-3 fields
- Standard items: 3-4 fields
- Complex items: 5-6 fields

**Same structure, natural variation.**

No rigid rules - use fields that add value.

---

## Field Progression Guide

### Decisions
- **Always**: Context, Solution
- **Often**: Alternatives
- **When valuable**: Rationale, Trade-offs, Implications

### Constraints
- **Always**: What, Discovery, Workaround, Impact
- **When valuable**: Why Non-Obvious, Testing

### Failures
- **Always**: Attempted, Why Failed, Lesson
- **When valuable**: Hypothesis, Failure Mode, Discovery, Alternative

### Patterns
- **Always**: Pattern, When, Approach
- **When valuable**: Why, Benefit, Anti-Pattern, Occurrences

---

This is progressive disclosure - the template adapts to the work, not vice versa.
