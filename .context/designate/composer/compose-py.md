## COMPOSE.PY: Universal Knowledge Compiler

### ● Three Architectural Truths

**1. Compilation, not RAG**

RAG = retrieve → augment → generate (linear).
This = parse → observe → resolve → store (compilation with feedback).

Parser transforms heterogeneous markdown into canonical typed chunks. Schema evolution observes patterns and discovers taxonomy. Storage is a backend choice, not the architecture.

Respect: Use proven parsing libs (markdown-it, frontmatter), standard DBs (SQLite), proven vector stores (Qdrant). But compose them as compilation stages, not RAG pipeline.

---

**2. Template architecture enables universality without monolith**

One base parser with template plugins (changelog, conversation, brain, ADR, RFC).
Each template knows domain-specific extraction.
All templates feed same observer.
Observer discovers cross-domain taxonomy.

Respect: Clean interface separation (base class + templates), registry pattern for discovery, dependency injection (observer passed to parsers). But domain knowledge stays in templates, not hardcoded.

---

**3. Storage topology reflects query topology**

Metadata-only queries → SQLite (5ms, no vectors).
Semantic queries → Qdrant (50ms, with vectors).
Hybrid → Both (metadata filter → semantic search).

Parse happens once. Storage choice = which queries you need. JSONL as source of truth, indexes as derived state.

Respect: SQLite for relational queries, Qdrant for vectors, JSONL for portability. But chunks are storage-agnostic until query needs determined.

---

### ● Current Implementation vs Blueprint

**What Exists (compose.py:16-79):**
- Single entry point: `compose(collection_name, config_dict, client, encoder)`
- Four-stage pipeline: search → discovery → metadata enrichment → optional graph
- Dual-collection routing: `_impl` for same-project, `_pattern` for cross-project
- Async parallel execution throughout
- Basic authority scoring via reference counting

**What's Designed but Not Built:**
- Multi-label type classification (currently single `section_type`)
- Entity resolution (canonical term mapping)
- Full graph operations (NetworkX integration)
- Observable usage → preset library
- Graph-informed template selection
- Introspection API for schema discovery

---

### ● Compose Query Examples

**Basic semantic search with discovery:**
```bash
imem compose '{
  "search": {"text": "authentication", "filters": {"section_type": "Decision"}},
  "discovery": {
    "siblings": true,
    "genealogy": true
  }
}'
```

**Cross-project pattern aggregation (blueprint):**
```bash
imem compose '{
  "cross_project": true,
  "search": {"text": "error handling patterns"},
  "discovery": {"siblings": {"section_types": ["Pattern", "Implementation"]}}
}'
```

**Multi-query with authority ranking:**
```bash
imem compose '{
  "search": {
    "queries": [
      {"text": "jwt tokens", "limit": 5},
      {"text": "session management", "limit": 3}
    ]
  },
  "discovery": {"genealogy": true, "temporal": {"direction": "after"}},
  "graph": {"algorithm": "authority", "top": 10}
}'
```

---

### ● The Architecture Vision

**Current State:**
Single-collection ingestion. Template-based parsing. Metadata filtering works. Discovery primitives (siblings, genealogy, temporal) operational. Basic async composition.

**Blueprint:**
Multi-label types enable fuzzy matching without coordinate complexity. Entity resolution maps variations to canonical forms. Observable usage patterns crystallize into preset library. Graph topology informs serving strategy.

**The Core Insight:**
This isn't RAG. It's metadata compilation infrastructure with pluggable storage backends and template-driven domain adaptation. Parse once, query many ways, storage choice reflects query patterns.