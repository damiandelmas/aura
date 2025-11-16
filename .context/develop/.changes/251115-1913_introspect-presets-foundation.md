---
schema_version: "v3_adaptive"
type: "feature.introspect-presets"
status: "completed"
keywords: "introspect progressive-disclosure presets lineage decisions failures synthesize timeline multi-query compose ai-onboarding"
timestamp: "2025-11-15T19:13:00-0800"
session_id: "c4fbb265-dbb9-49ca-b4ec-23180d0215a4"
---

# Introspect Enhancement + Preset Library Foundation

## Request
> "AI onboarding needs to discover system capabilities programmatically. Workflows should be accessible through ergonomic presets without requiring extensive documentation."

## Overview
Enhanced system introspection with three progressive disclosure levels for AI onboarding, plus a preset library that wraps granular query composition. System primitives and concept topology are now exposed through three graduated views offering different depth levels. Five preset templates enable common workflows by bundling parallel query execution with automatic deduplication and cross-collection routing.

<!-- ===== EXPAND SECTIONS BELOW AS NEEDED ===== -->
<!-- Use what provides value. Skip what doesn't. -->

## Decisions

### Progressive Disclosure with Three Views
- **Context**: Introspection output was too dense, mixing system shape, project landscape, metadata schema, and concept topology. Single monolithic view created cognitive overload for AI onboarding.
- **Solution**: Implemented three depth levels via optional flags (default, map, status)
- **Alternatives**: Single view (cognitive overload); separate commands per depth level (more API surface); graduated flags (chosen)
- **Rationale**: Three-tier approach keeps single entry point for discovery, adds optional depth, defaults to AI onboarding workflow, maintains backward compatibility

### Preset Invocation with Sigil Notation
- **Context**: Needed ergonomic way to invoke presets within query composition interface
- **Solution**: Sigil notation for preset invocation instead of explicit flag or dedicated commands
- **Alternatives**: Flag-based invocation; dedicated commands per preset type
- **Rationale**: Sigil is visually distinct from structured data syntax, familiar pattern from configuration tooling, shorter to type, keeps single entry point for composition

### Multi-Query Presets Instead of Single Query
- **Context**: Complex workflows like lineage require querying conversations, design phase, develop phase, and document phase simultaneously to ensure comprehensive results
- **Solution**: Structured preset templates with parallel multi-query support, automatic deduplication, and per-query filtering
- **Alternatives**: Single broad query (misses phase-specific content); sequential queries (slow, manual dedup)
- **Rationale**: Parallel execution provides single round-trip for complex workflows, leverage existing multi-query infrastructure, automatic deduplication prevents duplicates

---

## Constraints

### Multi-Source Routing Limitation
- **What**: Per-query source filter requires routing to different collections (conversation vs context). Initial routing based only on top-level source field, preventing per-query collection switching.
- **Discovery**: Discovered during preset testing when lineage queries needed to mix conversation and context sources in single multi-query
- **Workaround**: Added registry and project context parameters to routing functions; extract source from per-query filters and route to appropriate collection before querying; strip source from vector database filters (routing hint, not filter)
- **Impact**: Enables cross-collection presets to aggregate results from multiple sources

### Encoder Error with Incompatible Filters
- **What**: Multi-query with per-query source filters crashed when query against wrong collection returned None
- **Discovery**: Iteration over None results failed with type errors
- **Workaround**: Graceful failure handling with exception catching in parallel execution; skip None or failed results rather than crashing
- **Impact**: Presets resilient to partial query failures and type mismatches

### Phase Coverage Gap
- **What**: Only `document` phase indexed (144 chunks). Design/develop phases empty, limiting @lineage effectiveness.
- **Discovery**: Introspect --map shows all concepts tagged `phase: document`, no design/develop results
- **Impact**: @lineage can query design/develop phases but returns empty results. Full lifecycle story requires phase backfill.
- **Future Work**: Index `.context/design/` and `.context/develop/` content to enable complete artifact evolution tracking

---

## Patterns

### Pattern: Progressive Disclosure for System Introspection
- **Pattern**: Graduated depth levels for discovery interface
- **When**: Complex system needs to balance comprehensiveness with cognitive load
- **Approach**: Three tiers - default (system shape + landscape), map (full topology), status (stats only)
- **Why**: New users get quick start, experienced users get deep inspection, monitors get metrics
- **Benefit**: Single entry point serves multiple audiences without overwhelming newcomers
- **Reusable**: Any tool with complex introspection should offer progressive depth

---

