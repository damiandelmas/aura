# imem Architecture

## System Overview

imem is a vector search system for institutional memory that transforms development documentation into searchable knowledge bases. It's designed specifically for AI-augmented development, preserving strategic context (WHY) rather than technical tutorials (HOW).

## Core Architecture Layers

```
┌─────────────────────────────────────────────────────────────┐
│                    CLI Interface Layer                       │
│  (Click-based commands: init, search, trace, pulse, watcher) │
└─────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────┐
│                   Core Business Logic                        │
│  • ProjectRegistry (multi-project tracking)                  │
│  • QdrantService (Docker lifecycle)                          │
│  • MetadataValidator (YAML validation)                       │
│  • FileWatcher (auto-sync on file changes)                   │
└─────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────┐
│                Search & Retrieval Engine                     │
│  • EnhancedQdrantSearch (semantic + temporal search)         │
│  • ModularIngest (document processing & vectorization)       │
│  • E5-Large-v2 embeddings (1024 dimensions)                  │
└─────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────┐
│                    Storage Layer                             │
│  • Qdrant (vector database, port 6334)                       │
│  • Per-project collections (memory_<hash>)                   │
│  • Global registry (~/.imem/registry.json)                   │
└─────────────────────────────────────────────────────────────┘
```

## Key Architectural Decisions

### 1. Git Repository Boundaries

**Decision:** Use git repos as natural project boundaries

```python
# Project detection
def get_project_root() -> Path:
    current = Path.cwd()
    while current != current.parent:
        if (current / '.git').exists():
            return current
        current = current.parent
```

**Why:**
- Developers already understand git repos as project units
- No config files needed
- Prevents cross-project contamination

**Collection naming:** `memory_<md5_hash_of_path>[:8]`

### 2. Dual Directory Structure

```
.imem/
├── .snapshot/     # Stable strategic documentation
│   └── ARCHITECTURE.md, DATA_FLOW.md, etc.
└── .changes/      # Temporal implementation logs
    └── 2025-09-20-trace-improvements.md
```

**Business Driver:** Separate "what exists" from "what happened and why"

**Benefits:**
- AI agents understand context evolution over time
- Preserves decision rationale alongside current state
- Temporal search (hybrid scoring: 0.6 similarity + 0.4 recency)

### 3. Single Global Qdrant Instance

**Decision:** One Docker container (port 6334) for all projects

**Storage:**
```yaml
# ~/.imem/docker-compose.yml
services:
  qdrant:
    image: qdrant/qdrant:latest
    ports: ["6334:6333"]
    volumes: ["~/.imem/qdrant_storage:/qdrant/storage"]
```

**Why:**
- Reduce resource consumption (vs per-project instances)
- Simplify service management
- Project isolation via separate collections, not instances

**Trade-off:** Single point of failure (acceptable for local dev)

### 4. Relative Path Storage

**Critical Constraint Discovered:** Absolute paths broke when projects moved between machines

**Solution:**
```python
# Store relative to project root
file_path = ".imem/.snapshot/ARCHITECTURE.md"  # ✅
# NOT: /home/axp/projects/foo/.imem/.snapshot/ARCHITECTURE.md  # ❌
```

**Impact:** System can index its own documentation without confusion

### 5. E5-Large-v2 as Primary Model

**Decision:** Standardize on intfloat/e5-large-v2 (1024 dimensions)

**Performance Trade-off:**
- 500MB model download
- 2x slower than MiniLM
- 64% accuracy improvement (worth it)

**Failed Experiment:** CodeBERT performed worse for mixed technical/business docs

## Component Deep Dive

### Project Registry (core/registry.py)

**Purpose:** Track all indexed projects globally

```json
# ~/.imem/registry.json
{
  "projects": {
    "/path/to/project": {
      "collection": "memory_a3f2d8c1",
      "project_id": "a3f2d8c1",
      "indexed_at": "2025-09-11T23:00:00",
      "doc_count": 245,
      "imem_path": "/path/to/project/.imem"
    }
  }
}
```

**Key Methods:**
- `get_project_root()` - Git repo detection
- `get_collection_name()` - MD5-based naming
- `register_project()` - Add/update registry

### Qdrant Service (core/service.py)

**Purpose:** Docker lifecycle management

**Key Operations:**
```python
service = QdrantService()
service.start()      # docker compose up
service.stop()       # docker compose down
service.is_running() # Health check on port 6334
```

