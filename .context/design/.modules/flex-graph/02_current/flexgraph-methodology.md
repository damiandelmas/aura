# FlexGraph Methodology

**Proposed Pattern for Query-Adaptive Graph Operations**

*Status: Exploratory - Core concepts validated, full system under development*

---

## Core Principle

**Hypothesis: AI agents compose graph operations at runtime via declarative config.**

Traditional knowledge graphs: Build edges at write time, query fixed structure.
FlexGraph: AI agents compose operations at runtime via single command.

**Point of use:** `imem compose '{search, discovery, graph, output}'` → One call, full pipeline.

---

## The Inversion

```
Traditional KG:
Write → Build ALL edges (O(n²)) → Store graph → Query structure

FlexGraph:
Write → Store metadata only → Query → Build ephemeral graph (O(k²)) → Discard
```

**Key insight:** k << n (query 20 results, not 10,000 documents)

---

## Requirements

For FlexGraph methodology to work, you need:

### 1. Creation-Time Schema Enforcement

**Problem:** Post-hoc metadata extraction is probabilistic (~70% accuracy)

**Solution:** Template enforcement at document creation

```markdown
Template defines schema:
## Decision
- **Context**: (required field)
- **Solution**: (required field)
- **Rationale**: (optional field)

AI generates content → Validates against template → Guaranteed metadata
```

**Result:** 100% metadata compliance (deterministic, not probabilistic)

**Why this matters:**
- Enables deterministic filtering: `WHERE has_context=true AND has_alternatives=true`
- Competitors can't easily replicate (requires breaking change for existing users)
- Foundation for all downstream operations (validated in practice)

### 2. Small Result Sets

**Complexity trade-off:**
- Precomputed KG: O(n²) at write time, O(1) at read time
- FlexGraph: O(0) at write time, O(k²) at read time

**This works when:** k << n

**Typical scenarios:**
- n = 10,000 documents
- k = 20-50 query results
- O(k²) = 400-2,500 edge computations (~40-100ms)
- O(n²) = 100,000,000 edges (hours to precompute)

**1,000,000× efficiency gain**

### 3. Metadata as Edge Predicates

**Metadata dimensions become relationship types:**

| Metadata Field | Edge Type | Discovery Predicate |
|----------------|-----------|---------------------|
| file_path | SIBLING | file_path == X |
| session_id | GENEALOGY | session_id == Y |
| timestamp + semantic | TEMPORAL | timestamp > Z ∧ similarity > 0.7 |
| semantic similarity | SEMANTIC | cosine_similarity > 0.8 |

**No explicit edges stored.** Relationships discovered via metadata queries.

---

## Pattern: Query-Time Graph Construction

### Workflow

```
1. Semantic Search → Top-k results (20-50 chunks)
2. Build Graph:
   - Nodes: Results
   - Edges: Metadata relationships
   - O(k²) complexity (~40-100ms)
3. Apply Algorithm:
   - PageRank → Authority ranking
   - Centrality → Bridge detection
   - Communities → Clustering
4. Rerank Results
5. Discard Graph
```

### Ephemeral Property

**Graph lifecycle:**
- Created: On query
- Used: Single algorithm application
- Destroyed: After ranking

**Optional persistence:**
- Session graphs (reuse during conversation)
- Canonical graphs (frequently accessed patterns)
- Otherwise: ephemeral

---

## Edge Discovery Algorithms

### Chunk-Level Relationships

**SIBLING** (Same Document):
```python
def discover_siblings(chunk_id):
    chunk = get_chunk(chunk_id)
    return filter(file_path == chunk.file_path)
```

**GENEALOGY** (Conversation Origin):
```python
def discover_genealogy(chunk_id):
    chunk = get_chunk(chunk_id)
    return filter(session_id == chunk.session_id)
```

**TEMPORAL** (Evolution):
```python
def discover_temporal(chunk_id):
    chunk = get_chunk(chunk_id)
    return filter(
        timestamp > chunk.timestamp
        AND semantic_similarity(chunk) > 0.85
    )
```

### Document-Level Relationships

**SEQUENTIAL** (Project Narrative):
```python
def discover_sequential(doc_id):
    doc = get_document(doc_id)
    return filter(
        filename_chronology_adjacent(doc.filename)
        AND semantic_similarity > 0.7
    )
```

**THEMATIC** (Cross-Phase):
```python
def discover_thematic(doc_id):
    doc = get_document(doc_id)
    return filter(
        topic_keywords_overlap(doc.keywords)
        AND different_phase(doc.phase)
    )
```

---

## Graph Algorithms (Query-Adaptive)

Same chunks, different insights based on query intent:

### PageRank: Authority Ranking

**When:** "What's the most important pattern?"

**Algorithm:** PageRank weights nodes by incoming edges

**Result:** Most-referenced chunks surface first

**Use case:** Find canonical decisions

### Betweenness Centrality: Bridge Detection

**When:** "What connects topic A and B?"

**Algorithm:** Centrality scores nodes on shortest paths

**Result:** Bridge concepts surface

**Use case:** Find architectural patterns connecting domains

### Community Detection: Clustering

**When:** "Group related concepts"

**Algorithm:** Louvain communities

**Result:** Natural semantic clusters

**Use case:** Discover topic boundaries

### Temporal Sort: Evolution Timeline

**When:** "How did this decision evolve?"

**Algorithm:** Topological sort on temporal edges

**Result:** Chronological chain

**Use case:** Trace decision genealogy

