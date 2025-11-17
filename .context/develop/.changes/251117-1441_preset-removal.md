---
schema_version: "v3_adaptive"
type: "refactor.premature-abstraction-removal"
status: "completed"
keywords: "presets removal discovery-driven templates patterns codification validation"
timestamp: "2025-11-17T14:41:00-0800"
session_id: "96ef83ac-d66d-43e5-a0ca-7774b141afac"
---

# Preset System Removal

## Request
> "perhaps we should get rid of the presets? maybe they are premature?"

## Overview
Removed preset system (@lineage, @decisions, @failures, @synthesize, @timeline) from compose interface. Presets were premature - they codified query patterns before validation through actual usage. System now exposes primitives (siblings, genealogy, temporal, cross_phase) and compose JSON interface only. Patterns emerge through usage, not codification. Follows same rationale as template removal from earlier changelog.

## Decisions

### Remove All Preset Infrastructure
- **Context**: Presets required complete phase coverage (design/develop/document), assumed stable query patterns, and made same mistake as removed templates - codifying before proving value
- **Solution**: Delete presets directory, remove preset loading/parsing from CLI, update documentation to show direct JSON examples only
- **Rationale**: Discovery-driven approach proven correct with template removal - "honest empty JSON better than confident falsehoods"
- **Implications**: Users and AI agents compose queries manually using primitives; proven patterns can be extracted later from actual usage logs

### Keep Primitives + Compose JSON Interface
- **Context**: Needed minimal viable interface for knowledge retrieval
- **Solution**: Retain primitives as building blocks, compose as flexible orchestration layer with direct JSON config
- **Alternatives**: Remove compose entirely (too extreme); add more abstractions (wrong direction)
- **Rationale**: Primitives are atomic operations validated through testing; compose provides declarative orchestration without imposing patterns

## Constraints

### Multi-Source Routing Incomplete
- **What**: Preset configs mixed conversation/context filters in single multi-query but top-level source routing doesn't support per-query collection switching
- **Discovery**: During testing, found `@lineage` preset tried to query both sources in parallel but routing layer couldn't handle it
- **Workaround**: Documented limitation; users must use top-level `source` field for now
- **Impact**: Cross-collection queries require separate compose calls; limits some archaeology workflows

## Failures

### Initial Testing Confusion
- **Attempted**: Tested compose with `filters: {source: "conversation"}` expecting it to route to conversation collection
- **Why Failed**: Source routing happens at top level (`source: "conversations"`), not in search filters
- **Lesson**: Read code before testing; CLI examples showed correct syntax but we assumed filter-based routing would work

## Implementation

### Architecture

**Removal sequence:**
1. Delete `/imem/src/imem/presets/` directory (5 JSON files)
2. Remove `_load_preset()` helper function from cli.py
3. Strip preset syntax handling from compose() command
4. Update compose docstring with direct JSON examples
5. Remove preset references from introspect output
6. Delete `get_compose_patterns()` reference in introspect.py

**Interface now:**
```bash
# Simple search
imem compose '{"search": {"text": "authentication", "limit": 5}}'

# Conversations with discovery
imem compose '{"source": "conversations", "search": {"text": "bug", "limit": 3}, "discovery": {"genealogy": true}}'

# Multi-query with siblings
imem compose '{"search": {"queries": [{"text": "JWT", "filters": {"phase": "develop"}}, {"text": "JWT", "filters": {"phase": "document"}}]}, "discovery": {"siblings": {"limit": 3}}}'
```

### Code Signatures

**Compose Command** (`imem/src/imem/cli.py:508-546`)
```python
def compose(config_json, args):
    """Execute composition pipeline with JSON config.

    Compose orchestrates multi-stage knowledge retrieval:
    1. Search - Semantic similarity across sources
    2. Discovery - Enrich with primitives (siblings, genealogy, temporal)
    3. Graph - Apply graph algorithms (not yet implemented)
    4. Output - Structure results
    """
    # Removed: preset loading logic
    # Parse direct JSON only
    config_dict = json.loads(config_json)
    # ... routing and execution
```

**Introspect Output** (`imem/src/imem/introspect.py:547-562`)
```python
result = {
    "system": {
        "primitives": ["siblings", "genealogy", "temporal", "cross_phase"],
        "compose_syntax": "imem compose '{\"search\": {...}, \"discovery\": {...}}'"
        # Removed: "presets" dict with @lineage/@decisions/etc
    },
    "quick_start": [
        # Direct JSON examples only
        "imem compose '{\"search\": {\"text\": \"authentication\", \"limit\": 5}}'",
        "imem compose '{\"source\": \"conversations\", \"search\": {\"text\": \"bug\", \"limit\": 3}, \"discovery\": {\"genealogy\": true}}'"
    ]
}
```

## Patterns

### Pattern: Premature Abstraction Detection
- **Pattern**: Remove codified patterns when they assume behavior not yet validated through usage
- **When**: Abstraction layer requires features that don't exist (multi-phase coverage), assumes stable query patterns before real usage, or makes same mistakes as previously removed features
- **Approach**: Delete abstraction, expose primitives directly, let patterns emerge organically from usage logs
- **Benefit**: System remains honest about capabilities; users discover effective patterns through experimentation; codification happens after validation
- **Reusable**: Any system with layered abstractions can apply this test - does the abstraction assume more than the system delivers?

## Audit

### Created
- None

### Modified
- `imem/src/imem/cli.py` - Removed `_load_preset()` function (~37 lines), removed preset handling from compose() command, updated docstring with direct JSON examples only
- `imem/src/imem/introspect.py` - Removed preset references from system output, removed `get_compose_patterns()` call, updated quick_start examples

### Removed
- `imem/src/imem/presets/lineage.json` - Multi-phase artifact archaeology preset
- `imem/src/imem/presets/decisions.json` - Design phase decisions preset
- `imem/src/imem/presets/failures.json` - Develop phase failures preset
- `imem/src/imem/presets/synthesize.json` - Cross-session synthesis preset
- `imem/src/imem/presets/timeline.json` - Temporal evolution preset

### Configuration
- No environment changes
- CLI syntax simplified (no @ prefix)

### Deployment
- Backward incompatible for any users/scripts using @preset syntax
- Migration: Replace `imem compose @lineage file.py` with equivalent JSON config