**Configuration:** Auto-generates docker-compose.yml at ~/.imem/

### Enhanced Search (search/enhanced_search.py)

**Architecture:**
```python
class EnhancedQdrantSearch:
    def search(query, limit=5, sort_by='similarity'):
        # 1. Generate query embedding
        vector = model.encode(query)

        # 2. Vector similarity search
        results = client.search(
            collection_name=collection,
            query_vector=vector,
            limit=limit
        )

        # 3. Extract YAML frontmatter
        for result in results:
            metadata = extract_yaml_frontmatter(result.content)

        # 4. Temporal sorting (if requested)
        if sort_by == 'hybrid':
            score = 0.6 * similarity + 0.4 * recency

        return sorted_results
```

**Search Modes:**
- `similarity`: Pure cosine similarity
- `date`: Chronological (newest first)
- `hybrid`: Combined similarity + recency

**Timestamp Support:** 6 different date formats

### Modular Ingest (search/modular_ingest.py)

**Ingestion Pipeline:**
```
1. File Discovery
   ↓ Scan .imem/.snapshot/ and .imem/.changes/

2. Deduplication Check
   ↓ Path-based + MD5 hash-based

3. Text Processing
   ↓ Multi-encoding (utf-8, latin-1, cp1252)

4. Metadata Validation
   ↓ YAML frontmatter schema checks

5. Vector Generation
   ↓ E5-Large-v2 embeddings

6. Batch Upload
   ↓ 100 docs/batch → Qdrant

7. Registry Update
   ↓ Track doc count, timestamp
```

**Intelligent Deduplication:**
```python
# Content-based detection
content_hash = hashlib.md5(content.encode()).hexdigest()

if file_path in existing_paths:
    skip  # Same path
elif content_hash in existing_hashes:
    update_path(old_path → new_path)  # File moved
else:
    create_new_point()  # New content
```

### File Watcher (core/watcher.py)

**Purpose:** Real-time auto-sync on file changes

```python
# Watches .imem/.changes/*.md
from watchdog.observers import Observer

class ChangelogHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith('.md'):
            # Trigger: imem pulse <filename>
            subprocess.run(['imem', 'pulse', filename])
```

**Features:**
- 30-second cooldown between syncs
- VS Code temp file filtering (.tmp.)
- Per-project lock files: `~/.imem/watcher_<project_hash>.lock`
- Extended timeout (5 minutes for AI processing)

## Data Flow: End-to-End

### Indexing Flow

```
User: imem init
  ↓
ProjectRegistry.get_project_root()
  ↓ Detect git repo boundary
QdrantService.ensure_running()
  ↓ Start Docker if needed
ModularIngest.scan_directories()
  ↓ Find all .md files in .imem/
ModularIngest.filter_new_files()
  ↓ Check existing_paths + content_hashes
MetadataValidator.validate_document()
  ↓ Parse YAML frontmatter
SentenceTransformer.encode()
  ↓ Generate 1024D vectors
QdrantClient.upsert()
  ↓ Batch upload (100/batch)
ProjectRegistry.register_project()
  ↓ Update ~/.imem/registry.json
```

### Search Flow

```
User: imem search "vector database"
  ↓
ProjectRegistry.get_collection_name()
  ↓ Identify current project collection
QdrantService.is_running()
  ↓ Health check
SentenceTransformer.encode(query)
  ↓ Generate query vector
QdrantClient.search()
  ↓ Cosine similarity search
EnhancedQdrantSearch.extract_yaml_frontmatter()
  ↓ Parse metadata from results
EnhancedQdrantSearch.apply_temporal_sorting()
  ↓ If hybrid mode: 0.6*sim + 0.4*recency
Display formatted results
```

## Advanced Features

### TRACE (Conversation Archaeology)

**Purpose:** Retrieve past Claude Code conversations

```bash
imem trace --bookmark a3f7c2b1 --conversation
```

**Architecture:**
```python
# ~/.claude/projects/<project>/conversations.jsonl
# Parse JSONL → Extract messages → Filter tool noise → Return dialogue

class ConversationRetriever:
    def get_conversation(bookmark):
        # 1. Find JSONL file by bookmark hash
        # 2. Parse messages
        # 3. Extract USER ↔ ASSISTANT only
        # 4. Return clean conversation
```

**Key Insight:** Preserve institutional memory of AI sessions themselves

### Pulse (AI-Powered Sync)

**Purpose:** Spawn peer Claude agent to update docs from changelogs

