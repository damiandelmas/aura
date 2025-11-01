---
schema_version: "v3_adaptive"
type: "architecture.imem"
status: "stable"
keywords: "imem vector-search qdrant llamaindex embeddings section-chunking structured-retrieval metadata-rich"
sessionid: "cb91d93d-f844-4677-b8f0-ce8ebbbb0f0f"
---

# IMEM Architecture

## Purpose

IMEM is a structured knowledge retrieval system that provides filtering combined with semantic search across changelogs and conversations. The system extracts rich metadata from template-structured documents, enabling precision retrieval through phase/layer/section filters combined with vector similarity.

The system captures decision genealogy through bidirectional linking between conversations and changelogs, dual-layer architecture (implementation and pattern layers), and structured field detection (Context, Solution, Rationale). Each project receives an isolated Qdrant collection, allowing independent indexing and querying across multiple codebases.

**Path**: `imem/src/imem/`
**CLI**: `imem`
**Dependencies**: qdrant-client, sentence-transformers, click, llama-index-core

## Components

**config.py** - Centralized configuration management. Provides single source of truth for all settings through environment variables (IMEM_QDRANT_PORT, IMEM_QDRANT_HOST, IMEM_CONTEXT_DIR). Eliminates hardcoded values and enables runtime configuration.

**registry.py** - Project tracking system with dual-collection support. Maps project directories to Qdrant collections using JSON storage. Returns dict with 'context' and 'conversation' collection names from `register_project()`. Provides `get_collection_by_type(project_root, 'context'|'conversation')` for routing. Tracks separate doc_counts per collection type. Backward compatible with single-collection legacy format.

**cli.py** - Unified command interface with source-based routing. Primary commands: `imem index <source>`, `imem search <source> "query"`, `imem compose <config>`. Sources: develop, design, document, conversations, context. Handles project detection by locating `.git/` directory and `.context/` structure. Creates dual collections (context + conversation) using `imem_<hash>_{context|conversation}` naming convention. Dynamic collection routing via config 'source' field. Collection lifecycle management via `imem collections list/clean` commands.

**ingest.py** - Document indexing engine with content-aware filtering. Parses markdown files using LlamaIndex MarkdownNodeParser, chunks content at H3-level for changelogs and H2-level for conversations. Content-length filter (<20 chars) skips empty H2 parent headers while indexing substantive sections. Implements batch encoding for performance (2x faster than sequential). Extracts section metadata, detects structured fields (has_context, has_solution, etc.), and performs batch upserts to Qdrant. Generates Nomic Embed v1.5 embeddings (768 dimensions, 8k tokens) with auto-detection fallback for E5-Large-v2 legacy collections. Tracks chunk counts (not conversation counts) for accurate registry metrics.

**search.py** - Modular search engine architecture. Supports multiple embedding models through SearchConfig dataclass. Currently implements E5-Large-v2 with provisions for future models (MiniLM, BGE). Provides vector name specification for multi-model collections.

**enhanced.py** - High-level search interface. Implements metadata filtering (phase, section, session), timestamp extraction from frontmatter, hybrid scoring (semantic + recency), and multi-term search operators (AND/OR). Provides unified search method with filter composition and result sorting.

**primitives/discovery.py** - Compositional discovery primitives layer. Four orthogonal functions (get_siblings, get_genealogy, get_temporal, get_cross_phase) that retrieve related chunks based on metadata predicates. Each primitive accepts parameterized filters (section_types, order_by, limit, has_rationale, has_alternatives) for surgical retrieval. Backward compatible with boolean config (converts to dict internally). None-safe sorting handles null values in metadata fields (section_level, timestamp). Pure functions with no cross-dependencies enable flexible composition.

**compose.py** - Compositional orchestrator with intelligent routing. Executes four-stage pipeline (search → discovery enrichment → optional graph → template rendering) from declarative JSON config. Handles dict-based discovery config with backward compatibility for boolean flags. Implements metadata enrichment with temporal position detection (current_thrust, superseded, evolved, failed_branch) and confidence signals (has_rationale, has_alternatives, continuation_count). Routes to correct collection (context vs conversation) based on config 'source' field. Enables single-call retrieval with complete intent expression.

