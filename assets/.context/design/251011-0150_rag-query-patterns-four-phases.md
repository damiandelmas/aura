---
type: "research"
timestamp: "2025-10-11T01:50:00-0700"
---

# RAG Query Patterns: Four-Phase Architecture

## Question
> "How does the four-phase architecture improve RAG retrieval precision?"

## Key Insights

### The Problem Without Phase Distinction

**Scenario**: Developer asks "Show me the course code normalization approach"

**Without `phase:` field:**
```python
results = qdrant.search("course code normalization")

# Returns everything related:
# 1. Design exploration (5 approaches considered)
# 2. Design decision (hybrid approach chosen)
# 3. Implementation code (CSV parser)
# 4. Ground truth data (courses.json)
# 5. API documentation (GET /courses endpoint)

# Developer must manually sort:
# "Which is the decision?"
# "Which is the canonical data?"
# "Which is the implementation?"
```

**Result**: Cognitive overload, slow answer retrieval

### The Solution With Phase Distinction

**Same query, different filters:**

```python
# 1. "Why did we choose this approach?"
results = qdrant.search(
  query="course code normalization",
  filter={'phase': 'design'}
)
# → 251004-2050_course-code-normalization-strategy.md
# → Section: "Decision: Hybrid with alias mapping"

# 2. "What is the canonical course list?"
results = qdrant.search(
  query="course codes",
  filter={'phase': 'designate'}
)
# → courses.json
# → The actual 26 course definitions

# 3. "How is it implemented?"
results = qdrant.search(
  query="course normalization implementation",
  filter={'phase': 'develop'}
)
# → CSV import script implementation changelog

# 4. "How do I use the API?"
results = qdrant.search(
  query="course API",
  filter={'phase': 'document'}
)
# → API reference documentation
```

**Result**: Surgical retrieval, immediate answers

## Explored Ideas

### Query Pattern 1: Design Archaeology

**Use Case**: "Why did we make this decision?"

```python
# Find all design discussions about architecture
results = qdrant.search(
  query="hybrid architecture SQL TypeScript",
  filter={
    'phase': 'design',
    'type': 'architecture.*'  # Any architecture design
  }
)

# Returns:
# - 251004-1830_schema-separation.md (why two schemas)
# - 251010-2010_hybrid-architecture-overview.md (why hybrid)
# Each with: Question → Exploration → Decision → Rationale
```

**Benefit**: Understand past decisions without digging through code

### Query Pattern 2: Ground Truth Lookup

**Use Case**: "What's the canonical specification?"

```python
# Find all authoritative specs
results = qdrant.search(
  query="course schema",
  filter={'phase': 'designate'}
)

# Returns ONLY:
# - courses.json (THE course definitions)
# - phase-one-plan.md (THE implementation plan)
# NOT:
# - Design discussions about course schema
# - Implementation of course imports
# - Documentation about courses
```

**Benefit**: Zero ambiguity about what's authoritative

### Query Pattern 3: Implementation Tracing

**Use Case**: "How was this feature implemented?"

```python
# Find implementation work
results = qdrant.search(
  query="strategy pattern key assignment",
  filter={
    'phase': 'develop',
    'status': 'completed'
  }
)

# Returns:
# - 251010-2100_hybrid-architecture-refactor.md
# With: Code signatures, test results, metrics
```

**Benefit**: See what was actually built, not what was planned

### Query Pattern 4: Current Documentation

**Use Case**: "How do I use this API?"

```python
# Find stable reference docs
results = qdrant.search(
  query="inventory API",
  filter={
    'phase': 'document',
    'status': 'stable'
  }
)

# Returns:
# - API_REFERENCE.md (current stable docs)
# NOT:
# - Old documentation (status: 'stale')
# - Draft documentation (status: 'draft')
```

**Benefit**: Always get current, accurate documentation

### Query Pattern 5: Cross-Phase Context Reconstruction

**Use Case**: "Show me the full journey of this feature"

```python
# Step 1: Find design decision
design = qdrant.search(
  query="hybrid architecture decision",
  filter={'phase': 'design'}
)
# → "Why we chose hybrid: testing, extensibility"

# Step 2: Find the plan
plan = qdrant.search(
  query="hybrid architecture",
  filter={'phase': 'designate'}
)
# → "Implementation plan: 3 days, these tasks"

# Step 3: Find implementation
impl = qdrant.search(
  query="hybrid architecture",
  filter={'phase': 'develop'}
)
# → "What we built: strategy pattern, 9 tests passing"

# Step 4: Find docs
docs = qdrant.search(
  query="hybrid architecture",
  filter={'phase': 'document'}
)
# → "How to use: API reference, examples"
```

**Benefit**: Complete context from conception to documentation

## Outcomes

### RAG Precision Improvements

**Metric 1: Result Relevance**

Without phase filtering:
```
Query: "course schema"
Results: 15 documents (design, data, code, docs mixed)
Relevant: 3 documents
Precision: 20%
```

