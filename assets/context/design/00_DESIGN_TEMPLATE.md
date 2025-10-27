# Design Changelog Template

**Version:** v1_exploration
**Last Updated:** 2025-10-22
**Purpose:** Design thinking changelog template for `.context/design/.changes/`

---

## Template

```markdown
---
schema_version: "v1_exploration"
type: "exploration.specific-topic"
status: "exploring"  # or "decided", "rejected", "archived"
keywords: "space-separated keywords for-search indexing"
timestamp: "YYYY-MM-DDTHH:MM:SS-0700"
---

# Design Title

## Intent
> "What are we trying to understand, solve, or decide?"

## Context
Write 2-5 sentences describing:
- What prompted this exploration
- What problem or opportunity exists
- What constraints or requirements we're working with
- Why this matters now

<!-- ===== EXPAND SECTIONS BELOW AS NEEDED ===== -->
<!-- Use what provides value. Skip what doesn't. -->

## Research

### Topic or Question
- **Source**: Where this insight came from (docs, testing, discussion)
- **Finding**: What we learned
- **Implication**: What this means for our approach
<!-- Add more fields if needed:
- **Evidence**: Supporting data or examples
- **Confidence**: How certain we are
-->

<!-- Add more research items as needed -->

## Options Considered

### Option Name
- **Approach**: How this would work
- **Benefits**: What we gain
- **Drawbacks**: What we lose or risk
- **Fit**: How well it matches our constraints
<!-- Add more fields if complex:
- **Complexity**: Implementation difficulty
- **Cost**: Time/resource requirements
- **Examples**: Where this pattern is used successfully
- **Dependencies**: What else would need to change
-->

<!-- Add more options as needed -->

## Questions

### Question or Uncertainty
- **Question**: What we don't know
- **Impact**: Why this matters
- **Approach**: How we might answer it
<!-- Add more fields if needed:
- **Blocker**: Is this blocking a decision?
- **Deadline**: When we need to know
-->

<!-- Add more questions as needed -->

## Hypotheses

### Hypothesis Statement
- **Claim**: What we believe might be true
- **Reasoning**: Why we think this
- **Test**: How we could validate it
- **Risk**: What happens if we're wrong
<!-- Add more fields if needed:
- **Assumptions**: What this depends on
- **Alternatives**: Other possibilities
-->

<!-- Add more hypotheses as needed -->

## Decision

### Current Stance
- **Direction**: Where we're leaning (or "undecided")
- **Reasoning**: Why this direction
- **Confidence**: How certain we are (low/medium/high)
- **Next Steps**: What happens next
<!-- Add more fields if needed:
- **Dependencies**: What needs to happen first
- **Reversibility**: Can we change our mind later?
- **Timeline**: When we need to decide
-->

## References

### Source Title
- **Type**: Article, docs, example, discussion, etc.
- **URL**: Link if available
- **Key Insight**: What we took from it
- **Relevance**: How it applies to our situation

<!-- Add more references as needed -->
```

---

## Type Taxonomy (Dot Notation)

**Format:** `exploration.specific-topic`

**Common categories:**
- `exploration` - investigating options
- `research` - gathering information
- `decision` - finalizing direction
- `spike` - technical proof of concept
- `analysis` - understanding existing systems
- `strategy` - planning approach

**Examples:**
- `exploration.agent-orchestration`
- `research.vector-databases`
- `decision.api-architecture`
- `spike.async-spawning`

---

## Section Usage Guidance

### Always Include:
- **Intent** - Why this exploration exists
- **Context** - The situation and constraints
- **Decision** - Current stance (even if "undecided")

### Include When Relevant:
- **Research** - When gathering information
- **Options Considered** - When evaluating alternatives
- **Questions** - When uncertainties exist
- **Hypotheses** - When testing assumptions
- **References** - When external sources inform thinking

### Skip When:
- Section adds no value beyond what's already documented
- Exploration is simple and straightforward
- Content would just repeat other sections

---

## Progressive Disclosure

**The template adapts to the exploration, not vice versa.**

**Simple exploration (quick spike):**
- Intent, Context, 1-2 Options, Decision
- Result: ~40-60 lines

**Standard exploration (evaluating approaches):**
- Intent, Context, Research, 3-5 Options, Questions, Decision
- Result: ~80-120 lines

**Complex exploration (architectural investigation):**
- Intent, Context, Research, Options, Questions, Hypotheses, Decision, References
- Result: ~120-180 lines

**Field variation within sections:**
- Simple items: 2-3 fields
- Standard items: 3-4 fields
- Complex items: 5-6 fields

---

## Key Principles

### 1. Exploration is Valid Work
❌ "We decided on X" (hiding the journey)
✅ "We explored A, B, C and chose X because..."

### 2. Document Uncertainty
❌ "This is the best approach"
✅ "This seems promising because X, but we're uncertain about Y"

### 3. Capture Reasoning, Not Just Conclusions
❌ "Use library X"
✅ "Use library X (considered Y and Z, chose X for reasons A, B)"

### 4. Questions are Valuable
❌ Skip uncertainties
✅ Document what we don't know and why it matters

---

## Lifecycle States

### `exploring`
Active investigation, no decision yet

### `decided`
Decision made, ready to move to implementation planning

### `rejected`
Exploration complete but decided not to pursue

### `archived`
Superseded by later exploration or no longer relevant

---

## Difference from Development Changelogs

**Design (.context/design/.changes/):**
- What we're **thinking about**
- Options we're **considering**
- Questions we **need to answer**
- **Before** building

**Development (.context/develop/.changes/):**
- What we **actually built**
- Decisions we **actually made**
- Problems we **actually solved**
- **After** building

**Both are valuable** - design captures the journey, development captures the reality.

---

**This template is for AI agents and human developers creating `.context/design/.changes/` exploration changelogs in the AURA memory system.**
