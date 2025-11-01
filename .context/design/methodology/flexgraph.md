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

## Compositional Philosophy

**FlexGraph is not one pattern. It's compositional primitives that enable infinite combinations.**

### Layer 1: Primitives (Building Blocks)

FlexGraph provides composable primitives that can be combined ANY way:

| Primitive | What It Returns | Discovery Method |
|-----------|----------------|------------------|
| `siblings` | Chunks from same document | `filter(file_path=X)` |
| `genealogy` | Origin conversation | `filter(session_id=Y, source='conversation')` |
| `temporal` | Evolution over time | `semantic_search + timestamp filter` |
| `cross_phase` | Related phase chunks | `filter(phase=Z, keywords overlap)` |

**Key property:** These primitives are orthogonal. Any combination is valid.

---

### Layer 2: Infinite Compositions

**Agents compose primitives flexibly based on query intent.**

#### Composition Example A: Complete Story
**Query:** "Explain the JWT authentication decision"

**Composition:**
```json
{
  "discovery": {
    "genealogy": true,
    "cross_phase": "design",
    "siblings": {
      "section_types": ["Decisions", "Failures", "Patterns"]
    }
  },
  "output": {"template": "story"}
}
```

**Returns:**
1. Origin conversation (genealogy)
2. Design decisions (cross_phase)
3. What failed (siblings: Failures)
4. What worked (siblings: Decisions)
5. Patterns extracted (siblings: Patterns)

**Structure:** Narrative reconstruction from ideation → implementation

---

#### Composition Example B: Evolution Timeline
**Query:** "How did the caching strategy evolve?"

**Composition:**
```json
{
  "discovery": {
    "temporal": {"direction": "both"},
    "siblings": {
      "section_types": ["Patterns"],
      "order_by": "timestamp"
    }
  },
  "output": {"template": "timeline"}
}
```

**Returns:**
1. Earlier attempts (temporal: before)
2. Current implementation (primary)
3. Later refinements (temporal: after)
4. Patterns extracted over time (siblings: Patterns)

**Structure:** Chronological evolution showing how thinking changed

---

#### Composition Example C: Anti-Pattern Search
**Query:** "What approaches have we tried that didn't work?"

**Composition:**
```json
{
  "discovery": {
    "siblings": {
      "section_types": ["Failures"]
    }
  }
}
```

**Returns:**
- All Failures sections across documents
- What was attempted, why it failed, lessons learned

**Structure:** Cross-document failure compilation

---

#### Composition Example D: Pattern Library
**Query:** "Show me all reusable patterns for authentication"

**Composition:**
```json
{
  "discovery": {
    "siblings": {
      "section_types": ["Patterns"],
      "order_by": "timestamp"
    }
  }
}
```

**Returns:**
- Patterns sections from all related documents
- Ordered by recency (most recent first)

**Structure:** Curated pattern library for domain

---

#### Composition Example E: Design Journey
**Query:** "What was the design thinking before implementation?"

**Composition:**
```json
{
  "discovery": {
    "cross_phase": "design",
    "siblings": {
      "section_types": ["Decisions"],
      "has_rationale": true
    }
  }
}
```

**Returns:**
- Abstract design decisions (cross_phase)
- High-quality decisions with rationale (has_rationale filter)

**Structure:** Pre-implementation design exploration

---

#### Composition Example F: Constraint Analysis
**Query:** "What constraints influenced this decision?"

**Composition:**
```json
{
  "discovery": {
    "siblings": {
      "section_types": ["Constraints", "Decisions"]
    },
    "genealogy": true
  }
}
```

**Returns:**
- Constraint sections (limitations, trade-offs)
- Related decisions (how constraints were addressed)
- Origin conversation (where constraints emerged)

**Structure:** Decision drivers and limitations

---

### Layer 3: Observable Usage → Preset Library

**FlexGraph is usage-driven, not prescriptive.**

#### The Discovery Process

1. **Flexible composition:** AI agents compose primitives ANY way
2. **Usage observation:** System logs which compositions recur
3. **Pattern recognition:** After 10-20 uses of same composition
4. **Preset capture:** Proven pattern becomes slash command

#### Example: Emergence of `/explain-decision`

**Usage observation:**
```
Agent uses composition 30 times:
{"genealogy": true, "siblings": {"section_types": ["Decisions", "Failures", "Patterns"]}}

Queries that used this:
- "Explain the debounce fix"
- "Why did we choose JWT?"
- "How does caching work?"
- [27 more similar queries]
```

