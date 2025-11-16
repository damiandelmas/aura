# Mission: Gaps and Additions Analysis

You are Brother B executing Stage B of the IMEM re-assessment pipeline.

Your role: Identify functional gaps and define minimal additions to enable v1.

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

**TL;DR:**
Stage A mapped existing capabilities to vision. Now identify what's genuinely missing (functional gaps) vs what just needs organization (naming, wrappers). Define smallest additions to complete v1—no refactoring.

---

## Task

1. **Read Stage A output** — Understand current capability mapping
2. **Re-read vision and design docs** — What capabilities are required for v1?
3. **Distinguish gap types:**
   - Functional: Missing capabilities that block v1
   - Organizational: Naming, wrappers, documentation
4. **Define minimal additions** — Specific functions, interfaces, utilities needed
5. **Save analysis** to output path

---

## Constraints

- Focus on v1 blockers only
- Additions must use existing code (no rewrites)
- Prefer wrappers over new implementations
- Cite what exists that can be leveraged
- Under 200 lines

---

## Output Format

Save to: `/home/axp/projects/fleet/hangar/code/aura/main/.context/design/async-repo-study-1/01_re-assess/output/b-gaps-and-additions.md`

```markdown
# Gaps and Additions

## Functional Gaps (Missing Capabilities)

**Gap:** {Name}
**Blocks:** {What v1 capability this prevents}
**Current state:** {What we have related to this}
**Needed:** {Specific addition required}
**Leverages:** {Existing code/functions to build on}

---

## Organizational Gaps (Naming/Wrappers)

**Gap:** {Name}
**Issue:** {What's unclear or awkward}
**Current state:** {What exists but needs wrapping}
**Needed:** {Wrapper/interface/documentation}
**Leverages:** {Existing implementation}

---

## Minimal Additions List

### High Priority (v1 Blockers)
1. {Addition} — {Why needed, what it wraps/extends}

### Medium Priority (v1 Polish)
1. {Addition} — {Enhancement, not blocker}

### Low Priority (Post-v1)
1. {Addition} — {Nice to have, defer}
```
