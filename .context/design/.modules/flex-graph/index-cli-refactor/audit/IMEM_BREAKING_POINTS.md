# IMEM System: Breaking Points for Collection Name Changes

## Overview

This document identifies every place where collection names, metadata schemas, or configuration changes would break the IMEM system. Use this as a checklist for refactoring toward multi-collection support.

---

## Tier 1: Direct Collection Name References (Safe to Change)

These locations use collection_name as a parameter - they're safe to modify because collection_name is passed through the call chain.

### Search Flow
```
cli.search() → _execute_search() → EnhancedQdrantSearch(collection_name) → client.query_points()
```
**Files:** 
- `/imem/src/imem/cli.py:518` - `collection_name = info['collection']`
- `/imem/src/imem/enhanced.py:136` - `collection_name=self.collection_name`

**Status:** Safe. Collection parameter properly threaded.

### Compose Flow  
```
cli.compose() → compose_pipeline(collection_name) → _execute_search(collection_name)
                                                    → _enrich_with_discovery(collection_name)
                                                    → _apply_graph_operations(collection_name)
```
**Files:**
- `/imem/src/imem/cli.py:267` - `collection_name = info['collection']`
- `/imem/src/imem/compose.py:40` - All stage functions take collection_name

**Status:** Safe. Collection parameter properly threaded.

### Discovery Primitives
```
_enrich_with_discovery() → get_siblings(collection_name)
                        → get_genealogy(collection_name)
                        → get_temporal(collection_name)
                        → cross_phase_search(collection_name)
```
**Files:**
- `/imem/src/imem/primitives/discovery.py` - All functions take collection_name

**Status:** Safe. Collection parameter properly threaded.

---

## Tier 2: Metadata Schema Dependencies (BREAKS SILENTLY)

These locations assume specific metadata fields exist. If fields are missing, queries silently return zero results.

### Critical Field Dependencies

#### 1. `file_path` Field
**Required by:** `get_siblings()` primitives/discovery.py:54
**Breaking when:** Missing from source chunk payload
**Impact:** Sibling discovery returns empty list
**Code:**
```python
# discovery.py:54
FieldCondition(key='file_path', match=MatchValue(value=file_path))
```
**Fix:** Make file_path optional, check before querying

#### 2. `session_id` Field  
**Required by:** `get_genealogy()` primitives/discovery.py:146
**Breaking when:** Missing from source chunk payload OR no chunks with source='conversation'
**Impact:** Genealogy discovery returns empty list, conversation linkage lost
**Code:**
```python
# discovery.py:146
FieldCondition(key='session_id', match=MatchValue(value=session_id))
```
**Fix:** Conditional execution - skip genealogy if field not in schema

#### 3. `timestamp` Field
**Required by:** `get_temporal()` primitives/discovery.py:211, 247-252
**Breaking when:** Missing from multiple chunks
**Impact:** Temporal ordering becomes semantic-only (direction parameter useless)
**Code:**
```python
# discovery.py:211
timestamp = target_payload.get('timestamp') or target_payload.get('created')
# discovery.py:249
if direction == 'after' and point_timestamp <= timestamp:
    continue
```
**Fix:** Graceful degradation - temporal still works, just unordered

#### 4. `phase` Field
**Required by:** `cross_phase_search()` primitives/discovery.py:296
**Breaking when:** Not present in collection schema
**Impact:** Cross-phase search returns empty list
**Code:**
```python
# discovery.py:296
FieldCondition(key='phase', match=MatchValue(value=target_phase))
```
**Fix:** Conditional execution - skip cross_phase_search if field not in schema

#### 5. `section_type` Field
**Required by:** 
- `get_siblings()` filter primitives/discovery.py:61 (optional)
- `_detect_temporal_position()` compose.py:289 (checks for 'Failures')
- CLI taxonomy (hardcoded options) cli.py:79-87

**Breaking when:** Not present in collection, or collection uses different taxonomy values
**Impact:** 
- Silent filter failure if section_types specified
- Wrong temporal position classification
- CLI section filter has no matching documents

**Code:**
```python
# discovery.py:61
if section_types:
    must_conditions.append(
        FieldCondition(key='section_type', match=MatchAny(any=section_types))
    )

# compose.py:289
if result['payload'].get('section_type') == 'Failures':
    return 'failed_branch'
```
**Fix:** 
- Schema registry to validate fields exist
- Adaptive classification logic based on schema
- Dynamic CLI options based on collection schema

#### 6. `has_rationale`, `has_alternatives` Fields
**Required by:** 
- `get_siblings()` filter primitives/discovery.py:65-72 (optional)
- `_enrich_metadata()` compose.py:276-277

