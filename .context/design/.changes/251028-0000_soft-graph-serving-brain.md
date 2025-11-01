---
session_id: "c864eed1-35fd-4e4e-93a1-2b4aad3a2b15"
timestamp: "2025-10-28T16:30:00-0700"
---

# Architectural Decisions: Soft-Graph Serving & BRAIN Annotation

Decisions from conversation 251028-1630 on batch parallelization, supersession handling, template-aware serving, and endstate BRAIN annotation layer.

---

## Batch = Generic Parallelization Not Multi-Query Wrapper
**Quote:** "batch primitive allows you to call any primitive VIA json in parallel with a single bash call ;)"
**Why:** Infrastructure for parallelizing ANY operations (search, siblings, filter, graph), not specialized multi-query function—future-proof for new primitives

**Context:** Initial misunderstanding had batch as multi-query wrapper with graph operations. Actually batch is parallelization infrastructure accepting {"parallel": [{"op": "search", ...}, {"op": "siblings", ...}]} format. Works with ANY current or future primitive. Single bash call from Claude's perspective, internal parallel execution.

**Key Properties:**
- Generic dispatch mechanism (not query-specific)
- Single call efficiency (3 ops @ 100ms each = ~110ms vs 300ms sequential)
- Future-proof (new primitives automatically supported)
- Observable (single log entry, reproducible JSON)

---

## Accept RAG Imperfection + Model Intelligence
**Quote:** "i think we just accept the imperfection of RAG, and trust in intellgience of model to suss out and extrapolate. works in actuality."
**Why:** Changelogs will be incomplete/imprecise/bundled—model handles fuzzy better than enforcing perfect schema, RAG nature is ambiguity-tolerant

---

## Supersession Hints = Soft Programmatic at Write Time
**Quote:** "insofar as neighrest neohur for two chunks at NEW CHANGELOG CREATION COULD = seupersession? we could explore this in development."
**Why:** Store top-5 similar older chunks as metadata hints at indexing (fast O(k) per new chunk), not hard "IS superseded" facts—model interprets with context

**Context:** Changelogs will be imperfect (missing code, bundled decisions, incomplete). Accept this—RAG handles fuzzy. At indexing, compute semantic similarity to older same-section-type chunks (>0.85 threshold). Store as metadata hints, not facts. Model sees "May be related to [older-chunk]" and makes intelligent determination based on content.

**Options Considered:**
- A: Hard supersession detection (high-confidence auto-flag) - brittle, false positives
- B: No supersession tracking - model must infer entirely from content
- C: Soft hints in metadata - programmatic candidate detection, model interpretation

**Implementation:** At indexing, single vector search per new chunk against older chunks. Store top-5 as `supersession_candidates` array. Retrieval shows hints, model contextualizes.

---

## Template-as-Schema at Serve Time
**Quote:** "we could, given certain queries contrsuct it at point of serve in 'prompt templates' IE — explaining the chunks in relation to one anthoer given some relationship detection?"
**Why:** Template structure enables relationship-labeled prompt assembly—not flat "5 chunks" but "DECISION + CONSTRAINTS (same doc) + CONVERSATION ORIGIN (session)"—interpretable context

**Context:** Template-as-schema works at THREE levels: (1) Write time = enforce structure, (2) Query time = enable filtering, (3) Serve time = structure prompt assembly. Third level unlocked: Use template knowledge to construct relationship-aware prompts. Not "Here's 5 text blocks" but "Here's a DECISION (with Context/Solution/Rationale fields), its CONSTRAINTS (same file via file_path), and CONVERSATION ORIGIN (via session_id)."

**Key Innovation:** Prompt engineering at retrieval layer. Chunks served with explicit relationship labels based on metadata queries. Traditional RAG dumps chunks, model infers structure. AURA serves pre-structured, relationship-explicit context.

**Example Transformation:**
- Before: Chunk 1, Chunk 2, Chunk 3 (flat)
- After: "DECISION: [chunk 1]\n\nCONSTRAINTS (Same Changelog): [chunk 2]\n\nCONVERSATION ORIGIN: [chunk 3]"

