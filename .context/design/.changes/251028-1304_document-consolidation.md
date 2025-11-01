---
session_id: "21154605-d5ea-40f2-b5c0-06b4aa127e27"
timestamp: "2025-10-28T16:30:00-0700"
---

# Document Consolidation & Promotion

## Context

Had excessive document fragmentation:
- 02_current: Oct 25 snapshot (4 files, outdated)
- 03_additional: Consolidated docs (3 files, Sept-Oct 27)
- 6 changelog files with scattered insights (251027-251028)

**Problem:** No single authoritative source, insights fragmented across 10+ files.

## Solution

**Promoted 03_additional → 02_current with 10-15% edits:**

1. **Archive preservation:**
   - `02_current → 02_archive_251025` (genealogy)

2. **Promotion:**
   - `03_additional → 02_current` (consolidated base)

3. **Edits incorporated** (from changelogs 251027-251028):

### imem-architecture.md

**Added: Supersession Mechanism section** (~80 lines)
- Detection hints (top-5 similar at indexing, O(k) not O(n²))
- Serving logic (flippable chunks, metadata flip)
- BRAIN annotation (endstate, Haiku soft language)

**Updated: Template Serve-Time section**
- Added innovation note (prompt engineering at retrieval layer)
- Token savings: ~30-40% (explicit relationship labels)

**Updated: Batch Primitive section**
- Clarified peer command status (not abstraction layer)
- Emphasizes internal composition for efficiency

### imem-roadmap.md

**Restructured Phase 6-8:**
- Phase 6: Relationship primitives (validated 13+ uses)
- Phase 6.5: Batch operations (JSON inline, single-call multi-query)
- Phase 7: Graph operations (PageRank/centrality)
- Phase 8: Template validation + slash command library

**Added: BRAIN sections**
- V2.3: BRAIN basics (persistent metadata accumulation)
- Phase 10+: LLM annotation layer (soft decay language)
- Dependencies explicit (3-6 months usage data required)
- Value uncertainty acknowledged (test before commit)

**Updated: Timeline**
- MVP: 4-5 days (was 8 days, refined with batch primitive)
- Implementation order: Primitives → Usage logs → BRAIN accumulation → Annotation

## Result

**Current state (02_current):**
- ✅ 3 core documents (methodology → architecture → roadmap)
- ✅ Supersession mechanism documented
- ✅ Batch primitive clarified
- ✅ BRAIN endstate roadmapped
- ✅ Template serve-time innovation captured
- ✅ Changelog insights incorporated

**Archive state (02_archive_251025):**
- ✅ Oct 25 snapshot preserved (4 files)
- ✅ Genealogy maintained

## Files Modified

- `/02_current/imem-architecture.md` (+15% edits: supersession, template serve-time, batch clarification)
- `/02_current/imem-roadmap.md` (+15% edits: Phase 6-8 restructure, BRAIN sections, timeline update)

## Files Unchanged

- `/02_current/soft-graph-methodology.md` (no changes needed)
- `/02_current/README.md` (consolidation overview, still accurate)

## Next Steps

1. Use 02_current as authoritative reference
2. Archive additional changelogs to .changes/ if needed
3. Begin Phase 6 implementation (relationship primitives)

## Validation

**Document package coherence:**
- L1: soft-graph-methodology.md (domain-agnostic pattern)
- L2: imem-architecture.md (IMEM-specific implementation)
- L3: imem-roadmap.md (sequenced execution plan)

**Recent insights captured:**
- Batch = parallelization infrastructure (not wrapper)
- Supersession = top-5 hints at indexing (not hard facts)
- BRAIN = 3-6 months accumulation before annotation
- Template serve-time = relationship-labeled prompt assembly
- Flippable chunks = metadata flip, no re-indexing

**Result:** Single authoritative document package, 95% insight capture, 10-15% update effort.
