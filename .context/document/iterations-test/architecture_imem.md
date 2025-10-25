---
schema_version: "v3_adaptive"
type: "architecture.imem"
status: "stable"
keywords: "imem vector-search qdrant llamaindex embeddings section-chunking structured-retrieval metadata-rich"
timestamp: "2025-10-25T00:30:00-0700"
---

# IMEM Architecture

## Purpose

IMEM is a **structured knowledge retrieval system** (not traditional RAG) that provides SQL-like filtering + semantic search across changelogs and conversations. It extracts rich metadata from template-structured documents, enabling precision retrieval via phase/layer/section filters combined with vector similarity.

**Innovation**: Captures decision genealogy through bidirectional linking (conversations ↔ changelogs), dual-layer architecture (implementation + pattern), and structured field detection (Context/Solution/Rationale).

**Path**: `imem/src/imem/`
**Lines**: 2,273 lines (61% of codebase)
**CLI**: `imem`
**Dependencies**: qdrant-client, sentence-transformers, click, llama-index-core

---

## Core Capabilities

### 1. Per-Project Initialization
```bash
cd ~/my-project
imem init               # Creates unique collection
imem search "query"     # Searches THIS project only
```

Each project gets isolated Qdrant collection (`imem_<hash>`).

### 2. Section-Level Chunking
**Changelogs** (H3-level):
- Each Decision = 1 vector
- Each Code Signature = 1 vector
- ~15 vectors per changelog

**Conversations** (H2-level):
- User Messages = 1 vector
- Code Changes = 1 vector
- Tools Used = 1 vector
- ~5 vectors per conversation

### 3. Structured Filtering (SQL-like)
```bash
# Phase-based subcommands
imem develop search "auth" --decisions         # Only Decision sections
imem develop search "JSONB" --constraints      # Only Constraint sections
imem develop search "patterns" --pattern       # Pattern layer only

# Conversations
imem conversations search "database" --session abc123
```

**Rich metadata enables:**
- section_type filtering (Decisions, Constraints, Failures, Patterns)
- layer filtering (implementation vs pattern)
- structured field detection (has_context, has_solution, has_alternatives)

### 4. Bidirectional Linking
```bash
# Find changelog from conversation
imem search --session 5d8e69ea --in develop

# Find conversations from topic
imem search "authentication" --in conversations
```

---

## Two-Tier Architecture

### Tier 1: Changelogs (Precision)
**Source**: `.context/{design,designate,develop,document}/*.md`
**Chunking**: H3+ only (H1/H2 filtered as noise)
**Vectors per doc**: ~15 (varies by complexity)

**Use Case**: "What did we decide about JWT?"

**Query**: `imem develop search "JWT" --decisions`

**Returns**: Just the H3 Decision sections about JWT, not entire documents.

**Why H3+ only**:
- **H1/H2 filtered**: Titles and section headers are noise, not content
- **H3 = minimal knowledge unit**: Each Decision/Constraint/Pattern is self-contained
- Surgical retrieval (exact decision, not entire changelog)
- Progressive disclosure (simple docs = fewer vectors)
- Hierarchical context (section_type preserves H2 parent)

### Tier 2: Conversations (Completeness)
**Source**: TRACE-exported structured markdown
**Chunking**: H2-level (major sections)
**Vectors per conversation**: ~5

**Use Case**: "What conversations discussed database design?"

**Query**: `imem search "database" --in conversations`

**Returns**: Relevant conversation sections (User Messages, Code Changes, etc.)

**Why H2-level**:
- Broader discovery (find relevant conversations)
- Section-specific retrieval (just code changes, just questions)
- Lower vector count (faster indexing)

---

## Components

### `config.py` - Centralized Configuration
**Purpose**: Single source of truth for all settings

**Environment Variables**:
```python
IMEM_QDRANT_PORT = 6334      # Default port
IMEM_QDRANT_HOST = localhost # Default host
IMEM_CONTEXT_DIR = ~/.context # Storage directory
```

**Benefits**:
- No hardcoded values
- Runtime configuration
- Docker-compose generation

