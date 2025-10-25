---
date: 2025-10-25
type: architecture.technical
status: current
keywords: "five-layer llamaindex qdrant soft-graph metadata-schema"
references:
  - "251025-1201_vision.md (knowledge genealogy vision)"
  - "architecture_imem-i2.md (IMEM component)"
  - "architecture_trace-i2.md (TRACE component)"
---

# The Architecture: Five-Layer Technical Design

## System Overview

AURA implements a five-layer architecture that transforms template-enforced markdown into a queryable knowledge genealogy system:

```
┌─────────────────────────────────────────────────────────┐
│  LAYER 5: Navigation (Soft-Graph Object Model)         │
│  ├─ KnowledgeGraph, Item, Pattern, Discussion          │
│  └─ Lazy-loaded relationships via metadata queries     │
├─────────────────────────────────────────────────────────┤
│  LAYER 4: Retrieval (Multi-Modal Patterns)             │
│  ├─ search: Semantic discovery                         │
│  ├─ explain: Full context retrieval                    │
│  ├─ trace: Genealogy navigation                        │
│  └─ patterns: Abstraction comparison                   │
├─────────────────────────────────────────────────────────┤
│  LAYER 3: Storage (Qdrant Vector Database)             │
│  ├─ E5-Large-v2 embeddings (1024D)                     │
│  ├─ Named vectors (multi-model support)                │
│  └─ Rich metadata payloads (23 fields)                 │
├─────────────────────────────────────────────────────────┤
│  LAYER 2: Indexing (LlamaIndex Chunking)               │
│  ├─ MarkdownNodeParser (H2/H3 section-level)           │
│  ├─ Metadata extraction (frontmatter + fields)         │
│  └─ Batch embedding generation                         │
├─────────────────────────────────────────────────────────┤
│  LAYER 1: Creation (Template Enforcement)              │
│  ├─ Markdown templates define schemas                  │
│  ├─ Structured fields (Context/Solution/Rationale)     │
│  └─ Phase organization (design/develop/document)       │
└─────────────────────────────────────────────────────────┘
```

**Path:** `/home/axp/projects/fleet/hangar/code/aura/main/`

---

## Layer 1: Creation (Template Enforcement)

### Template Structure

**Location:** `assets/templates/.context/`

**Changelog Template:**
```markdown
---
schema_version: "v3_adaptive"
type: "changelog.develop"
timestamp: "YYYY-MM-DDTHH:MM:SS-0700"
session_id: "<claude-session-id>"  # Links to conversation
---

# Changelog Title

## Decisions
### Decision Name
- **Context**: Problem statement and background
- **Solution**: What was implemented
- **Rationale**: Why this approach
- **Alternatives**: What else was considered

## Constraints
### Constraint Name
- **Description**: What limits exist
- **Impact**: How it affects the system
- **Mitigation**: How we handle it

## Implementation
### Component Name
(Implementation details)

## Failures
### What Went Wrong
- **Issue**: What failed
- **Root Cause**: Why it failed
- **Resolution**: How we fixed it
```

**Pattern Variant** (`.pattern.md`):
```markdown
# Same structure, abstracted content
## Decisions
### Generic Principle Name
- **Context**: (Tech-agnostic problem description)
- **Solution**: (Language-independent approach)
- **Rationale**: (Universal reasoning)
- **Alternatives**: (Generic alternatives)
```

### Phase Organization

**Directory structure:**
```
.context/
├── design/          # R&D exploration, options evaluation
│   └── .changes/    # Exploration logs
├── designate/       # Ground truth plans (THE schema, THE plan)
│   └── .changes/    # Canonical specifications
├── develop/         # Validated implementation changelogs
│   └── .changes/    # Completed work records
└── document/        # Stable architectural documentation
    └── .changes/    # Long-term reference docs
```

**Phase metadata:**
- `phase: 'design'` → Exploratory, options considered
- `phase: 'designate'` → Canonical plan, ground truth
- `phase: 'develop'` → Validated implementation
- `phase: 'document'` → Stable architecture

### Dual-Layer Pattern

