# IMEM Structure

## Conceptual Architecture

```
imem/
├── compile/                    # Parse heterogeneous → canonical chunks
│   ├── Parser                 # Template-based parsing
│   ├── Templates              # Domain parsers (changelog, conversation, etc)
│   ├── Resolver               # Schema evolution (structure → types)
│   └── Observer               # Pattern discovery
│
├── manage/                     # Intelligence layers
│   ├── Temporal               # Git validation (project-level)
│   ├── Resolver               # Entity resolution (values → canonical)
│   ├── Registry               # Tier 1: Objective facts (cross-project)
│   └── Qualification          # Tier 2: Usage metadata (cross-project)
│
├── retrieve/                   # Query + graph operations
│   ├── Orchestrator           # Multi-stage composition pipeline
│   ├── Primitives             # Discovery (siblings, genealogy, temporal)
│   ├── Graph                  # Graph algorithms (PageRank, authority)
│   └── Ranking                # Authority, confidence, recency scoring
│
├── structure/                  # Post-retrieval enrichment
│   ├── Templates              # Jinja2 presentation templates
│   ├── Contextualize          # Add graph metadata to chunks
│   └── Render                 # Format for consumption
│
├── storage/                    # Backend adapters
│   ├── SQLite                 # Compiled output (metadata + chunks)
│   ├── Qdrant                 # Vector embeddings (derived)
│   └── Readers                # Parse markdown + JSONL conversations
│
└── CLI                         # Command interface
```

## Key Distinctions

**compile/resolver** — Schema evolution: maps heterogeneous structure → lifecycle-compatible types (onboards any codebase)
**manage/resolver** — Entity resolution: normalizes project entities (jwt, JWT → jwt) for reliable queries

**manage/temporal** — Project-level: validates chunks against git diffs (four-phase lifecycle)
**manage/registry** — Cross-project tier 1: objective reference facts (document exists, metadata)
**manage/qualification** — Cross-project tier 2: usage metadata and interpretation (about tier 1)

**retrieve/** — Determines WHAT to return (graph queries, ranking, filtering)
**structure/** — Determines HOW to present (templates, enrichment, rendering)

**Git repository** — Source of truth (markdown files, .jsonl conversations)
**storage/sqlite** — Compiled output (queryable metadata + chunks)
**storage/qdrant** — Vector embeddings (semantic search)