### `registry.py` - Project Tracking
**Purpose**: Map projects to Qdrant collections

**Data Structure**:
```json
{
  "projects": {
    "/home/user/project-a": {
      "collection": "imem_12345678",
      "indexed_at": "2025-10-23T20:00:00",
      "doc_count": 42
    }
  }
}
```

**Methods**:
- `register_project()` - Create collection mapping
- `is_registered()` - Check if project indexed
- `get_project_info()` - Retrieve collection name

### `cli.py` - Command Interface
**Purpose**: Phase-based CLI with structured filtering

**New Architecture (Oct 25, 2025)**:
```bash
# Phase-based subcommands
imem develop search "query" --decisions --constraints --pattern
imem conversations search "query" --session abc123
imem design search "query" --options --questions

# Legacy commands (still supported)
imem init [--force]                    # Index current project
imem search <query> [...filters]       # Search current project
imem service [start|stop|status]       # Manage Qdrant
```

**Why Phase Subcommands?**
- Natural grouping of section types (develop → Decisions/Constraints/Failures)
- Phase-specific flags (--decisions only makes sense for develop)
- Cleaner UX (no confusion between phase vs section filters)

**Project Detection**:
1. Find `.git/` directory (project root)
2. Look for `.context/{develop,design}/` structure
3. Create unique collection: `imem_<md5_hash_of_path>`
4. Register in `~/.context/imem_registry.json`

### `ingest.py` - Document Indexing
**Purpose**: Parse, chunk, embed, and store documents

**Key Method**: `ingest_markdown_chunked()`

**Flow (Updated Oct 25, 2025)**:
```python
def ingest_markdown_chunked(file_path, phase, layer, collection):
    # 1. Read file + extract frontmatter
    frontmatter = extract_frontmatter(content)

    # 2. Parse with LlamaIndex
    llama_doc = LlamaDocument(text=content)
    nodes = MarkdownNodeParser().get_nodes_from_documents([llama_doc])

    # 3. Batch encode all sections (2x faster)
    texts = [node.get_content() for node in nodes]
    embeddings = model.encode(texts)

    # 4. For each node:
    for node, embedding in zip(nodes, embeddings):
        content = node.get_content()
        first_line = content.split('\n')[0]

        # Parse header level by counting # symbols
        header_match = re.match(r'^(#{1,6})\s+(.+)$', first_line)
        header_level = len(header_match.group(1)) if header_match else None

        # FILTER: Only index H3+ sections (skip H1/H2 noise)
        if header_level is None or header_level < 3:
            continue

        # Extract H2 parent for section_type
        section_name = header_match.group(2)
        h2_section_type = extract_h2_parent(node.metadata['header_path'])

        # Detect structured fields
        has_context = '**Context**' in content
        has_solution = '**Solution**' in content
        # ... more field detection

        # Build rich payload
        payload = {
            'source': 'changelog',
            'phase': phase,
            'layer': layer,  # implementation or pattern
            'section_type': h2_section_type,  # H2 parent (Decisions, Constraints)
            'section_name': section_name,     # H3 title
            'section_level': header_level,
            'has_context': has_context,
            'has_solution': has_solution,
            'schema_version': 'v1.0',
            'word_count': len(content.split()),
            'char_count': len(content),
            'content': content,
            'file_path': str(file_path)
        }

        batch_points.append({
            'id': uuid4(),
            'vector': {"e5-large-v2": embedding},
            'payload': payload
        })

    # 5. Batch upsert to Qdrant
    client.upsert(collection, points=batch_points)
```

**Key Changes**:
- ✅ Batch encoding (2x faster)
- ✅ H1/H2 filtering (only H3+ indexed)
- ✅ Dual section tracking (section_type + section_name)
- ✅ Structured field detection
- ✅ Schema versioning

**Optimizations**:
- Batch upsert (10x faster than individual)
- Lazy model loading
- Named vectors for future multi-model support
- HNSW tuning (m=16, ef_construct=100) for search performance
- Token limit warnings (E5-Large-v2 512 token limit ≈ 2000 chars)

### `search.py` - Modular Search Engine
**Purpose**: Multi-model search architecture

