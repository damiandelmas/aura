---
session_id: 7b8d151d-3cfd-482f-a4e6-d9da4516bac5
---

# What is IMEM?

**A dialogue to understand the system**

---

## Core Concept

**Q: What is IMEM?**

A knowledge compiler for AI agent memories.

**Q: What does "knowledge compiler" mean?**

Like a code compiler transforms source → executable, IMEM transforms agent output → queryable knowledge.

**Q: What's the input?**

Agent coding session artifacts:
- Markdown files (design notes, development logs, research)
- Conversations (message sequences between user and assistant)
- Git metadata (commits, diffs, timestamps)

**Q: What's the output?**

Structured chunks with:
- Normalized metadata (phase, section type, timestamp)
- Explicit relationships (spatial, temporal, conceptual)
- Optional vector embeddings (for semantic search)

**Q: Why "compiler" and not "indexer"?**

Because we're transforming structure, not just creating search index. Compilation = parse + normalize + resolve + store.

---

## The Compilation Process

**Q: What does compilation do?**

Three stages:

**1. PARSE**
- Extract chunks from markdown (sections, paragraphs)
- Parse frontmatter metadata
- Extract conversation turns

**2. RESOLVE**
- Normalize structure: "planning notes" → "design" phase
- Normalize sections: "Key Decisions" → "Decision" type
- Normalize entities: "JWT auth" → "jwt" concept

**3. STORE**
- SQLite for metadata (phase, section_type, timestamp)
- Relationships table (graph edges between chunks)
- Optional vector embeddings (for semantic similarity)

**Q: What's the "canonical structure"?**

Four lifecycle phases that all agent work maps to:

- **design**: Exploration, ideation, research, problem framing
- **designate**: Specification, planning, architecture decisions
- **develop**: Implementation, coding, testing, iteration
- **document**: Reflection, lessons learned, documentation

**Q: Why these four?**

Because agent workflows follow this cycle. You explore (design), plan (designate), build (develop), reflect (document). Different agents use different words, but the structure is the same.

**Q: Example?**

Agent says "## Planning Phase" → IMEM resolves to `phase: "designate"`

Agent says "## Implementation Notes" → IMEM resolves to `phase: "develop"`

Same meaning, normalized representation.

---

## Why This Matters

**Q: Why not just full-text search?**

Because you want to ask:
- "What decisions were made during development?"
- "Show me all design explorations from last week"
- "Find patterns that were designated but never implemented"

Full-text search can't answer these. Structured metadata can.

**Q: Why not just RAG with embeddings?**

Because vector similarity doesn't understand temporal relationships, decision lineage, or phase transitions.

**Q: What does IMEM understand that RAG doesn't?**

- **Temporal**: This chunk came before/after that chunk
- **Structural**: This is a decision, that's an implementation
- **Relational**: This decision led to that code
- **Spatial**: These chunks are part of same document/conversation

---

## The Knowledge Graph

**Q: What kind of graph does IMEM build?**

Explicit relationship edges between chunks.

**Q: What relationships exist?**

- `spatial_proximity`: Chunks in same document (sequential context)
- `conversation_continues`: Chunks in same session (dialogue flow)
- `temporal_cluster`: Chunks from similar timeframe (what happened when)
- `decision_implements`: Decision chunk → implementation chunk (causality)
- `pattern_applied`: Pattern chunk → usage chunk (reuse)

**Q: Why explicit relationships instead of inferring from metadata?**

Because "same file_path" doesn't mean "related." Two chunks in same file might be completely unrelated. Explicit edges capture actual relationships.

**Q: How are relationships detected?**

During compilation:
- Spatial: Document structure (ordered chunks)
- Temporal: Timestamp proximity + phase correlation
- Causal: Pattern matching (decision language → implementation references)
- Conversational: Session ID continuity

---

## Metadata Architecture

**Q: What's the difference between metadata and relationships?**

Metadata = properties OF a chunk. Relationships = connections BETWEEN chunks.

**Q: Example?**

**Metadata:**
```json
{
  "id": "chunk_123",
  "content": "We decided to use JWT for authentication",
  "phase": "designate",
  "section_type": "Decision",
  "timestamp": "2025-11-18T10:30:00",
  "file_path": ".context/designate/auth-decisions.md"
}
```

**Relationship:**
```
chunk_123 --[decision_implements]--> chunk_456
(Decision about JWT) --> (JWT implementation code)
```

**Q: Where do these live?**

Metadata: Columns on `chunks` table (SQL queryable)

Relationships: Separate `relationships` table (JOIN queryable, graph traversable)

---

## Retrieval Model

**Q: How do you query IMEM?**

Three modalities:

**1. Metadata Filtering** (SQL-based, <10ms)
```
Find all decisions from develop phase last week
→ WHERE phase='develop' AND section_type='Decision' AND timestamp > '2025-11-11'
```

**2. Relationship Traversal** (Graph-based)
```
Given this decision, what implementations followed?
→ SELECT * FROM relationships WHERE source_id='chunk_123' AND type='decision_implements'
```

**3. Semantic Search** (Vector-based, optional)
```
Find chunks similar to "authentication patterns"
→ Embedding similarity search (requires vectors)
```

**Q: Can you combine these?**

Yes. Compose pipeline:
- Search by metadata (fast filter)
- Expand via relationships (graph traversal)
- Rank by recency or semantic similarity
- Return enriched results

