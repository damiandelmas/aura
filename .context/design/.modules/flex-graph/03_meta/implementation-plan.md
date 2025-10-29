# FlexGraph Phase 6.5: Compositional Primitives + Context-Aware Templates

**Implementation Plan for AI Agent**

---

## Context

**What exists (Phase 6-7 MVP):**
- ✅ Basic primitives: `get_siblings()`, `get_genealogy()`, `get_temporal()`, `cross_phase_search()`
- ✅ Compose orchestrator: Calls primitives based on config
- ✅ Basic templates: `genealogy.j2`, `timeline.j2`
- ⚠️ **Problem:** All-or-nothing retrieval, no filtering, no context signals

**What we're building:**
- Parameterized primitives (filter by section_type, order, limit)
- Metadata enrichment (temporal position, confidence signals)
- Context-aware templates (show genealogical position for AI comprehension)

**Why this matters:**
- Chunks go to AI agents (Claude, future agents)
- Structure affects AI comprehension of relationships
- 10 chunks with same headers = no context about which is current, which failed, which superseded

---

## Step 1: Parameterized Primitives (~140 lines, 2 hours)

### Goal
Enable compositional flexibility: agents can filter, order, and limit results.

### Current State

```python
# primitives/discovery.py (line ~14)
def get_siblings(collection_name, chunk_id, client, encoder):
    """Returns ALL siblings - no control"""
    siblings = scroll(filter={'file_path': file_path}, limit=100)
    return siblings  # All 17+ siblings, random order
```

### Target State

```python
def get_siblings(
    collection_name,
    chunk_id,
    section_types=None,      # NEW: ["Patterns", "Failures"]
    order_by='section_level', # NEW: 'timestamp', 'section_level'
    limit=None,               # NEW: Top 3 only
    has_rationale=None,       # NEW: Quality filter
    client=None,
    encoder=None
):
    """Returns filtered, ordered, limited siblings"""
    # Build Qdrant filter with section_types
    # Order by specified field
    # Limit results
    return filtered_siblings
```

### Implementation Details

**File:** `imem/src/imem/primitives/discovery.py`

**Function 1: `get_siblings()` (lines 14-68)**

Add parameters and filtering logic:

```python
from qdrant_client.models import MatchAny

def get_siblings(
    collection_name,
    chunk_id,
    section_types=None,      # List[str]: e.g., ["Patterns", "Failures"]
    order_by='section_level', # str: 'timestamp', 'section_level', 'score'
    limit=None,               # int: e.g., 3
    has_rationale=None,       # bool: Filter by has_rationale metadata
    client=None,
    encoder=None
):
    if client is None:
        client = QdrantClient(host=config.qdrant_host, port=config.qdrant_port)

    # Get target chunk
    target = client.retrieve(collection_name=collection_name, ids=[chunk_id])
    if not target:
        return []

    file_path = target[0].payload.get('file_path')
    if not file_path:
        return []

    # Build filter conditions
    must_conditions = [
        FieldCondition(key='file_path', match=MatchValue(value=file_path))
    ]

    # Add section_type filter if specified
    if section_types:
        must_conditions.append(
            FieldCondition(key='section_type', match=MatchAny(any=section_types))
        )

    # Add quality filter if specified
    if has_rationale is not None:
        must_conditions.append(
            FieldCondition(key='has_rationale', match=MatchValue(value=has_rationale))
        )

    scroll_filter = Filter(must=must_conditions)

    # Scroll with filter
    results, _ = client.scroll(
        collection_name=collection_name,
        scroll_filter=scroll_filter,
        limit=limit or 100,
        with_payload=True,
        with_vectors=False
    )

    # Convert to standard format
    siblings = [
        {
            'id': str(point.id),
            'payload': point.payload,
            'score': 0.9
        }
        for point in results
        if str(point.id) != chunk_id
    ]

    # Order results
    if order_by == 'timestamp':
        siblings.sort(key=lambda s: s['payload'].get('timestamp', ''), reverse=True)
    elif order_by == 'section_level':
        siblings.sort(key=lambda s: s['payload'].get('section_level', 999))

    return siblings
```

**Function 2-4: Apply same pattern to other primitives**

Update `get_temporal()`, `get_genealogy()`, `cross_phase_search()` with similar parameters where applicable.

---

**File:** `imem/src/imem/compose.py`

**Function: `_enrich_with_discovery()` (lines 167-208)**

Update to support dict config:

