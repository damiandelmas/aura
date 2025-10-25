# Universal IMEM Changelog Template

**Version:** v3_adaptive
**Last Updated:** 2025-10-07
**Purpose:** Ground truth changelog template for `.develop/.changes/`

---

## Template

```markdown
---
schema_version: "v3_adaptive"
type: "category.specific-work"
status: "completed"  # or "in-progress", "archived"
keywords: "space-separated keywords for-search indexing"
timestamp: "YYYY-MM-DDTHH:MM:SS-0700"
session_id: "uuid-of-originating-conversation"  # Optional: links to TRACE conversation
---

# Changelog Title

## Request
> "Exact user quote or request that triggered this work"

## Overview
Write 2-5 sentences describing what was accomplished in language-agnostic terms.
Focus on concepts not code - explain the problem, approach, and outcome without
framework-specific terminology. This should be readable by anyone familiar with
software development, regardless of their technology stack.

<!-- ===== EXPAND SECTIONS BELOW AS NEEDED ===== -->
<!-- Use what provides value. Skip what doesn't. -->

## Decisions

### Decision Title
- **Context**: Why this decision point arose
- **Solution**: What was chosen
<!-- Add more fields if the decision was complex:
- **Alternatives**: Other options considered (with reasons for rejection)
- **Rationale**: Technical reasoning if not obvious
- **Trade-offs**: What was sacrificed or compromised
- **Implications**: Future impact or when to revisit
-->

<!-- Add more decisions as needed - each as a new ### subsection -->

## Constraints

### Constraint Title
- **What**: The limitation or blocker discovered
- **Discovery**: How it was found
- **Workaround**: How it was handled
- **Impact**: What this affects
<!-- Add more fields if relevant:
- **Why Non-Obvious**: If it wasn't documented or expected
- **Testing**: How the workaround was validated
-->

<!-- Add more constraints as needed -->

## Failures

### Failed Approach Title
- **Attempted**: What was tried
- **Why Failed**: What broke or didn't work
- **Lesson**: What was learned
<!-- Add more fields for complex failures:
- **Hypothesis**: Why you thought it would work
- **Failure Mode**: How exactly it failed
- **Discovery**: How you found out
- **Alternative**: What you did instead
-->

<!-- Add more failures as needed -->

## Implementation

### Architecture
High-level description of the flow or system changes:
1. Step or component → Result
2. Step or component → Result
3. Continue as needed

### Code Signatures

**Component or Pattern Name** (`path/to/file.ext`)
```language
// Show the key pattern or signature, not full implementation
// Focus on what's essential: configs, key logic, integration points
// Omit error handling, edge cases - those live in the actual file
```

**Another Component** (`path/to/file.ext`)
```language
// Minimal code showing the pattern
// Enough to understand the approach
// Not enough to copy-paste blindly
```

<!-- Add more code signatures as needed -->

## Patterns

### Pattern Title
- **Pattern**: The reusable solution
- **When**: When to apply this pattern
- **Approach**: How to implement it
- **Benefit**: What you gain
<!-- Add more fields if relevant:
- **Why**: Rationale if not obvious
- **Anti-Pattern**: What NOT to do
- **Occurrences**: Where else this appears
-->

<!-- Add more patterns as needed -->

## Audit

### Created
- `path/to/file` - Brief description of what it does

### Modified
- `path/to/file` - What changed and why

### Removed
- `path/to/file` - What was deleted

### Configuration
Environment variables, settings, or config changes needed:
- `VARIABLE_NAME` - Purpose and value

### Deployment
- Build/deployment steps if relevant
- URLs or endpoints created

<!-- Optional subsections as needed -->
```

---

## Filename Convention

**Format:** `YYMMDD-HHMM_description-in-kebab-case.md`

**Examples:**
- `20251023-2002_trace-chronicle-refactor.md`
- `20251024-1430_imem-filter-support.md`
- `20251025-0915_authentication-implementation.md`

**Rationale:**
- **Chronological prefix** (`YYMMDD-HHMM`) enables time-based sorting
- **Human-readable description** makes directory listings understandable
- **Session ID in frontmatter** (not filename) reduces visual noise while maintaining traceability
- **Kebab-case** ensures filesystem compatibility and readability

**Session ID Linking:**
- Add `session_id` to frontmatter to link changelog to originating conversation
- Retrieve via `imem search --session <id>` or `grep "session_id:" *.md`
- Not required for manually created changelogs

---

## Type Taxonomy (Dot Notation)

**Format:** `category.specific-description`

**Common categories:**
- `implementation` - building new functionality
- `bug-fix` - fixing issues
- `design` - research and planning
- `architecture` - structural changes
- `refactor` - code cleanup
- `integration` - connecting systems

**Examples:**
- `implementation.security-guardrails`
- `bug-fix.timeout-handling`
- `design.api-exploration`
- `refactor.api-simplification`