**Q: What if I don't have vectors?**

Metadata + relationships still work. Vectors are enhancement, not requirement.

---

## The SQL-First Philosophy

**Q: Why SQLite primary instead of vector database?**

Because most queries are structural, not semantic:
- "Show me develop phase from this week" (metadata filter)
- "What decisions led to this code?" (relationship traversal)
- "How many chunks per phase?" (aggregation)

These are fast SQL queries. Vectors aren't needed.

**Q: When do you need vectors?**

For semantic similarity: "Find chunks about authentication" (concept, not keyword).

**Q: So vectors are optional?**

Exactly. Modality you add when needed. Core functionality works without them.

**Q: What vector backends exist?**

- **Qdrant**: External service (Docker), production scale
- **HNSW**: Embedded in SQLite (local, fast build)
- **None**: Metadata-only (fastest, simplest)

User chooses based on needs.

---

## Resolution: The Normalization Engine

**Q: What does "resolution" mean?**

Mapping variations to canonical forms.

**Q: Two types?**

**COMPILE Resolution** (structural):
- Input: "planning", "spec", "implementation notes"
- Output: phase="design"|"designate"|"develop"
- Purpose: Universal structure normalization

**MANAGE Resolution** (semantic):
- Input: "JWT", "Json Web Token", "jwt-auth"
- Output: entity="jwt", type="technology"
- Purpose: Project-specific concept normalization

**Q: Why separate?**

Different scopes. COMPILE = universal (same for all projects). MANAGE = project-specific (learns from corpus).

**Q: How does learning work?**

Resolution tables track variations:
```sql
INSERT INTO phase_variations VALUES ('planning notes', 'design', 0.95)
INSERT INTO entity_variations VALUES ('JWT auth', 'jwt', 'technology', 0.90)
```

System learns over time what variations map to canonical forms.

---

## The Four Domains

**Q: How is IMEM architected?**

Four separated domains:

**COMPILE**: Transform agent output → structured chunks
- Parse markdown, conversations, git metadata
- Detect sections, extract content
- Normalize structure (resolution)

**MANAGE**: Enrich with project-specific knowledge
- Entity detection and normalization
- Concept clustering
- Metadata enrichment

**STORAGE**: Abstract backend access
- Protocol-based (VectorStore interface)
- Supports SQLite, Qdrant, HNSW
- Handles metadata + relationships + vectors

**RETRIEVE/COMPOSE**: Orchestrate queries
- Build retrieval pipelines from config
- Search → discover → rank → return
- Processor chain pattern

**Q: Why separate domains?**

Single responsibility. Each domain has one job. Changes to storage don't affect compilation. New retrieval strategies don't touch parsing.

---

## What IMEM Enables

**Q: What can you do with compiled agent memories?**

**Temporal Analysis:**
- "What was I working on last Tuesday?"
- "Show me the decision timeline for this feature"

**Pattern Recognition:**
- "How often do I redesign after first implementation?"
- "What patterns appear in develop phase vs design phase?"

**Knowledge Reuse:**
- "Have I solved this problem before?"
- "What decisions led to successful outcomes?"

**Context Reconstruction:**
- "What was I thinking when I wrote this?"
- "Show me the conversation that led to this decision"

**Q: How is this different from reading markdown files?**

You can query across time, across projects, across phases. You can traverse relationships. You can aggregate patterns. You can't do this with raw files.

---

## Design Principles

**Q: What makes IMEM different from typical RAG?**

**Explicit Structure**: Phases, sections, relationships stored directly (not inferred)

**Temporal Awareness**: Time is first-class (not just a metadata field)

**Graph-Based**: Relationships are queryable edges (not just vector similarity)

**Compilation Model**: Transform structure (not just index text)

**SQL-Native**: Rich querying via SQL (not just vector similarity)

**Q: What's the core philosophy?**

Agent memories have inherent structure. Extract it. Make it queryable. Enable knowledge work at scale.

---

## Common Misconceptions

**Q: Is IMEM just a vector database?**

No. Vectors are optional. Core is metadata + relationships in SQL.

**Q: Is it a documentation tool?**

No. It compiles agent output. Documentation might be one input, but not the focus.

**Q: Is it project-specific?**

No. Works across any codebase. Learns project-specific concepts via MANAGE resolution, but compilation is universal.

**Q: Does it replace git?**

No. Git tracks code. IMEM tracks knowledge. Complementary, not competitive.

---

## When to Use IMEM

**Use IMEM when:**
- You have agents producing markdown/conversations regularly
- You want to query across time ("what did we decide last month?")
- You need to understand decision lineage
- You want to find patterns in agent behavior
- You're building knowledge over multiple sessions/projects

**Don't use IMEM when:**
- You just need full-text search (grep works)
- You have static documentation (wiki is fine)
- You don't have agent workflows
- You don't need temporal/relational queries

---

## Mental Model

Think of IMEM as:

**Not:** A search engine for documents

**Instead:** A compiler for agent memory, producing queryable knowledge graph with temporal and structural awareness

**Analogy:**
- Git compiles code changes → version history
- IMEM compiles agent output → knowledge history

---

**Remember:** IMEM transforms agent chaos into structured knowledge. Parse → resolve → store → query. Metadata + relationships + optional vectors. SQL-first, graph-aware, temporally structured.