### Pattern: Presets as Multi-Query Templates
- **Pattern**: Declarative workflow templates that bundle parallel query execution
- **When**: Common workflows require multiple coordinated queries across different sources
- **Approach**: Template files with variable substitution, per-query filters, automatic deduplication
- **Why**: Single preset invocation = complex workflow (4+ queries in parallel)
- **Benefit**: Template substitution enables reuse across topics; comprehensive coverage in one call; users can extend with custom presets
- **Reusable**: Any system with granular primitives can layer ergonomic presets on top

### Pattern: Source Filter as Routing Hint
- **Pattern**: Metadata filter used for collection routing, not query filtering
- **When**: Multi-collection system needs per-query routing within parallel execution
- **Approach**: Extract `source` from query filters, route to appropriate collection, strip before building vector query
- **Why**: Declarative routing via filter syntax; prevents filter mismatch errors; backward compatible (falls back to base collection)
- **Benefit**: Enables cross-collection queries in single preset invocation
- **Reusable**: Any multi-collection system can use metadata filters as routing hints

---

---

## Failures

### Cross-Collection Multi-Query Routing
- **Attempted**: Per-query source filtering within multi-query without thread context (registry, project_root)
- **Why Failed**: Router lacked collection context to route individual queries; all queries routed to same collection
- **Lesson**: Multi-query routing requires full pipeline context (registry, project_root) passed from CLI layer to enable per-query collection switching
- **Alternative**: Modified compose() signature and threading to pass registry context through routing pipeline

---

## Implementation

### Architecture

Introspection enhancement implements three-tier disclosure model:

1. **Default view** - System primitives and landscape (onboarding-optimized): returns system shape with available presets, project coverage metrics, top concepts by mention frequency
2. **Map view** - Complete concept topology: exposes all section titles with frequencies and phase coverage, shows architectural vocabulary
3. **Status view** - Coverage statistics: minimal output with context chunks, session counts, averages per session

Preset library wraps parallel multi-query execution with:
- Template-based variable substitution (artifact, topic, concept)
- Per-query source routing (conversation vs context collections)
- Automatic deduplication and result merging
- Five built-in workflows: lineage (multi-phase archaeology), decisions (design rationale), failures (learn from mistakes), synthesize (aggregate scattered discussions), timeline (concept evolution)

**Multi-Source Lineage Capability**:
Cross-collection routing enables true lineage archaeology:
- Conversation queries retrieve thinking/patches from live sessions
- Context queries retrieve design/develop/document phases
- Single `@lineage` call aggregates 3 conversation + 3 phase results
- Deduplication ensures unique results across sources
- Validated: artifact "chunking" → 3 conversation + 2 context = 5 total results

### Code Signatures

**Introspect Three Views** (`imem/src/imem/introspect.py`)
```python
def get_system_and_landscape() -> dict:
    # Returns system primitives, preset catalog, coverage metrics

def get_concept_topology() -> dict:
    # Returns all concepts with mention frequencies and phase coverage

def get_coverage_stats() -> dict:
    # Returns chunk/session counts and averages
```

**Preset Loading** (`imem/src/imem/cli.py`)
```python
def _load_preset(preset_name: str, user_arg: str) -> dict:
    # Load JSON template, substitute {{variable}} with user_arg
    # Returns compose config ready for execution
```

**Per-Query Routing** (`imem/src/imem/compose.py`)
```python
async def _execute_search(query, source_filter, registry, project_root):
    # Extract source from filters, route to appropriate collection
    # Strip source from vector database filters (hint for routing, not filtering)
    # Return results with graceful failure handling
```

## Audit

### Created
- `imem/src/imem/presets/lineage.json` - Multi-phase artifact archaeology
- `imem/src/imem/presets/decisions.json` - Design phase decisions with rationale
- `imem/src/imem/presets/failures.json` - Develop phase failures and constraints
- `imem/src/imem/presets/synthesize.json` - Cross-chunk synthesis workflow
- `imem/src/imem/presets/timeline.json` - Temporal concept evolution

### Modified
- `imem/src/imem/introspect.py` - Added 3 functions for progressive disclosure (~250 lines)
  - `get_system_and_landscape()` - Default onboarding view
  - `get_concept_topology()` - Full concept network
  - `get_coverage_stats()` - Coverage metrics only
- `imem/src/imem/cli.py` - Updated introspect command routing (~60 lines); added `_load_preset()` helper for template substitution
- `imem/src/imem/compose.py` - Per-query routing logic (~25 lines) to enable collection switching per query

### Configuration
- Backward compatible: existing entity and field flags still function
- New flags: map and status depth levels for introspection
- New preset syntax: sigil notation for preset invocation

### Deployment
- No new dependencies
- CLI updates handle version compatibility
- Preset templates are JSON configuration, not code
