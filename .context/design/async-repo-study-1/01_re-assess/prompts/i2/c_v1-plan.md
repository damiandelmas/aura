# Mission: v1 Completion Plan

You are Brother C executing Stage C of the IMEM re-assessment pipeline.

Your role: Create concrete roadmap to ship v1 using existing implementation plus minimal additions.

---

## Context

**Architecture documents (static snapshot, maintained after implementations):**
- `/home/axp/projects/fleet/hangar/code/aura/main/.context/document/architecture_imem-i2.md`

**Vision documents (hypotheses for end-state, treat as relative not absolute):**
- `/home/axp/projects/fleet/hangar/code/aura/main/.context/designate/overview.md`

**Design documents (conceptual evolution, may contain unimplemented ideas):**
- `/home/axp/projects/fleet/hangar/code/aura/main/.context/designate/codebase-shape.md`
- `/home/axp/projects/fleet/hangar/code/aura/main/.context/designate/compiler/knowledge-compiler-i4.md`
- `/home/axp/projects/fleet/hangar/code/aura/main/.context/designate/composer/compose-py.md`
- `/home/axp/projects/fleet/hangar/code/aura/main/.context/designate/composer/knowledge-composer.md`

**Stage A output (vision-reality mapping):**
- `/home/axp/projects/fleet/hangar/code/aura/main/.context/design/async-repo-study-1/01_re-assess/output/a-vision-and-reality.md`

**Stage B output (gaps and additions):**
- `/home/axp/projects/fleet/hangar/code/aura/main/.context/design/async-repo-study-1/01_re-assess/output/b-gaps-and-additions.md`

**TL;DR:**
Stage A mapped capabilities. Stage B identified gaps and additions. Now create actionable v1 completion plan—specific files to create, functions to write, no architectural changes.

---

## Task

1. **Read Stage A and B outputs** — Understand current state and needed additions
2. **Define v1 scope** — What minimal set of capabilities constitutes shippable v1?
3. **Create implementation plan:**
   - Specific files to create/modify
   - Functions to write (with signatures)
   - Wrappers to add
   - Documentation to write
4. **Sequence work** — What order to implement (dependencies)
5. **Save plan** to output path

---

## Constraints

- Concrete and actionable (file paths, function names)
- Use existing code (additions only, no refactoring)
- v1 scope (not everything, just shippable core)
- Implementation order matters (dependencies first)
- Under 250 lines

---

## Output Format

Save to: `/home/axp/projects/fleet/hangar/code/aura/main/.context/design/async-repo-study-1/01_re-assess/output/c-v1-plan.md`

```markdown
# v1 Completion Plan

## v1 Scope Definition

**Core capabilities for v1:**
- {Capability 1}
- {Capability 2}
- {Capability 3}

**Explicitly out of scope (post-v1):**
- {Future enhancement 1}
- {Future enhancement 2}

---

## Implementation Plan

### Phase 1: {Name} (Dependencies/Foundations)

**File:** `path/to/file.py`
**Purpose:** {What this enables}
**Functions:**
```python
def function_name(params) -> ReturnType:
    """Brief description"""
    # Uses existing: module.existing_function()
```
**Leverages:** {Existing code this builds on}

---

### Phase 2: {Name} (Core Additions)

**File:** `path/to/file.py`
**Purpose:** {What this enables}
**Functions:**
```python
def function_name(params) -> ReturnType:
    """Brief description"""
```
**Leverages:** {Existing code this builds on}

---

### Phase 3: {Name} (Integration/Polish)

**File:** `path/to/file.py`
**Purpose:** {What this enables}
**Functions:**
```python
def function_name(params) -> ReturnType:
    """Brief description"""
```
**Leverages:** {Existing code this builds on}

---

## Implementation Order

1. {Task} — {Why first, what it unblocks}
2. {Task} — {Depends on #1}
3. {Task} — {Depends on #1, #2}
...

---

## Success Criteria

**v1 is complete when:**
- [ ] {Capability 1 working}
- [ ] {Capability 2 working}
- [ ] {Integration test passing}
- [ ] {Documentation exists}

---

## Post-v1 Considerations

**After v1 ships, consider:**
- Refactoring: {What could be reorganized}
- Enhancements: {What could be added}
- Performance: {What could be optimized}
```
