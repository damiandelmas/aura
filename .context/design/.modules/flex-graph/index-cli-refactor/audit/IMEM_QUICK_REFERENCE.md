# IMEM Audit - Quick Reference Guide

## 1. Collection Resolution Path

```
CLI Command → Registry Lookup → Collection Name → Qdrant Operations
```

**Key Files:**
- `/imem/src/imem/cli.py` - Entry points (search, compose)
- `/imem/src/imem/registry.py` - Collection name generation
- `/imem/src/imem/enhanced.py` - Search execution
- `/imem/src/imem/compose.py` - Compose orchestration

## 2. Compose Four-Stage Pipeline

| Stage | File | Function | Collection Param |
|-------|------|----------|------------------|
| 1. Retrieve | compose.py:72 | `_execute_search()` | YES |
| 2. Enrich | compose.py:170 | `_enrich_with_discovery()` | YES |
| 2.5 Metadata | compose.py:267 | `_enrich_metadata()` | NO (computed) |
| 3. Graph | compose.py:319 | `_apply_graph_operations()` | YES |
| 4. Render | compose.py:355 | `_render_template()` | NO (Jinja2) |

## 3. Parameterized Primitives

**Discovery Functions in `/imem/src/imem/primitives/discovery.py`**

| Primitive | Required Fields | Optional Filters | Breaking When Missing |
|-----------|-----------------|------------------|----------------------|
| `get_siblings()` | file_path | section_types, has_rationale | Returns [] if no file_path |
| `get_genealogy()` | session_id, source | order_by | Returns [] if no session_id |
| `get_temporal()` | timestamp (for direction) | direction | No error, loses ordering |
| `cross_phase_search()` | phase | target_phase | Returns [] if no phase |

## 4. Metadata Filter Taxonomy (Hardcoded in CLI)

```python
# From cli.py lines 47-586

phase = ['develop', 'designate', 'document', 'design', 'conversations', 'all']
source = ['changelog', 'conversation']
section_type = ['Decisions', 'Constraints', 'Failures', 'Patterns', 'Implementation']
layer = ['pattern', 'implementation']
chunk_type = ['message', 'patch']  # For conversations only
role = ['user', 'assistant']  # For messages only
```

## 5. Template System

**Default Template:** `/imem/templates/story-context.j2`

**Required Variables:**
```
results[0].temporal_position     (computed by _enrich_metadata)
results[0].payload.section_name  (from metadata)
results[0].payload.timestamp     (from metadata)
results[0].confidence.*          (computed)
results[0].siblings[]            (from get_siblings)
results[0].temporal[]            (from get_temporal)
results[0].genealogy[]           (from get_genealogy)
```

## 6. Breaking Points Summary

| # | Issue | Impact | Solution |
|---|-------|--------|----------|
| 1 | Collection name hash collision | Data orphaning | Store name in registry ✓ |
| 2 | Missing metadata fields | Silent empty results | Schema validation needed |
| 3 | Hardcoded taxonomy (phase, source) | Can't add new types | Schema adapter pattern |
| 4 | Vector model assumption (E5-Large-v2) | Named vector query fails | Collection schema metadata |
| 5 | Single Qdrant instance | No multi-cluster | Config per collection |
| 6 | Temporal position detection | Wrong classifications | Null-safe field checking |
| 7 | Session ID requirement | No genealogy for static docs | Conditional primitive execution |

## 7. Call Chains to Watch

### Search Command
```python
cli.search()                           # Line 462
  ├─ registry.get_project_info()       # Line 517
  ├─ collection_name = info['collection']  # Line 518
  └─ EnhancedQdrantSearch(collection_name)  # Line 541
      └─ searcher.search(query, filters)    # Line 547
```

### Compose Command
```python
cli.compose()                          # Line 217
  ├─ registry.get_project_info()       # Line 260
  ├─ collection_name = info['collection']  # Line 267
  └─ compose_pipeline(collection_name, config)  # Line 270
      ├─ _execute_search(collection_name)  # compose.py:40
      ├─ _enrich_with_discovery(collection_name)  # compose.py:44
      ├─ _enrich_metadata()  # compose.py:53 (no param)
      ├─ _apply_graph_operations(collection_name)  # compose.py:57
      └─ _render_template()  # compose.py:67 (no param)
```

### Discovery Primitives
```python
get_siblings(collection_name, chunk_id, ...)
  → requires: payload.file_path

get_genealogy(collection_name, chunk_id, ...)
  → requires: payload.session_id, payload.source='conversation'

get_temporal(collection_name, chunk_id, direction, ...)
  → requires: payload.timestamp (optional)

cross_phase_search(collection_name, chunk_id, target_phase, ...)
  → requires: payload.phase
```

## 8. Configuration Points

**File:** `/imem/src/imem/config.py`

```python
qdrant_port: int = 6334
qdrant_host: str = 'localhost'
default_vector_name: str = 'e5-large-v2'
default_model: str = 'intfloat/e5-large-v2'
default_dimensions: int = 1024
context_dir: Path = ~/.context
```

**All hardcoded - need schema per collection for multi-collection support**

## 9. What Changes Break What

| If You Change | System Will Break At |
|---|---|
| Collection name | Cross-references in registry |
| Metadata field names | All primitives (silent failures) |
| Phase taxonomy | CLI options, cross_phase_search |
| Vector model | Named vector queries, compose.py:140 |
| Qdrant host/port | All collection operations |
| Template structure | Jinja2 rendering stage |
| Ingestion schema | get_siblings, get_genealogy predicates |

## 10. Key Files by Category

### Collection Management
- `/imem/src/imem/cli.py` - Entry points
- `/imem/src/imem/registry.py` - Collection name mapping

### Search & Discovery
- `/imem/src/imem/search.py` - ModularSearch interface
- `/imem/src/imem/enhanced.py` - EnhancedQdrantSearch (metadata extraction)
- `/imem/src/imem/primitives/discovery.py` - Discovery operations

### Orchestration
- `/imem/src/imem/compose.py` - Four-stage pipeline

### Rendering
- `/imem/templates/story-context.j2` - Main template
- `/imem/templates/genealogy.j2` - Genealogy view
- `/imem/templates/timeline.j2` - Timeline view

### Ingestion
- `/imem/src/imem/ingest.py` - Document ingestion & deduplication

## 11. For Multi-Collection Support, Add

1. **Schema Registry** - Describe expected fields per collection
2. **Metadata Adapter** - Normalize fields across collections
3. **Primitive Guards** - Skip inapplicable operations
4. **Template Variants** - Schema-aware template selection
5. **Filter Translator** - Map CLI taxonomy to collection schema

---

**Document:** IMEM_AUDIT.md contains full detailed analysis with code snippets and line numbers.
