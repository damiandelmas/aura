---
schema_version: "v3_adaptive"
type: "architecture.imem"
status: "stable"
keywords: "imem vector-search qdrant llamaindex embeddings section-chunking"
timestamp: "2025-10-23T20:45:00-0700"
---

# IMEM Architecture

## Purpose

IMEM is a vector search engine that provides section-level semantic retrieval across changelogs and conversations. It uses LlamaIndex for intelligent chunking and E5-Large-v2 embeddings for precise similarity search.

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

### 3. Intelligent Filtering
```bash
imem search "auth" --in develop          # Phase filter
imem search "auth" --section "Decisions" # Section filter
imem search "auth" --session abc123      # Session filter
```

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
**Chunking**: H3-level (individual items)
**Vectors per doc**: ~15 (varies by complexity)

**Use Case**: "What did we decide about JWT?"

**Query**: `imem search "JWT" --in develop --section "Decisions"`

**Returns**: Just the H3 Decision sections about JWT, not entire documents.

**Why H3-level**:
- Surgical retrieval (exact decision, not entire changelog)
- Progressive disclosure (simple docs = fewer vectors)
- Hierarchical context (H3 → H2 → H1 preserved)

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
**Purpose**: User-facing CLI with project isolation

**Commands**:
```bash
imem init [--force]                    # Index current project
imem search <query> [...filters]       # Search current project
imem index-conversation <session-id>   # Index single conversation
imem index-all-conversations           # Batch index all conversations
imem service [start|stop|status]       # Manage Qdrant
```

**Project Detection**:
1. Find `.git/` directory (project root)
2. Look for `.context/{develop,design}/` structure
3. Create unique collection: `imem_<md5_hash_of_path>`
4. Register in `~/.context/imem_registry.json`

### `ingest.py` - Document Indexing
**Purpose**: Parse, chunk, embed, and store documents

**Key Method**: `ingest_markdown_chunked()`

**Flow**:
```python
def ingest_markdown_chunked(file_path, phase, collection):
    # 1. Read file + extract frontmatter
    frontmatter = extract_frontmatter(content)

    # 2. Parse with LlamaIndex
    llama_doc = LlamaDocument(text=content)
    nodes = MarkdownNodeParser().get_nodes_from_documents([llama_doc])

    # 3. For each node (H2 or H3 section):
    for node in nodes:
        # Extract section name from content
        section_name = extract_section_name(node.content)

        # Generate embedding
        embedding = model.encode(node.content).tolist()

        # Build payload
        payload = {
            'source': 'changelog',  # or 'conversation'
            'phase': phase,         # 'develop', 'design', etc.
            'section_type': section_name,
            'category': frontmatter['type'].split('.')[0],
            'session_id': frontmatter.get('session_id'),
            'content': node.content,
            'file_path': str(file_path)
        }

        # 4. Batch upsert to Qdrant
        batch_points.append({
            'id': uuid4(),
            'vector': {"e5-large-v2": embedding},
            'payload': payload
        })

    client.upsert(collection, points=batch_points)
```

**Optimizations**:
- Batch upsert (10x faster than individual)
- Lazy model loading
- Named vectors for future multi-model support

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
- Extracts metadata (header_path, header_level)

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

### Changelog Metadata
```python
{
    'source': 'changelog',
    'phase': 'develop',              # design/designate/develop/document
    'section_type': 'Decisions',     # Extracted from H2/H3
    'section_level': 3,              # Header level
    'category': 'implementation',    # From frontmatter type
    'subtype': 'security',           # From frontmatter type
    'timestamp': '2025-10-23T20:00:00-0700',
    'session_id': 'abc123...',       # Optional: links to conversation
    'content': 'Full section text',
    'file_path': '.context/develop/.changes/...'
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
