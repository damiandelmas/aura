### (1) Project-Level: Lifecycle + Entities

**Four-Phase Lifecycle** (design → designate → develop → document)
- Metadata: `category`, `session_id`, `timestamp`
- Validated against git diffs
- Temporal cortex: validates chunks WRT project intent

**Entity Resolution** (within project)
- "jwt", "JWT", "jwt-tokens" → canonical `jwt`
- Enables reliable type queries for entire project
- Knowledge graph resolves entities within project scope

**Schema Evolution** (onboard to lifecycle)
- "Decision:", "Choice:", "We Decided:" → canonical `decision`
- Maps heterogeneous headers → lifecycle-compatible types
- **Allows any codebase to enter the four-phase system**

---

### (2) Meta-Level: Tier 0/1/2

**Tier 0:** Raw project documents (everything from (1))
**Tier 1:** Objective reference (each document gets entry)
**Tier 2:** Metadata ABOUT tier 1 (interpretation, context)

Different pipeline. Governs knowledge itself, not project lifecycle.

---

### The Distinction

**Entity Resolution:** Normalizes entities *within* a project already in lifecycle
**Schema Evolution:** Normalizes structure *to bring* projects *into* lifecycle

Same pattern. Different purpose.

Entity = project-internal consistency.
Schema = cross-project onboarding.