**Breaking when:** Not in schema, or ingester doesn't populate
**Impact:** Quality filtering fails silently, confidence signals missing
**Code:**
```python
# discovery.py:65
if has_rationale is not None:
    must_conditions.append(
        FieldCondition(key='has_rationale', match=MatchValue(value=has_rationale))
    )

# compose.py:276
result['confidence'] = {
    'has_rationale': result['payload'].get('has_rationale', False),
```
**Fix:** Null-safe defaults, optional quality signals in template

#### 7. `source` Field
**Required by:** 
- `get_genealogy()` primitives/discovery.py:147
- CLI phase filtering cli.py:523-526

**Breaking when:** Not in schema, or non-changelog docs don't have source field
**Impact:** Genealogy queries fail, phase filtering broken
**Code:**
```python
# discovery.py:147
FieldCondition(key='source', match=MatchValue(value='conversation'))

# cli.py:523
if phase_filter == 'conversations':
    filters['source'] = 'conversation'
```
**Fix:** Schema registry tracks which source values exist in collection

---

## Tier 3: Hardcoded Taxonomy & Configuration (BREAKS VISIBLY)

These are hardcoded assumptions in CLI and config that require code changes for new values.

### 1. Phase Taxonomy (CLI hardcoded - Line 452-454)
**File:** `/imem/src/imem/cli.py:452-454`
**Current Options:** `['develop', 'designate', 'document', 'conversations', 'all']`
**Breaking when:** New phases added to collection without CLI update
**Impact:** New phases inaccessible via `--in` option, always default to 'develop'
**Code:**
```python
@click.option('--in', 'phase_filter',
              type=click.Choice(['develop', 'designate', 'document', 'conversations', 'all']),
              default='develop')
```
**Fix:** Dynamic phase loading from schema

### 2. Section Type Filters (CLI hardcoded - Lines 49-52)
**File:** `/imem/src/imem/cli.py:49-52`
**Current Options:** `['Decisions', 'Constraints', 'Failures', 'Patterns', 'Implementation']`
**Breaking when:** New section types in collection without CLI update
**Impact:** New types can't be filtered via CLI flags
**Code:**
```python
@click.option('--decisions', is_flag=True, help='Only Decision sections')
@click.option('--constraints', is_flag=True, help='Only Constraint sections')
```
**Fix:** Schema registry for section types, dynamic CLI loading

### 3. Layer Taxonomy (CLI hardcoded - Line 456-459)
**File:** `/imem/src/imem/cli.py:456-459`
**Current Options:** `['implementation', 'pattern', 'both']`
**Breaking when:** Collections without layer concept (conversations, static docs)
**Impact:** Layer filter silently ignored for non-develop phases
**Code:**
```python
@click.option('--layer',
              type=click.Choice(['implementation', 'pattern', 'both']),
              default='implementation')
```
**Fix:** Conditional layer filtering based on collection schema

### 4. Vector Model Hardcoded (Config - Line 25-26)
**File:** `/imem/src/imem/config.py:25-26`
**Current Model:** `'intfloat/e5-large-v2'` (1024 dims)
**Breaking when:** Collection created with different model
**Impact:** Named vector queries fail with "vector not found", fallback to unnamed (might fail)
**Code:**
```python
default_vector_name: str = 'e5-large-v2'
default_model: str = 'intfloat/e5-large-v2'
```
**Breaking References:**
- `enhanced.py:31` - Self-initializes with hardcoded model
- `compose.py:140` - Uses config.default_vector_name in query
- `primitives/discovery.py:221` - Uses config.default_vector_name

**Fix:** Vector config stored in collection metadata, loaded per-collection

### 5. Qdrant Connection Hardcoded (Config - Line 11-12)
**File:** `/imem/src/imem/config.py:11-12`
**Current Target:** `localhost:6334`
**Breaking when:** Need multi-cluster or different Qdrant instance
**Impact:** Can't federate collections across instances
**Code:**
```python
qdrant_port: int = 6334
qdrant_host: str = 'localhost'
```
**Breaking References:**
- All files: `QdrantClient(host=config.qdrant_host, port=config.qdrant_port)`

**Fix:** Qdrant config per collection in registry

---

## Tier 4: Template System Dependencies (BREAKS ON MISSING FIELDS)

### Template: `story-context.j2`
**Location:** `/imem/templates/story-context.j2`

**Required Result Fields:**
```
results[0].temporal_position              # Must exist (set by compose.py:272)
results[0].payload.section_name           # Must exist in metadata
results[0].payload.timestamp              # Used in lines 19, 94
results[0].confidence.semantic_score      # Set by compose.py:278
results[0].confidence.continuation_count  # Set by compose.py:279
results[0].confidence.has_rationale       # Set by compose.py:276
results[0].siblings[]                     # May be empty (checked line 39)
results[0].temporal[]                     # May be empty (checked line 91)
results[0].genealogy[]                    # May be empty (checked line 108)
```