**Implementation layer** (`.md`):
- Code-specific details
- Technology stack references
- File paths, function names
- Platform identifiers

**Pattern layer** (`.pattern.md`):
- Language-agnostic principles
- Universal concepts
- Reusable across projects
- Tech details abstracted away

**Example:**
```
develop/.changes/
├── 251018-1200_auth-jwt.md           # Django-specific JWT implementation
└── 251018-1200_auth-jwt.pattern.md  # Generic stateless auth principle
```

---

## Layer 2: Indexing (LlamaIndex Chunking) ✅ IMPLEMENTED

### Component: `imem/src/imem/ingest.py`

**Core class:** `EnhancedModularIngest`

**Implementation status:** ✅ Complete (Oct 25, 2025)

### Changelog Indexing Pipeline

**H3-level chunking for surgical retrieval (WORKING):**

```python
from llama_index.core.node_parser import MarkdownNodeParser
from llama_index.core.schema import Document as LlamaDocument

def ingest_markdown_chunked(file_path, phase, collection_name):
    # 1. Read markdown
    with open(file_path, 'r') as f:
        content = f.read()

    # 2. Extract frontmatter (YAML)
    frontmatter = extract_frontmatter(content)
    # → {'session_id': 'abc123', 'timestamp': '2025-10-18T12:00:00'}

    # 3. Parse with LlamaIndex
    llama_doc = LlamaDocument(text=content, metadata={'file_path': str(file_path)})
    nodes = MarkdownNodeParser().get_nodes_from_documents([llama_doc])
    # → Each H3 section becomes a node

    # 4. Filter H1/H2 noise (only index H3+)
    for node in nodes:
        header_level = count_hashes(node.content.split('\n')[0])
        if header_level < 3:
            continue  # Skip document title (H1) and section headers (H2)

        # 5. Extract section metadata
        section_name = extract_header_text(node.content.split('\n')[0])
        # "### Use JWT Auth" → "Use JWT Auth"

        h2_parent = extract_h2_parent(node.metadata['header_path'])
        # "/Title/Decisions/Use JWT Auth" → "Decisions"

        # 6. Detect structured fields
        has_context = '**Context**' in node.content
        has_solution = '**Solution**' in node.content
        has_rationale = '**Rationale**' in node.content
        has_alternatives = '**Alternatives**' in node.content

        # 7. Build rich payload
        payload = {
            'source': 'changelog',
            'phase': phase,  # design/designate/develop/document
            'layer': detect_layer(file_path),  # implementation/pattern
            'section_type': h2_parent,  # "Decisions", "Constraints", etc.
            'section_name': section_name,  # "Use JWT Auth"
            'section_level': header_level,  # 3 for H3
            'header_path': node.metadata['header_path'],
            'timestamp': frontmatter.get('timestamp'),
            'session_id': frontmatter.get('session_id'),
            'content': node.content,
            # Structured field flags
            'has_context': has_context,
            'has_solution': has_solution,
            'has_rationale': has_rationale,
            'has_alternatives': has_alternatives,
            # Metadata for monitoring
            'schema_version': 'v1.0',
            'word_count': len(node.content.split()),
            'char_count': len(node.content),
            'file_path': str(file_path)
        }

        # 8. Generate embedding
        vector = model.encode(node.content).tolist()

        # 9. Store point
        points.append({
            'id': str(uuid4()),
            'vector': {'e5-large-v2': vector},  # Named vector
            'payload': payload
        })

    # 10. Batch upsert to Qdrant
    client.upsert(collection_name=collection_name, points=points)
```

**Code reference:** `imem/src/imem/ingest.py:626-788` ✅ EXISTS

### Conversation Indexing Pipeline

**H2-level chunking for broader discovery (WORKING):**

