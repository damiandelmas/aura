---
schema_version: "v3_adaptive"
type: "architecture.ecosystem"
status: "stable"
keywords: "aura institutional-memory microservices ecosystem per-project"
timestamp: "2025-10-23T20:45:00-0700"
---

# AURA Ecosystem Architecture

## System Overview

AURA is a three-microservice institutional memory ecosystem designed for per-project knowledge curation and retrieval. Each component operates independently but composes naturally through file-based coordination.

**Location**: `/home/axp/projects/fleet/hangar/code/aura/main/`

---

## The Three Microservices

### 1. IMEM - Vector Search & Retrieval
**Purpose**: Section-level semantic search across changelogs and conversations with compositional discovery primitives
**CLI**: `imem`
**Details**: See [architecture_imem-i2.md](./architecture_imem-i2.md)

**Core Capability**: Retrieval-only mode with LlamaIndex pipeline, H3/H2-section chunking via MarkdownNodeParser, E5-Large-v2 embeddings, returns top-k ranked sections. FlexGraph compositional system enables flexible primitive composition (siblings, genealogy, temporal, cross_phase) via declarative JSON for surgical knowledge retrieval with context-aware template rendering.

### 2. TRACE - Conversation Archaeology
**Purpose**: Parse and query Claude Code conversation history
**CLI**: `trace`
**Details**: See [architecture_trace-i2.md](./architecture_trace-i2.md)

**Core Capability**: Find conversations globally via semantic verb-noun commands, export H2-section chronicle markdown, provide chronologically merged messages + patches for vector indexing.

### 3. Qdrant - Vector Database Manager
**Purpose**: Docker lifecycle management for Qdrant vector database
**Library**: Python API only (no CLI)

**Core Capability**: Start/stop Qdrant container, manage port binding (6334), persist vectors to `~/.context/qdrant_storage/`.

---

## Quick Start Workflow

### Initialize Any Project
```bash
cd ~/my-project
aura                    # Create .context/ structure
imem init               # Index changelogs
```

### Search Your Knowledge
```bash
# Phase-based search
imem develop search "authentication" --decisions
imem search "decisions" --section "Decisions"
imem search "context" --session abc123

# Compositional retrieval (FlexGraph)
imem compose '{"search": {"text": "JWT"}, "discovery": {"siblings": true, "genealogy": true}}'
```

### Query Conversations
```bash
trace list                          # Browse all conversations
trace show chronicle abc123         # Full chronological timeline
trace export chronicle abc123 -o context.md  # Export for agents
```

---

## Directory Structure

```
aura/main/
├── venv/                      # Shared virtual environment
├── aura_cli/                  # AURA initialization command
│   └── cli.py
├── imem/
│   ├── src/imem/
│   └── setup.py
├── trace/
│   ├── src/aura_trace/
│   └── setup.py
├── qdrant/
│   ├── src/qdrant_manager/
│   └── setup.py
├── assets/
│   ├── changelogs/template/   # v3_adaptive templates
│   └── hooks/                 # SessionStart hook
└── install.sh                 # Unified installer
```

---

## Per-Project Structure

```
my-project/
├── .context/
│   ├── design/.changes/       # R&D exploration logs
│   ├── designate/             # Staged execution plans
│   ├── develop/.changes/      # Ground truth changelogs
│   └── document/              # Stable architecture docs
└── .claude/
    └── .trace/
        └── registry.json      # Session bookmarks
```

**Isolation**: Each project gets unique Qdrant collection (`imem_<hash>`)

---

## Data Flow: End-to-End

### Creating Knowledge
```
1. Work in Claude Code
   └→ Conversation saved: ~/.claude/projects/*/sessions/*.jsonl

2. Generate changelog
   └→ /log:develop command
   └→ Saved: .context/develop/.changes/YYMMDD-HHMM_description.md

3. Index for search
   └→ imem init
   └→ Vectors: Qdrant collection imem_<project_hash>
```

