---
schema_version: "v3_adaptive"
type: "pattern.compositional-memory-enrichment"
status: "completed"
keywords: "primitives metadata enrichment context-aware filtering composition temporal-position genealogy-detection ai-comprehension"
timestamp: "2025-10-29T00:13:00-0700"
session_id: "944609e1-6bef-4bf6-ad68-606ad3ca44e9"
---

# Pattern Mirror: Compositional Memory Enrichment Architecture

## Problem Statement

Memory retrieval systems designed for AI agent consumption face three core challenges:

1. **Retrieval Precision**: All-or-nothing discovery operations return entire result sets without filtering capability, forcing downstream consumers to handle irrelevant data.

2. **Temporal Disambiguation**: Retrieved content lacks signals to distinguish current active directions from superseded approaches, evolved strategies, or failed branches—leaving AI agents unable to prioritize effectively.

3. **AI Comprehension Gaps**: Traditional similarity-based retrieval embeds no decision genealogy or quality signals, causing AI agents to potentially resurface failed approaches or misweight evolved vs. current strategies.

## Architectural Pattern: Layered Filtering with Metadata Enrichment

### Pattern 1: Parameterized Discovery with Backward Compatibility

**Pattern**: Enable optional filtering at the primitive query layer while maintaining compatibility with existing boolean-flag consumers.

**Context**:
- Discovery operations initially support only binary activation (on/off)
- Need to add fine-grained filtering without breaking existing code
- System evolves gradually; multiple versions must coexist

**Solution Structure**:
1. Extend primitive signatures to accept optional filter parameters (type filters, ordering preferences, result limits, quality flags)
2. Maintain boolean config path as legacy mode
3. Detect config type at orchestration layer and route accordingly
4. Apply filters within primitive, before returning results

**Decision Rationale**:
- Avoids breaking changes to existing consumers
- Filters at source (primitive layer) for better performance than post-filtering
- Optional parameters allow simple queries to remain simple while enabling sophisticated queries
- Type detection at orchestration layer keeps decision logic centralized

**Key Principle**: Filter parameters should have sensible defaults that make partial specification possible. A consumer should be able to say "limit results to 3" without specifying sort order, or "get Patterns only" without specifying limits.

**Trade-offs**:
- Increased function signature complexity
- Config type detection adds orchestration logic
- Must maintain two config paths (boolean and dict-based)

---

### Pattern 2: Dict-Based Configuration Over Boolean Flags

**Pattern**: Use structured configuration objects (dict/record) instead of boolean flags to enable compositional filtering specifications.

**Context**:
- Boolean flags scale poorly (each new filter = new boolean parameter)
- Need to support combinations of filters: type+order+limit
- Configuration should be serializable and composable

**Solution Structure**:
```
Legacy: { "siblings": true }
New:    { "siblings": { "types": [...], "order": "key", "limit": N, "quality_flags": {...} } }
```

**Decision Rationale**:
- Dict-based config is naturally extensible (add new filter keys without changing function signatures)
- Allows semantic grouping of related parameters (all sibling filters in one dict)
- Configuration becomes self-documenting (filter intent is explicit)
- Supports composition (filters can be built incrementally)

**Application Pattern**:
- Orchestration layer detects config type (boolean vs. structured)
- Routes to appropriate handler
- Converts dict config to primitive parameters
- Maintains backward compatibility path

---

### Pattern 3: Temporal Position Detection Algorithm

**Pattern**: Classify retrieved content by temporal relationship to query context, enabling AI agents to understand novelty and supersession.

**Context**:
- Content comes with timestamps indicating when it was created/updated
- AI agents need to understand if content represents current direction or historical approach
- Multiple evolution types exist: current (active), evolved (iterated upon), superseded (abandoned), failed (explicitly marked)

**Solution Structure**:
1. Define temporal position categories: `current_thrust | evolved | superseded | failed_branch`
2. Implement detection algorithm:
   - Check explicit failure markers first (if section/category = "Failures" → failed_branch)
   - Count temporal continuations after content timestamp
   - If many continuations (>threshold) → superseded
   - If some continuations → evolved
   - If zero continuations → current_thrust

**Decision Rationale**:
- Continuation count is observable without external metadata (inherent in result set)
- Explicit failure markers catch known anti-patterns
- Categories map to AI agent decision strategies (avoid failed, consider evolved, prioritize current)
- Algorithm is deterministic and traceable

**Thresholds**:
- `superseded`: More than 2 later temporal chunks
- `evolved`: 1-2 later temporal chunks
- `current_thrust`: Zero later chunks

**Key Insight**: Temporal position is a property of the entire knowledge graph context, not just the individual item. Cannot be computed from single item in isolation.

---

### Pattern 4: Context-Aware Output Structure for AI Comprehension

**Pattern**: Embed genealogical signals in output presentation structure rather than expecting AI to infer decision history from content alone.

**Context**:
- AI agents consume retrieved memory and generate suggestions
- Pure semantic similarity provides no decision genealogy
- Preventing AI from resurfacing failed approaches requires explicit marking
- Comprehension improvement comes from presentation structure, not just content