**Breaking when:** 
- `section_name` not in payload (line 16)
- `timestamp` not in payload (line 19)

**Graceful degradation:** Template uses `{% if primary.siblings %}` so empty discovery is OK

**Fix:** Defensive template with fallbacks for missing fields

---

## Tier 5: Ingestion System Assumptions

**File:** `/imem/src/imem/ingest.py`

### Metadata Schema Assumed During Ingestion
```python
payload = {
    'content': str,
    'file_path': str,
    'file_hash': str (MD5),
    'phase': ['develop', 'designate', 'document', 'design'],
    'source': ['changelog', 'conversation'],
    'section_type': ['Decisions', 'Constraints', 'Failures', ...],
    'layer': ['pattern', 'implementation'],
    'timestamp': ISO 8601 string,
    'has_rationale': bool,
    'has_alternatives': bool,
    'session_id': UUID string,
    'chunk_type': ['message', 'patch'],
    'role': ['user', 'assistant'],
    'ingestion_timestamp': ISO 8601 string,
}
```

**Breaking when:** New collection with different schema ingested
**Impact:** Deduplication logic, path tracking breaks if hash/path fields differ
**Code:** Lines 68-156 (path/hash tracking)
**Fix:** Schema-aware ingestion based on collection registry

---

## Summary: Refactoring Checklist

### To Support Different Collection Schemas

- [ ] **1. Create Schema Registry**
  - Store metadata field definitions per collection
  - Track required vs optional fields
  - Record taxonomy values (phases, section types, etc)
  - Store vector config (model name, dimensions)
  - Store Qdrant connection (host, port)

- [ ] **2. Add Metadata Adapter**
  - Normalize field names across collections
  - Provide null-safe getters
  - Map old field names to new ones (migration)

- [ ] **3. Guard Primitive Execution**
  - Check schema before calling get_siblings() (needs file_path)
  - Check schema before calling get_genealogy() (needs session_id)
  - Check schema before calling cross_phase_search() (needs phase)
  - Allow get_temporal() to degrade gracefully

- [ ] **4. Adaptive CLI**
  - Load phase options from schema
  - Load section type options from schema  
  - Conditionally show layer option (only for collections with layer)
  - Conditionally show session option (only for collections with session_id)

- [ ] **5. Template Versioning**
  - Detect required fields before rendering
  - Load appropriate template variant per schema
  - Provide safe defaults in templates

- [ ] **6. Configuration Management**
  - Load vector config per collection (not global)
  - Load Qdrant connection per collection (not global)
  - Support collection-specific overrides

---

## Dependencies Matrix

| System Layer | Depends On | How to Fix |
|---|---|---|
| CLI | Hardcoded taxonomy | Dynamic schema loading |
| Search | Collection name, vector config | Schema registry |
| Discovery Primitives | Metadata fields | Conditional execution + guards |
| Compose Enrich | Metadata fields | Graceful degradation |
| Templates | Field presence | Null-safe Jinja2 filters |
| Ingestion | Collection schema | Schema-aware ingestion |
| Config | Global values | Per-collection settings |

---

## Complete Call Graph with Breaking Points

```
CLI Entry Point (cli.py)
  ↓
registry.get_project_info() → collection_name
  ↓
[BREAKING POINT 1: Collection must be in registry]
  ↓
EnhancedQdrantSearch(collection_name)
  ↓
search(query, filters)
  ├─ [BREAKING POINT 2: Vector model must match collection]
  ├─ [BREAKING POINT 3: Filter fields must exist in schema]
  └─ results[]
      ↓
      [COMPOSE PATH]
      ↓
      _execute_search(collection_name)
        └─ [Same as search above]
      ↓
      _enrich_with_discovery(collection_name)
        ├─ get_siblings(collection_name, chunk_id)
        │   [BREAKING POINT 4: file_path must exist]
        ├─ get_genealogy(collection_name, chunk_id)
        │   [BREAKING POINT 5: session_id must exist]
        ├─ get_temporal(collection_name, chunk_id)
        │   [BREAKING POINT 6: timestamp optional but degrades without]
        └─ cross_phase_search(collection_name, chunk_id)
            [BREAKING POINT 7: phase must exist]
      ↓
      _enrich_metadata()
        ├─ [BREAKING POINT 8: section_type check fails silently]
        ├─ [BREAKING POINT 9: timestamp missing causes wrong position]
        └─ [BREAKING POINT 10: has_rationale/alternatives defaults]
      ↓
      _apply_graph_operations(collection_name)
        └─ [No new breaking points]
      ↓
      _render_template()
        └─ [BREAKING POINT 11: template assumes all fields present]
```

---

**For detailed code locations and line numbers, see:** `IMEM_AUDIT.md`

**For quick reference table:** `IMEM_QUICK_REFERENCE.md`
