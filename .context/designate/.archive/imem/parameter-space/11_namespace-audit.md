## ● NAMESPACE AUDIT: ARCHITECTURAL CLARITY

**Historical context:** This document captures the clarification process that led to clean separation of concerns. See [00_NAMESPACE.md](../00_NAMESPACE.md) and [vision/00_architecture-vision.md](../vision/00_architecture-vision.md) for current canonical definitions.

---

## Core Issue Diagnosed

You're mixing storage architecture (Tiers 0-2) with operational concepts (parameter space, retrieval,
graph traversal). They describe different concerns at different levels.

---
PROPOSED UNIFIED NAMESPACE

I. STORAGE ARCHITECTURE (Where Things Live)

├─ Tier 0: RAW SOURCES (heterogeneous)
│  └─ Actual content: URLs, codebases, PDFs, APIs
│
├─ Tier 1: OBJECTIVE REGISTRY (normalized markdown)
│  └─ Metadata wrappers: source, retrieval_method, authority, summary
│
└─ Tier 2: **SUBJECTIVE** QUALIFIERS (per-project wrappers)
    └─ Usage context: attention, serve_as, motivation, keywords

Purpose: Data organization and access patterns

---
II. INTELLIGENCE LAYER (.mind/ - What Makes Sense of It)

MIND operates ACROSS tiers:

├─ Schema Evolution: Type-level pattern detection
├─ Entity Resolution: Canonical form mapping
├─ Runtime Graphs: Metadata → implicit edges
├─ Introspection: Capability exposure
└─ Temporal Cortex: Truth validation via code drift

Purpose: Intelligence on top of dumb storage

---
III. PARAMETER SPACE (What's in Each Chunk)

Not another tier - it's the DIMENSIONAL STRUCTURE of vectorized content:

Per-chunk parameters:
├─ Identity: id, source, file_path, timestamp
├─ Vector: embedding (768-dim), semantic score
├─ Template: section_type, section_name, schema_version
├─ Frontmatter: category, subtype, session_id, keywords
└─ Structural: has_rationale, word_count, etc.

Purpose: Rich metadata for retrieval and graph construction

---
IV. RETRIEVAL OPERATIONS (How to Get Things)

Metadata Network orchestrates:
├─ webfetch: Live API calls
├─ qdrant: Vector similarity search
├─ filesystem: Direct file reads
├─ neo4j: Graph traversal (if materialized)
└─ Custom: Any backend

Purpose: Pluggable retrieval abstracted by metadata network

# our retrieval system = IMEM

READ: /home/axp/projects/fleet/hangar/code/aura/main/.context/design/architecture-i2/vision/typed-vector-document-store.md
/home/axp/projects/fleet/hangar/code/aura/main/.context/design/architecture-i2/database/document-properties.md
/home/axp/projects/fleet/hangar/code/aura/main/.context/design/architecture-i2/database/type-system.md

IMEM is being WRAPPED in our KNOWLEDGE SYSTEM.

the graph building workflow for retrieval is utilzed by imem. that workflow / methodlogy is called flexgraph: /home/axp/projects/fleet/hangar/code/aura/main/.context/design/architecture-i2/flexgraph/methodology.md

but we've built a difernt taoxnomy / ontology / layer on top of it. with our three teir system.


## THE CLEANED MENTAL MODEL

Three Separate Concerns:

1. STORAGE (Tiers 0-2)

- Tier 0: Thing itself
- Tier 1: Objective wrapper (markdown)
- Tier 2: Subjective qualifier (per-project)

2. INTELLIGENCE (MIND)

- Schema/entity emergence
- Graph materialization
- Truth validation
- Capability introspection

3. OPERATIONS

- Parameter Space: Metadata dimensions per chunk
- Retrieval: Backend-agnostic fetch methods
- Serving: Authority qualification at runtime

**IMEM!!! but we could WRAP any vector store or treival engine as well. u are CORERECT to have imem, graphiti, web fetch as 'equal' tools.**

---
STOP SAYING:

❌ "Tier 0 content → Tier 1 → Tier 2 → Qdrant"❌ "Three-tier storage with Qdrant"❌ "Parameter space
in three tiers"

START SAYING:

✅ Storage: Tier 0 sources wrapped by Tier 1 registries, qualified by Tier 2 gateways✅ Retrieval:
Metadata network routes to appropriate backend (Qdrant/webfetch/filesystem)✅ Intelligence: MIND
operates across all storage, adding schema/graph/validation✅ Parameters: Rich metadata per chunk
enables graph construction and serving logic

---
CONCRETE FLOW

1. SOURCE (Tier 0)
    → Anthropic docs URL

2. REGISTRY (Tier 1)
    → Markdown entry: source, retrieval_method, authority

3. PROJECT GATEWAY (Tier 2)
    → barbar/.mind/: ref, attention, serve_as

4. INGEST TO VECTOR DB
    → Parse Tier 1 → Fetch Tier 0 → Vectorize → Store in Qdrant

5. QUERY
    → User: "auth patterns for barbar"
    → Qdrant semantic search + metadata filters
    → Returns k chunks with parameter space metadata

6. MIND ENRICHMENT
    → Materialize graph from metadata predicates
    → Compute PageRank, detect supersession
    → Qualify authority via Tier 2 context

7. SERVE
    → "Official: Anthropic hooks (canonical)"
    → "Implementation: barbar auth log (ground truth)"

---
KEY PRINCIPLE

Tiers ≠ pipeline stages

Tiers = data architecture (how sources are wrapped/qualified)Parameter space = metadata richness
(dimensions per chunk)MIND = intelligence architecture (how to understand/serve)Retrieval =
operational layer (how to fetch)

Don't conflate them.

---
Simpler framing:
- Tiers: where things live
- Parameters: what we know about chunks
- MIND: how we make sense of it
- Retrieval: how we get it

Clear?