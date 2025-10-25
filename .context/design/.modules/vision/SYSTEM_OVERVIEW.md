# IMEM: Structured Knowledge Retrieval for Agentic Coding

**Revolutionary Memory System - Not Traditional RAG**

---

## The Innovation

Most RAG systems throw unstructured text at vectors and pray for relevant results.

**IMEM is different:** We capture knowledge **at the point of creation** with enforced structure, then enable **SQL-level precision** combined with **semantic search**.

### Traditional RAG vs IMEM

```
Traditional RAG:
  Unstructured docs → Chunk arbitrarily → Vector search → Hope

IMEM:
  Structured templates → Semantic chunking → Rich metadata → Precision retrieval
```

---

## Core Architecture

### 1. **Structured Knowledge Capture**

**Changelog Templates** enforce structure at creation:

```markdown
# Provider-Agnostic Refactor

## Decisions

### Database as Inert Inventory Store
- **Context**: Why this decision arose
- **Solution**: What was chosen
- **Rationale**: Technical reasoning
- **Alternatives**: Options rejected and why
```

**Result:** Every decision is a self-contained knowledge unit with complete context.

### 2. **Template-Aware Chunking**

**LlamaIndex MarkdownNodeParser** chunks at H2/H3 boundaries:
- H2 sections: `Decisions`, `Constraints`, `Failures`, `Patterns`
- H3 sections: Individual decisions with Context/Solution/Rationale

**Metadata extracted per chunk:**
```python
{
  'source': 'changelog',
  'phase': 'develop',           # develop, design, document
  'layer': 'implementation',    # implementation or pattern
  'section_type': 'Decisions',  # H2 parent
  'section_name': 'Database as Inert...',  # H3 title
  'header_level': 3,

  # Structured field detection
  'has_context': True,
  'has_solution': True,
  'has_rationale': True,
  'has_alternatives': True,

  # Genealogy
  'timestamp': '2025-10-11T12:00:00',
  'session_id': 'cb91d93d',    # Link to conversation
  'file_path': '...',

  # Monitoring
  'schema_version': 'v1.0',
  'word_count': 127,
  'char_count': 689
}
```

### 3. **Hybrid Retrieval**

**Vector Search (Semantic):**
- E5-Large-v2 embeddings (1024 dimensions)
- HNSW-optimized Qdrant index
- Cosine similarity

**Metadata Filters (Precision):**
```bash
imem develop search "database approach" \
  --decisions \
  --pattern \
  --after 2025-10-01
```

Translates to:
```python
filters = {
  'phase': 'develop',
  'section_type': 'Decisions',
  'layer': 'pattern',
  'timestamp': '>2025-10-01'
}
```

**Result:** SQL-like precision + semantic understanding

---

## The Geography: Multi-Dimensional Knowledge Space

```
┌─────────────────────────────────────────────────────┐
│              KNOWLEDGE DIMENSIONS                    │
├─────────────────────────────────────────────────────┤
│                                                      │
│  TIME ─────────────────────────────────────────►    │
│  (timestamp chronology)                              │
│                                                      │
│  SOURCE                                              │
│  ├─ Changelogs (WHAT WE BUILT)                      │
│  │   ├─ Phase: develop/design/designate             │
│  │   ├─ Layer: implementation/pattern               │
│  │   └─ Sections: Decisions/Constraints/Failures    │
│  │                                                   │
│  └─ Conversations (HOW WE GOT THERE)                │
│      └─ Links via session_id                        │
│                                                      │
│  STRUCTURE                                           │
│  └─ Fields: Context/Solution/Rationale/Alternatives │
│                                                      │
└─────────────────────────────────────────────────────┘
```

**Query Examples:**

1. **Precision lookup:**
   ```bash
   imem develop search "JWT authentication" --decisions
   → Returns only Decision sections about JWT
   ```

2. **Pattern learning:**
   ```bash
   imem develop search "provider agnostic" --pattern
   → Returns language-agnostic learnings
   ```

3. **Decision archaeology:**
   ```bash
   imem conversations search "database discussion"
   → Returns conversation that led to database decisions
   → Follow session_id to see resulting changelog
   ```

4. **Temporal evolution:**
   ```bash
   imem develop search "authentication" --after 2025-09-01
   → Track how auth approach evolved over time
   ```

---

## Why This Is Revolutionary

### 1. **Capture at Creation (Not Afterthought)**

