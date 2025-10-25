# AURA - Institutional Memory Ecosystem

**AURA** is a suite of microservices for managing institutional memory through vector search, conversation archaeology, and document maintenance.

## Architecture

AURA consists of 3 independent microservices:

```
aura/main/
├── imem/      # Vector search (semantic search for docs)
├── trace/     # Conversation archaeology (parse Claude sessions)
├── qdrant/    # Vector DB manager (Docker lifecycle)
└── spawn/     # Brother spawning primitive (bash)
```

## Microservices

### IMEM - Vector Search

Semantic search for project documentation using Qdrant vector database.

**Installation**:
```bash
cd imem/
pip install -e .
```

**Usage**:
```bash
imem service start        # Start Qdrant
imem init                 # Index current project
imem search "query text"  # Search documentation
```

See: [imem/README.md](./imem/README.md)

---

### TRACE - Conversation Archaeology

Parse and query Claude Code conversation histories.

**Installation**:
```bash
cd trace/
pip install -e .
```

**Usage**:
```bash
trace --list                    # List all conversations
trace --session <id> --summary  # Get conversation summary
trace --session <id> --export session.md  # Export to markdown
```

See: [trace/README.md](./trace/README.md)

---

### Qdrant - Database Manager

Manages Qdrant vector database lifecycle via Docker.

**Installation**:
```bash
cd qdrant/
pip install -e .
```

**Usage** (library only):
```python
from qdrant_manager import QdrantService

service = QdrantService()
service.start()  # Start Qdrant Docker container
```

See: [qdrant/README.md](./qdrant/README.md)

---

### Spawn - Brother Spawning

Bash primitive for spawning "brother" agents using `claude -p`.

**Usage**:
```bash
echo "Task for brother agent" | spawn/spawn.sh
```

See: [spawn/README.md](./spawn/README.md)

## Quick Install (All Microservices)

```bash
# Install all at once
pip install -e ./imem -e ./trace -e ./qdrant

# Verify installation
imem --help
trace --help
python -c "from qdrant_manager import QdrantService; print('OK')"
```

## Dependencies

**Minimal** (only 3 external packages):

- `qdrant-client>=1.7.0` (used by imem and qdrant)
- `sentence-transformers>=2.2.0` (used by imem for embeddings)
- `click>=8.0.0` (used by all for CLI)

**Total**: ~1,430 lines of code

## System Requirements

- Python 3.8+
- Docker (for Qdrant service)
- 2GB+ RAM (for ML models in IMEM)

## Migration from v2

AURA v3 is a complete microservices rewrite:

**Before (v2)**:
- 4,020 lines (monolithic)
- 6 dependencies
- Complex orchestration
- Tightly coupled components

**After (v3)**:
- 1,430 lines (65% reduction)
- 3 dependencies (50% reduction)
- Independent microservices
- Simple, focused tools

See: [COMPLETE_MIGRATION.md](../COMPLETE_MIGRATION.md)

## Directory Structure

```
aura/main/
├── imem/
│   ├── src/imem/
│   │   ├── cli.py           # Command-line interface
│   │   ├── ingest.py        # Document ingestion
│   │   ├── search.py        # Search engine
│   │   ├── enhanced.py      # Enhanced search features
│   │   └── qdrant_service.py  # Qdrant integration
│   ├── setup.py
│   └── README.md
│
├── trace/
│   ├── src/aura_trace/      # Note: renamed to avoid Python conflict
│   │   ├── cli.py           # Command-line interface
│   │   ├── finder.py        # Session discovery
│   │   ├── retrieval.py     # JSONL parsing
│   │   └── query.py         # Agent interface
│   ├── setup.py
│   └── README.md
│
├── qdrant/
│   ├── src/qdrant_manager/
│   │   ├── __init__.py
│   │   └── service.py       # Docker lifecycle management
│   ├── setup.py
│   └── README.md
│
├── spawn/
│   ├── spawn.sh             # Brother spawning primitive
│   └── README.md
│
└── setup.py                 # Aggregate installer
```

## Design Philosophy

AURA follows these principles:

1. **Microservices**: Each tool is independent and focused
2. **Minimal Dependencies**: Only essential external packages
3. **Simple First**: Prefer simplicity over features
4. **Composable**: Tools work together but don't depend on each other
5. **Brother-Based**: Use spawned agents for intelligence, not hardcoded logic

## Use Cases

### Documentation Search

```bash
# Index your project
cd /path/to/project
imem init

# Search documentation
imem search "authentication flow"
imem search "database schema" --limit 5
```

### Conversation Analysis

```bash
# Find conversations about feature
trace --marker "new feature" --summary

# Export for documentation
trace --session abc123 --export session.md
```

### Development Workflow

```bash
# Start services
imem service start

# Index docs
imem init

# Work on project...
# Conversations auto-saved by Claude Code

# Later: find what you discussed
trace --marker "bug fix" --conversation
```

## Troubleshooting

### IMEM Issues

```bash
# Qdrant won't start
docker ps  # Check Docker is running
imem service restart

# No search results
imem status  # Check indexing status
imem init --force  # Re-index
```

### TRACE Issues

```bash
# No conversations found
ls ~/.claude/projects/  # Check conversations exist

# Session not found
trace --list  # List all sessions
```

### General Issues

```bash
# Import errors
pip install -e ./imem -e ./trace -e ./qdrant --force-reinstall

# Command not found
which imem trace  # Check installation
pip list | grep aura  # Check packages
```

## Development

```bash
# Install in development mode
pip install -e ./imem -e ./trace -e ./qdrant

# Run tests
cd imem && pytest tests/
cd trace && pytest tests/

# Make changes
# Changes reflect immediately (editable install)
```

## Contributing

Each microservice is independent:

1. Make changes in the appropriate directory
2. Test locally with editable install
3. Update README if needed
4. No need to touch other microservices

## License

[Add your license here]

## Related Projects

- **Claude Code**: https://claude.ai/code
- **Qdrant**: https://qdrant.tech
- **Sentence Transformers**: https://www.sbert.net
