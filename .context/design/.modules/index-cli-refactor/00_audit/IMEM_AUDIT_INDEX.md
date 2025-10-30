# IMEM Audit Documentation Index

## Three-Document Guide to IMEM Collection Dependencies

### 1. IMEM_BREAKING_POINTS.md (START HERE)
**Purpose:** Identify every breaking point, organized by severity tier
**Best For:** Understanding what will break and how to fix it
**Length:** ~500 lines
**Key Sections:**
- Tier 1: Safe collection name changes (properly parameterized)
- Tier 2: Silent metadata failures (missing fields)
- Tier 3: Hardcoded config requiring code changes
- Tier 4: Template system dependencies
- Tier 5: Ingestion system assumptions
- Complete call graph with breaking point annotations
- Refactoring checklist for multi-collection support

**Use this to answer:** "What breaks if I change X?"

---

### 2. IMEM_QUICK_REFERENCE.md (QUICK LOOKUP)
**Purpose:** Tables and matrices for rapid reference
**Best For:** Finding specific file locations and dependencies
**Length:** ~200 lines
**Key Sections:**
- Collection resolution path flowchart
- Four-stage compose pipeline table
- Parameterized primitives matrix
- Metadata filter taxonomy
- Template variable requirements
- Breaking points summary table
- Call chains to watch
- Configuration points
- What-breaks-what matrix
- File organization by category

**Use this to answer:** "Which file contains X? What fields does get_siblings need?"

---

### 3. IMEM_AUDIT.md (DETAILED REFERENCE)
**Purpose:** Comprehensive analysis with code snippets and line numbers
**Best For:** Deep understanding of the system architecture
**Length:** ~600 lines
**Key Sections:**
- Executive summary (high-level findings)
- Part 1: Collection resolution flow (with call chains and line numbers)
- Part 2: Four-stage compose pipeline (stage-by-stage analysis)
- Part 3: Parameterized primitives (detailed primitive analysis)
- Part 4: Template system (field dependency analysis)
- Part 5: Search filter taxonomy (hardcoded options)
- Part 6: Search implementation (filter application logic)
- Part 7: Ingestion system (metadata schema documentation)
- Part 8: Cross-cutting dependencies (vector model, Qdrant connection)
- Summary breaking points matrix
- Recommendations for multi-collection support

**Use this to answer:** "Show me the exact code at line X" or "Explain the architecture of Stage 2"

---

## Quick Navigation by Task

### "I need to support multiple collection schemas"
1. Read IMEM_BREAKING_POINTS.md - Refactoring Checklist section
2. Reference IMEM_QUICK_REFERENCE.md - Breaking Points Summary table
3. Check IMEM_AUDIT.md - Part 3 (Primitives) and Part 8 (Dependencies)

### "What breaks if I change collection names?"
1. IMEM_BREAKING_POINTS.md - Tier 1 (Safe Changes)
2. IMEM_AUDIT.md - Part 1 (Collection Resolution Flow)

### "What metadata fields are required?"
1. IMEM_QUICK_REFERENCE.md - Parameterized Primitives table
2. IMEM_BREAKING_POINTS.md - Tier 2 (Metadata Dependencies)
3. IMEM_AUDIT.md - Part 7 (Ingestion System)

### "What are the silent failure modes?"
1. IMEM_BREAKING_POINTS.md - Tier 2 entire section
2. IMEM_AUDIT.md - Part 3 (Primitives) - each function's breaking conditions

### "How does the system flow from CLI to results?"
1. IMEM_AUDIT.md - Part 1 (Collection Resolution Flow)
2. IMEM_AUDIT.md - Part 2 (Four-Stage Pipeline)
3. IMEM_BREAKING_POINTS.md - Complete Call Graph (end of document)

### "What's hardcoded and can't change without code updates?"
1. IMEM_BREAKING_POINTS.md - Tier 3 (Hardcoded Taxonomy & Config)
2. IMEM_QUICK_REFERENCE.md - Configuration Points (section 8)

### "Which files do I need to modify for X feature?"
1. IMEM_QUICK_REFERENCE.md - Key Files by Category (section 10)
2. IMEM_BREAKING_POINTS.md - Breaking Point details for that feature

---

## Key Findings Summary

**Good News:**
- Collection names are properly parameterized throughout the stack
- Registry system correctly tracks collection names (not regenerated)
- Four-stage compose pipeline properly threads collection_name parameter
- Discovery primitives accept collection_name as parameter

**Bad News:**
- Metadata schema is hardcoded (phase, source, section_type, etc.)
- Vector model (E5-Large-v2) assumed globally
- CLI taxonomy options are hardcoded, not dynamic
- Many queries silently fail if expected fields are missing
- Templates assume specific payload structure