**Solution Structure**:
1. Enrich retrieved results with metadata signals:
   - Temporal position (current/evolved/superseded/failed)
   - Quality indicators (has_rationale, has_alternatives)
   - Confidence metrics (semantic score, continuation count)

2. Organize presentation by decision value:
   - Failures first (with "Don't Suggest" warnings)
   - Patterns (with confidence signals)
   - Decisions (with timestamp and position context)

3. Use visual signals for quick scanning:
   - Failed approaches clearly marked
   - Superseded approaches contextualized
   - Current directions highlighted

**Decision Rationale**:
- Structure aids comprehension for AI consumers (same as humans)
- Genealogical position embedded in presentation prevents misuse
- Visual indicators enable quick filtering at consumption layer
- Explicit "don't suggest" warnings override similarity-based reasoning

**Key Principle**: In AI-comprehension contexts, how information is presented is as important as what information is presented.

---

### Pattern 5: None-Safe Sorting and Null Handling

**Pattern**: Handle null/missing values in sort operations using operator coercion instead of conditional defaults.

**Context**:
- Data stores may contain explicit null values distinct from missing keys
- Sort operations fail when key is null
- Different data stores handle null differently
- Need robust sorting across varied data

**Solution Pattern**:
```
Instead of:  key=lambda x: x.get('field', default)
Use:         key=lambda x: x.get('field') or default
```

**Decision Rationale**:
- `.get(key, default)` only handles missing keys, not explicit nulls
- `or` operator handles both missing and null, coercing to default
- Single pattern replaces conditional logic
- Explicitly documents null-tolerance in code

**Occurrences**:
- Timestamp sorting: `timestamp or ''` (coerce to empty string for comparison)
- Level/hierarchy sorting: `section_level or 999` (coerce to end position)

---

## Reusable Design Principles

### Principle 1: Backward Compatibility Through Layering
When extending query primitives, preserve old behavior paths alongside new ones. Use orchestration layer to detect config type and route appropriately. This allows gradual migration of consumers.

### Principle 2: Sensible Defaults for Optional Parameters
Every optional filter should have a reasonable default behavior. Consumers who specify few parameters shouldn't get "empty" results—they should get well-filtered results with system-chosen good defaults (e.g., chronological order, reasonable limits).

### Principle 3: Temporal Signals as Infrastructure
In systems managing evolving knowledge, make temporal position detection a standard enrichment step, not an afterthought. Classify content by relationship to "now" before returning to consumers.

### Principle 4: Presentation Structure Encodes Semantics
Use output organization (ordering, grouping, visual markers) to embed decision context. This is especially critical for AI agent comprehension—structure constrains reasoning as much as content does.

### Principle 5: Composition Over Accumulation
Build filtering as composable pieces (type filters, order preferences, limits) that can be combined, not as special-case functions for each filter combination.

---

## Architecture Overview

### Layered Structure
```
Discovery Layer (Primitives)
  ↓ Accepts: filter parameters
  ↓ Returns: filtered results

Orchestration Layer (Composition)
  ↓ Detects: config type (bool vs. dict)
  ↓ Routes: to appropriate primitive
  ↓ Extracts: parameters from dict config

Enrichment Layer (Metadata)
  ↓ Analyzes: temporal relationships
  ↓ Detects: position (current/evolved/superseded/failed)
  ↓ Calculates: confidence metrics

Template Layer (Presentation)
  ↓ Renders: enriched results
  ↓ Embeds: genealogical signals
  ↓ Produces: AI-comprehension-optimized output
```

### Data Flow
1. Query arrives with optional filter config (boolean or dict-based)
2. Orchestrator detects config type, extracts parameters
3. Primitives execute with filters applied
4. Results enriched with temporal position, confidence signals
5. Enriched results rendered with context-aware structure
6. Output presented with genealogical signals embedded

---

## Common Failure Modes and Mitigations

### Failure Mode 1: Null-Unsafe Sorting
**Symptom**: Sort operations fail or produce unexpected ordering when data contains explicit nulls

**Root Cause**: Relying on `.get(key, default)` which doesn't handle null values distinct from missing keys

**Mitigation**: Use `or` operator pattern for null-safe defaults: `value or default_value`

**Prevention**: Add null handling to sorting operations as standard practice

---

## Extension Points

1. **Filter Types**: Additional filter parameters can be added to primitives without changing signatures (backward compatible)

2. **Temporal Categories**: New position categories can be added by extending detection algorithm (e.g., "in_review", "blocked")

3. **Confidence Metrics**: New confidence signals can be calculated in enrichment layer and passed to template

4. **Presentation Formats**: Template layer can be extended with new output formats without changing upstream layers

---

## Learning Transfer

This pattern set is applicable to any system managing:
- Evolving knowledge bases or decision logs
- AI agent comprehension from retrieved data
- Query primitives requiring progressive filtering
- Mixed legacy and new consumer code paths
- Temporal or genealogical decision context

Key transfer points:
- Parameterized filtering strategy works in any language with optional parameters
- Temporal position detection applies wherever content has creation timestamps
- Backward compatibility through config type detection works with any structured config format
- Null-safe sorting is language-agnostic data handling technique
- Presentation structure for comprehension applies to any AI consumer
