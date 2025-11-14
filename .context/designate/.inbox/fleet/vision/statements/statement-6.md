● Three-Tier System: Architecturally Coherent Overview

The Structure

TIER 0: Raw Intellectual Capital (Heterogeneous)
↓
TIER 1: Objective Gateway (Normalization to Markdown)
↓
TIER 2: Subjective Gateway (Per-Project Qualification)
⊥
MIND: Intelligence Layer (Orthogonal)

---
TIER 0: The Things Themselves

All sources treated equally as intellectual capital:
- Anthropic official docs
- Your develop logs
- Code repositories
- Design documents
- Research papers

Key properties:
- Language-agnostic
- Format-agnostic (URL, PDF, markdown, code)
- No hierarchy at this layer
- Just existence—no judgment

---
TIER 1: Objective Gateway (Normalization)

Universal adapter: Wraps Tier 0 in standardized markdown + frontmatter

Purpose: Homogenize heterogeneous sources

Structure:
---
source: <pointer to Tier 0>
retrieval_method: webfetch|qdrant|filesystem|neo4j
authority: 1-10 (objective provenance fact)
tags: [official, develop-log, pattern]
created: <timestamp>
---

## Summary
[150-250 word description]

Key properties:
- INERT facts ABOUT sources
- Retrieval-method agnostic
- One entry serves infinite intentions
- Sitting side-by-side (Anthropic doc = develop log = code repo)

---
TIER 2: Subjective Gateway (Qualification)

Per-project wrappers that QUALIFY at point of serve

Structure:
project-barbar/.mind/references/
anthropic-hooks.md:
    ref: tier1-anthropic-hooks
    attention: 0.9
    motivation: "security validation patterns"

barbar-auth-log.md:
    ref: tier1-barbar-auth-develop
    attention: 0.95
    motivation: "ground truth for our implementation"

Key properties:
- Context determines authority
- Usage tracking (attention, access count)
- Append-only motivation logs
- Same source → different qualification per project

Authority at serve:
- barbar queries auth → barbar-auth-log served as "ground truth"
- npta queries auth → barbar-auth-log served as "reference example"

---
MIND: Intelligence Layer (Orthogonal)

Operates ACROSS tiers, not IN the stack

1. Schema Evolution (Type-level)

- Observe: "Decision:", "Choice:", "We Decided:"
- Cluster → canonical: "decision"
- Hindley-Milner for documents

2. Entity Resolution (Value-level)

- Observe: jwt, JWT, auth, oauth
- Cluster → canonical: auth.jwt: ["jwt", "JWT", ...]
- Query expansion automatic

3. Introspection (Capability Discovery)

- AI asks: "What can I query?"
- System exposes: fields, types, entities
- Zero documentation drift

4. Runtime Graph Composition

- Metadata predicates = implicit edges
- Materialize on-demand (O(k²) not O(n²))
- PageRank → authority, communities → clusters

5. Temporal Cortex (Truth Validation)

- Git diffs → code evolution
- Compare documented vs actual
- Graded supersession by narrative radius
- Code = truth, docs flagged when stale

---
The Key Principles

1. Authority at Point of Serve

Not: "Official docs > personal notes" (intrinsic hierarchy)But: Context
determines value (emergent authority)

2. Normalization Layer

Tier 1 = universal adapter patternHeterogeneous Tier 0 → homogeneous
markdown interface

3. Retrieval Agnostic

Tier 1 specifies method: webfetch, qdrant, neo4j, filesystemBackend
swappable, interface unchanged

4. Intellectual Capital Accumulation

- Low-friction capture (Tier 1: 30 seconds)
- Context accumulation (Tier 2: automatic)
- Selective deep ingestion (Qdrant: when needed)
- Metadata network > vector store

5. Intelligence Independent of Storage

MIND operates on metadata regardless of:
- Qdrant vs Elasticsearch vs Neo4j
- Summary vs full content
- Ingested vs not ingested

---
The Architecture in Motion

Query: "Auth patterns barbar used, high confidence"
↓
Tier 2: Filter barbar/.mind/ for auth + high attention
↓
MIND: Entity resolution (auth → [jwt, oauth, hooks])
        Schema evolution (pattern type discovered)
        Graph composition (PageRank for authority)
↓
Tier 1: Retrieve entries with mixed retrieval methods
↓
Tier 0: Execute retrievals (webfetch, qdrant, filesystem)
↓
MIND: Temporal cortex (drift detection)
        Introspection (qualify at serve)
↓
Results: Unified, contextualized, enriched
        "Canonical reference" vs "Ground truth" labels

---
Why It's Architecturally Powerful

Separation of concerns:
- Tiers = data (what exists, how wrapped, who accesses)
- MIND = intelligence (how to understand, serve, validate)

Clean abstraction:
- Data layer is dumb (markdown + frontmatter)
- Intelligence layer is smart (emergence, resolution, graphs)
- No mixing, no confusion

Contextual authority:
- Value emerges from usage, not pre-declaration
- Same source → different meaning per project
- Honest about reality

Self-organizing:
- Schemas emerge from observation
- Entities resolve from patterns
- Truth validated through implementation
- Intelligence compounds with usage

---
This is HTTP for knowledge: protocol-level abstraction over pluggable
backends, wrapped in contextual intelligence.