**templates/** - Jinja2 templates for context-aware AI comprehension. Includes `story-context.j2` with genealogical position indicators (🟢 current thrust, ⚠️ evolved, ❌ failed branch), structured sections (Failures → Patterns → Decisions), and explicit "Don't Suggest" warnings for failed approaches. Templates embed temporal context and continuation counts to help AI agents distinguish current directions from superseded approaches. Structure = comprehension pattern for AI memory systems.

**qdrant_service.py** - Docker lifecycle management for Qdrant container. Manages container lifecycle (start, stop, status, ensure_running). Configures Qdrant image with port mapping (6334 external to 6333 internal), volume mounting (`~/.context/qdrant_storage/`), and container naming (`imem_qdrant`).

## Data Flow

**Initialization Layer** - User invokes `imem init` from project directory. System detects project root by locating `.git/` directory. Finds `.context/develop/` or `.context/design/` structure. Creates dual collections using MD5 hash: `imem_<hash>_context` and `imem_<hash>_conversation`. Registers both collections in `~/.context/imem_registry.json` with separate doc_counts. Auto-creates collections on first use (no --force needed for initial run).

**Indexing Layer (Changelogs)** - System scans `.context/{design,designate,develop,document}/*.md` files. For each file: reads content and extracts frontmatter, parses with LlamaIndex MarkdownNodeParser to generate H3-level chunks, applies content-length filter (<20 chars) to skip empty H2 parent headers, extracts section names from headers, generates Nomic Embed v1.5 embeddings in batch mode (with E5 fallback for legacy collections), builds payload with rich metadata (phase, layer, section_type, section_name, structured field flags including has_rationale, has_alternatives), performs batch upsert to Qdrant with named vectors. Updates registry with chunk count (not file count) for accurate corpus metrics. Routes to context collection by default.

**Indexing Layer (Conversations)** - User invokes `imem index-all-conversations`. TRACE finds conversation files and exports structured markdown with H2 sections. System saves to temporary file, parses with LlamaIndex at H2-level, extracts section names (User Messages, Code Changes, Tools Used), generates embeddings, builds payload with session_id, performs batch upsert. Deletes temporary file.

**Search Layer** - User submits `imem search <source> "query"` with optional filters (phase, section_type, session_id). System determines collection type from source (develop/design/document → context, conversations → conversation). Loads correct collection from registry via `get_collection_by_type()`. Auto-detects embedding model from collection vector config (Nomic or E5). Builds Qdrant filter using FieldCondition and Filter objects. Embeds query with detected model. Executes vector search with metadata filtering. Returns top K results sorted by similarity score.

**Compositional Layer (FlexGraph)** - User invokes `imem compose <config>` with declarative JSON config specifying search, discovery, optional graph, and output parameters. System routes to correct collection based on config 'source' field. Executes four-stage pipeline: (1) Search stage retrieves base results via semantic search, (2) Discovery stage enriches each result with siblings/genealogy/temporal/cross_phase data using parameterized primitives (supports both dict config with filters or boolean legacy format), (3) Optional graph stage applies PageRank or centrality scoring, (4) Template stage renders results with context-aware structure. Metadata enrichment detects temporal position by counting continuation chunks (current_thrust: 0 later, evolved: 1-2 later, superseded: 3+ later, failed_branch: in Failures section). Adds confidence signals (has_rationale, has_alternatives, continuation_count). Returns rendered markdown or structured JSON.

**Output Layer** - Search results flow to terminal with formatted display. Each result includes section content, metadata (phase, section type, file path), similarity score, and contextual information (parent headers, structured fields present). Compose results render via Jinja2 templates with genealogical indicators and structured sections optimized for AI comprehension.

## Integration Points

**Filesystem Access** - Reads markdown files from `.context/` directory structure. Requires read permissions for changelog and conversation files. No write operations to source documents. Registry stored in `~/.context/imem_registry.json`.

**Qdrant Vector Database** - Connects via HTTP to Docker container on port 6334. Uses named vectors for multi-model support. Implements HNSW indexing (m=16, ef_construct=100, on_disk=False) for fast similarity search. Stores vectors with rich metadata payloads. Provides sub-100ms query performance.

**LlamaIndex Core** - Uses MarkdownNodeParser for intelligent chunking based on header hierarchy. Preserves parent-child relationships through metadata. Extracts header_path and parses header_level by counting # symbols in first line (LlamaIndex v0.14.5 doesn't populate header_level metadata). Creates one node per section with full content.

**Sentence Transformers** - Loads Nomic Embed v1.5 (768D, 8k tokens) as default model for new collections. Auto-detects model from collection vector config for backward compatibility with E5-Large-v2 (1024D) legacy collections. Model registry in config.py maps vector names to model paths. Supports batch encoding for performance. Models lazy-loaded on first use.

**TRACE System** - Receives conversation markdown exports with H2-level sections. Extracts session_id for bidirectional linking. Reads structured sections (User Messages, Code Changes, Tools Used). Enables changelog-to-conversation and conversation-to-topic queries.

**Docker Engine** - Manages Qdrant container lifecycle. Mounts persistent volume for data storage. Configures port mapping and health checks. Provides isolation between projects through collection namespacing.

## Patterns & Principles

**Per-Project Isolation** - Each project receives two unique Qdrant collections based on path hash: `imem_<hash>_context` and `imem_<hash>_conversation`. Projects maintain independent indices and cannot interfere. Collections persist across sessions. Registry tracks all indexed projects with dual collection names and separate doc_counts. Collection lifecycle commands (`list`, `clean`) show registered vs orphaned collections for maintenance.

**Section-Level Chunking** - Changelogs chunked at H3-level for surgical retrieval (individual decisions, constraints, failures). Conversations chunked at H2-level for broader discovery (sections like User Messages, Code Changes). Chunk granularity matches use case: precision for changelogs, completeness for conversations. Progressive disclosure: simple documents generate fewer vectors.

**Hierarchical Metadata** - Dual section tracking: section_type (H2 parent like "Decisions") and section_name (H3 title). Preserves document hierarchy in metadata. Enables parent-aware filtering and context reconstruction. Header paths provide full navigation breadcrumb.

**Structured Field Detection** - Parses template fields (Context, Solution, Rationale, Alternatives). Stores boolean flags in metadata for rich filtering. Enables queries like "find decisions with alternatives considered". Supports quality assessment through field completeness.

**Named Vectors Architecture** - Collections support multiple embedding models simultaneously. Each vector stored with model name (e.g., "e5-large-v2"). Search specifies which model to query. Future-proof for model upgrades and A/B testing.

**Batch Processing** - Encodes all sections in single model call (2x faster than sequential). Upserts multiple vectors in batch mode (10x faster than individual). Minimizes network roundtrips and model invocations. Registry updated with chunk count from indexing result (not input file/conversation count) for accurate corpus metrics.

**Metadata-Rich Payloads** - Each vector includes 23 metadata fields (schema_version v1.0: phase, layer, section_type, section_name, section_level, timestamps, structured field flags, word_count, char_count, etc.). Enables SQL-like filtering before semantic search. Supports sorting, grouping, and aggregation operations.

**Bidirectional Linking** - Changelogs link to conversations via session_id in frontmatter. Conversations link to changelogs via has_changelog and changelog_path metadata. Enables tracing decisions to originating discussions.

**Compositional Primitives Architecture** - Four orthogonal discovery functions (siblings, genealogy, temporal, cross_phase) compose flexibly via declarative config. Each primitive accepts optional parameters (section_types, order_by, limit, has_rationale, has_alternatives) while maintaining backward compatibility with boolean flags. Dict-based config enables surgical retrieval ("top 3 Patterns with rationale") instead of all-or-nothing queries. Compose orchestrator handles any combination without cross-dependencies between primitives.

**Observable Usage Pattern** - System tracks composition patterns by hashing discovery config and logging usage. Detects recurring patterns at thresholds (10/15/20/30 uses) and suggests preset creation as slash commands. Enables self-improving system where preset library grows organically from proven patterns. Narrative reconstruction (genealogy + siblings + temporal) represents one discovered pattern among many possible compositions.

**Graph-Informed Templates** - Templates selected and structured based on graph properties. High PageRank + temporal chain triggers evolution template. Many failures trigger anti-pattern template. Genealogical position embedded in presentation structure via visual indicators (🟢 current thrust, ⚠️ evolved, ❌ failed) and section ordering (Failures first). Structure conveys relationships for AI comprehension rather than expecting inference from raw content.

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
# Index current project (auto-creates dual collections)
cd ~/my-project
imem init

# Force re-index (recreates from scratch)
imem init --force
```

**Unified Search Commands**
```bash
# Search with source as positional argument
imem search develop "authentication"
imem search conversations "bug fix"
imem search context "pattern"  # All context sources

# With section filters
imem search develop "database" --decisions
imem search develop "error handling" --patterns

# With session filter
imem search conversations "implementation" --session abc12345

# Search pattern layer only
imem search develop "error handling" --pattern
```

**Collection Lifecycle**
```bash
# List registered and orphaned collections
imem collections list

# Clean orphaned collections
imem collections clean --dry-run
imem collections clean
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

**Compositional Retrieval (FlexGraph)**
```bash
# Basic composition with siblings
imem compose '{"search": {"text": "JWT auth"}, "discovery": {"siblings": true}}'

# Parameterized primitive filtering
imem compose '{"search": {"text": "error handling"}, "discovery": {"siblings": {"section_types": ["Failures"], "limit": 3, "has_rationale": true}}}'

# Narrative reconstruction pattern
imem compose '{"search": {"text": "authentication"}, "discovery": {"genealogy": true, "siblings": {"section_types": ["Patterns", "Decisions"]}, "temporal": {"direction": "after"}}, "output": {"template": "story-context"}}'

# Timeline evolution pattern
imem compose '{"search": {"text": "API design"}, "discovery": {"temporal": {"direction": "both"}}, "output": {"template": "timeline"}}'

# Anti-pattern discovery
imem compose '{"search": {"text": "retry logic"}, "discovery": {"siblings": {"section_types": ["Failures"], "order_by": "timestamp"}}}'
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
