---
schema_version: "v3_adaptive"
type: "architecture.imem"
status: "stable"
keywords: "imem vector-search qdrant llamaindex embeddings section-chunking structured-retrieval metadata-rich"
---

# IMEM Architecture

## Purpose

IMEM is a structured knowledge retrieval system that provides SQL-like filtering combined with semantic search across changelogs and conversations. The system extracts rich metadata from template-structured documents, enabling precision retrieval through phase/layer/section filters combined with vector similarity.

The system captures decision genealogy through bidirectional linking between conversations and changelogs, dual-layer architecture (implementation and pattern layers), and structured field detection (Context, Solution, Rationale). Each project receives an isolated Qdrant collection, allowing independent indexing and querying across multiple codebases.

**Path**: `imem/src/imem/`
**CLI**: `imem`
**Dependencies**: qdrant-client, sentence-transformers, click, llama-index-core

## Components

**config.py** - Centralized configuration management. Provides single source of truth for all settings through environment variables (IMEM_QDRANT_PORT, IMEM_QDRANT_HOST, IMEM_CONTEXT_DIR). Eliminates hardcoded values and enables runtime configuration.

**registry.py** - Project tracking system. Maps project directories to Qdrant collections using JSON storage. Provides methods for project registration (`register_project()`), status checking (`is_registered()`), and collection retrieval (`get_project_info()`). Stores metadata including collection name, index timestamp, and document count.

**cli.py** - Phase-based command interface. Provides subcommands organized by phase (develop, design, conversations) with phase-specific filtering flags. Handles project detection by locating `.git/` directory and `.context/` structure. Creates unique collections using `imem_<md5_hash_of_path>` naming convention. Supports legacy commands for backward compatibility.

**ingest.py** - Document indexing engine. Parses markdown files using LlamaIndex MarkdownNodeParser, chunks content at H3-level for changelogs and H2-level for conversations. Implements batch encoding for performance (2x faster than sequential). Filters H1/H2 noise (only indexes H3+ sections for changelogs), extracts section metadata, detects structured fields (has_context, has_solution, etc.), and performs batch upserts to Qdrant. Generates E5-Large-v2 embeddings (1024 dimensions) with named vector support.

**search.py** - Modular search engine architecture. Supports multiple embedding models through SearchConfig dataclass. Currently implements E5-Large-v2 with provisions for future models (MiniLM, BGE). Provides vector name specification for multi-model collections.

**enhanced.py** - High-level search interface. Implements metadata filtering (phase, section, session), timestamp extraction from frontmatter, hybrid scoring (semantic + recency), and multi-term search operators (AND/OR). Provides unified search method with filter composition and result sorting.

**qdrant_service.py** - Docker lifecycle management for Qdrant container. Manages container lifecycle (start, stop, status, ensure_running). Configures Qdrant image with port mapping (6334 external to 6333 internal), volume mounting (`~/.context/qdrant_storage/`), and container naming (`imem_qdrant`).

## Data Flow

**Initialization Layer** - User invokes `imem init` from project directory. System detects project root by locating `.git/` directory. Finds `.context/develop/` or `.context/design/` structure. Creates unique collection using MD5 hash of project path. Registers collection in `~/.context/imem_registry.json` with metadata.

**Indexing Layer (Changelogs)** - System scans `.context/{design,designate,develop,document}/*.md` files. For each file: reads content and extracts frontmatter, parses with LlamaIndex MarkdownNodeParser to generate H3-level chunks, extracts section names from headers, generates E5-Large-v2 embeddings in batch mode, builds payload with rich metadata (phase, layer, section_type, section_name, structured field flags), performs batch upsert to Qdrant with named vectors. Updates registry with document count.

**Indexing Layer (Conversations)** - User invokes `imem index-all-conversations`. TRACE finds conversation files and exports structured markdown with H2 sections. System saves to temporary file, parses with LlamaIndex at H2-level, extracts section names (User Messages, Code Changes, Tools Used), generates embeddings, builds payload with session_id, performs batch upsert. Deletes temporary file.

**Search Layer** - User submits query with optional filters (phase, section_type, session_id). System loads project collection from registry. Builds Qdrant filter using FieldCondition and Filter objects. Embeds query with E5-Large-v2 model. Executes vector search with metadata filtering against named vector "e5-large-v2". Returns top K results sorted by similarity score.

**Output Layer** - Search results flow to terminal with formatted display. Each result includes section content, metadata (phase, section type, file path), similarity score, and contextual information (parent headers, structured fields present).

## Integration Points

**Filesystem Access** - Reads markdown files from `.context/` directory structure. Requires read permissions for changelog and conversation files. No write operations to source documents. Registry stored in `~/.context/imem_registry.json`.

**Qdrant Vector Database** - Connects via HTTP to Docker container on port 6334. Uses named vectors for multi-model support. Implements HNSW indexing (m=16, ef_construct=100, on_disk=False) for fast similarity search. Stores vectors with rich metadata payloads. Provides sub-100ms query performance.