```python
def ingest_conversation_chunked(markdown_path, session_id, metadata, collection_name):
    # 1. TRACE exports structured markdown:
    """
    # Conversation: abc12345

    ## User Messages
    - How to implement JWT auth?
    - What about refresh tokens?

    ## Assistant Responses
    Use stateless JWT with short expiry...

    ## Code Changes
    ### auth/middleware.py
    ```diff
    + def verify_jwt(token):
    ```

    ## Tools Used
    - Edit: 12×
    - Bash: 5×
    """

    # 2. Parse with LlamaIndex (H2 sections)
    nodes = MarkdownNodeParser().get_nodes_from_documents([
        LlamaDocument(text=markdown_content, metadata={'session_id': session_id})
    ])

    # 3. Each H2 section → vector
    for node in nodes:
        section_name = extract_header_text(node.content.split('\n')[0])
        # "## User Messages" → "User Messages"

        payload = {
            'source': 'conversation',
            'session_id': session_id,
            'section_type': section_name,  # "User Messages", "Code Changes", etc.
            'section_level': 2,  # H2
            'content': node.content,
            'start_time': metadata.get('start_time'),
            'duration_minutes': metadata.get('duration_minutes'),
            'message_count': metadata.get('message_count'),
            'has_changelog': metadata.get('has_changelog'),
            'changelog_path': metadata.get('changelog_path')
        }

        vector = model.encode(node.content).tolist()

        points.append({
            'id': str(uuid4()),
            'vector': {'e5-large-v2': vector},
            'payload': payload
        })

    client.upsert(collection_name=collection_name, points=points)
```

**Code reference:** `imem/src/imem/ingest.py:789-868` ✅ EXISTS

### Batch Optimization ✅ IMPLEMENTED

**2x faster embedding generation (WORKING):**

```python
# Instead of:
for node in nodes:
    vector = model.encode(node.content)  # Sequential

# Do:
texts = [node.content for node in nodes]
vectors = model.encode(texts)  # Batch (2x faster)
```

**Code reference:** `imem/src/imem/ingest.py:669-670`

---

## Layer 3: Storage (Qdrant Vector Database)

### Qdrant Configuration

**Collection setup:**
```python
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

client = QdrantClient(host="localhost", port=6334)

client.create_collection(
    collection_name=f"imem_{project_hash}",
    vectors_config={
        "e5-large-v2": VectorParams(
            size=1024,  # E5-Large-v2 dimensions
            distance=Distance.COSINE
        )
        # Future: Add other models (MiniLM, BGE)
    }
)
```

**Per-project isolation:**
- Collection name: `imem_<md5_hash_of_project_path>`
- Registry: `~/.context/imem_registry.json`
- No cross-contamination between projects

### Metadata Schema v1.0

**Changelog chunks (23 fields):**
```python
{
    # Source identification
    'source': 'changelog',  # or 'conversation'

    # Phase/layer organization
    'phase': 'develop',  # design/designate/develop/document
    'layer': 'implementation',  # or 'pattern'

    # Section identification
    'section_type': 'Decisions',  # H2 parent section
    'section_name': 'Use JWT Auth',  # H3 title
    'section_level': 3,  # Header depth
    'header_path': '/Title/Decisions/Use JWT Auth',

    # Temporal metadata
    'timestamp': '2025-10-18T12:00:00-0700',

    # Relationship metadata
    'session_id': 'cb91d93d',  # Link to conversation

    # Content
    'content': '### Use JWT Auth\n- **Context**: ...',
    'file_path': '.context/develop/.changes/251018-1200_auth.md',

    # Structured field detection (template enforcement)
    'has_context': True,
    'has_solution': True,
    'has_rationale': True,
    'has_alternatives': True,
    'has_approach': False,
    'has_benefits': False,
    'has_drawbacks': False,

    # Document metadata
    'category': 'implementation',  # From frontmatter type field
    'subtype': 'security',

    # Monitoring metadata
    'schema_version': 'v1.0',
    'word_count': 234,
    'char_count': 1456
}
```

**Conversation chunks (12 fields):**
```python
{
    'source': 'conversation',
    'session_id': 'cb91d93d',
    'section_type': 'User Messages',  # or "Code Changes", "Tools Used"
    'section_level': 2,
    'content': '...',
    'start_time': '2025-10-18T12:00:00',
    'duration_minutes': 45,
    'message_count': 23,
    'has_changelog': True,
    'changelog_path': '.context/develop/.changes/251018-1200_auth.md',
    'header_path': '/Conversation: cb91d93d/User Messages'
}
```