**Critical Dependencies:**
1. Collection names stored in registry (not regenerated) ✓
2. Metadata fields: file_path, session_id, timestamp, phase, section_type
3. Vector config: e5-large-v2 (1024 dims) 
4. Qdrant connection: localhost:6334
5. Phase taxonomy: ['develop', 'designate', 'document', 'design']
6. Section types: ['Decisions', 'Constraints', 'Failures', 'Patterns', 'Implementation']

---

## File Locations (Absolute Paths)

**Source Code:**
- `/home/axp/projects/fleet/hangar/code/aura/main/imem/src/imem/cli.py`
- `/home/axp/projects/fleet/hangar/code/aura/main/imem/src/imem/registry.py`
- `/home/axp/projects/fleet/hangar/code/aura/main/imem/src/imem/search.py`
- `/home/axp/projects/fleet/hangar/code/aura/main/imem/src/imem/enhanced.py`
- `/home/axp/projects/fleet/hangar/code/aura/main/imem/src/imem/compose.py`
- `/home/axp/projects/fleet/hangar/code/aura/main/imem/src/imem/config.py`
- `/home/axp/projects/fleet/hangar/code/aura/main/imem/src/imem/ingest.py`
- `/home/axp/projects/fleet/hangar/code/aura/main/imem/src/imem/primitives/discovery.py`

**Templates:**
- `/home/axp/projects/fleet/hangar/code/aura/main/imem/templates/story-context.j2`
- `/home/axp/projects/fleet/hangar/code/aura/main/imem/templates/genealogy.j2`
- `/home/axp/projects/fleet/hangar/code/aura/main/imem/templates/timeline.j2`

**Audit Documents (this repository):**
- `IMEM_BREAKING_POINTS.md` (this directory)
- `IMEM_QUICK_REFERENCE.md` (this directory)
- `IMEM_AUDIT.md` (this directory)

---

## Reading Order Recommendation

**If you have 10 minutes:**
→ IMEM_QUICK_REFERENCE.md sections 1-6

**If you have 30 minutes:**
→ IMEM_BREAKING_POINTS.md sections "Tier 1" through "Tier 3"

**If you have 1 hour:**
→ IMEM_BREAKING_POINTS.md (entire document)

**If you're implementing multi-collection support:**
→ IMEM_BREAKING_POINTS.md (Refactoring Checklist)
→ IMEM_AUDIT.md (Part 3, 7, 8)
→ IMEM_QUICK_REFERENCE.md (sections 3-4, 10)

**If you're debugging a search failure:**
→ IMEM_QUICK_REFERENCE.md (section 7 - Call Chains)
→ IMEM_BREAKING_POINTS.md (Tier 2 - Silent Failures)
→ IMEM_AUDIT.md (Part 3 - Primitives)

---

## Document Statistics

| Document | Lines | Sections | Key Tables | Code Examples |
|----------|-------|----------|------------|---|
| IMEM_BREAKING_POINTS.md | 500+ | 6 main + checklist | 3 | 15+ |
| IMEM_QUICK_REFERENCE.md | 200 | 11 | 7 | 5 |
| IMEM_AUDIT.md | 600+ | 8 parts + summary | 1 | 30+ |
| **Total** | **1300+** | **Comprehensive** | **11** | **50+** |

---

## To Update These Documents

When the IMEM system changes:

1. **Collection resolution changes?** → Update IMEM_BREAKING_POINTS.md Tier 1
2. **Metadata fields added/removed?** → Update IMEM_BREAKING_POINTS.md Tier 2 + IMEM_QUICK_REFERENCE.md section 3
3. **New CLI options?** → Update IMEM_BREAKING_POINTS.md Tier 3 + IMEM_QUICK_REFERENCE.md section 4
4. **Template changes?** → Update IMEM_BREAKING_POINTS.md Tier 4 + IMEM_AUDIT.md Part 4
5. **Primitives added?** → Update IMEM_AUDIT.md Part 3 + IMEM_QUICK_REFERENCE.md section 3
6. **Call chain changes?** → Update IMEM_BREAKING_POINTS.md Complete Call Graph + IMEM_QUICK_REFERENCE.md section 7

All three documents were auto-generated on: 2025-10-29 14:45 UTC

---

## Contact & Questions

For questions about this audit:
- Breaking point analysis → See IMEM_BREAKING_POINTS.md with code references
- Architecture overview → See IMEM_AUDIT.md Part 1-2
- Specific file locations → See IMEM_QUICK_REFERENCE.md section 10
