---
schema_version: "v3_adaptive"
type: "feature.introspect-presets"
status: "completed"
keywords: "system-discovery progressive-disclosure multi-tier introspection workflow-templates composition preset-patterns cross-source-querying ai-onboarding"
timestamp: "2025-11-15T19:13:00-0800"
session_id: "c4fbb265-dbb9-49ca-b4ec-23180d0215a4"
source_changelog: "251115-1913_introspect-presets-foundation.md"
---

# System Introspection Enhancement + Workflow Preset Foundation

## Request
> "AI onboarding needs to discover system capabilities programmatically. Workflows should be accessible through ergonomic templates without requiring extensive documentation."

## Overview
Enhanced system introspection with three progressive disclosure levels for AI discovery, plus a preset template library that wraps multi-query composition. System structure and concept topology are now exposed through three graduated views offering different depth levels. Multiple preset templates enable common workflows by bundling parallel query execution with automatic deduplication and cross-collection aggregation.

<!-- ===== EXPAND SECTIONS BELOW AS NEEDED ===== -->
<!-- Use what provides value. Skip what doesn't. -->

## Decisions

### Progressive Disclosure with Multiple Depth Tiers
- **Context**: Introspection output overwhelmed users by mixing structural information, landscape overview, metadata schemas, and concept relationships. Single unified view created cognitive friction for discovery workflows.
- **Solution**: Implemented tiered depth levels via optional parameters (default, detailed, metrics-only)
- **Alternatives**: Single unified view (cognitive overload); separate entry points per depth level (increased API surface); graduated parameters (chosen)
- **Rationale**: Multi-tier approach maintains single discovery entry point, adds optional depth control, optimizes default for initial onboarding, preserves existing behavior

### Ergonomic Template Invocation with Special Syntax
- **Context**: Needed accessible method to invoke preset templates within query composition workflow
- **Solution**: Special syntax for preset invocation rather than flags or dedicated pathways
- **Alternatives**: Flag-based invocation; dedicated entry points per preset type
- **Rationale**: Special syntax provides visual distinction from structured queries, matches familiar patterns from configuration systems, reduces syntax verbosity, preserves single composition entry point

### Parallel Multi-Query Templates Instead of Single Queries
- **Context**: Complex discovery workflows require coordinated queries across multiple sources simultaneously to ensure comprehensive coverage
- **Solution**: Declarative template structures with parallel query execution, automatic result deduplication, and source-specific filtering
- **Alternatives**: Single broad query (incomplete coverage); sequential queries (performance penalty and manual deduplication)
- **Rationale**: Parallel execution provides single round-trip for complex workflows, leverages existing composition infrastructure, automatic deduplication prevents duplicate results

---

## Constraints

### Multi-Source Query Routing Limitation
- **What**: Per-query source filtering requires routing individual queries to different source collections. Initial routing logic operated only on top-level source specification, preventing per-query collection switching.
- **Discovery**: Identified during template testing when workflows required mixing sources from different collections in single multi-query execution.
- **Workaround**: Extended routing layer with full pipeline context (registry, project metadata) to enable source extraction from per-query filters; routing layer interprets source hint and directs query to appropriate collection; source field stripped before vector storage interaction (routing annotation, not storage filter).
- **Impact**: Enables templates to aggregate results from multiple collections in single execution pass.

### Partial Query Failure Handling
- **What**: Multi-query execution with mixed source filters failed when query returns empty or incompatible results.
- **Discovery**: Type mismatches during result aggregation caused pipeline failures.
- **Workaround**: Added resilience layer with exception handling in parallel execution; gracefully skip failed or empty results rather than halting entire workflow.
- **Impact**: Templates remain functional despite individual query failures or partial coverage.

### Source Coverage Gap
- **What**: Only active source collection indexed (144 chunks indexed). Historical and early-phase sources contain minimal indexed content, limiting template effectiveness.
- **Discovery**: Template testing shows all indexed concepts tagged with current phase only; queries for other phases return empty results.
- **Impact**: Templates can query historical sources but return empty results. Complete artifact discovery requires backfill of historical source content.
- **Future Work**: Index additional sources to enable complete lifecycle pattern tracking across all phases.

