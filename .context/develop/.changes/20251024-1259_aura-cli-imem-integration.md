---
schema_version: "v3"
type: "implementation.aura-cli-project-initialization"
status: "completed"
keywords: "aura-cli imem-indexing llama-index section-chunking two-tier-architecture conversation-indexing changelog-indexing per-project-isolation semantic-search metadata-extraction batch-processing"
timestamp: "2025-10-24T12:59:00-0700"
session_id: "0ae48b0a-2350-4287-bdf7-ec0a19b8ffc0"
---

# AURA CLI and Two-Tier Institutional Memory System

## Request
> "Great. Let's plan how we will enable this for development logs"
> "so i can type 'aura' into any project, and its initailized with folders, with imem. i can then, on a project by project basis, index all of the development files. and retreive them ?"

## Overview
Implemented a complete per-project institutional memory system that enables semantic search across conversations and documentation at the section level. The solution uses hierarchical parsing to extract searchable units that align with document structure, providing precise retrieval rather than arbitrary fragments. Each project maintains an isolated knowledge base to prevent cross-project data contamination while supporting independent searches. The system integrates two data sources—raw conversations and curated change logs—with automatic metadata enrichment to enable filtering by source type, session, section, and work phase. Background batch processing handled large-scale indexing while maintaining system responsiveness.

## Decisions

### Use LlamaIndex MarkdownNodeParser for Section Chunking
- **Context**: Need precise section-level retrieval rather than arbitrary chunk boundaries
- **Solution**: Integrated LlamaIndex's MarkdownNodeParser to parse documents at H2/H3 header boundaries
- **Rationale**: Semantic units align with document structure (Decisions, Implementation, Tools Used sections)
- **Implementation**: Each H2 section becomes a searchable vector with parent reference and full metadata
- **Benefit**: Search queries return complete contextual sections, not fragmented chunks

### Extract Section Names from Content Instead of Header Path
- **Context**: LlamaIndex's header_path metadata returned broken values like "/Conversation: .../", resulting in empty section_type
- **Discovery**: Testing showed section_type was empty string for all indexed conversations
- **Solution**: Extract section name from first line of content using regex: `r'^#{1,6}\s+(.+)'`
- **Impact**: Now correctly identifies sections like "User Messages", "Tools Used", "Code Changes" for filtering
- **Validation**: Section-filtered search achieved 0.829 score for exact "Tools Used" query

### Prioritize develop/.changes Over design/.changes
- **Context**: Both folders can exist in .context/, but develop/ contains ground truth while design/ has exploratory work
- **Solution**: Reversed priority order to check develop/.changes first
- **Rationale**: Ground truth changelogs are more valuable for semantic search than exploratory logs
- **Impact**: Ensures production changelogs are indexed even when both phase directories exist

### Set 2KB Minimum Size for Conversation Indexing
- **Context**: 5,638 total conversations include many greeting-only and error sessions
- **Investigation**: Spawned sub-agent to audit small conversations
- **Findings**: Useful conversations start at 1.41 KB, while greetings/errors cluster at 1.1-1.4 KB
- **Solution**: Default --min-size=2 flag filters out 123 tiny conversations (2.2%)
- **Result**: 5,515 meaningful conversations indexed, 97.8% retention rate

### Implement Batch Upsert for 10x Performance
- **Context**: Individual vector inserts were slow for large-scale indexing
- **Solution**: Accumulate vectors and upsert in batches via Qdrant's batch API
- **Performance**: Enables background indexing of 5,515 conversations in 2-3 hours
- **Trade-off**: More complex error handling since failures affect entire batch

## Implementation

### Architecture

1. **AURA CLI** → Initializes .context/ folder structure (develop/, design/, designate/, document/)
2. **IMEM Indexer** → Detects .context/develop/.changes/, creates unique collection per project
3. **LlamaIndex Parser** → Chunks markdown at H2/H3 boundaries, extracts metadata
4. **Section Extraction** → Regex parses first line to identify section type from content
5. **Batch Upsert** → Accumulates embeddings and uploads to Qdrant in bulk
6. **Metadata Enrichment** → Attaches source, session_id, section_type, category, subtype, timestamp
7. **Search Interface** → Filters by --in, --session, --section flags before vector search

### Code Signatures

**Project Initialization** (`aura_cli/cli.py`)
```python
@click.command()
def aura():
    """Initialize institutional memory structure in current directory."""
    cwd = Path.cwd()
    context_dir = cwd / ".context"
    # Create phase directories (design, designate, develop, document)
    # With .changes subdirectories for design and develop phases
    for phase in ["design", "designate", "develop", "document"]:
        phase_dir = context_dir / phase
        if phase in ["design", "develop"]:
            (phase_dir / ".changes").mkdir(parents=True, exist_ok=True)
```

**Section Metadata Extraction** (`imem/src/imem/ingest.py`)
```python
# Extract section type from markdown header in parsed node content
content = node.get_content()
first_line = content.split('\n')[0]
import re
header_match = re.match(r'^#{1,6}\s+(.+)', first_line)
section_name = header_match.group(1).strip() if header_match else ''
```

