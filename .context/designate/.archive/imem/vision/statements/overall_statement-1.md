---
session_id: "090c7e16-cb85-45e5-a1f0-8dd53f191a40"
---

# The System: IMEM

**Core:** Typed vector database where markdown structure defines semantic types for knowledge chunks.

---

## Three Architectural Exploitations

### 1. Template-as-Type-System

- AI writes markdown following template
- H2 declares types (Decision, Pattern, Failure), H3 instantiates them
- Frontmatter adds document properties (category, session_id, timestamp)
- LlamaIndex preserves hierarchy → typed chunks
- Every chunk has type metadata (section_type) + document properties
- All indexed in vector DB

### 2. Metadata Index = Implicit Graph

- Indexed metadata (file_path, session_id, timestamp) ARE traversable edges
- No separate graph storage
- Query metadata predicates = traverse graph O(log n)
- Traditional: O(n²) edge precomputation
- IMEM: O(0) precomputation, edges latent in index

### 3. Runtime Composition + Graph-Aware Serving

- API for AI to compose graphs from metadata queries
- 3-5 query budget → materialize subgraph → run algorithms
- Use topology to contextualize chunks intelligently
- Ephemeral (build, analyze, discard)

---

## MIND: Control Plane

Manager of document space.

**Runtime:** Graph composition API, schema introspection

**Storage:** Entity resolution (canonical terms), presets, optional persistent graphs

**Intelligence:** Pre-computed metrics, usage tracking

---

## The Flow

**Write:**
Template + frontmatter → LlamaIndex chunks → Entity resolution → Indexed with both type + document metadata

**Query:**
Schema introspection (optional) → Vector search + graph composition (optional) → Topology detection → Graph-aware serving

---

## The Value

Template creates typed chunks with indexed metadata.

That metadata enables:

- Type-safe queries (section_type='Decision')
- Implicit graph (metadata = edges)
- Runtime composition (materialize on demand)
- Intelligent serving (topology → context)

One system. Everything exploits what template already created.

**First typed vector database that's also a knowledge graph with intelligent serving.**