**Subtype:** Use clear, descriptive terms in kebab-case. The AI will auto-create meaningful subtypes.

**Parser behavior:** At index time, splits on dot to extract `category` and `subtype` for flexible querying.

---

## Section Usage Guidance

### Always Include:
- **Request** - Context for why this work happened
- **Overview** - Language-agnostic narrative
- **Audit** - File changes and configuration

### Include When Relevant:
- **Decisions** - When strategic choices were made with alternatives
- **Constraints** - When limitations or blockers were discovered
- **Failures** - When approaches didn't work (prevents repeating mistakes)
- **Implementation** - When technical details are worth preserving
- **Patterns** - When reusable insights emerged

### Skip When:
- Section adds no value beyond what's already documented
- Information is obvious or trivial
- Content would just repeat other sections

---

## Progressive Disclosure

**The template adapts to the work, not vice versa.**

**Simple work (bug fix, config change):**
- Request, Overview, maybe 1 Decision (2 fields), Audit
- Result: ~40-60 lines

**Standard work (feature, integration):**
- Request, Overview, 2-3 Decisions, Implementation, Audit
- Result: ~70-120 lines

**Complex work (architecture, major feature):**
- Request, Overview, multiple Decisions/Constraints/Failures, Implementation, Patterns, Audit
- Result: ~120-180 lines

**Field variation within sections:**
- Simple items: 2-3 fields
- Standard items: 3-4 fields
- Complex items: 5-6 fields

See `01_FIELD_GUIDE.md` for detailed field variations.

---

## Key Principles

### 1. Language-Agnostic Overview
❌ "Fixed React hooks violation in useAnimatedText"
✅ "Fixed framework execution order violation in animation function"

### 2. Code Signatures, Not Full Implementation
❌ 100 lines of complete code with error handling
✅ 10 lines showing the key pattern or configuration

### 3. Natural Variation
❌ Every decision must have exactly 6 fields
✅ Simple decisions 2 fields, complex decisions 5-6 fields

### 4. Value Over Completeness
❌ Document everything exhaustively
✅ Document what matters, skip what doesn't

---

## Examples

See `02_EXAMPLE_SPECTRUM.md` for 9 real examples ranging from 44 to 171 lines, demonstrating the full spectrum from minimal to complex changelogs.

---

## For LlamaIndex MarkdownNodeParser

**This template is optimized for hierarchical parsing:**

### Node Structure
- **h1** (`# Title`): Document root node
- **h2** (`## Decisions`, `## Implementation`): Section parent nodes
- **h3** (`### Decision Title`, `### Architecture`): Individual item nodes

**Each h3 becomes a searchable node** with parent reference and full metadata.

### Node Granularity
- **One node per h3 item** (Decision, Constraint, Failure, Pattern)
- **Includes all field content** (Context, Solution, Alternatives, etc.) as single node
- **Code Signatures section** becomes one node (intentional - signatures read together)

**Why:** When searching "decisions about X," you want the complete decision context, not isolated fields.

### Section IDs
Auto-generated from headers at parse time:
```
### Use Official Rate Limiting → section_id: "use-official-rate-limiting"
### Fix Execution Order Violation → section_id: "fix-execution-order-violation"
```

No manual ID management needed.

### Metadata Enrichment

**MarkdownNodeParser automatically extracts:**
- `header_path`: "Decisions > Use Official Rate Limiting"
- `node_type`: "h3"
- `file_path`: Original changelog path
- `parent_node_id`: Reference to parent h2 section

**Custom metadata added at index time:**
- `section_type`: Detected from parent header ("decision", "constraint", "failure", "pattern")
- `category`: From `type` field dot-notation (e.g., "implementation")
- `subtype`: From `type` field dot-notation (e.g., "security-guardrails")
- `timestamp`: From frontmatter
- `status`: From frontmatter

### Progressive Disclosure Handling

**Parser handles variable structure naturally:**
- Missing sections → No nodes created for those sections (fine)
- Optional fields → Included in node text if present (fine)
- Different field counts → Parser doesn't care, treats as text (fine)

**HTML comments in template:** AI agents can include them for guidance. Comments won't be indexed as content during vector embedding - they're guidance metadata only.

### Query Patterns Enabled

**Section-level retrieval:**
```python
filter={'section_type': 'decision'}  # All decisions across all changelogs
filter={'category': 'implementation'}  # All implementation work
```

**Specific item retrieval:**
```python
filter={'section_id': 'use-official-rate-limiting'}  # Exact decision
```

**Parent-child navigation:**
```python
# Get decision → Walk up to parent h2 → Get sibling decisions
node.parent_node_id → parent → parent.child_node_ids
```

**Context reconstruction:**
```python
# Found specific decision → Retrieve full changelog context
node → parent (Decisions section) → root (Full changelog)
```

---

**This template is for AI agents and human developers creating `.develop/.changes/` ground truth changelogs in the IMEM institutional memory system.**