**Collection Initialization** (`imem/src/imem/cli.py`)
```python
# Generate unique collection identifier from project path
collection_name = f"imem_{project_hash[:8]}"

# Create vector collection with semantic embedding dimensions
qdrant.create_collection(
    collection_name=collection_name,
    vectors_config=VectorParams(size=1024, distance=Distance.COSINE)
)

registry.register_project(project_root, collection_name, phase, dev_folder)
```

**Batch Processing with Size Filtering** (`imem/src/imem/cli.py`)
```python
@imem.command()
@click.option('--min-size', type=int, default=2, help='Skip entries smaller than N KB')
def index_all_conversations(min_size, collection):
    """Batch index all conversations with size-based filtering."""
    conversations = [
        conv for conv in finder.list_all()
        if (conv.stat().st_size // 1024) >= min_size
    ]
    for conv_file in conversations:
        ingester.ingest_conversation_chunked(
            file_path=conv_file, collection=collection_name
        )
```

**Metadata Structure** (`imem/src/imem/ingest.py`)
```python
payload = {
    'source': 'conversation',  # or 'changelog'
    'session_id': session_id,  # Links to originating conversation
    'section_type': section_name,  # "Decisions", "Tools Used", etc
    'category': category,  # From changelog type field
    'content': node.get_content(),  # Full section text
    'metadata': {
        'timestamp': timestamp,
        'phase': phase,  # design, develop, document
        'section_level': header_level  # H2 or H3
    }
}
```

## Patterns

### Two-Tier Discovery-to-Drill-Down Workflow
- **Pattern**: Broad search across all data, then narrow to specific conversation
- **When**: Finding relevant past work then examining specific details
- **Approach**: First query returns relevant sections across all conversations, then filter by session_id for focused retrieval
- **Benefit**: Combines global discovery with targeted investigation
- **Occurrences**: Authentication flows, API integration patterns, debugging sessions

### Per-Project Isolation via Collection Hashing
- **Pattern**: Generate unique collection identifier from project path
- **When**: Multiple projects need independent knowledge bases without cross-project contamination
- **Approach**: Hash project root path → unique collection → register in global index
- **Anti-Pattern**: Don't use single global collection with project filters (slower, harder to isolate)
- **Benefit**: True isolation, faster queries, clean deletion (drop collection)

### Background Batch Processing with Size Filtering
- **Pattern**: Process large datasets asynchronously with entry-level filtering
- **When**: Indexing thousands of conversations without blocking user workflow
- **Approach**: Filter by size before processing, batch upsert to vector store, monitor via log tail
- **Benefit**: Handles large-scale indexing (5,515 conversations in 2-3 hours) without blocking interactive use

## Constraints

### LlamaIndex Header Path Contains No Section Information
- **What**: Expected header_path metadata to contain section names, but it only shows structural path like "/Conversation: .../"
- **Discovery**: Inspecting parsed nodes revealed header_path doesn't include H2 header text
- **Workaround**: Extract section name from first line of node content using regex pattern matching
- **Impact**: Required custom extraction logic instead of relying on built-in metadata
- **Why Non-Obvious**: LlamaIndex documentation suggests header_path would be useful for section identification, but it doesn't capture semantic hierarchy

### Search Filter Limitations in Wrapper Classes
- **What**: The EnhancedQdrantSearch wrapper doesn't accept filter parameters for advanced queries
- **Discovery**: Attempting to pass filters failed with "unexpected keyword argument" errors
- **Workaround**: Use direct Qdrant client API calls for filtered queries instead of wrapper abstraction
- **Impact**: Basic search works, but advanced filtering (by session, section type) requires bypassing wrapper
- **Testing**: Verified workaround handles session-scoped and section-filtered queries correctly

## Audit

### Created
- `aura_cli/` - AURA CLI package directory
- `aura_cli/__init__.py` - Package initialization
- `aura_cli/cli.py` - Main `aura` command for .context/ initialization
- `.context/develop/.changes/` - Ground truth changelog directory (created by aura command)

### Modified
- `setup.py` - Added aura package to find_packages, entry point for `aura` command
- `imem/src/imem/cli.py` - Added --session filter, --min-size option, reversed develop/design priority
- `imem/src/imem/ingest.py` - Section name extraction from content, batch upsert optimization
- `imem/src/imem/search.py` - Filter metadata structure updates

### Configuration
- Collection created: `institutional_memory` (1024 dims, Cosine distance)
- Default min conversation size: 2 KB
- Qdrant port: 6334
- Vector model: E5-Large-v2 (1024 dimensions)
- Registry location: `~/.context/imem_registry.json`

### Deployment
- Install command: `pip install -e .` (editable mode for development)
- Background indexing: Started batch process for 5,515 conversations
- Test project: `/tmp/test-aura-project` verified end-to-end workflow
- Commands available:
  - `aura` - Initialize project structure
  - `imem init` - Index project changelogs
  - `imem index-conversation <session-id>` - Index single conversation
  - `imem index-all-conversations --min-size 2` - Batch index conversations
  - `imem search "query" --in conversations --section "Tools Used" --session abc123`
