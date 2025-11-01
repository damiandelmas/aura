---
type: "design"
timestamp: "2025-10-28T21:51:00-07:00"
session_id: "b9af3e9f-3abe-4616-b50d-a340e9121f27"
---

# FlexGraph: Compositional Primitives for Narrative Reconstruction

## Question
> "Are we all on the same page about FlexGraph? Should we update the docs to reflect narrative reconstruction?"

## Key Insights

### 1. The Core Purpose: Time Machine for Developer Thinking
- **Not:** Search engine for finding files
- **But:** System that reconstructs COMPLETE development narratives
- Every query returns: Conversation → Design → Failures → Implementation → Patterns
- "Git commits + developer's ENTIRE BRAIN downloaded"

### 2. FlexGraph = Compositional Flexibility
- **Not locked to ONE composition** (complete genealogy)
- **ANY composition of primitives** is possible:
  - Composition A: genealogy + cross_phase + siblings = "Complete story"
  - Composition B: temporal + siblings(patterns) = "Evolution timeline"
  - Composition C: siblings(failures only) = "Anti-pattern search"
  - Composition D: siblings(patterns, order_by timestamp) = "Pattern library"

### 3. Observable Usage → Preset Library
- AI agents compose primitives flexibly
- Usage patterns emerge (e.g., composition used 30+ times)
- Proven patterns captured as slash commands
- Example: `/explain-decision`, `/evolution-trace`, `/anti-patterns`

### 4. The Moat: Template-as-Schema
- 100% metadata compliance (AI-written docs)
- Enables deterministic primitives (section_type, has_rationale, timestamp)
- Competitors can't replicate (requires breaking change)
- Foundation for all compositional flexibility

### 5. Smart Primitives vs Dumb Primitives
- **Current roadmap:** `get_siblings(chunk_id)` → Returns ALL siblings, unsorted
- **What metadata enables:** `get_siblings(chunk_id, section_types, order_by, limit)` → Filtered, ordered
- Rich metadata (section_type, timestamp, has_rationale) currently unexploited
- Need to build smart primitives that USE the metadata

## Explored Ideas

### Narrative Reconstruction as Primary Use Case
- **Story template structure:**
  - The Problem (from conversation)
  - What Failed (failures with lessons)
  - The Design Decision (rationale, alternatives rejected)
  - The Implementation (code signatures, architecture)
  - Patterns Extracted (reusable learnings)
- Template tells STORY, not dumps data

### Type-Aware Template Selection
- `type: "bug-fix"` → bug-fix.j2 (highlights failures + working solution)
- `type: "architecture"` → architecture.j2 (shows decisions + trade-offs)
- Auto-detect from metadata instead of hardcoding

### Cross-Document Authority (Real Authority)
- **Not:** Sibling count = authority (that's just complexity)
- **Actually:** Citation count across documents
- Track: Changelog A references Pattern from Changelog B
- Authority = How many OTHER docs cite this

### Meta-Recursion Test
- **Ultimate validation:** Can IMEM explain its own creation?
- Query: "How was FlexGraph built?"
- Returns: This conversation + design docs + implementation + patterns
- The system documents itself

## Design Decisions

### 1. Update Docs to Emphasize Composition
**flexgraph-methodology.md:**
- Add "Composition Philosophy" section
- Show multiple composition examples (not just genealogy)
- Explain: Observable usage → Preset library

**imem-architecture.md:**
- Add "The Purpose: Time Machine for Developer Thinking" at top
- Update "Intelligence" section to show 4 composition examples
- Make it clear: Flexibility IS the innovation

**imem-roadmap.md:**
- Retitle Phase 6: "Narrative Reconstruction Engine" (not just "Primitives")
- Add smart primitive signatures (section_types, order_by, limit)
- Phase 8: Emphasize observable usage → slash command capture

### 2. Smart Primitives Must Use Metadata
```python
def get_siblings(
    collection_name,
    chunk_id,
    section_types=None,      # Filter by section
    order_by='section_level', # Or 'timestamp'
    has_rationale=None,       # Quality filter
    limit=None               # Top N
):
```

Not:
```python
def get_siblings(chunk_id):
    # Returns ALL, unsorted
```

### 3. Story Templates (Not Data Dumps)
- story.j2 - Complete narrative reconstruction
- timeline.j2 - Evolution over time
- anti-patterns.j2 - Failures across docs
- Templates TELL STORIES using metadata

### 4. Success Criteria
- ✅ Single query returns complete story (conversation → code)
- ✅ ANY composition of primitives is possible
- ✅ Template tells STORY, not dumps chunks
- ✅ **Meta test:** IMEM can explain its own creation
- ✅ Observable usage captures patterns as slash commands

## Outcomes

### Alignment Achieved
- **Vision:** 100% aligned across all conversations
  - This is Git for thought processes
  - Narrative reconstruction, not file search
  - Time machine for developer thinking
- **Roadmap:** Needs framing updates (70% → 100%)
  - Technical details are correct
  - Purpose/framing needs clarity

### What to Build
1. **Smart primitives** that use metadata (section_types, order_by, limit)
2. **Compose orchestrator** that enables ANY composition
3. **Story templates** that reconstruct narratives
4. **Observable usage tracking** → slash command capture

### What Makes FlexGraph "Flex"
- **Not:** Fixed to one pattern (genealogy)
- **But:** Compositional primitives enabling ANY pattern
- Flexibility = AI agents discover useful compositions
- Observable patterns → Preset library

## References

### Key Files
- `/home/axp/projects/fleet/hangar/code/aura/main/.context/251028-2140.md` - "Git for thought processes"
- `/home/axp/projects/fleet/hangar/code/aura/main/.context/251028-2144_best.md` - Meta-recursion insight
- `/home/axp/projects/fleet/hangar/code/aura/main/.context/251028-2145_best.md` - Narrative reconstruction

### Docs to Update
- `flexgraph-methodology.md` - Add composition philosophy
- `imem-architecture.md` - Add purpose section, show 4 composition examples
- `imem-roadmap.md` - Retitle Phase 6, add smart primitive signatures

### Core Concepts
- Template-as-schema (the moat)
- Compositional primitives (the flexibility)
- Observable usage (the evolution path)
- Narrative reconstruction (the purpose)
- Meta-recursion (the validation test)

---

## Next Steps

1. Update docs to emphasize:
   - Narrative reconstruction (not just retrieval)
   - Compositional flexibility (not just genealogy)
   - Observable usage → presets

2. Build smart primitives:
   - Accept metadata filters (section_types, order_by, limit)
   - ~50 lines per primitive to add filtering

3. Implement story templates:
   - story.j2 (narrative structure)
   - timeline.j2 (evolution)
   - anti-patterns.j2 (failures)

4. Test with meta-query:
   - "How was FlexGraph built?"
   - Should return THIS conversation + design docs + patterns