---

## Complexity Analysis

| Scenario | Precomputed KG | Soft-Graph |
|----------|----------------|------------|
| **Write time** | O(n²) edges | O(0) |
| **Storage** | O(n²) | O(0) |
| **Query time** | O(edges) traversal | O(k²) construction |
| **Maintenance** | O(n) rebuild | O(0) |

**Where:**
- n = corpus size (thousands)
- k = result set (20-50)

**Trade-off:**
- Slower queries (80-200ms vs <10ms)
- Zero maintenance (vs continuous reindexing)
- Query-adaptive (vs fixed structure)

---

## When to Use FlexGraph

### Ideal For:

✅ **Evolving knowledge** (not static corpora)
- Documents constantly added/updated
- Relationships change over time
- Traditional KG maintenance overhead unacceptable

✅ **AI-generated content** (template compliance natural)
- AI agents create structured documents
- Schema enforcement straightforward
- Metadata guaranteed

✅ **Flexible relationships** (not fixed schema)
- New relationship types emerge
- Query-specific graph structure
- No schema migration needed

✅ **Moderate latency tolerance** (80-200ms acceptable)
- Not real-time systems
- User queries (not API microseconds)
- Latency acceptable for quality

### NOT Ideal For:

❌ **Static document corpus**
- One-time ingest, rarely updated
- Precomputed KG amortizes well

❌ **Human-generated unstructured content**
- Can't enforce template compliance
- Post-hoc extraction necessary
- Metadata not guaranteed

❌ **Millisecond latency requirements**
- High-frequency API calls
- Precomputed graph faster

❌ **Fixed relationship schema**
- Known relationships upfront
- No query-time adaptation needed

---

## Domain Implementations

FlexGraph is a **methodology**, not a product. Different domains implement it differently:

### IMEM (Coding Agents)

**Domain:** Software development changelogs

**Template Structure:**
- Decisions (Context, Solution, Rationale)
- Constraints (Description, Impact, Mitigation)
- Failures (Attempted, Why Failed, Lesson)

**Metadata → Edges:**
- file_path → siblings
- session_id → genealogy
- timestamp + semantic → temporal

**Use case:** Coding agent memory

### WriteMem (Hypothetical)

**Domain:** Long-form writing

**Template Structure:**
- Ideas (Thesis, Evidence, Counter-Argument)
- Drafts (Version, Changes, Rationale)
- Citations (Source, Context, Reliability)

**Metadata → Edges:**
- draft_version → revision chain
- section_id → structural
- citation_id → reference graph

**Use case:** Writing agent memory

### ResearchMem (Hypothetical)

**Domain:** Academic research

**Template Structure:**
- Hypotheses (Claim, Evidence, Confidence)
- Experiments (Method, Result, Analysis)
- Literature (Paper, Summary, Relevance)

**Metadata → Edges:**
- experiment_id → hypothesis testing
- paper_doi → citation network
- topic_tags → semantic clusters

**Use case:** Research agent memory

---

## Properties Required for FlexGraph

**Methodology checklist:**

1. ✅ **Creation-time schema** (deterministic metadata)
2. ✅ **Runtime edge discovery** (metadata → predicates)
3. ✅ **Ephemeral graphs** (build per query, discard)
4. ✅ **Query-adaptive** (different algorithms per intent)

**NOT required:**
- ❌ Specific template structure
- ❌ Specific metadata fields
- ❌ Specific edge types
- ❌ Specific algorithms

**The pattern is portable. The details are domain-specific.**

---

## Architectural Layers

### L1: Methodology (This Document)

**What:** Pattern for building query-time knowledge graphs
**Who:** System architects, researchers
**Content:** Principles, complexity analysis, when to use

### L2: Domain Implementation

**What:** Application of pattern to specific domain
**Who:** Product builders
**Content:** Template structure, metadata mapping, algorithms

**Examples:**
- `imem-architecture.md` (coding agents)
- `writemem-architecture.md` (writing agents)

### L3: Codebase

**What:** Actual implementation
**Who:** Developers
**Content:** Python code, CLI, tests

**Examples:**
- `imem/src/` (IMEM implementation)
- `writemem/src/` (WriteMem implementation)

---

## The Proposed Innovation

**Traditional knowledge graphs:**
- Build structure at write time
- Query fixed relationships
- High maintenance overhead
- O(n²) precomputation

**FlexGraph (proposed approach):**
- Build structure at query time
- Discover relationships via metadata
- Zero maintenance (hypothesis)
- O(k²) on-demand construction
- AI agents compose operations declaratively

**Expected result:** Flexible, query-adaptive graph operations for agentic workflows.

*To be validated: Whether graph operations provide meaningful improvements over metadata-based discovery alone.*

---

## Summary

**Core Insight:** Relationships as queries, not stored structures

**Requirements:**
1. Creation-time schema (guaranteed metadata) - *Validated*
2. Small result sets (k << n) - *Working hypothesis*
3. Metadata predicates (latent edges) - *To be validated*

**Proposed Pattern:**
Query → top-k → build graph → apply algorithm → discard

**When to explore this approach:**
- Evolving knowledge bases
- AI-generated structured content
- Need for flexible relationship discovery
- Moderate latency tolerance (80-200ms)

**Status:** Methodology is domain-agnostic pattern. IMEM is first implementation (in development).

*Next: Validate whether graph operations (Layer 2B) provide meaningful value over metadata discovery (Layer 2A) alone.*