---

## Patterns

### Pattern: Progressive Disclosure for System Introspection
- **Pattern**: Tiered depth levels for discovery interface
- **When**: Complex system needs to balance completeness with usability for new users
- **Approach**: Multiple tiers - default (essential structure + overview), detailed (complete topology), metrics-only (statistics)
- **Why**: New users get quick start with essentials, experienced users access complete information, monitoring systems get metrics
- **Benefit**: Single discovery entry point serves multiple user personas without cognitive overload
- **Reusable**: Any system offering introspection should consider progressive depth matching user expertise levels

---

### Pattern: Presets as Parallel Multi-Query Templates
- **Pattern**: Declarative workflow templates bundling parallel multi-query execution
- **When**: Repeated workflows require coordinated queries across multiple sources
- **Approach**: Template specifications with variable substitution, per-query source directives, automatic deduplication
- **Why**: Single preset invocation executes complex workflow (multiple coordinated queries)
- **Benefit**: Templating enables workflow reuse; parallel execution provides performance; single invocation hides complexity
- **Reusable**: Any system with granular query primitives can expose ergonomic templates layered on top

---

## Failures

### Cross-Source Query Routing Without Pipeline Context
- **Attempted**: Per-query source filtering within multi-query composition without full routing context
- **Why Failed**: Routing layer lacked metadata context to make per-query collection decisions; all queries routed to same source
- **Lesson**: Multi-source routing requires full execution context (metadata, project scope) propagated through entire composition pipeline to enable per-query source switching
- **Resolution**: Extended composition layer signature to thread full context through routing pipeline

---

## Implementation

### Architecture

Introspection system implements multi-tier disclosure model:

1. **Default tier** - Essential structure and overview (onboarding-optimized): exposes system capabilities, available templates, coverage summary with aggregate metrics
2. **Detailed tier** - Complete topology view: exposes all discoverable concepts with coverage indicators, shows concept relationships and distribution
3. **Metrics tier** - Coverage statistics only: minimal output with aggregate counts and averages

Preset template library wraps parallel multi-query execution with:
- Template-based variable substitution (topic, artifact, concept, scope)
- Per-query source routing (enables cross-collection aggregation)
- Automatic deduplication and result merging
- Multiple built-in workflow templates enabling: artifact lifecycle archaeology, design rationale discovery, failure pattern analysis, scattered discussion synthesis, temporal concept tracking

### Code Signatures

**Multi-Tier Discovery Functions**
```
discover_essential_structure():
  Returns system capabilities, template catalog, aggregate coverage metrics

discover_complete_topology():
  Returns all discoverable concepts with coverage details and relationships

discover_coverage_metrics():
  Returns aggregate counts and statistical summaries
```

**Template Loading and Composition**
```
load_preset_template(template_identifier, user_input):
  1. Retrieve template specification
  2. Substitute variables with user input
  3. Return composed query configuration ready for execution
```

**Multi-Source Query Routing**
```
execute_composed_search(query_specification, source_filter, execution_context):
  1. Extract source directive from query filter
  2. Route query to appropriate source collection
  3. Remove source directive from vector storage filter (routing hint, not data filter)
  4. Execute query with graceful failure handling for partial results
  5. Return results with error state tracking
```

## Audit

### Created
- Preset template: artifact lifecycle archaeology
- Preset template: design phase rationale discovery
- Preset template: failure and constraint analysis
- Preset template: cross-document synthesis workflow
- Preset template: temporal concept evolution tracking

### Modified
- Discovery interface: Added 3 tiered discovery functions (~250 lines total)
  - Default tier for onboarding scenarios
  - Detailed tier for complete topology
  - Metrics tier for coverage monitoring
- Command routing: Updated preset invocation parsing (~60 lines); added template loading and substitution helper
- Query composition: Per-source routing logic (~25 lines) enabling per-query collection switching

### Configuration
- Backward compatible: existing query parameters still function
- New parameters: depth control for discovery interface
- New syntax: special notation for preset invocation

### Deployment
- No new external dependencies
- Interface updates maintain version compatibility
- Preset templates are configuration specifications, not executable code
