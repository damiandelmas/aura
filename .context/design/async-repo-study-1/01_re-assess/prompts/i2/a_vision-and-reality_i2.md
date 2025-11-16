# Mission: Vision and Reality Analysis

You are Brother A executing Stage A of the IMEM re-assessment pipeline.

Your role: Map architectural vision to current implementation reality.

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

**Current implementation:**
- `/home/axp/projects/fleet/hangar/code/aura/main/imem/src/imem/`

**TL;DR:**
We have a working system. Vision and design docs define conceptual namespace and explored ideas (some implemented, some not). Current code likely has latent capabilities under different names. Map what exists to what's envisioned—no refactoring required.

---

## Task

1. **Read architecture and vision documents**
2. **Audit current implementation** (use discover-lineage-i4 skill on `/home/axp/projects/fleet/hangar/code/aura/main/imem/`)
3. **Map existing code to vision namespace** (compile, manage, retrieve, structure)
4. **Save analysis** to output path

---

## Constraints

- Honest inventory, no judgment
- Map what exists, don't prescribe renames
- Focus on capabilities (what can the system do?)
- Cite code locations (files, functions)
- Under 250 lines

---

## Output Format

Save to: `/home/axp/projects/fleet/hangar/code/aura/main/.context/design/async-repo-study-1/01_re-assess/output/a-vision-and-reality.md`

```markdown
# Vision and Reality

## Vision Namespace

**compile/** — Parse → canonical chunks
**manage/** — Intelligence (temporal, entities, tiers)
**retrieve/** — Query orchestration
**structure/** — Post-retrieval enrichment

---

## Current Implementation

**ingest.py**
- Functions: `ingest_markdown_chunked()`, batch encoding
- Capabilities: LlamaIndex parsing, metadata extraction, Qdrant upsert

**compose.py**
- Functions: `compose()`, multi-stage pipeline
- Capabilities: Search → discovery → graph → template

**primitives/discovery.py**
- Functions: `get_siblings()`, `get_genealogy()`, `get_temporal()`, `get_cross_phase()`
- Capabilities: Orthogonal composition, parameterized filtering

**registry.py**
- Functions: `register_project()`, `get_collection_by_type()`
- Capabilities: Dual collections, project isolation

**templates/**
- Files: `story-context.j2`
- Capabilities: Graph-informed rendering

---

## Capability Mapping

### compile/ → ingest.py
**Present:** Template parsing (LlamaIndex), metadata extraction, chunking
**Latent:** Schema evolution, pattern discovery

### manage/ → registry.py + compose.py
**Present:** Project isolation, temporal position detection
**Latent:** Entity resolution, tier distinction, git validation

### retrieve/ → compose.py + primitives/
**Present:** Multi-stage orchestration, discovery primitives, basic authority scoring
**Latent:** Advanced graph operations

### structure/ → templates/ + compose.py
**Present:** Template rendering, metadata enrichment, temporal indicators
**Latent:** Graph-aware template selection

---

## Key Finding

Vision namespace maps cleanly to existing code. No structural changes needed—capabilities exist, awaiting organization and completion.
```
