# TRACE Architecture Redesign Plan

## Problem Statement

TRACE has evolved through multiple iterations, resulting in 6 conflicting components with redundant functionality and parsing bugs. We need a clean, elegant 3-component architecture that serves the core requirements:

1. **Find conversations** for current project
2. **Retrieve conversation data** (messages, tools, files)  
3. **Query conversations** with agent interface

## Current State Analysis

### ✅ What Works (Keep)
- `conversation_retrieval.py` - Perfect JSONL parsing with fixed tool detection
- CLI integration pattern - `imem retrieve` command works well

### ❌ What's Broken (Remove)
- `conversation_parser.py` - Has same parsing bug we fixed
- `conversation_index.py` - SQLite over-engineering
- `trace.py` - 493 lines of redundant legacy code
- `simple_curator.py` - Broken imports, superseded functionality

### 🔄 What's Missing (Build)
- Simple conversation discovery for current project
- Clean agent interface for conversation queries

## Target Architecture

### Clean 3-Component Design
```
trace/
├── conversation_finder.py      # Project-specific discovery
├── conversation_retrieval.py   # Direct JSONL access (COPY from existing)
└── conversation_query.py       # Agent interface
```

### Data Flow Pipeline
```
ConversationFinder → ConversationRetrieval → ConversationQuery → Agent
   (filesystem)       (JSONL parsing)        (agent prep)
```

## Migration Strategy

### Phase 1: Safe Migration Setup
**Goal**: Preserve working system during transition

1. Rename `imem/src/trace/` → `imem/src/trace-old/`
2. Create new `imem/src/trace/` directory
3. Copy `conversation_retrieval.py` to new trace/ (exact copy)
4. Create basic `__init__.py` with exports

### Phase 2: Build Missing Components
**Goal**: Implement clean discovery and agent interface

1. **Build ConversationFinder**
   - Claude path encoding logic: `/path` → `~/.claude/projects/-path/`
   - List all conversations for current project
   - Find by markers, date range, recent files
   - Use filesystem timestamps (lean approach)

2. **Build ConversationQuery**
   - Format conversation data for agent consumption
   - Handle context preparation and question answering
   - Clean interface for agent handoff

### Phase 3: CLI Integration
**Goal**: Connect new components to existing CLI

1. Update CLI imports to use new trace components
2. Test existing `imem retrieve` command still works
3. Add new commands using full pipeline
4. Ensure backward compatibility

### Phase 4: Validation & Cleanup
**Goal**: Verify system works and remove legacy

1. Test complete pipeline: Find → Retrieve → Query
2. Validate with real conversation data
3. Remove `trace-old/` directory
4. Update documentation

## Implementation Details

### ConversationFinder Requirements
```python
class ConversationFinder:
    def __init__(self, project_root: Path = None)
    def list_all(self) -> List[Path]                    # All conversations for project
    def find_recent(self, count: int = 1) -> List[Path] # Most recent by mtime
    def find_by_marker(self, marker: str) -> List[Path] # Content search
    def find_by_date_range(self, start: date, end: date) -> List[Path]
```

### Claude Path Encoding
```python
# Current: /home/axp/projects/aura-retrieval-qdrant/aura/projects/imem-suite/main
# Encoded: -home-axp-projects-aura-retrieval-qdrant-aura-projects-imem-suite-main
# Folder:  ~/.claude/projects/-home-axp-projects-aura-retrieval-qdrant-aura-projects-imem-suite-main/
```

### ConversationQuery Requirements
```python
class ConversationQuery:
    def prepare_for_agent(self, conversation_data: Dict, query: str) -> str
    def format_context(self, messages: List, files: List) -> str
    def answer_question(self, conversation_data: Dict, question: str) -> str
```

## Success Criteria

### Functional Requirements
- ✅ Find conversations for current project
- ✅ Retrieve conversation sections/slices/entire conversations
- ✅ Query conversations with agent interface
- ✅ Existing CLI commands continue working

### Architectural Requirements
- ✅ 3 focused components (down from 6 conflicting ones)
- ✅ No redundant parsing logic
- ✅ No SQLite over-engineering
- ✅ Clean separation of concerns

### Performance Requirements
- ✅ Fast filesystem-based discovery
- ✅ Real-time conversation access
- ✅ No pre-processing overhead

## Risk Mitigation

### Development Risks
- **Risk**: Breaking existing CLI during migration
- **Mitigation**: Keep trace-old/ until new system validated

- **Risk**: Losing working conversation_retrieval.py functionality  
- **Mitigation**: Exact copy, no modifications to working code

- **Risk**: Claude path encoding logic incorrect
- **Mitigation**: Test with actual conversation files first

### Operational Risks
- **Risk**: Users lose access to conversation history
- **Mitigation**: Incremental migration, backward compatibility

- **Risk**: New system doesn't handle edge cases
- **Mitigation**: Thorough testing with real conversation data

## Timeline

### Immediate (Today)
- Phase 1: Safe migration setup
- Phase 2: Build ConversationFinder

### Next Session  
- Phase 2: Build ConversationQuery
- Phase 3: CLI integration

### Validation
- Phase 4: Testing and cleanup
- Documentation updates

## Notes

- This is a **selective migration**, not a rewrite
- Preserve all working functionality
- Build only what's missing
- Focus on simplicity and elegance
- Use filesystem as the index (no SQLite complexity)
