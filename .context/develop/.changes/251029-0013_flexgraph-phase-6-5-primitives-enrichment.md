---
schema_version: "v3_adaptive"
type: "implementation.parameterized-primitives"
status: "completed"
keywords: "flexgraph primitives metadata enrichment context-aware templates aiUX filtering composition"
timestamp: "2025-10-29T00:13:00-0700"
session_id: "944609e1-6bef-4bf6-ad68-606ad3ca44e9"
---

# FlexGraph Phase 6.5: Parameterized Primitives and Context-Aware AI Memory

## Request
> "ASSESS architecture, recent changes, and implementation plan for FlexGraph Phase 6.5"

## Overview
Implemented Phase 6.5 of compositional memory architecture, closing the gap between documented design and actual implementation. Added parameterized filtering to graph traversal functions, metadata enrichment for temporal position detection, and context-aware output formatting optimized for AI agent comprehension. The work enables surgical memory retrieval with genealogical context signals that help AI agents distinguish current directions from superseded approaches and failed branches.

## Decisions

### Parameterized Primitives with Backward Compatibility
- **Context**: Discovery primitives (`get_siblings`, `get_genealogy`) were all-or-nothing retrieval with no filtering capability
- **Solution**: Added optional parameters (section_types, order_by, limit, has_rationale, has_alternatives) while maintaining backward compatibility with boolean config
- **Rationale**: Enables surgical retrieval ("get top 3 Patterns with rationale") instead of returning all siblings
- **Trade-offs**: Increased function signature complexity, but optional parameters preserve existing usage

### Dict-Based Configuration Over Boolean Flags
- **Context**: Discovery config only supported `{"siblings": true}` boolean flags
- **Solution**: Extended to support both boolean (legacy) and dict-based config `{"siblings": {"section_types": ["Patterns"], "limit": 3}}`
- **Alternatives**: Could have deprecated boolean config entirely, but breaking existing code was unnecessary
- **Benefit**: Compositional filtering without breaking changes

### Temporal Position Detection Algorithm
- **Context**: Need to distinguish current thrust from superseded directions for AI comprehension
- **Solution**: Implemented position detection based on continuation count and section type
- **Approach**: Count temporal chunks after target timestamp - high count indicates superseded, zero indicates current thrust
- **Categories**: current_thrust | superseded | evolved | failed_branch

### Context-Aware Template for AI Comprehension
- **Context**: Traditional RAG returns chunks by similarity with no temporal or quality signals
- **Solution**: Created story-context.j2 template with visual indicators (🟢⚠️❌), structured sections (Failures → Patterns → Decisions), and explicit AI guidance
- **Rationale**: Structure = comprehension for AI agents - embedding genealogical position in presentation
- **Impact**: AI agents can avoid suggesting failed approaches explicitly marked with "Don't Suggest" warnings

## Implementation

### Architecture
1. Primitive layer (`discovery.py`) → Accepts filter parameters, maintains backward compatibility
2. Compose orchestrator (`compose.py`) → Detects config type (bool vs dict), passes parameters to primitives
3. Metadata enrichment stage → Analyzes temporal relationships, adds position/confidence signals
4. Template rendering → Structures output with genealogical context for AI comprehension

### Code Signatures

**Parameterized Primitive** (`imem/src/imem/primitives/discovery.py`)
```python
def get_siblings(collection_name: str, chunk_id: str,
                 section_types: Optional[List[str]] = None,
                 order_by: str = 'section_level',
                 limit: Optional[int] = None,
                 has_rationale: Optional[bool] = None,
                 has_alternatives: Optional[bool] = None,
                 client: Optional[QdrantClient] = None,
                 encoder: Optional[SentenceTransformer] = None):
    # Build filter conditions
    must_conditions = [FieldCondition(key='file_path', match=MatchValue(value=file_path))]

    if section_types:
        must_conditions.append(
            FieldCondition(key='section_type', match=MatchAny(any=section_types))
        )

    # Order results - handle None values
    if order_by == 'timestamp':
        siblings.sort(key=lambda s: s['payload'].get('timestamp') or '', reverse=True)
    elif order_by == 'section_level':
        siblings.sort(key=lambda s: s['payload'].get('section_level') or 999)
```