**Supports**:
- E5-Large-v2 (1024 dimensions)
- Future: MiniLM, BGE, custom models

**Search Config**:
```python
@dataclass
class SearchConfig:
    name: str
    model_name: str
    collection_name: str
    vector_name: str
    dimensions: int
```

### `enhanced.py` - Enhanced Qdrant Search
**Purpose**: High-level search with filtering and sorting

**Features**:
- Metadata filtering (phase, section, session)
- Timestamp extraction from frontmatter
- Hybrid scoring (semantic + recency)
- Multi-term search (AND/OR operators)

**Key Method**: `search(query, filters, limit, sort_by)`

**Filter Support**:
```python
filters = {
    'phase': 'develop',
    'section_type': 'Decisions',
    'session_id': 'abc123'
}

results = searcher.search(query, filters=filters)
```

### `qdrant_service.py` - Docker Lifecycle
**Purpose**: Start/stop/status Qdrant container

**Container Config**:
- Image: `qdrant/qdrant:latest`
- Port: 6334 (external) → 6333 (internal)
- Volume: `~/.context/qdrant_storage/`
- Container name: `imem_qdrant`

**Methods**:
- `ensure_running()` - Start if not running
- `start()` - Start container
- `stop()` - Stop container
- `status()` - Check if running

---

## Data Flow

### Indexing Flow (Changelogs)
```
1. User: imem init
2. Detect project root (find .git/)
3. Find .context/develop/ or .context/design/
4. For each markdown file:
   a. Read file + extract frontmatter
   b. Parse with LlamaIndex (H3 chunks for changelogs)
   c. Extract section names from headers
   d. Generate E5-Large-v2 embeddings (1024D)
   e. Build payload with metadata
   f. Batch upsert to Qdrant
5. Update registry with doc count
```

### Indexing Flow (Conversations)
```
1. User: imem index-all-conversations
2. TRACE finds all conversations
3. For each conversation:
   a. TRACE exports structured markdown (H2 sections)
   b. Save to temp file
   c. IMEM parses with LlamaIndex (H2 chunks)
   d. Extract section names (User Messages, Code Changes, etc.)
   e. Generate embeddings
   f. Build payload with session_id
   g. Batch upsert to Qdrant
4. Delete temp file
```

### Search Flow
```
1. User: imem search "authentication" --in develop
2. Load project collection from registry
3. Build Qdrant filter:
   Filter(must=[
       FieldCondition(key='source', match='changelog'),
       FieldCondition(key='phase', match='develop')
   ])
4. Embed query with E5-Large-v2
5. Search Qdrant with filter
6. Return top K results sorted by similarity
```

---

## LlamaIndex Integration

### MarkdownNodeParser
**Purpose**: Intelligent markdown chunking based on headers

**Behavior**:
- Detects H1/H2/H3 hierarchy
- Creates node per section
- Preserves parent-child relationships
- Extracts metadata (header_path)

