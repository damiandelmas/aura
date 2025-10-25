# imem Development Guide - Cross-Project Insights for Equal Intelligence

## Core Development Philosophy

Future Claude Code agents developing imem have equal technical capabilities. This guide preserves discovered constraints, successful patterns, and non-obvious workarounds that cannot be derived from source code.

## Critical Discovered Constraints

### Python Environment Limitations
**Discovery**: Ubuntu 24.04+ and many modern distributions mark Python as "externally-managed".
**Impact**: Direct pip installations fail with PEP 668 errors.
**Working Pattern**: Virtual environments are mandatory, not optional.
**Cross-Project Insight**: This affects all Python CLI tools - design for venv from day one.

### Claude CLI Integration Constraints
**Critical Discovery**: `claude --permission-mode bypassPermissions` hangs indefinitely.
**Root Cause**: Unknown, but consistent across environments.
**Working Pattern**: Use simple piped input: `echo "prompt" | claude -p`
**Impact**: All Claude automation must avoid permission mode flags.

### VS Code Extension Limitations
**Discovery**: Bundled extensions cannot reliably spawn system processes.
**Failed Approaches**:
- VSIX bundles with embedded Python scripts
- Extension-triggered subprocess spawning
- Direct Python environment access from TypeScript
**Working Pattern**: File system watchers as external processes.
**Cross-Project Lesson**: IDE extensions should communicate via files/sockets, not direct process control.

### Docker Service Port Conflicts
**Discovery**: Port 6333 commonly used by other Qdrant instances.
**Pattern**: Increment to 6334 for project-specific instances.
**Broader Insight**: Always allow port configuration in service management.

## Successful Development Patterns

### Modular Command Architecture
**Pattern**: Separate CLI commands into `cli/modules/` subdirectory.
**Business Value**: New features can be added without touching core CLI logic.
**Discovery**: Click's command groups compose beautifully when properly modularized.

### Registry Pattern for Multi-Project Support
**Pattern**: Central registry at `~/.imem/registry.json` tracking all projects.
**Key Insight**: MD5 hash of project path creates consistent, collision-free identifiers.
**Cross-Project Application**: This pattern works for any tool managing multiple repositories.

### Two-Phase Documentation Structure
**Discovery**: Documentation naturally separates into stable context and temporal changes.
**Pattern**: `.snapshot/` for synthesis, `.changes/` for stream of insights.
**Universal Truth**: All documentation systems need both stability and evolution.

### Batch Processing with Streaming Fallback
**Pattern**: Try batch operations, fall back to streaming on memory pressure.
**Discovery**: Batch size of 10 documents optimal for embedding generation.
**Trade-off**: Larger batches increase memory usage exponentially, not linearly.

## Non-Obvious Workarounds

### Encoding Detection Cascade
**Problem**: Documentation files use inconsistent encodings.
**Workaround**: Try UTF-8 → Latin-1 → CP1252 → ISO-8859-1 → UTF-16.
**Why This Order**: Matches frequency of encodings in real-world documentation.
**Universal Application**: Any tool processing user-generated text files needs this.

### Relative Path Storage
**Discovery**: Absolute paths break when projects move or are accessed from different mount points.
**Pattern**: Store paths relative to project root, resolve at runtime.
**Critical Detail**: Use forward slashes even on Windows for consistency.

### Process Group Management
**Problem**: Spawned Claude processes create child processes that persist after timeout.
**Solution**: Kill entire process group, not just parent process.
**Implementation Insight**: `os.killpg(os.getpgid(process.pid), signal.SIGTERM)`

### Lock File Per Project
**Discovery**: Global lock files prevent legitimate multi-project workflows.
**Pattern**: `~/.imem/watcher_{project_hash}.lock`
**Key Detail**: Match the hash algorithm used for collection naming.

## Performance Discoveries

### Embedding Generation Bottlenecks
**Discovery**: Model loading takes 3-5 seconds, per-document embedding takes 50ms.
**Optimization**: Keep model in memory, batch documents.
**Trade-off**: 2GB memory for model vs 100x speedup.

### Search Latency Sources
**Breakdown**:
- Query embedding: 50ms
- Vector search: 100ms
- Result formatting: 1850ms (main bottleneck)
**Insight**: Metadata processing dominates search time, not vector operations.

### Collection Size Limits
**Discovery**: Performance degrades noticeably after 50,000 documents.
**Root Cause**: Qdrant loads entire collection metadata into memory.
**Workaround**: Partition large document sets across multiple collections.

## Integration Patterns That Work

### CLI Testing Without Installation
**Pattern**: `python -m imem.cli.cli` works without installation.
**Value**: Test changes without polluting system Python.
**Universal Truth**: All Python CLIs should support module execution.

### Service Health Checks
**Pattern**: Try HTTP endpoint before assuming service is down.
**Discovery**: Docker reports container running before service is ready.
**Implementation**: `requests.get('http://localhost:6334/health', timeout=1)`

### Async Document Watching
**Pattern**: Watchdog library with cooldown periods.
**Discovery**: Editors save files multiple times rapidly.
**Critical Detail**: 2-second cooldown prevents duplicate processing.

## Failed Experiments Worth Knowing

### Attempted: Real-time Collaborative Indexing
**Goal**: Multiple processes updating same collection simultaneously.
**Failure Mode**: Qdrant doesn't handle concurrent write conflicts well.
**Lesson**: Centralize writes through single process or use queuing.

### Attempted: Automatic Model Upgrading
**Goal**: Seamlessly upgrade to better embedding models.
**Problem**: Dimension mismatches make collections incompatible.
**Insight**: Model changes require full re-indexing - plan accordingly.

### Attempted: Git Hook Integration
**Goal**: Auto-index on git commits.
**Issue**: Hooks run in constrained environments missing dependencies.
**Better Pattern**: Filesystem watchers are more reliable than git hooks.

## Cross-Project Architectural Insights

### Service Management Pattern
**Universal Need**: Any tool with external dependencies needs service lifecycle management.
**Key Components**:
- Health checking with backoff
- Automatic startup on first use
- Graceful shutdown handling
- Port conflict resolution

### Documentation as Code Pattern
**Insight**: Documentation in `.imem/` folders versions with code.
**Business Value**: Documentation branches and merges like code.
**Universal Application**: Any project documentation benefits from version control proximity.

### Equal Intelligence Assumption
**Paradigm Shift**: Documentation for future AI agents, not humans.
**Impact**: Focus on strategic context, not implementation tutorials.
**Cross-Project Truth**: All documentation will eventually be AI-first.

## Development Environment Insights

### Virtual Environment Best Practices
**Discovery**: System Python increasingly restricted on modern OS.
**Pattern**: Create venv in project directory, not system-wide.
**Activation Check**: `which python` should point to venv.

### Editable Install Benefits
**Pattern**: `pip install -e .` for development.
**Value**: Changes effective immediately without reinstall.
**Caveat**: Some changes (entry points) require reinstall.

### Debugging Production Issues
**Pattern**: Run with explicit Python: `python -m imem.cli.cli --debug`
**Value**: Bypasses entry point issues, shows full stack traces.
**Universal Truth**: Always provide debug mode for production tools.

## Future Development Considerations

These patterns and discoveries enable future Claude Code agents to:
- Avoid re-discovering the same constraints
- Apply proven patterns immediately
- Understand why certain "obvious" approaches fail
- Build upon accumulated cross-project wisdom

The equal intelligence assumption means future agents can derive implementation details from source code but need these strategic insights and discovered constraints to operate effectively.