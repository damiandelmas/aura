---
session_id: "034ba596-240e-4bc3-b71a-2194dafd9656"
---

# Aura Architecture Namespace

**Glossary of all architectural concepts, methodologies, and components**

---

## Storage Architecture (Three-Tier Gateway)

### **Tier 0: Raw Sources**
The thing itself. Heterogeneous formats: URLs, codebases, PDFs, local markdown, APIs, databases. All treated as intellectual capital regardless of authority.

### **Tier 1: Objective Registry**
Normalized markdown wrappers around Tier 0 sources. Contains objective facts: source URL, retrieval_method, authority (as provenance fact), tags, summary. Inert metadata—no judgment about value.

### **Tier 2: Subjective Qualifiers**
Per-project wrappers that qualify sources at serve time. Contains: attention (usage accumulation), serve_as (qualification), motivation (why accessed), keywords. Same source has different Tier 2 wrappers per project.

### **Authority at Point of Serve**
Core principle: Authority is not intrinsic to sources. It's determined by Tier 2 context + usage patterns at serve time. A develop log is "ground truth" in its origin project, "reference example" elsewhere.

---

## Intelligence Layer (MIND)

### **MIND**
Intelligence architecture operating ACROSS storage layer. Consists of: Schema Evolution, Entity Resolution, Runtime Graphs, Introspection, Temporal Cortex. Backend-agnostic—works regardless of retrieval method.

### **Schema Evolution**
Observes natural language patterns in Tier 0 content, clusters to canonical section_type values. Type-level resolution: "Decision:", "Choice:", "We Decided:" → section_type="Decision". Part of FlexSchema methodology.

### **Entity Resolution**
Clusters keyword/tag variants to canonical forms. Value-level resolution: "jwt", "JWT", "jwt-tokens" → canonical entity "auth". Enables query expansion without standardization.

### **Runtime Graphs**
Materializes graph edges from metadata predicates on-demand. Query returns k chunks → compute k² implicit edges from session_id, timestamp, file_path, section_type. Run PageRank, communities, etc. Discard after serving. Part of FlexGraph methodology.

### **Introspection**
Exposes system capabilities programmatically. AI queries: "What can I search?" System returns: discovered section_types, entity mappings, available fields. Self-describing, zero documentation drift.

### **Temporal Cortex**
Validates documentation against code via git diffs. Detects drift, computes divergence radius (0=direct, 1=sibling, 2=same-log). Serves as pattern when code evolved. Truth through implementation.

---

## Core Methodologies

### **FlexSchema**
Type system evolution methodology. Pipeline: Observation → Clustering → Emerged types → Semantic relationships. Write naturally, schemas emerge from patterns, no pre-declared types. Hindley-Milner for documents. (CORE dimensions would enhance this if implemented.)

### **FlexGraph**
Runtime graph materialization methodology. Index metadata predicates → Query returns k results → Materialize k-subgraph → Compute O(k²) edges on-demand → Run graph algorithms → Serve with topology context. No precomputed O(n²) graph.

### **Three-Tier Gateway**
Data organization pattern. Normalize heterogeneous sources (Tier 0→1) → Objective facts (Tier 1) → Subjective qualification (Tier 2) → Authority at serve time. Low-friction capture, intellectual capital accumulation.

### **Temporal Truth Validation**
Reality grounding methodology. Track code via git → Compare docs vs implementation → Detect drift → Compute divergence radius → Graduated serving based on divergence. Code is source of truth.

### **Metadata Network Orchestration**
Universal retrieval interface. Query intent → Route to appropriate backend(s) (IMEM, Graphiti, WebFetch, filesystem) → Execute retrieval → Enrich with MIND intelligence → Serve with qualification. Backend-agnostic.

---

## CORE Dimensions (Architectural Design)

**NOTE: THIS IS HYPOTHETICAL! We may be better off juse using an LLM to resolve TYPE to our schema without having this 'objective' layer**

**Six universal dimensions for chunk classification:**

- **Interrogative:** WHO | WHAT | WHERE | WHEN | WHY | HOW
- **Valence:** GOOD | BAD | NEUTRAL
- **Abstraction:** CONCRETE | ABSTRACT | META
- **Epistemic:** KNOWN | HYPOTHETICAL | UNKNOWN
- **Temporal:** PAST | PRESENT | FUTURE
- **Structural:** ATOMIC | COMPOSITE | RELATIONAL