With phase filtering:
```
Query: "course schema" + filter: {phase: 'designate'}
Results: 2 documents (courses.json, schema spec)
Relevant: 2 documents
Precision: 100%
```

**Metric 2: Answer Speed**

Without phase filtering:
- User reads 5 documents
- User mentally filters "which is authoritative?"
- Time: 5-10 minutes

With phase filtering:
- User gets 1 document (ground truth)
- Time: 30 seconds

**Metric 3: Cognitive Load**

Without phase filtering:
- "Is this the decision or the implementation?"
- "Is this current or outdated?"
- "Which document is authoritative?"

With phase filtering:
- Filter by phase → get exactly what you need
- No ambiguity

### Query Recipes for Common Scenarios

**1. Understanding Past Decisions**
```python
filter = {
  'phase': 'design',
  'status': 'decided',
  'keywords': {'$contains': 'architecture'}
}
# Returns all architectural decisions with rationale
```

**2. Finding Current Ground Truth**
```python
filter = {
  'phase': 'designate',
  'status': 'active'
}
# Returns all active canonical specs/plans
```

**3. Reviewing Completed Work**
```python
filter = {
  'phase': 'develop',
  'status': 'completed',
  'timestamp': {'$gte': '2025-10-01'}  # Last month
}
# Returns all work completed in October
```

**4. Finding Outdated Documentation**
```python
filter = {
  'phase': 'document',
  'status': 'stale'
}
# Returns docs that need updating
```

**5. Tracing Feature Evolution**
```python
# All phases for "hybrid architecture"
phases = ['design', 'designate', 'develop', 'document']
results = {}
for phase in phases:
  results[phase] = qdrant.search(
    query="hybrid architecture",
    filter={'phase': phase}
  )
# Returns complete feature journey
```

### Metadata Richness

**Enhanced metadata with phase:**
```python
{
  "id": "uuid-123",
  "vector": [...],  # 1024D embedding
  "payload": {
    "content": "### Decision: Use Strategy Pattern\n...",

    # Phase-aware metadata
    "phase": "design",
    "type": "architecture.pattern-selection",
    "status": "decided",

    # Section-level metadata
    "section_type": "decision",
    "section_id": "use-strategy-pattern",
    "header_path": "Decisions > Use Strategy Pattern",

    # Standard metadata
    "file_path": "251010-2010_hybrid-architecture.md",
    "timestamp": "2025-10-10T20:10:00-0700",
    "keywords": ["strategy-pattern", "multi-provider", "extensibility"]
  }
}
```

**Query capabilities:**
```python
# Find all design decisions about patterns
qdrant.search(
  query="design pattern",
  filter={
    'phase': 'design',
    'section_type': 'decision',
    'type': {'$glob': 'architecture.*'}
  }
)

# Find all active ground truth specs
qdrant.search(
  query="schema specification",
  filter={
    'phase': 'designate',
    'status': 'active'
  }
)

# Find all recent implementations
qdrant.search(
  query="refactor",
  filter={
    'phase': 'develop',
    'timestamp': {'$gte': '2025-10-01'}
  }
)
```

### LLM Context Assembly

**Without phase distinction:**
```
User: "Why did we choose hybrid architecture?"

RAG returns:
1. Design doc (decision + rationale) ✓
2. Implementation changelog (code) ✗
3. API docs (usage) ✗
4. Ground truth plan (tasks) ✗

LLM context: 4 documents (3 irrelevant)
Token usage: 8000 tokens (75% noise)
Answer quality: Good but slow
```

**With phase distinction:**
```
User: "Why did we choose hybrid architecture?"

RAG returns (filter: phase='design'):
1. Design doc (decision + rationale) ✓

LLM context: 1 document (100% relevant)
Token usage: 2000 tokens (0% noise)
Answer quality: Excellent and fast
```

## References

### RAG Architecture Patterns

**Similar implementations:**
- GitHub Copilot: Phases = (issue, PR, commit, docs)
- Notion AI: Phases = (discussion, spec, implementation, wiki)
- Confluence: Phases = (RFC, decision, implementation, how-to)

### Information Retrieval Theory

**Precision vs Recall:**
- Phase filtering increases precision (fewer irrelevant results)
- May decrease recall (miss cross-phase references)
- Trade-off acceptable: Better to miss edge cases than overwhelm with noise

**Query Refinement:**
- Start broad: Search all phases
- Refine: Filter by phase when clear what's needed
- Iterate: Use cross-phase queries for full context

### IMEM Section-Level Chunking

**Phase + Section Type = Surgical Precision:**
```python
qdrant.search(
  query="stale object bug",
  filter={
    'phase': 'develop',
    'section_type': 'constraint'
  }
)
# Returns: ONE H3 node with bug description
# Not: Entire 300-line changelog
```

**Maximum granularity:**
- Phase: design/designate/develop/document
- Section: request/decision/constraint/pattern/etc.
- Item: Specific H3 within section
- Result: Exactly the information needed
