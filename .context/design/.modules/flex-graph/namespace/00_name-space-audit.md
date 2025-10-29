● Namespace Audit

  ---
  A. Industry Standard Graph Terms

  Node/Vertex Concepts

  - Node - Single entity in graph
  - Vertex - Synonym for node
  - Degree - Number of edges connected to node
  - In-degree - Incoming edges count
  - Out-degree - Outgoing edges count

  Edge/Relationship Concepts

  - Edge - Connection between nodes
  - Directed edge - One-way relationship (A → B)
  - Undirected edge - Bidirectional (A ↔ B)
  - Weight - Edge strength/importance
  - Edge type - Relationship category (SIBLING, TEMPORAL, etc)

  Graph Topology Patterns

  - Hub - Node with many connections
  - Bridge - Node connecting clusters
  - Cluster - Densely connected subgraph
  - Chain - Linear sequence (A→B→C→D)
  - Star - Hub with spokes
  - Tree - Hierarchical structure
  - DAG - Directed Acyclic Graph

  Graph Metrics

  - PageRank - Authority score based on incoming links
  - Centrality - Importance in network position
  - Betweenness - Bridge importance (shortest paths)
  - Closeness - Average distance to all nodes
  - Community - Detected cluster

  Graph Operations

  - Traversal - Walking the graph
  - Search - Finding nodes/paths
  - Ranking - Ordering by metric
  - Clustering - Grouping by similarity
  - Path finding - Route between nodes

  ---
  B. RAG/Retrieval Standard Terms

  Chunk Concepts

  - Chunk - Single retrievable unit
  - Document - Source containing chunks
  - Embedding - Vector representation
  - Score - Semantic similarity score
  - Payload - Chunk metadata

  Retrieval Concepts

  - Semantic search - Vector similarity
  - Hybrid search - Vector + keyword
  - Reranking - Reordering results
  - Filtering - Metadata constraints
  - Top-k - Limit to k results

  Context Concepts

  - Context window - Token limit for LLM
  - Augmentation - Adding retrieved chunks to prompt
  - Grounding - Source citations
  - Hallucination - LLM fabrication

  ---
  C. Our Domain-Specific Terms (Changelogs)

  Session Concepts

  - Session - One work conversation/session
  - Changelog - Documented session output
  - File path - Unique changelog file
  - Phase - conversation | design | develop | document

  Section Concepts

  - Section - Chunk within changelog (## header)
  - Section type - Decisions | Failures | Constraints | Patterns | Code
  - Section level - H2 vs H3 hierarchy
  - Section name - Heading text

  Temporal Concepts

  - Timestamp - When created
  - Age - Time since creation
  - Recency - How recent
  - Currency - How current/relevant

  Quality Concepts

  - Has rationale - Contains reasoning
  - Has alternatives - Considered other options
  - Semantic score - Search relevance
  - Confidence - Signal strength

  ---
  D. Our Current (Confused) Namespace

  What We Call Things Now

  "Sibling" - Sections from same changelog
  - ⚠️ Confusing: Sounds like peer relationship
  - Reality: Same-session sections (file_path match)

  "Genealogy" - Conversation origin
  - ⚠️ Confusing: Sounds like inheritance chain
  - Reality: Session_id filter for conversation chunks

  "Temporal" - Semantically similar across time
  - ✅ Decent: Implies time dimension
  - ⚠️ Vague: Doesn't clarify semantic + temporal

  "Cross-phase" - Related chunks in different phase
  - ✅ Clear: Describes exactly what it does

  "Superseded" - Replaced by newer work
  - ❌ WRONG: We can't actually detect this
  - Reality: High topic activity (not actual supersession)

  "Authority" - Important/canonical
  - ❌ WRONG: Using sibling count (wrong metric)
  - Reality: Should be reference count or pagerank

  "Current thrust" - Active development direction
  - ⚠️ Confusing: Unclear what "thrust" means
  - Reality: Trying to detect active vs abandoned

  "Continuation count" - Later related chunks
  - ✅ Descriptive but wordy

  ---
  E. Proposed Clean Namespace

  Retrieval Primitives (What They Actually Do)

  same_session_sections() - Previously "siblings"
  - What: Sections from same changelog file
  - Signal: Documentation granularity
  - Metric: Count = session comprehensiveness

  session_origin() - Previously "genealogy"
  - What: Conversation chunks that led to this
  - Signal: Origin thinking/debugging
  - Filter: session_id + source='conversation'

  semantic_temporal() - Previously "temporal"
  - What: Similar chunks across time dimension
  - Signal: Topic evolution/activity
  - Filter: embedding_similarity + timestamp

  phase_related() - Previously "cross_phase"
  - What: Related chunks in different phase
  - Signal: Design → develop → document continuity
  - Filter: keyword_overlap + phase≠current

  Graph Relationships (Edges)

  SAME_SESSION - Edge type (file_path match)
  SESSION_ORIGIN - Edge type (session_id match)
  SEMANTIC_TEMPORAL - Edge type (embedding + time)
  PHASE_CONTINUATION - Edge type (cross-phase)

  Topology Patterns

  linear_chain - A→B→C→D (evolution)
  hub_spoke - A ← B,C,D,E (many references)
  story_arc - conversation→decision→code (narrative)
  cluster - A↔B↔C↔D (thematic group)

  Context Signals (What We Can Actually Detect)

  topic_activity - Count of semantic_temporal chunks
  - High: Hot topic (many sessions)
  - Low: Isolated work
  - NOT: Supersession status

  session_granularity - Count of same_session_sections
  - High: Comprehensive documentation
  - Low: Quick fix
  - NOT: Authority

  reference_frequency - How often retrieved (from BRAIN)
  - High: Frequently referenced
  - Low: Rarely accessed
  - IS: Actual usage-based authority

  temporal_position - Where in evolution chain
  - Inferred from: Graph topology + BRAIN state
  - Types: active_branch | abandoned_branch | intermediate
  - NOT: Boolean current/superseded

  ---
  F. The Mapping (Old → New)

  | Old Term           | New Term                    | Why Changed                     |
  |--------------------|-----------------------------|---------------------------------|
  | siblings           | same_session_sections()     | Clearer what it returns         |
  | genealogy          | session_origin()            | Less academic, more descriptive |
  | temporal           | semantic_temporal()         | Explicit: semantic + time       |
  | cross_phase        | phase_related()             | ✅ Keep or phase_continuation()  |
  | superseded         | topic_activity (signal)     | We can't detect supersession    |
  | authority          | reference_frequency (BRAIN) | Use actual metric               |
  | current_thrust     | temporal_position (enum)    | More precise                    |
  | continuation_count | continuation_count          | ✅ Keep                          |

  ---
  G. Clean Architecture Terms

  Storage Layers

  - Qdrant - Immutable chunk storage
  - Entity Map - Term canonicalization
  - BRAIN - Persistent learned metadata
  - Graph - Ephemeral composition

  Operations

  - Retrieve - Get chunks from Qdrant
  - Compose - Build ephemeral graph
  - Analyze - Detect topology
  - Enrich - Add context signals
  - Structure - Topology-aware formatting
  - Serve - Return to AI agent

  ---
  H. Questions for You

  1. Primitives naming: Prefer same_session_sections() or keep siblings() with clear docs?
  2. Temporal position: Use enum active_branch | abandoned_branch | intermediate or
  different terms?
  3. Topic activity: Call it topic_activity or evolution_activity or semantic_lineage?
  4. BRAIN metrics: Keep reference_frequency or usage_count or retrieval_frequency?

  Let's hash it out. What resonates? What's still confusing?