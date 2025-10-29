---
session_id: eee3b7a5-3870-4b50-984c-19eb2e2fa729
date: 2025-10-27
type: pattern.architecture
resolution: level-2a
keywords: "unix-philosophy composable-primitives observable-layer learning-substrate"
---

# Runtime Composition: Architecture Pattern

## The Pattern

**Minimal primitives + AI orchestration + observable substrate.**

System exposes 4-5 primitives.
AI composes sequences dynamically.
Usage logged → patterns emerge → shortcuts generated.

---

## The Mechanism

**Primitive layer (stable):**
```
Core operations:
- search(query, filters) → result_set
- filter(conditions) → result_set
- graph build(results) → graph_id
- graph apply(graph_id, algorithm) → rankings
- combine(result_sets) → merged_set
```

**Composition layer (dynamic):**
```
Claude Code composes:
- Decides which primitives
- Determines sequence
- Passes results between operations
- Visible as bash commands
```

**Observation layer (learning):**
```
Usage logged:
- Every primitive call
- Composition sequences
- Success/failure patterns
- Frequency detection
```

---

## The Operations

**1. Execute primitive:**
- AI decides operation needed
- Calls primitive with params
- Receives structured JSON response
- Passes to next operation or returns to user

**2. Compose sequence:**
- AI determines multi-step workflow
- Executes primitives in sequence
- Chains results between operations
- Observable as individual commands

**3. Detect pattern:**
- Usage.log shows repeated sequences
- Pattern detector: `search + filter(file) + filter(session)` = 13 occurrences
- Validate: Success rate >80%, different contexts
- Candidate for shortcut

**4. Generate shortcut:**
- Proven composition → markdown slash command
- Document as reusable pattern
- Git-tracked, user-editable
- Optional convenience, not requirement

---

## The Layers

**Layer 1: Kernel (code):**
- 4-5 primitives
- Stable interface
- Rarely changes

**Layer 2: Orchestration (AI):**
- Claude Code composes
- Dynamic per context
- Intelligence layer

**Layer 3: Shortcuts (markdown):**
- Validated compositions
- Git-tracked commands
- Optional convenience

**Layer 4: Observation (logging):**
- Every operation tracked
- Pattern detection
- Learning substrate

---

## The Benefits

**Composability:**
- Primitives combine infinitely
- No pre-defined modes
- Adapts to any use case

**Transparency:**
- Bash commands visible
- No black boxes
- Debuggable compositions

**Evolvability:**
- System learns from usage
- Shortcuts emerge organically
- No premature abstraction

**Minimal maintenance:**
- Primitives stable
- Compositions disposable
- Shortcuts optional

---

## The Anti-Pattern

**Don't:**
- Build explain/trace/patterns functions before validation
- Hide composition in wrapper code
- Generate shortcuts speculatively
- Skip observation phase

**Do:**
- Expose primitives first
- Let AI compose transparently
- Observe actual usage patterns
- Generate shortcuts only when proven (>10 uses, >0.8 success)