**Version-Specific Issues (LlamaIndex v0.14.5)**:
- ❌ `header_level` metadata NOT populated (should be but isn't)
- ✅ **Workaround**: Parse header_level by counting `#` symbols in first line
- ✅ Verified via LlamaIndex spec validation agent

**Example**:
```markdown
# Changelog Title              ← H1 (root)

## Decisions                   ← H2 (section parent)
### Use JWT Authentication     ← H3 (1 vector)
**Context**: ...
**Solution**: ...

### Implement Rate Limiting    ← H3 (1 vector)
**Context**: ...
**Solution**: ...
```

**Result**: 2 vectors (one per H3 Decision)

### Section Name Extraction
**Problem**: LlamaIndex `header_path` can be malformed

**Solution**: Extract from content (first line)
```python
content = node.get_content()
first_line = content.split('\n')[0]

# Extract: "## Decisions" → "Decisions"
header_match = re.match(r'^#{1,6}\s+(.+)$', first_line)
section_name = header_match.group(1).strip()
```

**Benefit**: Clean section names for filtering

---

## Metadata Schema

### Changelog Metadata (v1.0)
```python
{
    # Core identification
    'source': 'changelog',
    'phase': 'develop',                  # design/designate/develop/document
    'layer': 'implementation',           # implementation or pattern

    # Hierarchical section tracking
    'section_type': 'Decisions',         # H2 parent (Decisions, Constraints, etc.)
    'section_name': 'Database as Inert...',  # H3 title
    'section_level': 3,                  # Actual header level (H3)
    'header_path': '/Provider-Agnostic Refactor/Decisions/Database...',

    # Frontmatter metadata
    'category': 'implementation',        # From frontmatter type
    'subtype': 'security',               # From frontmatter type
    'timestamp': '2025-10-23T20:00:00-0700',
    'session_id': 'abc123...',           # Links to conversation

    # Structured field detection (for rich filtering)
    'has_context': True,
    'has_solution': True,
    'has_rationale': True,
    'has_alternatives': False,
    'has_approach': False,
    'has_benefits': False,
    'has_drawbacks': False,

    # Schema versioning and monitoring
    'schema_version': 'v1.0',
    'word_count': 145,
    'char_count': 892,

    # Content
    'content': 'Full H3 section text with Context/Solution/Rationale',
    'file_path': '.context/develop/.changes/251011-1200_provider-agnostic-refactor.md'
}
```
### Conversation Metadata
```python
{
    'source': 'conversation',
    'session_id': 'abc123-...',      # Full UUID
    'section_type': 'User Messages', # Extracted from H2
    'section_level': 2,
    'start_time': '2025-10-23T19:00:00',
    'duration_minutes': 42.5,
    'message_count': 87,
    'has_changelog': True,           # Bidirectional link
    'changelog_path': '.context/develop/...',
    'content': 'Full section text'
}
```

---

## Named Vectors Architecture

### Why Named Vectors?
**Problem**: Single collection might use multiple embedding models

**Solution**: Named vectors allow model-specific retrieval
```python
# Collection config
vectors_config = {
    "e5-large-v2": VectorParams(size=1024, distance=Distance.COSINE),
    # Future: "bge-large": VectorParams(size=1536, ...),
}

# Upsert with named vector
point = {
    'id': uuid4(),
    'vector': {"e5-large-v2": embedding},  # Specify model
    'payload': {...}
}

# Search specific model
results = client.query_points(
    collection_name=collection,
    query=query_vector,
    using="e5-large-v2"  # Specify which model
)
```

**Benefits**:
- Multi-model support
- Model-specific retrieval
- Future-proof architecture

---

## Performance

### Indexing
- **First-time**: ~2-5 sec per document (embedding generation)
- **Batch mode**: ~30 docs in 5 minutes
- **Conversations**: ~10 sec per conversation
- **Batch conversations**: 2377/5515 in ~2 hours (43%)

### Search
- **Vector search**: <100ms (Qdrant HNSW index)
- **Metadata filtering**: <10ms overhead
- **Section retrieval**: 10-50× smaller than full documents

### Storage
- **Per changelog**: ~75KB (15 vectors × 4KB + metadata)
- **Per conversation**: ~25KB (5 vectors × 4KB + metadata)
- **100 changelogs + 50 conversations**: ~8.75MB total

---

## Filter System

### Phase Filtering
```bash
imem search "auth" --in develop    # Ground truth only
imem search "auth" --in design     # R&D explorations
imem search "auth" --in document   # Stable docs
```

**Implementation**:
```python
filters = {'source': 'changelog', 'phase': 'develop'}
query_filter = Filter(must=[
    FieldCondition(key='source', match=MatchValue(value='changelog')),
    FieldCondition(key='phase', match=MatchValue(value='develop'))
])
```

### Section Filtering
```bash
imem search "rate limiting" --section "Decisions"
```

**Implementation**:
```python
filters = {'section_type': 'Decisions'}
```

### Session Filtering
```bash
imem search "implementation" --session abc123
```

**Implementation**:
```python
filters = {'session_id': 'abc123-...'}  # Full UUID required
```

### Combined Filtering
```bash
imem search "JWT" --in develop --section "Decisions"
```

**Implementation**:
```python
filters = {
    'source': 'changelog',
    'phase': 'develop',
    'section_type': 'Decisions'
}
```

---

## Configuration

### Environment Variables
```bash
export IMEM_QDRANT_PORT=6334
export IMEM_QDRANT_HOST=localhost
export IMEM_QDRANT_TIMEOUT=2
export IMEM_CONTEXT_DIR=~/.context
```

### Registry File
**Path**: `~/.context/imem_registry.json`

**Structure**:
```json
{
  "projects": {
    "/home/user/project-a": {
      "collection": "imem_12345678",
      "indexed_at": "2025-10-23T20:00:00",
      "doc_count": 42
    }
  }
}
```

---

## Integration with TRACE

### Conversation Indexing
```bash
# Single conversation
imem index-conversation abc123

# What happens:
# 1. TRACE finds conversation file
# 2. TRACE exports structured markdown
# 3. IMEM chunks with LlamaIndex (H2 sections)
# 4. IMEM embeds with E5-Large-v2
# 5. IMEM stores in Qdrant with session_id
```

### Bidirectional Linking
**Changelog → Conversation**:
```yaml
# changelog frontmatter
session_id: "abc123-..."
```

Search: `imem search --session abc123 --in develop`

**Conversation → Changelog**:
```python
# conversation metadata
{
    'has_changelog': True,
    'changelog_path': '...'
}
```

---

## Testing & Validation

### Pre-Indexing Validation
**Purpose**: Test indexing logic before full reindex

**Tool**: `imem/tests/validate_indexing.py`

**Usage**:
```bash
# Test on sample files (default: first 3 changelogs)
python imem/tests/validate_indexing.py

# Test specific files
python imem/tests/validate_indexing.py file1.md file2.md
```

**Output**:
- Filtered vs kept chunks
- Header level distribution
- Section type distribution
- Metadata extraction preview
- Large chunk warnings (>2000 chars)

**Benefits**:
- Fast iteration (seconds vs minutes)
- Validate filter logic before committing
- Preview metadata schema
- Industry best practice (RAG pipeline testing)

### LlamaIndex Spec Validation
**Validated**: October 25, 2025

**Findings**:
- ✅ Hybrid architecture approved (MarkdownNodeParser + direct Qdrant)
- ✅ Metadata schema exemplary for structured retrieval
- ✅ Batch encoding optimal
- ⚠️ HNSW tuning recommended (implemented)
- ⚠️ Token limit validation recommended (implemented)

**Verdict**: Approved with minor optimizations (all implemented)

---

## Performance Optimizations

### HNSW Configuration
**Purpose**: Search speed vs accuracy tradeoff

**Settings** (Qdrant collection config):
```python
hnsw_config = HnswConfigDiff(
    m=16,              # Links per node (higher = better recall)
    ef_construct=100,  # Build-time search depth
    on_disk=False      # Keep vectors in RAM for speed
)
```

**Impact**: 2-5x faster search with proper tuning

### Token Limit Monitoring
**Problem**: E5-Large-v2 has 512 token limit (~2000 chars)

**Solution**: Warn about large chunks during indexing
```python
if char_count > 2000:
    logger.warning(f"Large chunk ({char_count} chars) may exceed token limit")
```

**Results**: 2 large chunks detected in test corpus
- 251011-1130_provider-agnostic-refactor.pattern.md: Implementation (2061 chars)
- 251011-1800_critical-bug-fixes.md: Implementation (2611 chars)

---

## Future Enhancements

### High Priority
- Hybrid search (semantic + keyword BM25)
- Cross-section queries (find patterns across Decisions)
- Parent-child node traversal

### Medium Priority
- Temporal analysis (show decisions from last week)
- Code snippet detection (find similar implementations)
- Multi-model support (BGE, MiniLM)

### Low Priority
- Conversation similarity (find related sessions)
- Auto-tagging (extract keywords automatically)
- Query history tracking

---

## Related Documentation

- **Ecosystem Overview**: [architecture_aura.md](./architecture_aura.md)
- **Conversation Parsing**: [architecture_trace.md](./architecture_trace.md)
