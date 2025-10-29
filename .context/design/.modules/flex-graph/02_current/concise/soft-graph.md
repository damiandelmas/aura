● ● Soft-Graph as Methodology vs Implementation

  Three Abstraction Levels:

  ---
  Level 1: Soft-Graph (Methodology)

  Core Principle:
  Relationships = queries, not structures

  Requirements:
  1. Guaranteed metadata (creation-time enforcement)
  2. Small result sets (k << n, enables O(k²))
  3. Metadata predicates that represent relationships

  Pattern:
  Query → top-k results → build graph from metadata → apply algorithm → discard

  Domain-agnostic. Pure architectural approach.

  ---
  Level 2: Domain Implementations

  IMEM (Coding Agents)

  Domain: Software development changelogs

  Template:
  - Decisions (Context, Solution, Rationale)
  - Constraints (What, Discovery, Workaround)
  - Failures (Attempted, Why Failed, Lesson)

  Metadata → Edges:

  Chunk-level:
  - session_id → genealogy (conversation origin)
  - timestamp + semantic → temporal (chunk evolution)
  - file_path → siblings (sections within same file)
  - section_type → categorical (decisions/constraints)

  Document-level:
  - filename chronology + semantic → sequential work (project narrative arc)
  - topic keywords + phase → thematic continuity (design → develop → document)

  Graph Algorithms:
  - PageRank → authority (most-referenced patterns)
  - Centrality → bridges (connecting architecture concepts)
  - Temporal chains → evolution (decision/document genealogy)
  - Community detection → thematic clusters (related work grouping)

  ---
  WriteMem (Writing Agents) - Hypothetical

  Domain: Long-form writing (essays, articles, books)

  Template:
  - Ideas (Thesis, Evidence, Counter-Argument)
  - Drafts (Version, Changes, Rationale)
  - Citations (Source, Context, Reliability)

  Metadata → Edges:
  - draft_version → revision chain
  - section_id → structural (chapter/section)
  - citation_id → reference graph
  - theme_tags → semantic clusters

  Graph Algorithms:
  - PageRank → most-cited sources
  - Temporal → draft evolution
  - Community detection → thematic clusters

  ---
  ResearchMem (Research Agents) - Hypothetical

  Domain: Academic research notes

  Template:
  - Hypotheses (Claim, Evidence, Confidence)
  - Experiments (Method, Result, Analysis)
  - Literature (Paper, Summary, Relevance)

  Metadata → Edges:
  - experiment_id → hypothesis testing
  - paper_doi → citation network
  - topic_tags → semantic relationships
  - lab_notebook_id → genealogy

  Graph Algorithms:
  - Citation PageRank → influential papers
  - Hypothesis → experiment chains
  - Topic clustering → research themes

  ---
  Level 3: Infrastructure (Shared)

  Vector Storage: Qdrant, Pinecone, Weaviate
  Embeddings: E5, BGE, OpenAI
  Graph Ops: NetworkX, igraph
  LLM: Haiku/Sonnet for pattern extraction

  Same infrastructure, different domain implementations.

  ---
  The Naming Question

  Soft-Graph: The methodology
  IMEM: Soft-graph for coding agents
  WriteMem: Soft-graph for writing agents (hypothetical)
  ResearchMem: Soft-graph for research (hypothetical)

  Or:
  AURA: The platform/framework
  IMEM module: Coding agent implementation
  WriteMem module: Writing agent implementation

  ---
  What Makes Something "Soft-Graph"?

  Required properties:
  1. Creation-time schema (deterministic metadata)
  2. Runtime edge discovery (metadata → predicates)
  3. Ephemeral graphs (build per query, discard)
  4. Query-adaptive (different algorithms per intent)

  Not required:
  - Specific template structure
  - Specific metadata fields
  - Specific edge types
  - Specific algorithms

  The methodology is the pattern, not the details.

  ---
  IMEM's Position

  IMEM = Soft-graph methodology applied to coding agent memory

  Specific choices:
  - Template: Software development structure
  - Edges: session/temporal/sibling
  - Algorithms: PageRank/centrality/temporal

  But another domain (writing, research, legal) would make different choices while
   using same methodology.

  ---
  The Generalization

  Soft-Graph Methodology:
  - Works for any domain with structured knowledge creation
  - Requires discipline (template compliance)
  - Enables zero-maintenance relationship discovery
  - Scales to O(k²) not O(n²)

  When to use:
  - Knowledge constantly evolving (not static)
  - AI agents creating content (compliance natural)
  - Need flexible relationships (not fixed schema)
  - Want zero graph maintenance

  When NOT to use:
  - Static document corpus (precomputed KG better)
  - Human-generated unstructured content (can't enforce template)
  - Need millisecond latency (precomputed faster)
  - Fixed relationship schema sufficient

  ---
  Bottom Line

  Soft-Graph: Architectural methodology (relationships via runtime queries)

  IMEM: Domain-specific implementation (coding agents, changelogs)

  *Future Mem systems: Same methodology, different domains

  The insight is portable. The implementation is domain-specific.