```python
async def _enrich_with_discovery(collection_name, results, discovery_config, client, encoder):
    """Execute discovery stage with parameterized primitives"""

    async def enrich_single_result(result):
        chunk_id = result['id']
        tasks = []
        keys = []

        # Handle siblings config (bool or dict)
        if discovery_config.get('siblings'):
            sibling_config = discovery_config['siblings']

            if isinstance(sibling_config, bool):
                # Legacy: Just true/false
                tasks.append(asyncio.to_thread(get_siblings, collection_name, chunk_id, client, encoder))
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
                    client=client,
                    encoder=encoder
                ))
            keys.append('siblings')

        # Handle genealogy config (similar pattern)
        if discovery_config.get('genealogy'):
            genealogy_config = discovery_config['genealogy']

            if isinstance(genealogy_config, bool):
                tasks.append(asyncio.to_thread(get_genealogy, collection_name, chunk_id, client, encoder))
            else:
                tasks.append(asyncio.to_thread(
                    get_genealogy,
                    collection_name,
                    chunk_id,
                    order_by=genealogy_config.get('order_by', 'timestamp'),
                    limit=genealogy_config.get('limit'),
                    client=client,
                    encoder=encoder
                ))
            keys.append('genealogy')

        # Handle temporal config
        if discovery_config.get('temporal'):
            temporal_config = discovery_config['temporal']

            if isinstance(temporal_config, bool):
                direction = 'after'
            else:
                direction = temporal_config.get('direction', 'after')

            tasks.append(asyncio.to_thread(get_temporal, collection_name, chunk_id, direction, client, encoder))
            keys.append('temporal')

        # Handle cross_phase config
        if discovery_config.get('cross_phase'):
            cross_phase_config = discovery_config['cross_phase']

            if isinstance(cross_phase_config, str):
                # Legacy: Just phase name
                target_phase = cross_phase_config
                section_types = None
            else:
                # New: Dict with parameters
                target_phase = cross_phase_config['phase']
                section_types = cross_phase_config.get('section_types')

            tasks.append(asyncio.to_thread(cross_phase_search, collection_name, chunk_id, target_phase, client, encoder))
            keys.append('cross_phase')

        # Execute all discovery operations in parallel
        if tasks:
            values = await asyncio.gather(*tasks)
            for key, value in zip(keys, values):
                result[key] = value

        return result

    # Enrich all results in parallel
    enriched_results = await asyncio.gather(*[enrich_single_result(r) for r in results])

    return enriched_results
```

### Success Criteria

**Test config works:**
```json
{
  "search": {"text": "authentication", "limit": 1},
  "discovery": {
    "siblings": {
      "section_types": ["Patterns", "Failures"],
      "order_by": "timestamp",
      "limit": 3
    }
  }
}
```

**Returns:** Only Patterns and Failures sections, ordered by timestamp, top 3 only.

**Backward compatibility:** Boolean config still works:
```json
{"discovery": {"siblings": true}}
```

---

## Step 2: Metadata Enrichment (~50 lines, 1 hour)

### Goal
Add temporal position and confidence signals to help AI understand genealogical context.

### Implementation

**File:** `imem/src/imem/compose.py`

**Add new function after `_enrich_with_discovery()`:**

```python
def _enrich_metadata(results):
    """Add temporal position and confidence signals"""

    for result in results:
        # Detect temporal position
        result['temporal_position'] = _detect_temporal_position(result)

        # Calculate confidence signals
        result['confidence'] = {
            'has_rationale': result['payload'].get('has_rationale', False),
            'has_alternatives': result['payload'].get('has_alternatives', False),
            'semantic_score': result.get('score', 0),
            'continuation_count': _count_continuations(result)
        }

    return results


def _detect_temporal_position(result):
    """Detect if this is current thrust, superseded, or failed branch"""

    # Check if in Failures section
    if result['payload'].get('section_type') == 'Failures':
        return 'failed_branch'

    # Check temporal continuations
    temporal = result.get('temporal', [])
    if not temporal:
        return 'current_thrust'  # No temporal = likely current

    # Count how many temporal chunks are AFTER this one
    result_timestamp = result['payload'].get('timestamp', '')
    later_chunks = [t for t in temporal if t['payload'].get('timestamp', '') > result_timestamp]

    if len(later_chunks) > 2:
        return 'superseded'  # Many later chunks = old direction
    elif len(later_chunks) > 0:
        return 'evolved'  # Some later = evolved from this
    else:
        return 'current_thrust'  # No later = current direction


def _count_continuations(result):
    """Count temporal chunks that continue this direction"""
    temporal = result.get('temporal', [])
    if not temporal:
        return 0

    result_timestamp = result['payload'].get('timestamp', '')
    return len([t for t in temporal if t['payload'].get('timestamp', '') > result_timestamp])
```

**Update `compose()` function to call enrichment:**

