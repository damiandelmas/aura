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

**cli.py** - Unified command interface with source-based routing. Primary commands: `imem index <source>`, `imem search <source> "query"`, `imem compose <config>`, `imem introspect`. Sources: develop, design, document, conversations, context. Handles project detection by locating `.git/` directory and `.context/` structure. Creates dual collections (context + conversation) using `imem_<hash>_{context|conversation}` naming convention. Dynamic collection routing via config 'source' field. Preset loading with sigil notation (@lineage, @decisions, @failures, @synthesize, @timeline) performs template variable substitution before execution. Collection lifecycle management via `imem collections list/clean` commands.

**ingest.py** - Document indexing engine with content-aware filtering. Parses markdown files using LlamaIndex MarkdownNodeParser, chunks content at H3-level for changelogs and H2-level for conversations. Content-length filter (<20 chars) skips empty H2 parent headers while indexing substantive sections. Implements batch encoding for performance (2x faster than sequential). Extracts section metadata, detects structured fields (has_context, has_solution, etc.), and performs batch upserts to Qdrant. Generates Nomic Embed v1.5 embeddings (768 dimensions, 8k tokens) with auto-detection fallback for E5-Large-v2 legacy collections. Tracks chunk counts (not conversation counts) for accurate registry metrics.

**search.py** - Modular search engine architecture. Supports multiple embedding models through SearchConfig dataclass. Currently implements E5-Large-v2 with provisions for future models (MiniLM, BGE). Provides vector name specification for multi-model collections.

**enhanced.py** - High-level search interface. Implements metadata filtering (phase, section, session), timestamp extraction from frontmatter, hybrid scoring (semantic + recency), and multi-term search operators (AND/OR). Provides unified search method with filter composition and result sorting.

**primitives/discovery.py** - Compositional discovery primitives layer. Four orthogonal functions (get_siblings, get_genealogy, get_temporal, get_cross_phase) that retrieve related chunks based on metadata predicates. Each primitive accepts parameterized filters (section_types, order_by, limit, has_rationale, has_alternatives) for surgical retrieval. Backward compatible with boolean config (converts to dict internally). None-safe sorting handles null values in metadata fields (section_level, timestamp). Pure functions with no cross-dependencies enable flexible composition.

**Discovery Thresholds**: Temporal similarity threshold set to 0.65 (lowered from 0.85) to match typical cross-time evolution scores (0.6-0.7 range). Genealogy uses cross-collection routing via base name extraction (`split('_context')[0]`) to correctly route from context collections to conversation collections.

**compose.py** - Compositional orchestrator with intelligent multi-source routing. Executes parallel multi-query pipeline with per-query collection routing from declarative JSON config. Accepts registry and project_root parameters for source detection. Routes each query independently based on `filters.source` field (conversation vs context collections). Strips source filter before database query (routing hint, not filter). Aggregates results from multiple sources with automatic deduplication. Implements result filtering to return clean JSON output (~10 fields: id, score, source, chunk_type, content, metadata) instead of noise-filled payloads (35+ fields with session stats, unvalidated flags). Enables single-call multi-source retrieval with complete intent expression.

**Thread Safety**: Uses per-thread encoder instances by passing `None` to parallel tasks, letting workers create thread-local SentenceTransformer instances. Prevents tensor size mismatch exceptions from shared encoder state across threads.

**Collection Routing**: Context collections require `_impl` suffix appended after registry lookup. Per-query routing extracts base collection then adds suffix for context sources, while conversation sources use collection name directly.

**introspect.py** - System capability discovery for AI onboarding. Implements three progressive disclosure levels: default (system primitives + landscape for onboarding), map (complete concept topology with mention frequencies), status (coverage statistics only). Provides live schema discovery by sampling collection points and aggregating metadata field types and enum values. Enumerates project ontology (types, phases, sessions, files) for context awareness. Returns JSON schema enabling zero-documentation AI agent onboarding where agents construct valid queries autonomously.