### Named Vectors Architecture

**Multi-model support:**
```python
# Current: Single model
'vector': {'e5-large-v2': [0.123, 0.456, ...]}

# Future: Multiple models
'vector': {
    'e5-large-v2': [0.123, 0.456, ...],  # General semantic
    'code-bert': [0.789, 0.012, ...],     # Code-specific
    'bge-large': [0.345, 0.678, ...]      # Alternative model
}
```

**Search specifies model:**
```python
client.query_points(
    collection_name="imem_abc123",
    query=query_vector,
    using="e5-large-v2",  # Which vector to search
    limit=10
)
```

---

## Layer 4: Retrieval (Multi-Modal Patterns)

### Component: `imem/src/imem/enhanced.py`

**Implementation status:** ✅ Mode 1 complete, ❌ Modes 2-4 planned

### Mode 1: SEARCH (Semantic Discovery) ✅ IMPLEMENTED

**Implementation (WORKING):**
```python
from qdrant_client.models import Filter, FieldCondition, MatchValue

def search(query, filters=None, limit=10):
    # 1. Embed query
    query_vector = model.encode(query).tolist()

    # 2. Build Qdrant filter
    query_filter = None
    if filters:
        must_conditions = []
        for key, value in filters.items():
            must_conditions.append(
                FieldCondition(key=key, match=MatchValue(value=value))
            )
        query_filter = Filter(must=must_conditions)

    # 3. Vector search with filters
    results = client.query_points(
        collection_name=collection_name,
        query=query_vector,
        using="e5-large-v2",
        query_filter=query_filter,
        limit=limit,
        with_payload=True
    )

    return results.points
```

**Example query:**
```python
decisions = search(
    "authentication",
    filters={
        'phase': 'develop',
        'section_type': 'Decisions',
        'has_alternatives': True
    },
    limit=10
)
```

**Code reference:** `imem/src/imem/enhanced.py:95-144` ✅ EXISTS

### Mode 2: EXPLAIN (Context Retrieval) ❌ PLANNED

**Architecture (NOT YET IMPLEMENTED - Phase 7):**
```python
def explain(query, collection_name):
    # 1. Find primary match
    primary = search(query, limit=1)[0]

    # 2. Get related sections from same file
    related = search(
        "",  # No semantic query
        filters={
            'file_path': primary.payload['file_path'],
            'section_type': ['Constraints', 'Implementation']
        }
    )

    # 3. Get pattern layer variant
    pattern_path = primary.payload['file_path'].replace('.md', '.pattern.md')
    pattern = search(
        "",
        filters={'file_path': pattern_path}
    )

    # 4. Get origin conversation
    if primary.payload.get('session_id'):
        conversation = search(
            "",
            filters={
                'source': 'conversation',
                'session_id': primary.payload['session_id']
            }
        )

    # 5. Format complete context
    return {
        'decision': primary,
        'constraints': [r for r in related if r.payload['section_type'] == 'Constraints'],
        'implementation': [r for r in related if r.payload['section_type'] == 'Implementation'],
        'pattern_layer': pattern,
        'conversation': conversation
    }
```

### Mode 3: TRACE (Genealogy Navigation) ❌ PLANNED

**Architecture (NOT YET IMPLEMENTED - Phase 7):**
```python
def trace(query, collection_name):
    # 1. Find decision in develop phase
    decision = search(query, filters={'phase': 'develop'})[0]
    session_id = decision.payload['session_id']

    # 2. Get conversation (earliest timestamp)
    conversation = search(
        "",
        filters={
            'source': 'conversation',
            'session_id': session_id
        }
    )[0]

    # 3. Get design exploration
    design_docs = search(
        query,
        filters={
            'phase': 'design',
            'session_id': session_id
        }
    )

    # 4. Get designate plan
    plan = search(
        query,
        filters={
            'phase': 'designate',
            'session_id': session_id
        }
    )

    # 5. Get later refinements (timestamp + semantic)
    decision_timestamp = decision.payload['timestamp']
    later_docs = search(
        query,
        filters={
            'timestamp': f'>{decision_timestamp}',  # Qdrant range filter
            'phase': 'develop'
        }
    )

    # 6. Return chronological timeline
    return {
        'conversation': conversation,
        'design_exploration': design_docs,
        'plan': plan,
        'implementation': decision,
        'refinements': later_docs
    }
```

