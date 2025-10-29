---
type: "design"
timestamp: "2025-10-11T01:45:00-0700"
---

# Four-Phase Changelog Architecture: Design → Designate → Develop → Document

## Question
> "We should have a completely different field for design, designate, develop, document. These are structured changes in complete stage. Also I created a new one 'designate' - it's the ground truth PLAN that emerges from design."

## Key Insights

### The Missing Link Identified
- **Problem**: Existing IMEM template conflates work phase with domain category
- **Discovery**: There's a critical gap between design decisions and implementation
- **Solution**: "Designate" phase - where design crystallizes into ground truth

### Four Distinct Phases
1. **Design** (Exploration & Decisions)
   - Question-driven exploration
   - Multiple approaches considered
   - Decision made, principles established
   - Output: Design changelog

2. **Designate** (Planning)
   - THE PLAN emerges from design
   - Authoritative specifications created
   - Output: Plans, schemas, roadmaps

3. **Develop** (Implementation)
   - Code written, tests passing
   - Based on designate artifacts
   - Output: Implementation changelog

4. **Document** (Stable Reference)
   - Living documentation
   - Reference material, how-to guides
   - Output: README, API docs, architecture diagrams

### Frontmatter Restructure
```yaml
---
schema_version: "v3_adaptive"
phase: "design" | "designate" | "develop" | "document"  # NEW: Where in lifecycle
type: "category.subcategory"  # Domain classification only
status: "exploring" | "decided" | "active" | "completed" | "stable"
keywords: "space-separated for search"
timestamp: "YYYY-MM-DDTHH:MM:SS-0700"
---
```

**Key Separation:**
- `phase:` = Where in lifecycle (design → designate → develop → document)
- `type:` = What domain (architecture, security, feature, etc.)

## Explored Ideas

### Original Structure (Rejected)
```yaml
type: "design" | "implementation" | "ideation" | "research"
```
**Problem**: Mixing lifecycle phase with domain category

### Proposed Structure (Accepted)
```yaml
phase: "design" | "designate" | "develop" | "document"
type: "architecture.hybrid" | "security.guardrails" | "feature.voice-input"
```
**Benefit**: Clean separation, enables precise RAG filtering

### Directory Structure
```
.context/
├── design/           # Exploration → decision
│   └── .changes/
│       ├── 251004-1830_schema-separation.md
│       └── 251004-1845_design-principles.md
│
├── designate/        # Plans
│   ├── phase-one-plan.md
│   ├── courses.json
│   └── aliases/
│
├── develop/          # Implementation changelogs
│   └── .changes/
│       └── 251010-2100_hybrid-architecture.md
│
└── document/         # Stable reference
    ├── README.md
    └── API_REFERENCE.md
```

### RAG Query Patterns
```python
# Find all design decisions
qdrant.search(
  query="schema separation",
  filter={'phase': 'design'}
)

# Find ground truth specs
qdrant.search(
  query="course codes",
  filter={'phase': 'designate'}
)

# Find implementation work
qdrant.search(
  query="strategy pattern",
  filter={'phase': 'develop'}
)
```

## Outcomes

### Decision: Implement Four-Phase Architecture

**Rationale:**
- Separates lifecycle phase from domain category
- "Designate" fills critical gap between design and development
- Enables precise RAG filtering by work phase
- Matches actual workflow (explore → specify → implement → document)

**Implementation Plan:**
1. Create 4 phase-specific templates:
   - `design-template.md` (exploration → decision)
   - `designate-template.md` (ground truth specification)
   - `develop-template.md` (implementation changelog)
   - `document-template.md` (stable reference)

2. Update existing changelogs with new frontmatter:
   - NPTA design changelogs: Add `phase: "design"`
   - Ground truth files: Add `phase: "designate"`
   - Implementation changelogs: Add `phase: "develop"`

3. Update IMEM architecture documentation:
   - Explain when to use each phase
   - Show examples of each
   - Document RAG query patterns

### Phase-Specific Status Values

```yaml
design:
  - exploring  # Multiple approaches being considered
  - decided    # Decision made, principles established

designate:
  - draft      # Plan being created
  - active     # Current ground truth
  - deprecated # Superseded by newer version

develop:
  - in-progress  # Work ongoing
  - completed    # Implementation done, tests passing
  - archived     # Old implementation

document:
  - draft   # Documentation being written
  - stable  # Current accurate documentation
  - stale   # Needs update
```

### Key Insight: Designate is the Ground Truth Layer

**Before (incomplete flow):**
```
design → ??? → develop
(decisions)      (code)
```

**After (complete flow):**
```
design → designate → develop
(decisions) (THE PLAN) (implementation)
```

**Designate is where:**
- Design decisions crystallize into authoritative specs
- Ground truth emerges (courses.json = THE canonical course list)
- Roadmaps get written (phase-one_plan.md = THE sequence)
- Everyone references this as source of truth

## References

### NPTA Project Examples
- **Design**: `251004-1830_schema-separation-production-ready.md`
- **Designate**: `ground-truth/courses.json`, `phase-one_plan.md`
- **Develop**: `251010-2100_hybrid-architecture-refactor.md`
- **Document**: `README.md` (future)

### IMEM Architecture
- Section-level chunking strategy
- Progressive disclosure philosophy
- RAG optimization patterns
- Metadata auto-detection

### Related Concepts
- Domain-Driven Design: Bounded contexts
- Software Development Lifecycle (SDLC)
- Knowledge Management: DIKW pyramid (Data → Information → Knowledge → Wisdom)
- Technical Writing: Documentation-as-code