```python
async def compose(collection_name, config_dict, client=None, encoder=None):
    # ... existing code ...

    # Stage 2: Discovery (if requested)
    if config_dict.get('discovery'):
        results = await _enrich_with_discovery(...)

    # NEW: Stage 2.5: Metadata enrichment
    results = _enrich_metadata(results)

    # Stage 3: Graph (if requested)
    if config_dict.get('graph'):
        results = _apply_graph_operations(...)

    # ... rest of function ...
```

### Success Criteria

**Results include metadata:**
```json
{
  "temporal_position": "current_thrust",
  "confidence": {
    "has_rationale": true,
    "continuation_count": 3,
    "semantic_score": 0.89
  }
}
```

---

## Step 3: Context-Aware Template (~50 lines, 30 min)

### Goal
Prove the full concept: Template uses metadata to structure chunks for AI comprehension.

### Implementation

**File:** `imem/templates/story-context.j2` (NEW FILE)

```jinja2
{# Context-aware template showing genealogical position #}

{% set primary = results[0] %}

{# Show temporal position with appropriate styling #}
{% if primary.temporal_position == "current_thrust" %}
# 🟢 Current Direction (Active)
{% elif primary.temporal_position == "superseded" %}
# ⚠️ Superseded Direction (Context Only)
{% elif primary.temporal_position == "failed_branch" %}
# ❌ Failed Branch (Don't Suggest)
{% elif primary.temporal_position == "evolved" %}
# 🔄 Evolved Direction (Continued Later)
{% endif %}

## {{ primary.payload.section_name }}

**Metadata:**
- 📅 {{ primary.payload.timestamp }}
- 📊 Semantic Score: {{ "%.3f"|format(primary.confidence.semantic_score) }}
{% if primary.confidence.continuation_count > 0 %}
- ⚡ Active Thrust: {{ primary.confidence.continuation_count }} continuations
{% endif %}
{% if primary.confidence.has_rationale %}
- ✅ Has Full Rationale
{% endif %}

---

### Content

{{ primary.payload.content }}

---

{% if primary.siblings %}
{% set failures = [] %}
{% set patterns = [] %}
{% set decisions = [] %}

{% for sibling in primary.siblings %}
  {% if sibling.payload.section_type == 'Failures' %}
    {% set _ = failures.append(sibling) %}
  {% elif sibling.payload.section_type == 'Patterns' %}
    {% set _ = patterns.append(sibling) %}
  {% elif sibling.payload.section_type == 'Decisions' %}
    {% set _ = decisions.append(sibling) %}
  {% endif %}
{% endfor %}

{% if failures %}
## ❌ Failed Approaches (Don't Suggest)

{% for failure in failures[:3] %}
### {{ failure.payload.section_name }}
📅 {{ failure.payload.timestamp }} | Abandoned

{{ failure.payload.content[:300] }}...

{% endfor %}
{% endif %}

{% if decisions %}
## ✅ Related Decisions

{% for decision in decisions[:3] %}
### {{ decision.payload.section_name }}
{% if decision.payload.has_rationale %}🎯 Has Rationale | {% endif %}📅 {{ decision.payload.timestamp }}

{{ decision.payload.content[:300] }}...

{% endfor %}
{% endif %}

{% if patterns %}
## 📋 Extracted Patterns (Reusable)

{% for pattern in patterns[:3] %}
### {{ pattern.payload.section_name }}

{{ pattern.payload.content[:200] }}...

{% endfor %}
{% endif %}

{% endif %}

{% if primary.temporal %}
## 🕐 Temporal Evolution

{% for temporal in primary.temporal[:5] | sort(attribute='payload.timestamp') %}
### {{ temporal.payload.timestamp }}: {{ temporal.payload.section_name }}
**Score:** {{ "%.3f"|format(temporal.score) }}
{% if temporal.payload.timestamp < primary.payload.timestamp %}
⏮️ Earlier in genealogy
{% else %}
⏭️ Later continuation
{% endif %}

{{ temporal.payload.content[:200] }}...

{% endfor %}
{% endif %}

---

## Context Summary

- **Genealogical Position:** {{ primary.temporal_position }}
- **Siblings Found:** {{ primary.siblings|length if primary.siblings else 0 }}
  - Failures: {{ failures|length if failures else 0 }}
  - Patterns: {{ patterns|length if patterns else 0 }}
  - Decisions: {{ decisions|length if decisions else 0 }}
- **Temporal Evolution:** {{ primary.temporal|length if primary.temporal else 0 }} related chunks
{% if primary.confidence.continuation_count > 0 %}
- **Active Direction:** This thrust continues in {{ primary.confidence.continuation_count }} later chunks
{% endif %}

*Structure optimized for AI agent comprehension of genealogical context.*
```

