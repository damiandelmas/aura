---
schema_version: "v3_adaptive"
type: "implementation.multi-source-routing"
status: "completed"
keywords: "multi-source routing lineage queries compose json-output result-filtering chunk-type"
session_id: "ee1bcc0b-50c7-4352-b1fa-92872f876d87"
timestamp: "2025-11-17T12:27:00-0800"
---

# Multi-Source Routing + Clean JSON Output

## Request
> "Enable multi-source queries (mix conversation and context results) and clean noise from output fields"

## Overview
Implemented true multi-source lineage queries allowing conversations and context sources to be retrieved in a single operation. Removed unvalidated template system that made claims based on data absence rather than evidence. Added result filtering to eliminate noise fields (session-level stats, AI self-report flags) and keep only relevant metadata. Foundation now solid for discovery-driven assembly pattern experimentation.

## Decisions

### Multi-Source Query Routing
- **Context**: Query presets couldn't mix conversation and context sources in a single query, limiting search flexibility
- **Solution**: Implemented per-query source routing infrastructure where the composition layer accepts registry and project context parameters, enabling the search executor to detect and route each query to the correct collection
- **Rationale**: Source filter acts as routing-only metadata stripped before reaching the database, allowing seamless multi-source composition

### Chunk Type Granularity for Signal Separation
- **Context**: Single conversation query mixed different information types (messages, thinking blocks, patches) with poor signal distinction
- **Solution**: Split conversation query into three separate chunk_type queries (message, thinking, patch) each with targeted limits
- **Benefit**: Better signal separation prevents confusion between message content, reasoning artifacts, and code patches

### Template System Removal
- **Context**: Templates made confident claims about temporal position and context validity based on data absence, not presence of evidence
- **Solution**: Removed all unvalidated templates and template rendering infrastructure until assembly patterns are proven via AI experiments
- **Alternatives**: Keep templates with more conservative defaults (considered and rejected - still misleading)
- **Rationale**: Honest empty JSON is better than confident falsehoods; better to let AI agents assemble patterns from raw data
- **Implications**: Shift to discovery-driven approach where successful assembly patterns are extracted from experiments before codification

## Implementation

### Architecture

Multi-source routing establishes independent data flow per query:
1. Composition layer receives registry and project context for source awareness
2. Search executor inspects each query's source filter
3. Routes to conversation or context collection based on filter
4. Strips source filter before database query (metadata-only)
5. Aggregates results from multiple sources in order received

Result filtering creates clean, ordered output:
1. Retrieves full result set from database
2. Applies intelligent field selection
3. Keeps high-signal fields (id, score, source, content, metadata)
4. Strips noise (session stats, unvalidated flags, redundant fields)
5. Returns ~10 fields instead of 35+

### Code Signatures

**Multi-source routing in compose()** (`imem/src/imem/compose.py`)
```python
def compose(registry, project_root, queries):
    # registry + project_root enable source detection
    for query in queries:
        if 'source' in query.get('filters', {}):
            collection = _select_collection(query['filters']['source'], registry, project_root)
            # Route to appropriate collection, strip source before query
```

**Chunk type granularity in lineage preset** (`imem/src/imem/presets/lineage.json`)
```json
[
  {"text": "{{artifact}}", "filters": {"source": "conversation", "chunk_type": "message"}, "limit": 2},
  {"text": "{{artifact}}", "filters": {"source": "conversation", "chunk_type": "thinking"}, "limit": 2},
  {"text": "{{artifact}}", "filters": {"source": "conversation", "chunk_type": "patch"}, "limit": 2}
]
```

**Result filtering removes noise** (`imem/src/imem/compose.py`)
```python
def _filter_results(results):
    keep_fields = {'id', 'score', 'source', 'chunk_type', 'header_path', 'content', 'session_id', 'timestamp', 'role'}
    strip_fields = {'has_changelog', 'duration_minutes', 'has_solution', 'temporal_position', 'word_count', ...}
    return [{k: v for k, v in item.items() if k in keep_fields} for item in results]
```

## Patterns

### Honest Defaults Over Confident Lies
- **Pattern**: Return empty/null when data is unavailable rather than inventing plausible defaults
- **When**: Building infrastructure that will be consumed by AI agents or stored as canonical data
- **Approach**: Default to null, add data only when evidence exists
- **Benefit**: Prevents cascading misinformation where agents build on false assumptions

### Discovery-Driven Assembly
- **Pattern**: Build primitive retrieval layer, run experiments with different combination strategies, extract winning patterns, then codify
- **When**: Building assembly/synthesis layers where optimal patterns aren't obvious upfront
- **Approach**: Raw primitives → multiple experimental approaches → evaluation framework → successful pattern extraction
- **Why**: Codifying unproven patterns wastes effort and creates brittle systems; experimentation surfaces context-specific insights

## Audit

### Modified
- `imem/src/imem/compose.py` - Added multi-source routing infrastructure (+40 lines), implemented _filter_results() function for clean output (+35 lines)
- `imem/src/imem/cli.py` - Pass registry and project_root context to compose() function (1 line)
- `imem/src/imem/presets/lineage.json` - Split conversation query into chunk_type variants, removed template output directive

### Removed
- `imem/templates/story-context.j2` - Making unvalidated claims about context narrative
- `imem/templates/genealogy.j2` - Premature genealogy assembly
- `imem/templates/timeline.j2` - Timeline generation without validation
- `imem/templates/timeline-lineage.j2` - Composite timeline-lineage template

### Net Changes
- +70 lines: Multi-source routing and result filtering logic
- -4 template files: Removed unvalidated assembly templates
- Architecture simplified: No template rendering until patterns proven