### Mode 4: PATTERNS (Abstraction Comparison) ❌ PLANNED

**Architecture (NOT YET IMPLEMENTED - Phase 7):**
```python
def patterns(query, collection_name):
    # 1. Find implementation
    implementation = search(
        query,
        filters={'layer': 'implementation'}
    )[0]

    # 2. Find pattern variant (naming convention)
    pattern_path = implementation.payload['file_path'].replace('.md', '.pattern.md')
    pattern = search(
        "",
        filters={'file_path': pattern_path}
    )

    # 3. Find similar patterns across projects (cross-collection)
    # Requires multi-collection search
    similar_patterns = []
    for project in registry.list_projects():
        results = search(
            query,
            filters={'layer': 'pattern'},
            collection_name=project.collection
        )
        similar_patterns.extend(results)

    return {
        'implementation': implementation,
        'pattern': pattern,
        'similar_patterns': similar_patterns
    }
```

---

## Layer 5: Navigation (Soft-Graph Object Model) ❌ PLANNED

### Architecture (NOT YET IMPLEMENTED - Phase 6)

**Domain objects with lazy-loaded relationships (DESIGN ONLY):**

```python
class KnowledgeGraph:
    def __init__(self, project_root):
        self.project_root = project_root
        self.collection = registry.get_collection(project_root)

    def search(self, query, **filters):
        """Semantic search → returns Item objects"""
        results = search_engine.search(query, filters=filters)
        return [Item(result, self) for result in results]

class Item:
    def __init__(self, point, graph):
        self.point = point
        self.graph = graph
        self.payload = point.payload

    # Lazy-loaded relationships (cached after first access)

    @property
    def constraints(self):
        """Get constraints from same file"""
        return self.graph.search(
            "",
            file_path=self.payload['file_path'],
            section_type='Constraints'
        )

    @property
    def pattern_layer(self):
        """Get pattern abstraction (naming convention)"""
        pattern_path = self.payload['file_path'].replace('.md', '.pattern.md')
        results = self.graph.search("", file_path=pattern_path)
        return results[0] if results else None

    @property
    def origin_discussion(self):
        """Get conversation via session_id"""
        if not self.payload.get('session_id'):
            return None
        return self.graph.search(
            "",
            source='conversation',
            session_id=self.payload['session_id']
        )

    @property
    def later_evolution(self):
        """Get later docs (timestamp + semantic)"""
        return self.graph.search(
            self.payload['content'][:200],  # Semantic similarity
            timestamp=f">{self.payload['timestamp']}",
            phase=self.payload['phase']
        )

    @property
    def quality_score(self):
        """Computed authority (query-time)"""
        score = 1.0

        # Check if superseded
        later = self.later_evolution
        if later:
            score *= 0.5  # Significant penalty

        # Count constraints
        constraints_count = len(self.constraints)
        score -= constraints_count * 0.05

        # Boost if pattern exists
        if self.pattern_layer:
            score *= 1.2

        return max(0.0, score)

class Pattern(Item):
    @property
    def source_implementation(self):
        """Get implementation variant"""
        impl_path = self.payload['file_path'].replace('.pattern.md', '.md')
        results = self.graph.search("", file_path=impl_path)
        return results[0] if results else None

    @property
    def similar_across_contexts(self):
        """Find similar patterns in other projects"""
        # Multi-collection search (future)
        pass

class Discussion(Item):
    @property
    def resulting_changelog(self):
        """Get changelog created from this conversation"""
        if not self.payload.get('has_changelog'):
            return None
        changelog_path = self.payload['changelog_path']
        results = self.graph.search("", file_path=changelog_path)
        return results[0] if results else None
```