**Pattern recognized:** "Explain decision with full context" composition

**Capture as preset:**
```markdown
# .claude/commands/explain-decision.md

Find a decision and reconstruct complete context:
- Origin conversation (how we got here)
- Related failures (what we tried first)
- Extracted patterns (reusable learnings)

Usage: /explain-decision <query>

Internally expands to:
imem compose '{
  "search": {"text": "$QUERY", "limit": 1},
  "discovery": {
    "genealogy": true,
    "siblings": {"section_types": ["Decisions", "Failures", "Patterns"]}
  },
  "output": {"template": "story"}
}'
```

**Result:** Proven pattern captured for reuse

---

#### More Emergent Presets (Examples)

**Pattern detected (20 uses):**
```json
{"temporal": true, "siblings": {"section_types": ["Patterns"]}}
```
→ Captured as `/evolution-trace`

**Pattern detected (15 uses):**
```json
{"siblings": {"section_types": ["Failures"]}}
```
→ Captured as `/anti-patterns`

**Pattern detected (12 uses):**
```json
{"cross_phase": "design"}
```
→ Captured as `/design-journey`

**Pattern detected (10 uses):**
```json
{"siblings": {"section_types": ["Constraints"], "has_impact": true}}
```
→ Captured as `/constraint-analysis`

---

### The Innovation: Compositional + Observable + Self-Improving

**Traditional systems:**
- Fixed query types
- Predefined relationships
- Static structure
- No learning from usage

**FlexGraph:**
- ✅ Compositional primitives (any combination valid)
- ✅ Observable usage (track what agents do)
- ✅ Self-improving (capture proven patterns)
- ✅ Usage-driven presets (not prescriptive)

**The power hierarchy:**

```
Template-as-Schema (Foundation)
    ↓ enables
Deterministic Metadata (Primitives)
    ↓ enables
Compositional Flexibility (Any combination)
    ↓ enables
Observable Usage (Track patterns)
    ↓ enables
Self-Improving System (Capture proven patterns)
```

**Each layer builds on the previous.**

---

### When to Use Compositional FlexGraph

**Ideal for:**

✅ **Evolving knowledge bases**
- New composition patterns emerge with use
- System learns what works
- Preset library grows organically

✅ **AI agent workflows**
- Agents compose primitives based on query intent
- No manual pattern specification needed
- Natural language queries → automatic composition

✅ **Diverse query intents**
- Same chunks, different compositions
- "Explain decision" vs "Show evolution" vs "Find failures"
- Flexibility without predefining all patterns

✅ **Self-improving systems**
- Observable usage reveals useful patterns
- Proven patterns captured automatically
- System gets smarter with use

**Not ideal for:**

❌ **Static query types**
- If only one composition ever needed
- Flexibility unused
- Simple search sufficient

❌ **No usage observation**
- If can't track agent behavior
- Can't discover patterns
- Preset library doesn't emerge

---

### Domain Implementations with Composition

**IMEM (Coding Agents)**

Compositions naturally emerge:
- Narrative reconstruction (genealogy + siblings)
- Evolution timeline (temporal + patterns)
- Anti-pattern search (failures only)
- Design journey (cross-phase design)

**WriteMem (Hypothetical)**

Different compositions would emerge:
- Draft evolution (temporal chain of revisions)
- Citation network (reference traversal)
- Style analysis (comparison across drafts)

**ResearchMem (Hypothetical)**

Yet different compositions:
- Literature review (citation + semantic)
- Experiment lineage (temporal + genealogy)
- Hypothesis testing (cross-phase experiment → analysis)

**Same primitives. Different emergent patterns per domain.**

---

## Summary

**Core Insight:** Compositional primitives enable flexible, usage-driven knowledge retrieval

**Requirements:**
1. Creation-time schema (guaranteed metadata) - *Validated*
2. Compositional primitives (orthogonal building blocks) - *Core innovation*
3. Observable usage (track agent patterns) - *Self-improving mechanism*

**The Pattern:**
Flexible composition → Observable usage → Preset capture → Self-improvement

**When to use this approach:**
- Evolving knowledge bases
- AI-generated structured content
- Diverse query intents
- Self-improving systems

**Status:** Methodology is domain-agnostic pattern. IMEM is first implementation (in development).

*Next: Build primitives, enable flexible composition, observe usage patterns, capture presets.*