**LlamaIndex Core** - Uses MarkdownNodeParser for intelligent chunking based on header hierarchy. Preserves parent-child relationships through metadata. Extracts header_path and parses header_level by counting # symbols in first line (LlamaIndex v0.14.5 doesn't populate header_level metadata). Creates one node per section with full content.

**Sentence Transformers** - Loads E5-Large-v2 model for embedding generation. Produces 1024-dimensional vectors. Supports batch encoding for performance. Models lazy-loaded on first use.

**TRACE System** - Receives conversation markdown exports with H2-level sections. Extracts session_id for bidirectional linking. Reads structured sections (User Messages, Code Changes, Tools Used). Enables changelog-to-conversation and conversation-to-topic queries.

**Docker Engine** - Manages Qdrant container lifecycle. Mounts persistent volume for data storage. Configures port mapping and health checks. Provides isolation between projects through collection namespacing.

## Patterns & Principles

**Per-Project Isolation** - Each project receives unique Qdrant collection based on path hash. Projects maintain independent indices and cannot interfere. Collections persist across sessions. Registry tracks all indexed projects for fast lookup.

**Section-Level Chunking** - Changelogs chunked at H3-level for surgical retrieval (individual decisions, constraints, failures). Conversations chunked at H2-level for broader discovery (sections like User Messages, Code Changes). Chunk granularity matches use case: precision for changelogs, completeness for conversations. Progressive disclosure: simple documents generate fewer vectors.

**Hierarchical Metadata** - Dual section tracking: section_type (H2 parent like "Decisions") and section_name (H3 title). Preserves document hierarchy in metadata. Enables parent-aware filtering and context reconstruction. Header paths provide full navigation breadcrumb.

**Structured Field Detection** - Parses template fields (Context, Solution, Rationale, Alternatives). Stores boolean flags in metadata for rich filtering. Enables queries like "find decisions with alternatives considered". Supports quality assessment through field completeness.

**Named Vectors Architecture** - Collections support multiple embedding models simultaneously. Each vector stored with model name (e.g., "e5-large-v2"). Search specifies which model to query. Future-proof for model upgrades and A/B testing.

**Batch Processing** - Encodes all sections in single model call (2x faster than sequential). Upserts multiple vectors in batch mode (10x faster than individual). Minimizes network roundtrips and model invocations.

**Metadata-Rich Payloads** - Each vector includes 23 metadata fields (schema_version v1.0: phase, layer, section_type, section_name, section_level, timestamps, structured field flags, word_count, char_count, etc.). Enables SQL-like filtering before semantic search. Supports sorting, grouping, and aggregation operations.

**Bidirectional Linking** - Changelogs link to conversations via session_id in frontmatter. Conversations link to changelogs via has_changelog and changelog_path metadata. Enables tracing decisions to originating discussions.

## Usage

**Installation**
```bash
cd /path/to/project
pip install -e imem/
```

**Service Management**
```bash
# Start Qdrant container
imem service start

# Check status
imem service status

# Stop container
imem service stop
```

**Project Initialization**
```bash
# Index current project
cd ~/my-project
imem init

# Force re-index
imem init --force
```

**Phase-Based Search Commands**
```bash
# Search develop changelogs with section filters
imem develop search "authentication" --decisions --constraints

# Search design changelogs
imem design search "database schema" --options --questions

# Search conversations by session
imem conversations search "bug fix" --session abc12345

# Search pattern layer only
imem develop search "error handling" --pattern
```

**Legacy Search Commands**
```bash
# Basic search
imem search "JWT authentication"

# Search specific phase
imem search "database" --in develop
imem search "api design" --in design

# Section filtering
imem search "rate limiting" --section "Decisions"
imem search "constraints" --section "Constraints"

# Session filtering
imem search "implementation" --session abc12345

# Combined filtering
imem search "JWT" --in develop --section "Decisions"
```

**Conversation Indexing**
```bash
# Index single conversation
imem index-conversation abc12345

# Index all conversations (batch mode)
imem index-all-conversations
```

**Programmatic Access**
```python
from imem.ingest import ingest_markdown_chunked
from imem.enhanced import EnhancedSearch
from imem.registry import ProjectRegistry

# Register project
registry = ProjectRegistry()
collection = registry.register_project("/path/to/project")

# Index changelog
ingest_markdown_chunked(
    file_path="changelog.md",
    phase="develop",
    layer="implementation",
    collection=collection
)

# Search with filters
searcher = EnhancedSearch(collection_name=collection)
results = searcher.search(
    query="authentication",
    filters={
        'phase': 'develop',
        'section_type': 'Decisions'
    },
    limit=10
)

# Access results
for result in results:
    print(f"Score: {result.score}")
    print(f"Section: {result.payload['section_name']}")
    print(f"Content: {result.payload['content']}")
```

**Configuration**
```bash
# Environment variables
export IMEM_QDRANT_PORT=6334
export IMEM_QDRANT_HOST=localhost
export IMEM_QDRANT_TIMEOUT=2
export IMEM_CONTEXT_DIR=~/.context

# Registry location
cat ~/.context/imem_registry.json
```