**Enables:** Query-driven template selection (search vs explain vs trace use different templates), interpretable context, token efficiency (less parsing overhead for Claude)

---

## BRAIN = Runtime Graph Accumulating Relationship Knowledge
**Quote:** "We could have a quick LLM do passes on (1) actual chunk (2) the header (3) the prompt explanation given some stored knowledge in 'BRAIN' <<< runtime graph."
**Why:** Persistent JSON graph tracking supersession/authority/reference-counts/temporal-decay—accumulates from usage patterns, informs annotation layer

**Context:** BRAIN = persistent graph state (~/.context/imem_graphs/brain.json) tracking chunk relationships discovered through usage. Every query updates reference counts, graph operations cache PageRank scores, supersession patterns accumulate. Over 3-6 months, BRAIN learns which chunks are authoritative (high reference count), superseded (newer similar chunks), or decaying (old, rarely referenced).

**Key Properties:**
- Continuous learning (updates from every query/graph operation)
- Persistent state (survives across sessions)
- Usage-driven (not design speculation—learns from actual retrieval patterns)
- Feeds annotation layer (provides temporal/supersession context for LLM pass)

**Structure:**
```json
{
  "chunks": {
    "chunk-id": {
      "superseded_by": ["newer-chunk-id"],
      "supersession_confidence": 0.89,
      "age_months": 18,
      "reference_count": 23,
      "pagerank_score": 0.72
    }
  }
}
```

**Endstate Role:** Informs cheap LLM annotation pass. Haiku reads BRAIN state, adds soft language: "This decision (18 months old, referenced 23 times) was later refined..." vs "OBSOLETE"

---

## Soft Decay Language via Cheap LLM Pass
**Quote:** "that could soften language for temporally decayed chunks, or superceded chrunks."
**Why:** Haiku annotation pass ($0.0001/chunk) adds interpretive context before Claude sees—"This was later refined..." not "OBSOLETE"—contextualization not removal

**Context:** Don't remove old chunks. Contextualize them. Before serving to Claude, cheap LLM (Haiku) reads BRAIN state and annotates chunks with soft temporal/supersession language. "This decision from 18 months ago was later refined..." preserves genealogy while signaling currency. Cost negligible (~$0.001 per 10-chunk query).

**Three Annotation Targets:**
1. Chunk content (inline warnings): "⏳ Temporal Context: This decision from Oct 2023..."
2. Header labels (status badges): "# DECISION: Use Redis [⏳ SUPERSEDED] [📅 Oct 2023]"
3. Prompt templates (section notes): "## Primary Decision [Historical] - ⚠️ Interpretive Note: This decision was later refined..."

**Language Philosophy:** Soft not harsh. "Later refined" not "obsolete". "Historical context" not "deprecated". Preservation with awareness.

---

## Documents 98-100% Aligned
**Quote:** "i think these are 100%?"
**Why:** Architecture.md already shows batch correctly (parallelization peer command), vision.md shows CLI composition, roadmap phases validated—only 2% refinement needed

---

## Cross-Project Authority = High Theoretical Power
**Quote:** Review of pattern.md + "how valuable do oyu see this being? feels powerful. but dont know until we test it."
**Why:** PageRank across projects finds authoritative patterns—BUT stacked assumptions (pattern abstraction burden, authority usefulness, project similarity) require validation

---

## Incremental Testing Path Defined
**Quote:** "dont know until we test it"
**Why:** Phase 1: Test pattern layer usage → Phase 2: Test graph ops single-project → Phase 3: Test cross-project IF 1+2 succeed—kill criteria at each phase prevents overbuilding

---

## BRAIN Annotation = Endstate Not MVP
**Quote:** "we are thinking long-term, not MVP obviously. But it is good to know the endstate."
**Why:** Requires persistent state, usage accumulation (3-6 months), LLM pass latency, soft language refinement—build primitives first, let BRAIN learn, add annotation when validated

