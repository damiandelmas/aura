---
type: changelog.implementation
subtype: feature
phase: develop
session_id: current
timestamp: 2025-11-17T12:27:00-0800
---

# Multi-Source Routing + Clean JSON Output

## Summary

Enabled true multi-source lineage queries (conversations + context in single compose call) and cleaned output by stripping noise fields and removing premature templates. Foundation solid for AI-driven assembly pattern discovery.

---

## Changes

### 1. Multi-Source Query Routing

**Problem**: Lineage preset couldn't mix conversation + context sources in single query.

**Solution**: Per-query source routing infrastructure.

**Implementation**:
- `compose()` accepts `registry` + `project_root` params
- `_execute_search()` detects `source` filter per query, routes to correct collection
- `source` filter stripped before Qdrant (routing-only metadata)
- Works for both multi-query arrays AND single queries

**Files Modified**:
- `imem/src/imem/compose.py` (lines 16-20, 58, 90-161)
- `imem/src/imem/cli.py` (line 607)

**Test**:
```bash
imem compose @lineage chunking
# Returns: 3 conversation + 2 context = 5 mixed results
```

---

### 2. Chunk_Type Granularity in @lineage

**Enhancement**: Split conversation query into 3 separate chunk_type queries.

**Before**:
```json
{"text": "{{artifact}}", "filters": {"source": "conversation"}, "limit": 3}
```

**After**:
```json
{"text": "{{artifact}}", "filters": {"source": "conversation", "chunk_type": "message"}, "limit": 2},
{"text": "{{artifact}}", "filters": {"source": "conversation", "chunk_type": "thinking"}, "limit": 2},
{"text": "{{artifact}}", "filters": {"source": "conversation", "chunk_type": "patch"}, "limit": 2}
```

**Benefit**: Better signal separation (messages ≠ patches ≠ thinking blocks).

**File Modified**: `imem/src/imem/presets/lineage.json` (lines 14-16)

---

### 3. Template System Removal

**Decision**: Scrap all templates until assembly patterns proven via AI experiments.

**Rationale**:
- Templates made unvalidated claims (`temporal_position = "current_thrust"` from absence of data)
- Better to serve honest JSON than misleading narratives
- Strategy shift: Build eval framework → spawn AI experiments → extract winning patterns → codify

**Deleted**:
- `imem/templates/story-context.j2` (made confident claims on unreliable data)
- `imem/templates/genealogy.j2`
- `imem/templates/timeline.j2`
- `imem/templates/timeline-lineage.j2`

**Updated**: `lineage.json` - removed `"output": {"template": "timeline-lineage"}`

**Infrastructure Kept**: `_render_template()` function in compose.py (ready for future proven templates)

---

### 4. Result Filtering & Intelligent Ordering

**Problem**: Results returned 35+ fields including noise (session-level stats, unvalidated flags, redundant data).

**Solution**: Post-query filter strips to ~10 relevant fields in intelligent order.

**Implementation**: `_filter_results()` function (compose.py:404-474)

**Fields Kept**:
```
1. id, score
2. source, chunk_type/phase
3. header_path, section_name
4. content
5. session_id, file_path, timestamp/start_time
6. role (if exists)
7. siblings, genealogy, temporal (if discovery ran)
```

**Fields Stripped**:
- `has_changelog`, `changelog_path` (always null)
- `duration_minutes`, `message_count` (session-level, not chunk)
- `has_context`, `has_solution`, `has_rationale`, `has_alternatives`, `has_approach`, `has_benefits`, `has_drawbacks` (unvalidated AI self-reports)
- `word_count`, `char_count` (noise)
- `section_type` (redundant with header_path)
- `section_level`, `schema_version`, `header_path` internals
- `temporal_position`, `confidence` (unreliable defaults)

**File Modified**: `imem/src/imem/compose.py` (lines 83-90, 404-474)

---

## Architecture Insights

### Honest Defaults Matter

**Bad Pattern** (removed):
```python
if not temporal:
    return 'current_thrust'  # Lying when we don't have data
```

**Good Pattern**:
```python
if not temporal:
    return None  # Admit we don't know
```

Templates were making claims ("This is the CURRENT approach") based on absence of evidence, not presence of contradictory evidence. This misleads AI agents.

---

### Discovery-Driven Assembly

**Old Approach**: Design templates → hope they're useful
**New Approach**: Primitives → AI experiments → observe what works → codify

**Reasoning** (from `.testing/251108-1501_lineage/`):
- AI successfully assembled compose.py lineage using raw primitives (git log, glob, read)
- No templates, no predetermined assembly
- Result: Perfect narrative from first principles

**Strategy**: Build eval framework for "good lineage", spawn 10 AI experiments with different primitive combos, extract best practices from winners, codify as presets/templates.

---

## Testing

**Multi-source routing**:
```bash
imem compose @lineage chunking
# ✅ Returns 4 conversation + 2 context chunks
```

**Chunk_type filtering**:
```bash
imem compose '{"search": {"text": "database", "filters": {"source": "conversation", "chunk_type": "message"}, "limit": 3}}'
# ✅ Returns only message chunks (no mixing with thinking/patches)
```

**Clean output**:
```bash
imem compose @lineage chunking | jq '.results[0] | keys'
# ✅ Returns ~10 fields (was 35+)
```

---

## Current State

**Working**:
- ✅ Multi-source routing (conversation + context in single query)
- ✅ Chunk_type granularity (message/thinking/patch separation)
- ✅ Discovery primitives (siblings, genealogy, temporal)
- ✅ Clean JSON output (no noise, no lies)

**Removed**:
- ❌ Templates (lying about validation state)

**Next Phase**:
1. Build eval framework (what's "good lineage"?)
2. Spawn AI experiments with different retrieval patterns
3. Extract winning patterns
4. Codify as proven templates/presets

**Foundation solid. Assembly layer awaits discovery through experimentation.**

---

## Files Changed

**Modified**:
- `imem/src/imem/compose.py` (+72 lines: routing, filtering)
- `imem/src/imem/cli.py` (1 line: pass registry context)
- `imem/src/imem/presets/lineage.json` (chunk_type split, template removal)

**Deleted**:
- `imem/templates/story-context.j2`
- `imem/templates/genealogy.j2`
- `imem/templates/timeline.j2`
- `imem/templates/timeline-lineage.j2`

**Net**: +70 LOC, -4 template files, cleaner architecture