**Architecture:** Apply at index time (universal), resolve at serve time (contextual).

**Enables:**
- Bootstrap without corpus (first doc gets full typing)
- Cross-domain transfer (same coordinates, different domain interpretations)
- Confidence scoring (epistemic dimension prevents over-resolution)
- AI-augmented construction (structured input for agents)

**Status:** Foundational to FlexSchema methodology. Current system implements implicitly via template parsing. Explicit CORE classifier would make coordinate system visible.

**See:** [CORE Schema](./flexschema/01_core-schema.md), [Hindley-Milner conversation](./tiny-models/Claude-Hindley-Milner type system explained.md)

---

## Implementation Layer

### **IMEM**
Typed vector document store. Implements FlexGraph methodology internally. Provides: vector similarity search, parameter space metadata, runtime graph composition. One retrieval backend among many (equal to Graphiti, WebFetch, etc.).

### **Parameter Space**
~30-35 metadata dimensions per vectorized chunk: id, embedding, section_type, section_name, category, subtype, session_id, timestamp, keywords, status, has_* fields, word_count, etc. Foundation for all MIND operations.

### **Template System**
Markdown structure as type system. H2 headers declare types (Decision, Pattern, Failure). H3 instances have required/optional fields. MarkdownNodeParser extracts structure → section_type metadata. Template IS the database schema.

---

## Data Structures

### **Chunk**
Vectorized content unit with full parameter space. Contains: embedding (768-dim), content (text), metadata (all parameters). Unit of storage in vector database, unit of retrieval in queries.

### **Collection Types**
H2 section with multiple H3 instances. Examples: Decisions (0-N Decision instances), Patterns (0-N Pattern instances). Each H3 is a chunk with section_type from parent H2.

### **Singleton Types**
H2 section with inline content (no H3s). Examples: Request (user quote), Overview (narrative). Single chunk with section_type from H2 title.

### **Dual Metadata**
Every chunk has two metadata layers: Template (structural types from H2/H3 parsing) + Frontmatter (semantic context inherited from document). Enables: type-safe semantic search.

---

## Query Operations

### **Semantic Search**
Vector similarity search via embedding. Query text → embed → find nearest neighbors in vector space. Returns chunks sorted by cosine similarity score (0-1).

### **Type-Safe Queries**
Semantic search + metadata filtering. Example: section_type='Decision' + vector_similarity("auth") = semantically similar Decision instances about auth. Fuzzy + precise combined.

### **Genealogical Traversal**
Follow session_id links. Changelog chunk → session_id → conversation chunks. Bidirectional: user request → AI response → generated changelog.

### **Temporal Traversal**
Order by timestamp + semantic similarity. Find evolution chains: earlier Decision → later Decision (semantically similar). Detect supersession via forward temporal edges.

### **Metadata Predicates**
Indexed fields enabling graph edge materialization: session_id (genealogy), timestamp (temporal), file_path (co-location), section_type + category (type-based). FlexGraph materializes edges from these.

---

## Key Principles

### **Authority at Point of Serve**
Authority determined by context at serve time, not declared upfront. Tier 2 qualifies sources: canonical, ground truth, reference example, pattern inspiration.

### **Templates as Type Declarations**
Markdown structure defines database schema. Write `## Decisions`, you declare Decision type. Write `### Use JWT` with `- Context:`, you instantiate with required fields.

### **Retrieval-Agnostic Intelligence**
MIND operations work across any backend. Swap Qdrant for Pinecone, add Neo4j—intelligence persists. Metadata Network abstracts retrieval method.

### **Truth Through Implementation**
Documentation validated against code. Git diffs reveal divergence. Temporal Cortex detects drift. Serve based on validation state. Code = ground truth.

### **Progressive Instantiation**
Not every changelog has every type. Not every instance uses every optional field. Schema flexible, structure guaranteed when present. Write what matters.

---

## Related Documents

**Vision:** [vision/00_architecture-vision.md](./vision/00_architecture-vision.md)

**Storage:** [three-tier/](./three-tier/), [architecture-i2/database/](./architecture-i2/database/)

**Intelligence:** [architecture-i2/mind/](./architecture-i2/mind/)

**Methodologies:** [architecture-i2/flexgraph/](./architecture-i2/flexgraph/)

**Parameters:** [parameter-space/](./parameter-space/)