### Retrieving Knowledge
```
1. Search changelogs
   └→ imem develop search "query" --decisions
   └→ Returns: Section-level matches

2. Compositional discovery (FlexGraph)
   └→ imem compose '{"search": {...}, "discovery": {"siblings": true, "genealogy": true}}'
   └→ Returns: Enriched results with context (siblings, genealogy, temporal)
   └→ Template rendering with genealogical indicators

3. Find conversations
   └→ imem conversations search "query" --messages-only
   └→ Returns: Relevant conversation sections

4. Drill down
   └→ trace show chronicle <id>
   └→ Returns: Chronologically merged messages + patches
```

---

## Design Principles

### 1. Microservices Independence
- Each service installable separately
- No cross-dependencies (IMEM doesn't import TRACE)
- Minimal dependencies (3 unique packages total)
- Shared nothing architecture

### 2. File-Based Composition
- Services coordinate via files (no orchestrator needed)
- Markdown-centric (documentation as data)
- Registry pattern for state tracking (simple JSON)
- Idempotent operations (safe to re-run)

### 3. Per-Project Isolation
- Each project = unique Qdrant collection
- No cross-contamination between projects
- Registry tracks project → collection mapping
- Works across unlimited projects

### 4. Progressive Disclosure
- Simple changelogs = fewer vectors
- Complex changelogs = more vectors
- Complexity emerges naturally from document structure
- No manual tuning required

---

## Installation

### Single Command
```bash
cd /path/to/aura/main
./install.sh
```

**What It Does:**
1. Creates shared virtual environment (`aura/main/venv/`)
2. Installs all 3 microservices in editable mode
3. Installs `aura` CLI command
4. Creates `~/.context/` global storage
5. Ready for per-project use

### Multi-Project Usage
```bash
# Install once
cd /path/to/aura/main
./install.sh

# Use in any project
cd ~/project-a && aura && imem init
cd ~/project-b && aura && imem init
# Each gets isolated knowledge base
```

---

## Storage Architecture

### Global Storage
```
~/.context/
├── qdrant_storage/            # Vector database persistence
├── docker-compose.yml         # Qdrant container config
└── imem_registry.json         # Project → collection mappings

~/.claude/projects/
└── */conversations/*.jsonl    # Claude Code conversations (read-only)
```

### Per-Project Storage
```
project/.context/
├── design/.changes/           # Exploration logs
├── designate/                 # Staged plans
├── develop/.changes/          # Ground truth
└── document/                  # Stable docs

project/.claude/.trace/
└── registry.json              # Session bookmarks
```

---

## Version History

### v3.0 (Current) - Production-Ready
**Released**: 2025-10-23
**Status**: ✅ Zero P0/P1 technical debt

**Metrics**:
- Total codebase: 3,720 lines
- Dependencies: 3 unique packages
- Microservices: 3 independent CLIs
- Quality: 85% docstring coverage

**Major Additions (Phase 5A+B)**:
- ✅ `aura` command for project initialization
- ✅ LlamaIndex section-level chunking
- ✅ Filter support (`--in`, `--session`, `--section`)
- ✅ Conversation indexing pipeline
- ✅ Bidirectional session linking

### v2.0 - Monolithic Package
**Completed**: 2025-10-21

**Migration**:
- 4,020 lines → 3,720 lines (7% reduction)
- Monolithic → 3 microservices
- 6 dependencies → 3 dependencies
- Removed blocking orchestrator

---

## Component Details

For detailed architecture of each microservice:
- **IMEM**: See [architecture_imem-i2.md](./architecture_imem-i2.md) (i2: retrieval-only mode)
- **TRACE**: See [architecture_trace-i2.md](./architecture_trace-i2.md) (i2: semantic commands, chronicle pattern)

---

## Known Limitations

1. **Docker Required**: Qdrant runs in container (no native option)
2. **Single-User**: Registry not designed for concurrent access
3. **No Live Watcher**: Only static conversation discovery
4. **Manual Testing**: Automated test suite not implemented

---

## Future Work

### High Priority
- SessionStart hooks (auto-register conversations)
- Hybrid search (semantic + keyword)
- Cross-section pattern detection

### Medium Priority
- Live conversation watcher
- Configuration file support (YAML)
- Automated test suite

### Low Priority
- Multi-user registry support
- Native Qdrant option
- Distributed execution
