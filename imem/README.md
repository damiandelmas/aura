# AURA IMEM - Vector Search Microservice

**IMEM** (Institutional Memory) provides vector search capabilities for project documentation using Qdrant vector database.

## Features

- 🔍 **Semantic Search**: Find documentation using natural language queries
- 📦 **Incremental Indexing**: Only index new/changed files
- 🔄 **Deduplication**: Automatically detect and remove duplicate content
- 🐳 **Docker Integration**: Manages Qdrant service lifecycle
- 📊 **Multi-Project Support**: Track multiple projects with separate collections

## Installation

```bash
# Install from source
cd imem/
pip install -e .

# Verify installation
imem --help
```

## Dependencies

- `qdrant-client>=1.7.0` - Vector database client
- `sentence-transformers>=2.2.0` - ML models for embeddings
- `click>=8.0.0` - CLI framework

## Quick Start

```bash
# 1. Start Qdrant service (Docker required)
imem service start

# 2. Index your project
cd /path/to/your/project
imem init

# 3. Search documentation
imem search "authentication flow"
imem search "error handling" --limit 10
imem search "database" "connection" --operator AND
```

## Commands

### Service Management

```bash
imem service start   # Start Qdrant Docker container
imem service stop    # Stop Qdrant
imem service status  # Check service status
```

### Indexing

```bash
imem init           # Initialize and index current project
imem init --force   # Force re-indexing
imem update         # Incremental update (index new files only)
```

### Search

```bash
# Basic search
imem search "query text"

# Advanced options
imem search "query" --limit 5           # Limit results
imem search "query" --sort-by date      # Sort by date
imem search "query" --after 2025-01-01  # Filter by date
imem search "query" --show-metadata     # Show metadata
imem search "multiple terms" --split-terms --operator AND  # Multi-term search
```

### Maintenance

```bash
imem status  # Show all indexed projects
imem dedupe  # Remove duplicate documents
```

## Architecture

IMEM indexes markdown files from `.context/design/` or `.context/develop/` directories:

```
project/
├── .context/
│   ├── design/
│   │   └── .changes/       # Design documents
│   └── develop/
│       └── .changes/       # Implementation logs
```

## How It Works

1. **Service**: Docker-based Qdrant runs on port 6334
2. **Indexing**: Files are embedded using E5-Large-v2 model (1024 dimensions)
3. **Storage**: Each project gets a unique collection in Qdrant
4. **Registry**: Project mappings stored in `~/.context/imem_registry.json`

## Configuration

### Collection Names
IMEM generates collection names as `imem_<hash>` based on project path.

### Storage Location
Qdrant data stored in `~/.context/qdrant_storage/`

## Troubleshooting

**Qdrant won't start**:
```bash
# Check Docker is running
docker ps

# Restart service
imem service stop
imem service start
```

**Import errors**:
```bash
# Reinstall with dependencies
cd imem/
pip install -e . --force-reinstall
```

**No results found**:
```bash
# Check indexing status
imem status

# Re-index project
imem init --force
```

## Development

```bash
# Install in editable mode
pip install -e .

# Run tests
pytest tests/
```

## Related Microservices

- **TRACE**: Conversation archaeology (`../trace/`)
- **Qdrant**: Database manager (`../qdrant/`)
