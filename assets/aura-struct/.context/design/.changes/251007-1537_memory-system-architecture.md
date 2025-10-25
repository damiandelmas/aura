---
type: "design"
timestamp: "2025-10-07T15:37:00-07:00"
---

# Memory System Architecture for Decision Support

## Question
> "How can we standardize documentation/memory handling across projects using the design/develop/document pattern, specifically for decision-making (advisory-board) vs code projects?"

## Key Insights

### Ontological Distinction
- **Code projects**: `.document/` describes codebase architecture → omega point is `src/` (the actual code)
- **Decision projects**: `.document/` describes professional reality → omega point is real life (relationships, outcomes)
- The memory system is always ABOUT something external, never the thing itself

### Three-Tier Structure
```
.design/      # R&D for what to do
.develop/     # Record of what happened + emergent patterns  
.document/    # Current stable state
```

### Temporal vs Static Separation
- **`.document/` = SHAPE** (timeless, static current state)
- **`.develop/` = INERTIA** (temporal, chronological record)
- AI agents reference `.document/` for structure, `.develop/` for history

### Module Evolution Pattern
- `.design/.modules/` = experimental (might fail)
- `.develop/.modules/` = 100% proven, needs dedicated docs (fresh patterns)
- `.document/` = mature, integrated knowledge

## Explored Ideas

### Document Taxonomy for Decision Support
Four core documents in `.document/`:
1. **01_context-and-state.md** - Current professional ecosystem
2. **02_decision-framework.md** - Decision trees and proven patterns
3. **03_mental-models.md** - Conceptual frameworks and metaphors
4. **04_operational-guide.md** - How AI agents should work with system

### Update Pattern (0-10% per changelog)
- Most `.develop/.changes/` entries update 0-2 documents
- 1-5 lines changed per update
- Incremental refinement, never rewrites
- Temporal data NEVER enters `.document/`

### Flow Architecture
```
.design/ exploration → decision
    ↓
.develop/.changes/ (ground truth)
    ↓
Pattern emerges → .develop/.modules/ (proven, needs docs)
    ↓
Matures → .document/ (integrated, stable)
```

## Design Decisions

### No Temporal Data in `.document/`
- Removed: `last_updated`, "Recent Changes", "Next Review"
- `.document/` is pure shape/structure
- All "when/what happened" lives in `.develop/.changes/`

### AI-Native Format
- Based on imem ARCHITECTURE.md and NPTA snapshot patterns
- Strategic design philosophy over technical details
- Business drivers and discovered constraints
- Mental models and metaphors

### Module Graduation
- Patterns stay in `.develop/.modules/` until proven (3+ uses)
- Extract essence (200 lines → 20-30 lines) when integrating
- Module can be archived once knowledge integrated

## Outcomes

Created:
1. **imem-new-structure.md** - General memory system pattern
2. **advisory-board-structure.md** - Applied to decision support
3. **Four `.document/` templates** in `main_02/.document/`
   - Spartan, concise, timeless structure
   - Ready for population from design modules

Clarified:
- `.design/.modules/architecture-documents_0X/` = design exploration (meta)
- `.develop/.changes/` = ground truth decisions (what happened)
- `.develop/.modules/` = empty (no patterns graduated yet)
- `.document/` = templates (ready for extraction)

## References

### Pattern Sources
- `/home/axp/projects/aura-retrieval-qdrant/aura/projects/imem-suite/main/.document/code/ARCHITECTURE.md`
- `/home/axp/projects/jesse-benson/projects/npta_shopify-widget/5_npta-styling/.memory/.snapshot/`
- Arc42, C4 Model, Lean Documentation principles

### Key Files Created
- `/home/axp/projects/advisory-board/imem-new-structure.md`
- `/home/axp/projects/advisory-board/advisory-board-structure.md`
- `/home/axp/projects/advisory-board/main_02/.document/01-04_*.md`

### Next Steps
Extract content from `.design/.modules/architecture-documents_02/` into `.document/`:
- `250909-1823_situation.md` → `01_context-and-state.md`
- `250909-1823_constraints.md` → `02_decision-framework.md`
- `250909-1823_team.md` → `01_context-and-state.md` (team section)