**Usage example:**
```python
graph = KnowledgeGraph("~/my-project")

# Semantic search
decision = graph.search("JWT authentication")[0]

# Navigate relationships
print(f"Decision: {decision.payload['section_name']}")
print(f"Constraints: {len(decision.constraints)}")
print(f"Pattern: {decision.pattern_layer.payload['content'][:100]}")
print(f"Conversation: {decision.origin_discussion[0].payload['session_id']}")
print(f"Quality: {decision.quality_score}")

# Chaining
auth_constraint = decision.constraints[0]
original_conversation = auth_constraint.origin_discussion
patches = original_conversation[0].payload  # Get patches section
```

---

## Data Flow: End-to-End

### Creating Knowledge

```
1. Developer writes changelog using template
   ↓
   .context/develop/.changes/251018-1200_auth.md
   (Template enforces Context/Solution/Rationale/Alternatives)

2. Claude Code conversation saved
   ↓
   ~/.claude/projects/my-project/conversations/cb91d93d.jsonl
   (session_id: cb91d93d)

3. Index changelog
   ↓
   $ imem init
   ↓
   LlamaIndex chunks at H3 level
   ↓
   E5-Large-v2 embeddings generated
   ↓
   Qdrant points created with rich metadata
   (session_id: cb91d93d links to conversation)

4. Index conversation
   ↓
   $ trace --index cb91d93d
   ↓
   TRACE exports structured markdown
   ↓
   LlamaIndex chunks at H2 level
   ↓
   Qdrant points created
   (has_changelog: true, changelog_path: ...)
```

### Retrieving Knowledge

```
1. Semantic search
   ↓
   $ imem search "JWT authentication" --in develop --section Decisions
   ↓
   Query embedded with E5-Large-v2
   ↓
   Qdrant search with metadata filters
   ↓
   Returns H3 sections (not full docs)

2. Context retrieval
   ↓
   decision = search("JWT")[0]
   ↓
   decision.constraints (metadata query: same file_path)
   ↓
   decision.pattern_layer (naming: .md → .pattern.md)
   ↓
   decision.origin_discussion (session_id match)
   ↓
   Returns complete knowledge bundle

3. Genealogy trace
   ↓
   $ imem trace "JWT decision"
   ↓
   Find develop changelog (session_id: cb91d93d)
   ↓
   Find conversation (source='conversation', session_id='cb91d93d')
   ↓
   Find design docs (phase='design', session_id='cb91d93d')
   ↓
   Find later refinements (timestamp > decision + semantic match)
   ↓
   Returns chronological timeline
```

---

## CLI Interface

### IMEM Commands

```bash
# Service management ✅ WORKING
imem service start     # Start Qdrant container
imem service stop      # Stop Qdrant
imem service status    # Check status

# Indexing ✅ WORKING
imem init                      # Index current project (H3-level chunking)
imem init --force              # Re-index from scratch
imem index-conversation abc123 # Index specific conversation (H2-level)
imem index-all-conversations   # Batch index conversations

# Phase-based search ✅ WORKING (Phase 5A+B)
imem develop search "database" --decisions --constraints --pattern
imem conversations search "auth" --session abc123
imem design search "options" --questions

# Legacy search ✅ WORKING
imem search "query"                        # All phases
imem search "query" --in develop           # Phase filter
imem search "query" --section Decisions    # Section filter
imem search "query" --session abc123       # Conversation filter

# Multi-modal retrieval ❌ PLANNED (Phase 7)
# imem develop explain "database JSONB"      # Full context bundle
# imem develop trace "database decision"     # Genealogy timeline
# imem develop patterns "provider agnostic"  # Abstraction comparison
```

### TRACE Commands

```bash
# Discovery
trace list                      # All conversations
trace list --marker "auth"      # Filter by keyword
trace list --limit 10           # Recent 10

# Display
trace show chronicle <id>       # Messages + patches timeline
trace show messages <id>        # Messages only
trace show patches <id>         # Code changes only
trace show metadata <id>        # Session info

# Export
trace export chronicle <id> -o file.md   # Save timeline
trace export messages <id>               # Auto-name file

# Indexing (planned)
trace --index <id>              # Index to IMEM
trace --index-all               # Batch index
```

