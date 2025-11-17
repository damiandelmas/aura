---
schema_version: "v3_adaptive"
type: "pattern.multi-source-composition"
status: "completed"
keywords: "multi-source routing composition filtering field-selection signal-separation honest-defaults discovery-driven"
session_id: "ee1bcc0b-50c7-4352-b1fa-92872f876d87"
timestamp: "2025-11-17T12:27:00-0800"
---

# Multi-Source Composition + Signal Filtering

## Core Problem
Heterogeneous data sources (conversation logs, context artifacts) cannot be queried in a single operation. Result sets contain high-noise metadata that obscures meaningful signals.

## Solution Overview
Implement source-aware query routing at composition layer. Separate result filtering from retrieval logic. Replace confidence-based defaults with evidence-based data inclusion.

## Principles

### Multi-Source Query Routing
- **Context**: Individual query execution targets only one data source type, forcing external choreography
- **Solution**: Composition layer receives source registry and project context, enabling per-query source detection and routing
- **Mechanism**: Source identifier acts as routing metadata, stripped before reaching storage layer, preserving clean data flow
- **Benefit**: Single operation supports heterogeneous source mixing; external systems see unified result set

### Signal Separation via Data Typing
- **Context**: Mixed information types (primary records, thinking artifacts, code changes) collapse into single query result, reducing interpretability
- **Solution**: Split unified queries into multiple typed queries, each with dedicated retrieval parameters
- **Benefit**: Downstream consumers distinguish signal types without post-processing; clearer intent in query definitions

### Evidence-Based Defaults (Honest Null Over Confident Falsehood)
- **Context**: Systems make declarative claims about data characteristics (temporal relationships, validity states) based on absence of contradicting evidence
- **Solution**: Remove all default generation mechanisms that aren't grounded in explicit evidence
- **Consequence**: Return empty/null states rather than plausible but unvalidated inferences
- **Rationale**: Prevents cascading misinformation where dependent systems treat inference-defaults as factual data

### Discovery-Driven Pattern Extraction
- **Context**: Assembly and synthesis patterns are codified before experimental validation
- **Solution**: Build minimal retrieval primitives; run multiple experimental composition strategies; evaluate results; extract validated patterns; codify only winners
- **When to Apply**: Domains where optimal combination strategies are context-dependent or not obvious upfront
- **Benefit**: Captures organic, context-specific patterns rather than imposing a priori designs

## Architecture Pattern

### Multi-Source Routing Flow
1. Composition orchestrator receives registry (source definitions) and project context
2. For each query operation: inspect source specification
3. Route to appropriate data collection based on source routing rules
4. Strip source specification (routing metadata only) before storage query
5. Aggregate results from multiple sources in sequence received
6. Apply result filtering to final set

### Result Filtering Pattern
1. Retrieve complete result set from storage
2. Define explicit inclusion set (high-signal fields: identifiers, relevance scores, content, necessary metadata)
3. Define explicit exclusion set (noise fields: session-level aggregates, unvalidated state flags, redundant duplicates)
4. Transform each result: keep only inclusion-set fields
5. Return cleaned, ordered result set

## Pattern Applications

### When to Use Multi-Source Routing
- Multiple data sources with semantic distinctions
- Need for single-operation queries spanning sources
- Source-aware composition logic required
- Clean separation between routing and storage layers

### When to Use Signal Separation via Typing
- Mixed information types in single result stream
- Downstream systems need type discrimination without post-processing
- Query intent benefits from explicit type constraints
- Retrieval parameters differ by information type

### When to Use Evidence-Based Defaults
- Building infrastructure consumed by autonomous systems
- Long-term canonical data storage (defaults become facts)
- Need to prevent inference chains that amplify misinformation
- Systems where null/empty is semantically valid

### When to Use Discovery-Driven Assembly
- Optimal combination patterns are unknown or context-dependent
- Experimentation infrastructure exists
- Multiple plausible composition strategies to evaluate
- Pattern extraction from successful experiments is feasible

## Decision Tree

**Should you implement multi-source routing?**
- If: Multiple distinct data sources + single-operation queries needed
- Then: Implement source-aware composition layer
- Else: Implement traditional per-source query chains

**Should you separate signals via typing?**
- If: Single result stream mixes multiple information types + downstream consumers need discrimination
- Then: Split into typed sub-queries
- Else: Keep unified query

**Should you remove confidence-based defaults?**
- If: Data will be consumed by autonomous systems or stored long-term
- Then: Remove all defaults; use evidence-only data
- Else: Conservative defaults acceptable

**Should you adopt discovery-driven assembly?**
- If: Optimal patterns are unknown + experimentation is feasible
- Then: Build primitives, run experiments, extract patterns, codify winners
- Else: Design patterns upfront based on domain knowledge

## Implications

### Architecture Simplification
- Remove template/generation systems that make unvalidated claims
- Replace with explicit filtering and evidence-based output
- Defer codification until patterns are validated

### Shift in Development Workflow
- Early stage: Build minimal retrieval primitives
- Mid stage: Experiment with multiple composition strategies
- Late stage: Extract successful patterns into reusable components
- Final stage: Codify validated patterns

### Data Quality and Trust
- Systems consuming output can distinguish evidence from inference
- Absence of data is not confused with evidence of absence
- Autonomous agents build on factual foundation rather than plausible fiction

## Related Patterns
- Single Responsibility Separation (routing vs. retrieval vs. filtering)
- Type-Based Signal Discrimination
- Evidence-Based Data Systems
- Experimental Pattern Discovery
- Metadata-Driven Composition
