# ONBOARD: Metadata-First Indexing

**(1) READ IMPLEMENTATION PLAN**

/home/axp/projects/fleet/hangar/code/aura/main/.context/designate/implementation-plans/metadata-first-indexing.md

## ARCHITECTURE

**Current Vision Documents:**
/home/axp/projects/fleet/hangar/code/aura/main/.context/designate/codebase-shape.md
/home/axp/projects/dashboard/251115-1221/markdowndb/metadata-for-all.md

## RECENT CONTEXT

**Most Recent Changelog:**
/home/axp/projects/fleet/hangar/code/aura/main/.context/develop/.changes/251117-1227_multi-source-routing-clean-output.md

**Current State:**
/home/axp/projects/fleet/hangar/code/aura/main/.prompts/state-251117.md

## CODEBASE

**Relevant Files:**

**Current Parsing:**
```
imem/src/imem/ingest.py (1200 LOC)
  - Uses LlamaIndex + Qdrant (vector-first)
  - Only indexes document phase (8/284 files)
```

**Target Files to Create:**
```
imem/src/imem/parse/markdown.py
imem/src/imem/storage/sqlite.py
imem/src/imem/cli.py (modify for new commands)
```

## OBJECTIVE

Parse 284 markdown files → SQLite (no vectors) → Query metadata in <10ms

**Current:** 8 files indexed (vector-required)
**Target:** 284 files indexed (metadata-only, vectors optional)

## KEY CONSTRAINTS

- No LlamaIndex for parsing (too heavy)
- Use `python-frontmatter` + standard library
- SQLite only (Qdrant remains for selective vectorization)
- <15 seconds total indexing time
- Backward compatible (don't break existing Qdrant flow)
