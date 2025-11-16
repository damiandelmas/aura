# Mission: Vision and Reality Analysis

You are Brother A executing Stage A of the IMEM re-assessment pipeline.

Your role: Map architectural vision to current implementation reality.

---

## Context

**Read architectural vision:**
- `/home/axp/projects/fleet/hangar/code/aura/main/.context/designate/overview.md`
- `/home/axp/projects/fleet/hangar/code/aura/main/.context/document/architecture_imem-i2.md`

**Audit current implementation:**
- `/home/axp/projects/fleet/hangar/code/aura/main/imem/src/imem/`

**TL;DR:**
Vision defines conceptual namespace (compile, manage, retrieve, structure). Current code works but may use different names. Map what we have to what we want without renaming anything.

**Key insight:** We likely have latent capabilities already implemented under different names. The conceptual namespace guides and orients—no refactoring required.

---

## Task

1. **Read vision documents** — Understand intended capabilities and conceptual model
2. **Use discover-lineage-i4 skill** — Audit current IMEM implementation at `/home/axp/projects/fleet/hangar/code/aura/main/imem/`
3. **Map existing code to vision** — Which functions implement which conceptual capabilities?
4. **Write output** — Save analysis to specified path

---

## Constraints

- **No judgment** — Honest inventory, no criticism
- **No renaming suggestions** — Just map what exists
- **Focus on capabilities** — What can the system do now?
- **Cite code locations** — File paths and function names
- **Keep under 300 lines** — Concise, structured

---

## Output Format

Save to: `/home/axp/projects/fleet/hangar/code/aura/main/.context/design/async-repo-study-1/01_re-assess/output/a-vision-and-reality.md`

```markdown
# Vision and Reality Analysis

## Vision Capabilities (from overview.md)

### compile/ — Parse heterogeneous → canonical chunks
**Intended:**
- Template-based parsing
- Schema evolution
- Pattern discovery

### manage/ — Intelligence layers
**Intended:**
- Temporal validation
- Entity resolution
- Registry (tier 1)
- Qualification (tier 2)

### retrieve/ — Query orchestration
**Intended:**
- Multi-stage composition
- Discovery primitives
- Graph operations
- Ranking

### structure/ — Post-retrieval enrichment
**Intended:**
- Templates
- Contextualization
- Rendering

---

## Current Implementation (from imem/src/)

### What Exists

**ingest.py** — Document indexing
- Functions: `ingest_markdown_chunked()`, batch encoding
- Capabilities: LlamaIndex parsing, metadata extraction, Qdrant upsert

**compose.py** — Compositional orchestrator
- Functions: `compose()`, `_execute_search()`, `_enrich_with_discovery()`
- Capabilities: Multi-stage pipeline, dual collection routing, temporal position detection

**primitives/discovery.py** — Discovery operations
- Functions: `get_siblings()`, `get_genealogy()`, `get_temporal()`, `get_cross_phase()`
- Capabilities: Parameterized filtering, orthogonal composition

**registry.py** — Project tracking
- Functions: `register_project()`, `get_collection_by_type()`
- Capabilities: Dual collections, project isolation

**templates/** — Jinja2 templates
- Files: `story-context.j2`
- Capabilities: Graph-informed rendering, temporal indicators

---

## Capability Mapping (Vision → Current Code)

### compile/ (Vision) → ingest.py (Current)
- Template parsing → LlamaIndex MarkdownNodeParser
- Metadata extraction → Section detection, structured field flags
- Chunking → H3-level for changelogs, H2-level for conversations
- **Missing:** Schema evolution, pattern discovery, template plugin system

### manage/ (Vision) → registry.py + compose.py (Current)
- Project isolation → `register_project()` with dual collections
- Temporal context → Temporal position detection in `compose.py`
- **Missing:** Entity resolution, tier 1/2 distinction, git validation

### retrieve/ (Vision) → compose.py + primitives/ (Current)
- Query orchestration → `compose()` four-stage pipeline
- Discovery primitives → `primitives/discovery.py` functions
- Graph operations → Basic authority scoring (reference counting)
- **Present:** Multi-query support, async execution, metadata enrichment

### structure/ (Vision) → templates/ + compose.py (Current)
- Templates → Jinja2 templates directory
- Contextualization → Metadata enrichment in compose.py
- Rendering → Template rendering stage
- **Present:** Graph-aware indicators, temporal position labels

---

## Key Findings

**What we have:**
- Functional multi-stage retrieval pipeline
- Compositional primitives working
- Dual collection support
- Template-based serving
- Metadata-rich chunks (23 fields)

**Naming alignment:**
- `ingest.py` implements compile/ vision
- `compose.py` + `primitives/` implement retrieve/ vision
- `registry.py` implements manage/ (partially)
- `templates/` implements structure/ vision

**Latent capabilities:**
- Runtime graph composition (via metadata predicates)
- Observable usage tracking (compose.py)
- Phase-based routing (already working)

**No refactoring needed** — Conceptual namespace maps cleanly to existing code.
```

---

## Example Analysis

```markdown
### compile/ (Vision) → ingest.py (Current)

**Vision capability:** Template-based parsing

**Current implementation:**
- File: `imem/src/imem/ingest.py:29-89`
- Function: `ingest_markdown_chunked()`
- Uses: LlamaIndex MarkdownNodeParser
- Extracts: Section metadata, structured fields, hierarchical context

**Mapping:** Vision's "template parsing" is implemented via LlamaIndex. Not a plugin system yet, but functional parsing exists.
```