---

## Storage Architecture

### Global Storage

```
~/.context/
├── qdrant_storage/            # Vector persistence
│   └── collections/
│       ├── imem_a1b2c3d4/     # Project A vectors
│       └── imem_e5f6g7h8/     # Project B vectors
├── docker-compose.yml         # Qdrant container config
└── imem_registry.json         # Project → collection mapping
```

### Per-Project Storage

```
my-project/
├── .context/
│   ├── design/.changes/       # Exploration logs
│   ├── designate/.changes/    # Ground truth plans
│   ├── develop/.changes/      # Implementation changelogs
│   └── document/              # Stable docs
└── .claude/
    └── .trace/
        └── registry.json      # Session bookmarks
```

---

## Performance Characteristics

### Indexing Performance

**Changelog (H3-level chunking):**
- ~15 vectors per changelog
- Batch embedding: 2x faster than sequential
- Batch upsert: 10x faster than individual

**Conversation (H2-level chunking):**
- ~5-10 vectors per conversation
- Structured export: ~3s per conversation
- No LLM costs (vs summary generation)

### Query Performance

**Semantic search:**
- Sub-100ms for typical queries
- HNSW index (m=16, ef_construct=100)
- Cosine similarity distance

**Metadata filtering:**
- Fast (indexed fields)
- Composition: AND/OR conditions
- Range queries (timestamps)

**Soft-graph navigation:**
- Slower than indexed graph traversal
- Acceptable for AI agent use cases
- Cached after first access

---

## Technical Debt & Known Gaps

### Missing Features

1. **Template validation at ingestion**
   - Current: Detects fields, doesn't reject
   - Needed: Validate required fields, reject violations

2. **Soft-graph object model**
   - Current: Direct search API only
   - Needed: Item/Pattern/Discussion classes

3. **Multi-modal retrieval modes**
   - Current: Only search() implemented
   - Needed: explain(), trace(), patterns()

4. **Cross-collection search**
   - Current: Single project only
   - Needed: Pattern search across projects

5. **Supersession detection**
   - Current: Manual tracking
   - Needed: Automated via timestamp + semantic similarity

### Design Decisions (Open)

1. **Authority score caching**
   - Options: Session-temporary, persistent, hybrid
   - Recommendation: Session-temporary (recompute each query)

2. **Supersession threshold**
   - Options: Conservative (0.90), aggressive (0.80), configurable
   - Recommendation: 0.85 default

3. **Temporal decay**
   - Options: Linear, exponential, step function
   - Recommendation: Exponential (recent = higher authority)

---

## Dependencies

**IMEM:**
```python
# imem/setup.py
install_requires=[
    'qdrant-client>=1.7.0',
    'sentence-transformers>=2.2.0',
    'click>=8.0.0',
    'llama-index-core>=0.10.0'
]
```

**TRACE:**
```python
# trace/setup.py
install_requires=[
    'click>=8.0.0'
]
```

**AURA CLI:**
```python
# aura_cli/setup.py
install_requires=[
    'click>=8.0.0'
]
```

**Total unique dependencies:** 4 packages

---

## Summary

**Five-layer architecture:**
1. **Creation:** Templates enforce schema at write time
2. **Indexing:** LlamaIndex chunks with metadata extraction
3. **Storage:** Qdrant vectors + 23-field payloads
4. **Retrieval:** Multi-modal patterns (search/explain/trace/patterns)
5. **Navigation:** Soft-graph object model with lazy relationships

**Key innovations:**
- Creation-time schema enforcement (templates)
- Section-level chunking (H2/H3 surgical retrieval)
- Rich metadata payloads (23 fields, guaranteed presence)
- Soft-graph navigation (metadata queries = implicit edges)
- Multi-modal retrieval (different graph traversal patterns)

**Next:** See `251025-1203_roadmap.md` for implementation plan.