**Context:** Annotation layer is 12-18 month horizon. Depends on: (1) Primitives working (Phase 6-7), (2) BRAIN accumulating usage patterns (3-6 months data), (3) Supersession hints validated, (4) Authority scores meaningful. Cannot build without foundation.

**Dependencies:**
- BRAIN needs data (reference counts, supersession patterns, authority scores)
- Soft language needs refinement (test what works: "later refined" vs "superseded" vs "evolved")
- Annotation latency must be acceptable (~200ms per chunk with Haiku)

**Value Uncertainty:**
- Unknown if soft language improves retrieval vs clutters
- Unknown if temporal decay matters in practice
- Unknown if Claude benefits from annotations vs raw chunks

**Build Order:** Primitives (Phase 6-7) → Usage logs (Phase 8) → BRAIN accumulation (Phase 9, 3-6 months) → Annotation layer (Phase 10, test with subset)

---

## Serving Pipeline = Six Layers at Endstate
**Architecture:**
1. Semantic search (Qdrant)
2. Relationship discovery (siblings/genealogy/temporal)
3. Graph operations (if requested—pagerank/centrality)
4. BRAIN lookup (load supersession/authority/decay state)
5. LLM annotation (Haiku adds soft language)
6. Template assembly (structure with relationship labels)

**Why:** Each layer adds interpretability—from raw vectors to "This decision (superseded Oct 2024, but context valuable) originally chose Redis..."

---

## Implementation Order Validated
**Phase 6:** siblings + filter primitives (~100 lines, 1 day)
**Phase 7:** graph build + apply (~200 lines, 1.5 days)
**Phase 8:** Slash command library (ongoing, 10-20 lines markdown each)
**Phase 9+:** Usage mining → BRAIN accumulation → Annotation layer (12-18 months)

**Why:** Build validated primitives (13+ real uses), observe patterns, defer complexity until proven need

---

## "queries" Format = Right Interface for v1
**Quote:** Discussion of "queries" vs generic "op" format complexity
**Why:** Specialized sugar for common case (90% = multi-query + graph rank), concise without "op" boilerplate—defer generic "parallel" format until validated mixed-operation need

---

## Knowledge Graph = Fixed Bundling, AURA = Dynamic Bundling
**Quote:** "Oh, thats the only difference? the knoweldge graph bundle related chunks? but then we could one up that no?"
**Why:** KG precomputes edges (rigid), AURA constructs graph per query (flexible)—authority query uses PageRank bundling, explanation query uses sibling bundling, timeline query uses temporal bundling—same primitives, infinite strategies

---

## Soft-Graph Inverts Paradigm
**Insight:** KG = Static graph → dynamic queries | AURA = Dynamic graph ← query intent
**Why:** Graph structure adapts to query not vice versa—this IS the architectural innovation distinguishing from both traditional RAG and graph DBs

**Context:** Traditional knowledge graphs precompute edges at write time. Query navigates fixed structure. AURA inverts: Edges discovered at query time via metadata. Graph constructed per-query based on intent. Authority query uses PageRank bundling. Explanation query uses sibling bundling. Timeline query uses temporal bundling. Same primitives, infinite bundling strategies.

**Key Distinction:**
- **Knowledge Graphs:** Write-time edge computation, read-time traversal, fixed relationships
- **Traditional RAG:** No relationships, flat semantic search, model infers structure
- **AURA Soft-Graph:** Query-time edge discovery, runtime graph construction, flexible relationships

**Example:**
```
Query: "Most authoritative auth decision"
→ Multi-query (decisions + failures + patterns)
→ Build graph from results
→ Apply PageRank (authority bundling)
→ Return top-ranked with context

Query: "Explain auth decision completely"
→ Single query (decision)
→ Find siblings (sibling bundling)
→ Find conversation (genealogy bundling)
→ Return decision + constraints + origin

Same chunks. Different bundling strategies. Query intent shapes graph.
```

**Innovation:** Not better KG (rigid), not better RAG (flat), but query-adaptive relationship assembly. Graph as serving strategy, not storage structure.