**Dict-Based Config Handler** (`imem/src/imem/compose.py`)
```python
# Handle siblings config (bool or dict)
if discovery_config.get('siblings'):
    sibling_config = discovery_config['siblings']

    if isinstance(sibling_config, bool):
        # Legacy: Just true/false
        tasks.append(asyncio.to_thread(get_siblings, collection_name, chunk_id,
                                      client=client, encoder=encoder))
    else:
        # New: Dict with parameters
        tasks.append(asyncio.to_thread(
            get_siblings,
            collection_name,
            chunk_id,
            section_types=sibling_config.get('section_types'),
            order_by=sibling_config.get('order_by', 'section_level'),
            limit=sibling_config.get('limit'),
            has_rationale=sibling_config.get('has_rationale'),
            has_alternatives=sibling_config.get('has_alternatives'),
            client=client,
            encoder=encoder
        ))
```

**Temporal Position Detection** (`imem/src/imem/compose.py`)
```python
def _detect_temporal_position(result: Dict[str, Any]) -> str:
    """Detect if this is current thrust, superseded, or failed branch"""

    # Check if in Failures section
    if result['payload'].get('section_type') == 'Failures':
        return 'failed_branch'

    # Count how many temporal chunks are AFTER this one
    temporal = result.get('temporal', [])
    result_timestamp = result['payload'].get('timestamp', '')
    later_chunks = [t for t in temporal if t['payload'].get('timestamp', '') > result_timestamp]

    if len(later_chunks) > 2:
        return 'superseded'  # Many later chunks = old direction
    elif len(later_chunks) > 0:
        return 'evolved'  # Some later = evolved from this
    else:
        return 'current_thrust'  # No later = current direction
```

**Metadata Enrichment** (`imem/src/imem/compose.py`)
```python
def _enrich_metadata(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Add temporal position and confidence signals to results"""

    for result in results:
        result['temporal_position'] = _detect_temporal_position(result)

        result['confidence'] = {
            'has_rationale': result['payload'].get('has_rationale', False),
            'has_alternatives': result['payload'].get('has_alternatives', False),
            'semantic_score': result.get('score', 0),
            'continuation_count': _count_continuations(result)
        }

    return results
```

## Patterns

### aiUX: Structure as Comprehension
- **Pattern**: Embed genealogical context in presentation structure rather than expecting AI to infer it
- **When**: Designing memory retrieval systems for AI agent consumption
- **Approach**: Use visual indicators (🟢⚠️❌), section ordering (Failures first), and explicit metadata (continuation counts) to route attention
- **Benefit**: AI agents make better suggestions because memory system encodes decision genealogy, not just content similarity
- **Example**: Marking failed branches with "❌ Failed Approaches (Don't Suggest)" prevents AI from repeating known mistakes

### Progressive Filtering with Default Behaviors
- **Pattern**: Accept optional filter parameters with sensible defaults, avoid requiring full specification
- **When**: Building composable query primitives
- **Approach**: Default to chronological ordering and reasonable limits (e.g., limit=100 for siblings, limit=200 for genealogy)
- **Benefit**: Simple queries stay simple (`get_siblings(collection, chunk_id)`) while complex queries are possible

### None-Safe Sorting
- **Pattern**: Handle null values in sort keys using `or` operator instead of `.get()` defaults
- **Approach**: `siblings.sort(key=lambda s: s['payload'].get('section_level') or 999)` handles both missing keys and explicit null values
- **Why**: Qdrant can store explicit `null` values, which `.get(key, default)` doesn't handle
- **Occurrences**: Applied to both timestamp and section_level sorting in discovery.py

## Failures

### Section Level Default Parameter
- **Attempted**: Used `.get('section_level', 999)` for sort key default
- **Why Failed**: Explicit `null` values in Qdrant payload return `None`, not the default value, causing comparison errors
- **Lesson**: Use `or` operator for null-safe defaults when sorting: `s['payload'].get('section_level') or 999`
- **Alternative**: Changed to `.get('section_level') or 999` pattern for all sort operations

## Audit

### Modified
- `imem/src/imem/primitives/discovery.py` - Added parameterized filtering to get_siblings() and get_genealogy() (~95 lines modified)
- `imem/src/imem/compose.py` - Added dict-based config handling and metadata enrichment pipeline (~105 lines modified)

### Created
- `imem/templates/story-context.j2` - Context-aware template with genealogical position indicators for AI comprehension (~150 lines)

### Configuration
No environment variables or deployment changes required. Changes are backward compatible with existing boolean config usage.