Traditional: Code → Documentation (maybe) → RAG indexing (lossy)

IMEM: Structured template → Enforced capture → Rich indexing → Zero loss

### 2. **Decision Genealogy**

Every decision has:
- **Context**: Why it arose
- **Solution**: What was chosen
- **Rationale**: Why it was chosen
- **Alternatives**: What was rejected and why
- **Conversation**: Full ideation thread (via session_id)
- **Pattern**: Language-agnostic learnings

### 3. **SQL-Level Filtering**

Traditional RAG: "Find me authentication decisions"
→ Returns 100 random chunks mentioning "authentication"

IMEM: `--decisions` filter
→ Returns only H3 sections under H2 "Decisions" sections
→ With Context/Solution/Rationale guaranteed

### 4. **Two-Layer Learning**

**Implementation Layer** (code-specific):
```markdown
# 251011-1200_auth.md
### Use JWT Tokens
- **Context**: TypeScript API needs stateless auth
- **Solution**: JWT with RS256 signing
- **Rationale**: Enables microservices without shared sessions
```

**Pattern Layer** (language-agnostic):
```markdown
# 251011-1200_auth.pattern.md
### Stateless Authentication Pattern
- **Pattern**: Token-based auth with asymmetric signing
- **When**: Distributed systems, microservices
- **Benefit**: No session storage, scales horizontally
```

**Query both:**
```bash
imem develop search "authentication" --pattern
→ See universal pattern applicable to any language
```

### 5. **Bidirectional Linking**

```
Conversation (ideation)
    ↓ session_id
Changelog (decision)
    ↓ file_path
Full Implementation
```

**Example:**
1. Search: "database JSONB approach"
2. Find: Decision section from changelog
3. View: session_id → Original conversation exploring options
4. Read: file_path → Full changelog with all constraints/failures
5. Learn: Pattern layer → Language-agnostic JSONB pattern

---

## Technical Implementation

### Stack

- **Chunking:** LlamaIndex MarkdownNodeParser
- **Embeddings:** E5-Large-v2 (intfloat, 1024 dims)
- **Vector DB:** Qdrant with HNSW optimization
- **Search:** Hybrid (vector + metadata filters)
- **CLI:** Click-based phase subcommands

### Performance

- **Indexing:** ~2-5 sec per document (batch encoding)
- **Search:** <100ms with filters
- **Scale:** Tested to 1000 docs, projects to 10K+

### LlamaIndex Validation

✅ Approved by LlamaIndex spec-validator agent:
- Valid hybrid architecture
- Correct use of MarkdownNodeParser
- Metadata schema: "Exemplary"
- Performance optimizations: "Excellent"

---

## CLI Interface

### Phase-Based Commands

```bash
# Develop phase (what we built)
imem develop search "query" --decisions --constraints --pattern

# Conversations (how we got there)
imem conversations search "query" --session abc123

# All (cross-source)
imem search "query" --all
```

### Filters Available

**Section types:**
- `--decisions` - What was chosen and why
- `--constraints` - What blocked us
- `--failures` - What didn't work
- `--patterns` - Reusable solutions
- `--implementation` - Code-specific sections

**Layers:**
- `--pattern` - Language-agnostic learnings
- `--impl` - Code-specific implementation

**Temporal:**
- `--after YYYY-MM-DD` - Only recent work

---

## Future Directions

### Completed ✅
- Template-aware chunking
- Rich metadata extraction
- Phase-based CLI
- HNSW optimization
- Schema versioning
- Token limit monitoring

### Planned
1. **Query engines** - Optional LLM-powered Q&A
2. **Graph navigation** - Python API for traversing genealogy
3. **Multi-project** - Cross-project pattern learning
4. **Auto-dedup** - Section-level content deduplication
5. **Design phase** - Index exploration docs

---

## The Paradigm Shift

**From:** "Throw text at vectors, hope for relevance"

**To:** "Structured capture → Rich metadata → Precision retrieval"

**Result:** Not "better RAG" - it's a **queryable knowledge genealogy** with:
- SQL-level precision (metadata filters)
- Semantic understanding (vector search)
- Decision archaeology (conversation threads)
- Pattern learning (language-agnostic layer)
- Temporal evolution (chronological queries)

**For AI agents, not humans.** Optimized for programmatic access with complete context in one shot.

---

**This is how memory should work for agentic coding.**
