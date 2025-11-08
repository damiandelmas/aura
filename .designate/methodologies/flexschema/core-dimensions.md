---
session_id: "034ba596-240e-4bc3-b71a-2194dafd9656"
---

# CORE Dimensions

**Six universal coordinates for knowledge classification.**

---

## The Dimensions

**1. Interrogative**
WHO | WHAT | WHERE | WHEN | WHY | HOW

What fundamental questions does this chunk answer?

**2. Valence**
GOOD | BAD | NEUTRAL

What's the outcome orientation?

**3. Abstraction**
CONCRETE | ABSTRACT | META

What's the level of generality?

**4. Epistemic**
KNOWN | HYPOTHETICAL | UNKNOWN

What's the certainty state?

**5. Temporal**
PAST | PRESENT | FUTURE

What's the time position?

**6. Structural**
ATOMIC | COMPOSITE | RELATIONAL

What's the compositional nature?

---

## Domain Template Examples

### Software Development
```yaml
Decision:
  core_signature: {what: 0.8, why: 0.7, valence: good, epistemic: known}

Pattern:
  core_signature: {why: 0.9, how: 0.85, abstraction: abstract, structural: relational}

Failure:
  core_signature: {what: 0.75, why: 0.8, valence: bad, temporal: past}
```

### Legal
```yaml
Statute:
  core_signature: {what: 0.9, valence: neutral, abstraction: abstract, epistemic: known}

Precedent:
  core_signature: {what: 0.85, why: 0.75, who: 0.7, temporal: past}

Argument:
  core_signature: {why: 0.95, epistemic: hypothetical, structural: relational}
```

### Business
```yaml
Objective:
  core_signature: {what: 0.9, why: 0.75, valence: good, temporal: future}

Risk:
  core_signature: {what: 0.85, why: 0.7, valence: bad, epistemic: hypothetical}

Milestone:
  core_signature: {what: 0.85, when: 0.9, temporal: future, structural: atomic}
```

---

## Cross-Domain Pattern Transfer

**Same CORE signature = analogous types across domains**

Software Failure: `{what: 0.75, why: 0.8, valence: bad, temporal: past}`
Legal Breach: `{what: 0.78, why: 0.82, valence: bad, temporal: past}`

→ Pattern recognized: Both describe "thing that went wrong in the past"

---

## Implementation

**Current:** Template structure implies CORE coordinates (implicit)

**Future:** CORE classifier scores each dimension explicitly (6D coordinates per chunk)

Both approaches enable FlexSchema's universal foundation and cross-domain resolution.