### Success Criteria

**Query returns structured output:**
```bash
imem compose '{
  "search": {"text": "authentication", "limit": 1},
  "discovery": {
    "siblings": {"section_types": ["Failures", "Patterns"], "order_by": "timestamp"},
    "temporal": true
  },
  "output": {"template": "story-context"}
}'
```

**Output shows:**
- Temporal position (🟢 Current / ⚠️ Superseded / ❌ Failed)
- Confidence signals (continuation count, rationale status)
- Structured sections (Failures first, then Patterns)
- Temporal evolution with before/after indicators

---

## Testing Plan

### Test 1: Parameterized Siblings
```bash
imem compose '{
  "search": {"text": "JWT", "limit": 1},
  "discovery": {
    "siblings": {
      "section_types": ["Patterns"],
      "order_by": "timestamp",
      "limit": 2
    }
  }
}'
```

**Expected:** Only 2 Pattern sections, ordered by timestamp.

---

### Test 2: Backward Compatibility
```bash
imem compose '{
  "search": {"text": "JWT", "limit": 1},
  "discovery": {"siblings": true}
}'
```

**Expected:** All siblings (backward compatible with Phase 6-7).

---

### Test 3: Context-Aware Template
```bash
imem compose '{
  "search": {"text": "authentication", "limit": 1},
  "discovery": {
    "siblings": {"section_types": ["Failures", "Patterns"]},
    "temporal": true
  },
  "output": {"template": "story-context"}
}'
```

**Expected:**
- Shows temporal position (🟢/⚠️/❌)
- Failures listed separately with "Don't Suggest" warning
- Patterns shown as reusable
- Temporal evolution with genealogical position

---

## Validation Checklist

- [ ] Step 1: Parameterized primitives work
  - [ ] `get_siblings()` accepts section_types, order_by, limit
  - [ ] Config `{"siblings": {"section_types": ["Patterns"], "limit": 3}}` works
  - [ ] Backward compatibility: `{"siblings": true}` still works

- [ ] Step 2: Metadata enrichment works
  - [ ] Results include `temporal_position` field
  - [ ] Results include `confidence` object
  - [ ] Temporal position detection accurate (current vs superseded vs failed)

- [ ] Step 3: Context template works
  - [ ] Template renders with temporal position indicators
  - [ ] Failures shown with ❌ and "Don't Suggest"
  - [ ] Continuation count displayed for active thrusts
  - [ ] Temporal evolution shows before/after context

---

## Files to Modify

1. `imem/src/imem/primitives/discovery.py` (~100 lines changed)
2. `imem/src/imem/compose.py` (~90 lines added/changed)
3. `imem/templates/story-context.j2` (~150 lines new file)

**Total: ~240 lines, ~3.5 hours**

---

## Success Definition

**After implementation, this query:**
```bash
imem compose '{
  "search": {"text": "authentication patterns", "limit": 1},
  "discovery": {
    "siblings": {"section_types": ["Failures", "Patterns"], "order_by": "timestamp", "limit": 3},
    "temporal": {"direction": "both"}
  },
  "output": {"template": "story-context"}
}'
```

**Returns chunks structured for AI comprehension showing:**
1. **Genealogical position** - Which direction is current vs superseded vs failed
2. **Temporal context** - Evolution over time with before/after signals
3. **Confidence signals** - Continuation count, rationale status
4. **Structured sections** - Failures separate from patterns, with appropriate warnings

**This enables AI agents to:**
- Understand current development direction
- Avoid suggesting failed approaches
- See full genealogical context
- Give better advice based on complete picture

---

## Notes for Implementation

**Order matters:**
1. Do Step 1 first (primitives) - enables everything else
2. Then Step 2 (metadata) - adds context signals
3. Finally Step 3 (template) - proves the concept

**Backward compatibility:**
- Keep boolean config working (`{"siblings": true}`)
- Only use new features if dict config provided

**Error handling:**
- If section_types filter returns nothing, fall back to all siblings
- If order_by field doesn't exist, skip ordering
- Default to safe behavior

**Performance:**
- Qdrant does filtering/ordering (efficient)
- Async execution maintained (parallel operations)
- No additional queries needed (metadata from existing results)

---

## Future Enhancements (Not in This Plan)

- Graph topology detection (linear vs hub vs arc)
- Dynamic template selection based on topology
- Usage tracking for pattern discovery
- More specialized templates (anti-patterns, pattern-library, etc.)

**This plan focuses on core capability: compositional flexibility + context-aware serving.**
