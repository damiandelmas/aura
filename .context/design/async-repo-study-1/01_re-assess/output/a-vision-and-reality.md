# Vision and Reality: IMEM Capability Mapping

## Vision Namespace (Conceptual Architecture)

**compile/** — Parse heterogeneous sources → canonical typed chunks
**manage/** — Intelligence layers (temporal, resolution, registry, qualification)
**retrieve/** — Query orchestration, discovery primitives, graph operations
**structure/** — Post-retrieval enrichment, template rendering, contextualization

---

## Current Implementation (Working System)

### Core Files

**ingest.py** (1,200+ LOC)
- Functions: `EnhancedModularIngest`, `ingest_markdown_chunked()`, batch encoding
- Location: `imem/src/imem/ingest.py`

**compose.py** (400+ LOC)
- Functions: `compose()`, `_execute_search()`, `_enrich_with_discovery()`, `_enrich_metadata()`
- Location: `imem/src/imem/compose.py`

**primitives/discovery.py** (335 LOC)
- Functions: `get_siblings()`, `get_genealogy()`, `get_temporal()`, `cross_phase_search()`
- Location: `imem/src/imem/primitives/discovery.py`

**registry.py** (110 LOC)
- Functions: `register_project()`, `get_collection_by_type()`, `update_doc_count()`
- Location: `imem/src/imem/registry.py`

**cli.py** (1,800+ LOC)
- Functions: `_index_phase()`, `imem init`, `imem search`, `imem compose`
- Location: `imem/src/imem/cli.py`

**templates/** (3 files)
- Files: `story-context.j2`, `genealogy.j2`, `timeline.j2`
- Location: `imem/templates/`

---

## Capability Mapping

### compile/ → ingest.py

**Present:**
- Template parsing via LlamaIndex MarkdownNodeParser (ingest.py:61)
- Metadata extraction: phase, layer, section_type, section_name, structured fields
- H3-level chunking for changelogs, H2-level for conversations
- Dual-collection routing: `_impl` vs `_pattern` based on `.pattern.md` suffix (cli.py:139)
- Batch encoding for performance (2x speedup)
- Nomic Embed v1.5 with auto-detection fallback to E5-Large-v2

**Latent:**
- Schema evolution observer (discover canonical types from corpus patterns)
- Multi-label type classification (chunks with multiple types)
- Pattern discovery across heterogeneous sources
- Universal resolver for arbitrary markdown structures

**Gap:**
- No compile/Resolver for schema evolution
- No compile/Templates plugin system
- No compile/Observer for pattern discovery
- Parser is fixed to LlamaIndex, not template-driven

---

### manage/ → registry.py + compose.py (partial)

**Present:**
- Project isolation via path hashing: `imem_{hash}_context` (registry.py:39)
- Dual-collection tracking (context + conversation) (registry.py:41-44)
- Collection lifecycle: registration, doc counts, indexed_at timestamps
- Temporal position detection: current_thrust, evolved, superseded, failed_branch (compose.py:63)

**Latent:**
- Git validation against commits (Temporal intelligence)
- Entity resolution within projects (normalize "jwt", "JWT" → canonical)
- Cross-project Registry (tier 1: objective facts)
- Cross-project Qualification (tier 2: usage metadata, authority scores)
- Full schema evolution (heterogeneous structure → lifecycle-compatible types)

**Gap:**
- No manage/Temporal (git diff comparison, four-phase validation)
- No manage/Resolver for entity normalization
- No cross-project tier 1/tier 2 distinction
- Registry is single-project, not cross-project intelligence

---

### retrieve/ → compose.py + primitives/discovery.py

**Present:**
- Multi-stage orchestrator: search → discovery → metadata enrichment → graph (compose.py:16-79)
- Async parallel execution for search and discovery stages
- Discovery primitives with parameterized filtering:
  - `get_siblings()`: Same file_path, filtered by section_types, has_rationale, has_alternatives (discovery.py:14-107)
  - `get_genealogy()`: Same session_id from conversations (discovery.py:110-176)
  - `get_temporal()`: Semantic similarity + chronological direction (discovery.py:179-260)
  - `cross_phase_search()`: Design → develop lineage via embeddings (discovery.py:263-334)
- Basic authority scoring via reference counting
- Collection routing: `_impl` for same-project, `_pattern` for cross-project (compose.py:41-47)

**Latent:**
- Full graph operations (PageRank, centrality, communities via NetworkX)
- Advanced authority scoring (git validation + usage patterns)
- Observable usage → preset library (pattern discovery from compose configs)
- Introspection API (schema discovery, corpus statistics)

**Gap:**
- Graph stage placeholder only (compose.py:66-73)
- No NetworkX integration
- No authority ranking beyond basic scores
- No preset library for recurring composition patterns

---

### structure/ → templates/ + compose.py

**Present:**
- Jinja2 template rendering (3 templates: story-context, genealogy, timeline)
- Metadata enrichment with temporal indicators (🟢 current, ⚠️ evolved, ❌ failed) (story-context.j2:6-14)
- Structured sections: Failures → Patterns → Decisions (story-context.j2:54-87)
- Confidence signals: continuation_count, has_rationale, has_alternatives (story-context.j2:22-29)
- Template selection via config: `output.template` (compose.py:76-77)

**Latent:**
- Graph-aware template selection (high PageRank + temporal chain → evolution template)
- Dynamic template generation based on result properties
- Contextualize layer (add graph metadata to chunks)
- Render layer (format for different consumption modes)

**Gap:**
- Template selection is manual, not graph-informed
- No separate Contextualize/Render modules
- Templates fixed to story-context pattern, not adaptive

---

## Storage Layer (Not in Vision but Implemented)

**Present:**
- Qdrant vector store (localhost:6334)
- Dual collections per project: `{hash}_context` + `{hash}_conversation`
- Dual layers per phase: `{collection}_impl` + `{collection}_pattern`
- Named vectors: Nomic Embed v1.5 (768D) with E5-Large-v2 (1024D) fallback
- HNSW indexing (m=16, ef_construct=100)
- Batch upsert operations

**Vision alignment:**
- Storage choice reflects query needs (semantic search via Qdrant)
- SQLite mentioned in vision but not implemented
- JSONL source of truth mentioned but not implemented (current: markdown → Qdrant directly)

---

## Key Finding: Implementation-First, Vision-Aligned

**Architecture exists, terminology differs:**

| Vision Namespace | Current Implementation | Status |
|------------------|------------------------|--------|
| compile/Parser | ingest.py:MarkdownNodeParser | ✅ Basic |
| compile/Templates | _(none)_ | ❌ Not modular |
| compile/Resolver | _(none)_ | ❌ Missing |
| compile/Observer | _(none)_ | ❌ Missing |
| manage/Temporal | compose.py:_enrich_metadata | 🟡 Partial |
| manage/Resolver | _(none)_ | ❌ Missing |
| manage/Registry | registry.py | 🟡 Single-project only |
| manage/Qualification | _(none)_ | ❌ Missing |
| retrieve/Orchestrator | compose.py:compose | ✅ Working |
| retrieve/Primitives | primitives/discovery.py | ✅ Working |
| retrieve/Graph | compose.py (placeholder) | 🟡 Designed, not built |
| retrieve/Ranking | compose.py:basic scores | 🟡 Partial |
| structure/Templates | templates/*.j2 | ✅ Working |
| structure/Contextualize | compose.py:_enrich_metadata | 🟡 Inline, not separate |
| structure/Render | compose.py:_render_template | 🟡 Basic |

---

## Capabilities Present (What System Can Do)

### Compilation Phase
✅ Parse markdown with LlamaIndex (H2/H3 chunking)
✅ Extract structured fields (Context, Solution, Rationale, Alternatives)
✅ Dual-layer routing (.pattern.md → pattern collection)
✅ Batch embedding generation (Nomic v1.5 + E5 fallback)
✅ Metadata-rich payloads (23 fields per chunk)

### Management Phase
✅ Project isolation via path hashing
✅ Dual-collection tracking (context + conversation)
✅ Temporal position detection (current_thrust, evolved, superseded, failed_branch)
🟡 Basic continuation counting for temporal classification
❌ No git validation against commits
❌ No entity resolution (jwt, JWT, jwt-tokens → canonical)
❌ No cross-project intelligence tiers

### Retrieval Phase
✅ Multi-stage orchestration (search → discover → enrich → graph)
✅ Async parallel execution
✅ Parameterized discovery primitives (siblings, genealogy, temporal, cross-phase)
✅ Metadata filtering (section_types, has_rationale, has_alternatives, order_by, limit)
✅ Collection routing (_impl vs _pattern)
🟡 Basic authority scoring (reference counting)
❌ No full graph operations (PageRank, centrality, communities)
❌ No preset library from observable usage patterns

### Structuring Phase
✅ Jinja2 template rendering (3 templates)
✅ Temporal indicators (🟢/⚠️/❌) for AI comprehension
✅ Structured sections (Failures → Patterns → Decisions)
✅ Confidence signals (continuation_count, has_rationale)
🟡 Manual template selection (not graph-informed)
❌ No adaptive template generation

---

## Lineage Timeline

**2025-10-24** — Genesis (commit 9268206)
- Initial implementation: basic search works

**2025-10-25** — Retrieval operational (commit 5fa703b)
- Search + metadata filtering functional

**2025-10-29** — Composition primitives (commits 0807ef0, d50113b, 0585e6c)
- Discovery layer: siblings, genealogy, temporal
- Multi-stage pipeline prototype

**2025-10-30** — Model migration (commit 3481866)
- Nomic Embed v1.5 + auto-detection architecture
- CLI refactor (commit 1e6db55)

**2025-11-01** — Dual-layer architecture (commit f642e70)
- `_impl` vs `_pattern` collection split
- .pattern.md routing

**2025-11-06** — Designate docs created (commit a36a018)
- Vision documents: compiler, composer, codebase-shape
- Conceptual architecture formalized

---

## Critical Insight

**The system works. Vision namespace provides organizational clarity, not structural changes.**

Capabilities exist under different names:
- "compile" → ingest.py (template parsing, metadata extraction)
- "manage" → registry.py + compose._enrich_metadata (isolation, temporal detection)
- "retrieve" → compose.py + primitives/ (orchestration, discovery)
- "structure" → templates/ + compose._render_template (presentation)

**Missing pieces are enhancements, not foundations:**
- Schema evolution (compile/Resolver, compile/Observer)
- Git validation (manage/Temporal)
- Entity resolution (manage/Resolver)
- Cross-project tiers (manage/Registry, manage/Qualification)
- Full graph operations (retrieve/Graph)
- Observable usage patterns (retrieve/preset library)
- Graph-informed templates (structure/Contextualize)

**No refactoring required. Clean organization awaiting completion.**