```python
# sync/sync.py
def invoke_claude_for_sync(changelog_path):
    system_prompt = f"""
    You are an institutional memory curator with equal intelligence.
    Extract strategic context from this changelog:
    - Business rationale for decisions
    - Discovered constraints
    - Failed experiments

    Update documentation to preserve WHY, not HOW.
    """

    result = subprocess.run(
        ["claude", "-p"],  # NO --permission-mode flag (hangs!)
        input=system_prompt,
        timeout=120  # 2 minutes for AI processing
    )
```

**Critical Constraint:** `--permission-mode bypassPermissions` causes indefinite hanging

**Equal Intelligence Pattern:** Treat spawned Claude as peer curator, not documentation bot

## Storage Architecture

### Global Storage (~/.imem/)

```
~/.imem/
├── docker-compose.yml          # Qdrant service config
├── registry.json               # Project registry
├── qdrant_storage/             # Vector database files
│   └── collections/
│       ├── memory_a3f2d8c1/   # Project 1
│       └── memory_f8e1c4a0/   # Project 2
└── watcher_a3f2d8c1.lock      # Per-project watcher locks
```

### Project Storage (.imem/)

```
project_root/
├── .git/                       # Required for project detection
├── .imem/
│   ├── .snapshot/              # Stable docs
│   │   ├── ARCHITECTURE.md
│   │   ├── DATA_FLOW.md
│   │   └── USER_GUIDE.md
│   └── .changes/               # Temporal docs
│       ├── 2025-09-20-feature-x.md
│       └── 2025-09-21-bugfix-y.md
└── src/                        # Source code
```

### Vector Storage Format

```python
# Qdrant point structure
{
    "id": 42,
    "vector": [0.123, -0.456, ...],  # 1024 dimensions
    "payload": {
        "information": "Full document text...",
        "file_path": ".imem/.snapshot/ARCHITECTURE.md",  # Relative!
        "config_name": "current",
        "model_name": "intfloat/e5-large-v2",
        "ingestion_timestamp": "2025-09-20T11:00:00",
        "file_hash": "a3f2d8c1..."  # MD5 for dedup
    }
}
```

## Performance Characteristics

- **Indexing:** ~100 documents/second
- **Search:** <2 seconds typical response
- **Storage:** ~500MB per 10,000 documents
- **Accuracy:** 64% improvement over MiniLM baseline
- **Model Cache:** 500MB (E5-Large-v2)

## Equal Intelligence Paradigm (v2.0)

**Core Insight:** Future Claude Code agents can read code. They need:
- ❌ NOT: "How to implement X" (derivable from code)
- ✅ YES: "Why we chose X" (non-derivable context)

**Documentation Transformation:**
```yaml
# Old (technical tutorial)
---
title: "How to Use Qdrant"
---
## Installation
pip install qdrant-client

## Usage
client = QdrantClient(...)

# New (strategic context)
---
title: "Qdrant Choice Rationale"
business_driver: "Local-first, no API costs"
discovered_constraint: "Port 6333 conflicted with internal tool"
failed_experiment: "Tried Pinecone but latency unacceptable"
---
```

**Impact:** 69% documentation reduction, 100% strategic value preservation

## Multi-Tenancy Design

**Project Isolation:**
- Unique collection per git repo
- No cross-project data leakage
- Independent indexing/searching

**Resource Sharing:**
- Single Qdrant instance
- Shared embedding model (cached)
- Common storage location
- Unified registry

## Extension Points

### v1.1 - Chunking (Planned)
- Parallel `chunks_<hash>` collections
- 450-token chunks with 50-token overlap

### v1.2 - Multi-Format (Planned)
- Code file support (.py, .js, .ts)
- Docstring extraction

### v1.3 - Smart Metadata (Planned)
- Git integration (commit history)
- Auto-tagging

## Security Considerations

- Local-only (localhost:6334)
- No authentication (planned for v2)
- File system permissions respected
- No external API calls

## Key Takeaways

1. **Git-native:** Project boundaries via repos
2. **Temporal awareness:** .snapshot/ vs .changes/
3. **AI-first:** Docs for AI agents, not humans
4. **Strategic focus:** WHY over HOW
5. **Self-referential:** Can index its own documentation
6. **Conversation archaeology:** TRACE retrieves past AI sessions
7. **Equal intelligence:** Spawned Claude agents are peers, not bots

This architecture enables institutional memory preservation optimized for AI-augmented development workflows.