**presets/** - Declarative workflow templates wrapping parallel multi-query execution. Five built-in presets: `lineage.json` (multi-phase artifact archaeology with 3 conversation + 3 context queries), `decisions.json` (design phase rationale), `failures.json` (develop phase constraints and anti-patterns), `synthesize.json` (cross-chunk topic aggregation), `timeline.json` (temporal concept evolution). Templates support variable substitution ({{artifact}}, {{topic}}, {{concept}}) and per-query source routing for cross-collection composition. Automatic deduplication ensures unique results across sources.

**qdrant_service.py** - Docker lifecycle management for Qdrant container. Manages container lifecycle (start, stop, status, ensure_running). Configures Qdrant image with port mapping (6334 external to 6333 internal), volume mounting (`~/.context/qdrant_storage/`), and container naming (`imem_qdrant`).

## Data Flow

**Initialization Layer** - User invokes `imem init` from project directory. System detects project root by locating `.git/` directory. Finds `.context/develop/` or `.context/design/` structure. Creates dual collections using MD5 hash: `imem_<hash>_context` and `imem_<hash>_conversation`. Registers both collections in `~/.context/imem_registry.json` with separate doc_counts. Auto-creates collections on first use (no --force needed for initial run).

**Indexing Layer (Changelogs)** - System scans `.context/{design,designate,develop,document}/*.md` files. For each file: reads content and extracts frontmatter, parses with LlamaIndex MarkdownNodeParser to generate H3-level chunks, applies content-length filter (<20 chars) to skip empty H2 parent headers, extracts section names from headers, generates Nomic Embed v1.5 embeddings in batch mode (with E5 fallback for legacy collections), builds payload with rich metadata (phase, layer, section_type, section_name, structured field flags including has_rationale, has_alternatives), performs batch upsert to Qdrant with named vectors. Updates registry with chunk count (not file count) for accurate corpus metrics. Routes to context collection by default.

**Indexing Layer (Conversations)** - User invokes `imem index-all-conversations`. TRACE finds conversation files and exports structured markdown with H2 sections. System saves to temporary file, parses with LlamaIndex at H2-level, extracts section names (User Messages, Code Changes, Tools Used), generates embeddings, builds payload with session_id, performs batch upsert. Deletes temporary file.

**Search Layer** - User submits `imem search <source> "query"` with optional filters (phase, section_type, session_id). System determines collection type from source (develop/design/document → context, conversations → conversation). Loads correct collection from registry via `get_collection_by_type()`. Auto-detects embedding model from collection vector config (Nomic or E5). Builds Qdrant filter using FieldCondition and Filter objects. Embeds query with detected model. Executes vector search with metadata filtering. Returns top K results sorted by similarity score.

**Compositional Layer (Multi-Source)** - User invokes `imem compose <config>` or `imem compose '@preset' variable="value"` with declarative config. Preset invocation loads JSON template, performs variable substitution ({{artifact}} → value), returns expanded config. System receives registry and project_root context for collection routing. Executes parallel multi-query pipeline with thread-safe encoder instantiation: (1) For each query, inspect `filters.source` field, (2) Route to conversation or context collection, appending `_impl` suffix for context sources, (3) Strip source filter before database query (metadata-only routing hint), (4) Create per-thread encoder instance to prevent shared state corruption, (5) Execute semantic search with remaining filters, (6) Aggregate results from multiple sources in order received, (7) Apply recursive result filtering to keep high-signal fields (id, score, source, chunk_type, content, metadata) and strip noise from both primary results and discovery data (siblings, temporal, genealogy), (8) Automatic deduplication ensures unique results across collections. Returns clean JSON (~10 fields) or structured output optimized for AI consumption.

**Output Layer** - Search results flow to terminal with formatted display. Each result includes section content, metadata (phase, section type, file path), similarity score, and contextual information (parent headers, structured fields present). Compose results return clean JSON with filtered fields for AI consumption. Introspect command outputs progressive disclosure views (default/map/status) as JSON for programmatic capability discovery.

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

**Multi-Source Routing Architecture** - Per-query source filter acts as collection routing hint stripped before database execution. Composition layer accepts registry and project_root parameters enabling source detection. Search executor inspects each query's `filters.source` field and routes to appropriate collection (conversation vs context). Source filter removed before building vector query to prevent filter mismatch errors. Enables declarative cross-collection queries where single preset invocation aggregates results from multiple sources with automatic deduplication.

**Direct JSON Composition** - System exposes primitives (siblings, genealogy, temporal, cross_phase) and compose JSON interface for flexible query orchestration. Users and AI agents compose queries manually using declarative JSON config. Patterns emerge through usage rather than premature codification. Examples: `imem compose '{"search": {"text": "auth", "limit": 5}}'` for simple queries, `imem compose '{"source": "conversations", "search": {"text": "bug", "limit": 3}, "discovery": {"genealogy": true}}'` for cross-source enrichment, multi-query with siblings via queries array. Discovery-driven approach preferred over premature abstraction.

**Discovery-Driven Assembly** - System provides raw retrieval primitives and clean JSON output without imposing assembly patterns. Removed template rendering infrastructure (story-context.j2, genealogy.j2, timeline.j2) that made unvalidated claims about temporal position and context validity. Honest empty JSON preferred over confident falsehoods. AI agents experiment with different assembly strategies, successful patterns extracted from experiments, then codified as presets. Experimentation surfaces context-specific insights before pattern codification.

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
imem search develop "database" --section "Decisions"
imem search develop "error handling" --section "Patterns"

# With session filter
imem search conversations "implementation" --session abc12345

# Search pattern layer only
imem search develop "error handling" --layer pattern
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

**Compositional Retrieval (Direct JSON)**
```bash
# Simple search
imem compose '{"search": {"text": "authentication", "limit": 5}}'

# Conversations with discovery
imem compose '{"source": "conversations", "search": {"text": "bug", "limit": 3}, "discovery": {"genealogy": true}}'

# Multi-query with siblings
imem compose '{"search": {"queries": [{"text": "JWT", "filters": {"phase": "develop"}}, {"text": "JWT", "filters": {"phase": "document"}}]}, "discovery": {"siblings": {"limit": 3}}}'

# Cross-phase with temporal discovery
imem compose '{"search": {"text": "routing", "filters": {"phase": "develop"}}, "discovery": {"temporal": true, "siblings": true}}'

# System introspection (AI onboarding)
imem introspect                    # Default: system primitives + landscape
imem introspect --map              # Complete concept topology
imem introspect --status           # Coverage statistics only
imem introspect --entities         # Enumerate types, phases, sessions, files
imem introspect --fields           # Available filter fields and types
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
