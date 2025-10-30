# IMEM Search & Compose System: Comprehensive Dependency Audit

## Executive Summary

The IMEM system demonstrates a well-architected collection-aware design where **collection names are properly parameterized** throughout the entire stack. However, there are **critical collection-dependent breaking points** in metadata filters, discovery primitives, and hardcoded phase/source assumptions that would fail with multi-collection support.

**Key Finding:** Collection resolution is correct, but the system has **implicit single-collection dependencies** via hardcoded metadata schemas (phase, source, section_type, layer, session_id).

---

## Part 1: Call Path Architecture - Collection Resolution Flow

### 1.1 Entry Point: CLI Commands

**File:** `/home/axp/projects/fleet/hangar/code/aura/main/imem/src/imem/cli.py`

#### Search Command Chain (Lines 462-545)
```
imem search "query" 
  ↓
search() CLI handler
  ↓
_execute_search() [Line 145]
  ↓
registry.get_project_root() [Line 510]
  ↓
registry.is_registered(project_root) [Line 513]
  ↓
registry.get_project_info(project_root) [Line 517]
  ↓
collection_name = info['collection'] [Line 518]
  ↓
EnhancedQdrantSearch(collection_name=collection_name) [Lines 541-543]
  ↓
searcher.search(query, filters=filters) [Lines 547-555]
```

#### Compose Command Chain (Lines 215-286)
```
imem compose '{"search": {...}, "discovery": {...}}'
  ↓
compose() CLI handler [Line 217]
  ↓
registry.get_project_info(project_root) [Lines 259-261]
  ↓
collection_name = info['collection'] [Line 267]
  ↓
compose_pipeline(collection_name, config_dict) [Line 270]
  ↓
async compose(collection_name, config_dict) [compose.py Line 16]
```

### 1.2 Registry System - Collection Name Generation

**File:** `/home/axp/projects/fleet/hangar/code/aura/main/imem/src/imem/registry.py`

```python
def register_project(self, project_root: Path) -> str:
    """Generate collection name from project path hash"""
    project_key = str(project_root.resolve())
    collection_name = f"imem_{hashlib.md5(project_key.encode()).hexdigest()[:8]}"
    # Example: imem_a1b2c3d4
```

**Breaking Point #1:** Collection names are deterministic MD5 hashes. If project path changes:
- Old: `/home/user/project` → `imem_abc12345`
- New: `/home/user/myproject` → `imem_xyz98765`
- **Result:** Registry desynchronization, data orphaning

**Mitigation:** Registry records collection_name (not regenerated), but if project is moved and re-registered, creates duplicate collections.

---

## Part 2: Four-Stage Compose Pipeline

**File:** `/home/axp/projects/fleet/hangar/code/aura/main/imem/src/imem/compose.py`

### Stage 1: Retrieve (Lines 39-116)
```python
async def _execute_search(collection_name, search_config, client, encoder):
    """Execute search stage with parallel query execution"""
    
    # Flow:
    # search_config = {"text": "query", "filters": {...}, "limit": 10}
    # ↓
    # _single_search(collection_name, query_text, filters, limit, client, encoder)
    # ↓
    # client.query_points(collection_name=collection_name, query=vector, ...)
```

**Collection Dependency:** ✓ Properly parameterized
**Filter Types Accepted:**
- `phase`: ['develop', 'designate', 'document', 'design']
- `source`: ['changelog', 'conversation']
- `section_type`: ['Decisions', 'Constraints', 'Failures', 'Patterns', 'Implementation']
- `layer`: ['pattern', 'implementation']
- `session_id`: conversation session UUID

### Stage 2: Enrich (Lines 170-264)
```python
async def _enrich_with_discovery(collection_name, results, discovery_config, client, encoder):
    """Execute discovery stage with parallel enrichment"""
    
    for each result:
        await gather([
            get_siblings(collection_name, chunk_id, ...),      # metadata: file_path
            get_genealogy(collection_name, chunk_id, ...),     # metadata: session_id, source
            get_temporal(collection_name, chunk_id, ...),      # semantic + timestamp
            cross_phase_search(collection_name, chunk_id, ...)  # metadata: phase
        ])
```

**Collection Dependency:** ✓ Properly parameterized
**Metadata Dependencies:**
- **get_siblings:** Requires `file_path` field
- **get_genealogy:** Requires `session_id` field + `source='conversation'`
- **get_temporal:** Requires `timestamp` field
- **cross_phase_search:** Requires `phase` field

**Breaking Point #2:** Primitives assume specific metadata schema. If ingesting to different collection with different schema:
- Missing `session_id` → get_genealogy returns []
- Missing `timestamp` → get_temporal can't filter by direction
- Missing `phase` → cross_phase_search fails

### Stage 2.5: Metadata Enrichment (Lines 267-282)
```python
def _enrich_metadata(results):
    """Add temporal position and confidence signals"""
    
    result['temporal_position'] = _detect_temporal_position(result)
    # Logic depends on:
    # - section_type == 'Failures' (checks payload.section_type)
    # - temporal relationships (payload.timestamp)
    
    result['confidence'] = {
        'has_rationale': payload.get('has_rationale'),        # metadata field
        'has_alternatives': payload.get('has_alternatives'),  # metadata field
        'semantic_score': result.score,
        'continuation_count': _count_continuations(result)
    }
```

**Breaking Point #3:** Assumes presence of:
- `section_type` field (to detect Failures)
- `timestamp` field (for temporal ordering)
- `has_rationale`, `has_alternatives` fields (for confidence)

### Stage 3: Graph (Lines 319-352)
```python
def _apply_graph_operations(collection_name, results, graph_config, client, encoder):
    """Execute graph stage - currently does simple authority ranking"""
    
    # Authority = count(siblings) + count(genealogy)
    # Just reference counting, not full graph analysis
    # No additional metadata required
```

**Collection Dependency:** ✓ Properly parameterized
**No new metadata dependencies**

### Stage 4: Render (Lines 355-376)
```python
def _render_template(results, template_name):
    """Render with Jinja2 template"""
    
    template_dir = Path(__file__).parent.parent.parent / 'templates'
    template = env.get_template(f"{template_name}.j2")
    return template.render(results=results)
```

**Collection Dependency:** ✓ Properly parameterized
**Template Dependencies:** See story-context.j2 analysis below

---

## Part 3: Parameterized Primitives & Metadata Filtering

**File:** `/home/axp/projects/fleet/hangar/code/aura/main/imem/src/imem/primitives/discovery.py`

### Primitive 1: get_siblings (Lines 14-107)

```python
def get_siblings(collection_name, chunk_id,
                 section_types=None,      # Optional: filter by specific types
                 order_by='section_level', # 'section_level' | 'timestamp' | None
                 limit=None,
                 has_rationale=None,      # Optional: filter by quality
                 has_alternatives=None,   # Optional: filter by quality
                 client=None,
                 encoder=None):
```

**Filter Building (Lines 53-73):**
```python
must_conditions = [
    FieldCondition(key='file_path', match=MatchValue(value=file_path))
    # ↑ CRITICAL: Requires file_path in payload
]

if section_types:
    must_conditions.append(
        FieldCondition(key='section_type', match=MatchAny(any=section_types))
        # ↑ CRITICAL: Requires section_type field
    )

if has_rationale is not None:
    must_conditions.append(
        FieldCondition(key='has_rationale', match=MatchValue(value=has_rationale))
        # ↑ CRITICAL: Requires has_rationale field
    )
```

**Parameterized Options:**
- `section_types`: Can filter by specific types (e.g., ["Patterns", "Failures"])
- `order_by`: Can order by 'section_level', 'timestamp', or unsorted
- `has_rationale`, `has_alternatives`: Can filter quality

**Breaking Points:**
- `file_path` is ALWAYS required (no fallback if missing)
- Returns empty list if source chunk has no `file_path`
- `section_type` filtering will return zero results if field doesn't exist in collection

### Primitive 2: get_genealogy (Lines 110-176)

```python
def get_genealogy(collection_name, chunk_id,
                  order_by='timestamp',  # 'timestamp' | None
                  limit=None,
                  client=None,
                  encoder=None):
```

**Filter Building (Lines 144-149):**
```python
scroll_filter = Filter(
    must=[
        FieldCondition(key='session_id', match=MatchValue(value=session_id)),
        # ↑ CRITICAL: Requires session_id in payload
        FieldCondition(key='source', match=MatchValue(value='conversation'))
        # ↑ CRITICAL: Requires source='conversation'
    ]
)
```

**Breaking Points:**
- If source chunk missing `session_id`, returns []
- If no chunks have `source='conversation'`, returns []
- Silently fails if collection is pure-changelog (no conversations ingested)

### Primitive 3: get_temporal (Lines 179-260)

```python
def get_temporal(collection_name, chunk_id,
                 direction='after',  # 'after' | 'before' (temporal direction)
                 client=None,
                 encoder=None):
```

**Logic (Lines 239-252):**
```python
# Semantic search (high threshold 0.85)
# + post-filter by timestamp direction

if timestamp:
    point_timestamp = point.payload.get('timestamp') or point.payload.get('created')
    
    if direction == 'after' and point_timestamp <= timestamp:
        continue  # Skip earlier chunks
    if direction == 'before' and point_timestamp >= timestamp:
        continue  # Skip later chunks
```

**Breaking Points:**
- If source chunk has no timestamp fields, post-filter becomes no-op (no chronological filtering)
- Works with semantic similarity alone, but direction parameter becomes useless

### Primitive 4: cross_phase_search (Lines 263-334)

```python
def cross_phase_search(collection_name, chunk_id,
                       target_phase,  # Phase to search in
                       client=None,
                       encoder=None):
```

**Filter Building (Lines 293-297):**
```python
phase_filter = Filter(
    must=[
        FieldCondition(key='phase', match=MatchValue(value=target_phase))
        # ↑ CRITICAL: Requires phase field
    ]
)
```

**Breaking Points:**
- If collection has no `phase` field, query returns zero results
- Silent failure if target collection doesn't use phase taxonomy

---

## Part 4: Template System - story-context.j2

**File:** `/home/axp/projects/fleet/hangar/code/aura/main/imem/templates/story-context.j2`

### Template Variable Dependencies (Lines 1-136)

```jinja2
{% set primary = results[0] %}

{# Requires: results[0].temporal_position #}
{% if primary.temporal_position == "current_thrust" %}

{# Requires: results[0].payload.section_name #}
{{ primary.payload.section_name }}

{# Requires: results[0].payload.timestamp #}
📅 {{ primary.payload.timestamp }}

{# Requires: results[0].confidence.* #}
- 📊 Semantic Score: {{ primary.confidence.semantic_score }}
- ⚡ Active Thrust: {{ primary.confidence.continuation_count }}
- ✅ Has Full Rationale: {{ primary.confidence.has_rationale }}

{# Requires: results[0].siblings[].payload.section_type #}
{% if sibling.payload.section_type == 'Failures' %}

{# Requires: results[0].temporal[].payload.* #}
{% for temporal in primary.temporal %}
  {{ temporal.payload.timestamp }}: {{ temporal.payload.section_name }}

{# Requires: results[0].genealogy[].payload.* #}
{% for conv in primary.genealogy %}
  {{ conv.payload.content }}
```

**Required Fields in Payload:**
1. `temporal_position` (added by compose.py _enrich_metadata)
2. `confidence` (added by compose.py _enrich_metadata)
3. `payload.section_name`
4. `payload.timestamp`
5. `payload.section_type`
6. `payload.has_rationale`, `payload.has_alternatives`
7. `siblings[].payload.*` (from get_siblings)
8. `temporal[].payload.*` (from get_temporal)
9. `genealogy[].payload.*` (from get_genealogy)

**Breaking Point #4:** Template assumes:
- All results have `temporal_position` (computed field)
- All payloads have `section_name`, `timestamp`, `section_type`
- Sibling/genealogy/temporal discovery executed successfully

If any discovery returns [], template handles gracefully with `{% if primary.siblings %}`

---

## Part 5: Search Command Filters - Hardcoded Phase/Source Taxonomy

**File:** `/home/axp/projects/fleet/hangar/code/aura/main/imem/src/imem/cli.py:443-586`

### Phase-Based Search (develop/conversations groups)

#### Develop Search (Lines 47-89)
```python
@imem.group()
def develop():
    """Search develop phase (what we built)"""

@develop.command(name='search')
def develop_search(query, decisions, constraints, failures, patterns, implementation, 
                   pattern, impl, limit, after):
    filters = {
        'source': 'changelog',      # Hardcoded
        'phase': 'develop'          # Hardcoded
    }
```

**Hardcoded Dependency:** Assumes:
- Two sources: 'changelog' and 'conversation'
- Phases: ['develop', 'designate', 'document', 'design']
- Section types: ['Decisions', 'Constraints', 'Failures', 'Patterns', 'Implementation']
- Layers: ['pattern', 'implementation']

#### Conversations Search (Lines 98-142)
```python
filters = {'source': 'conversation'}  # Hardcoded

if messages_only:
    filters['chunk_type'] = 'message'  # Hardcoded type
elif patches_only:
    filters['chunk_type'] = 'patch'    # Hardcoded type
```

### Generic Search Command (Lines 443-586)

```python
@click.option('--in', 'phase_filter',
              type=click.Choice(['develop', 'designate', 'document', 'conversations', 'all']),
              default='develop')
@click.option('--layer',
              type=click.Choice(['implementation', 'pattern', 'both']),
              default='implementation')
@click.option('--section', help='Filter by section type')

def search(query, ..., phase_filter, layer, section, session):
    filters = {}
    if phase_filter == 'conversations':
        filters['source'] = 'conversation'
    elif phase_filter != 'all':
        filters['source'] = 'changelog'
        filters['phase'] = phase_filter
```

**Breaking Points for Multi-Collection Support:**
1. **Phase filtering assumes single taxonomy:** Can't query multiple phase schemas
2. **Layer filtering assumes changelog structure:** Only applies to develop phase
3. **Session ID requires conversation source:** Silently ignored for changelog
4. **Hardcoded section types:** New types require CLI code changes

---

## Part 6: Search Implementation - Filter Application

**File:** `/home/axp/projects/fleet/hangar/code/aura/main/imem/src/imem/enhanced.py:95-162`

### Search Filter Building (Lines 122-131)
```python
def search(self, query, limit=10, filters=None):
    """Enhanced search with metadata extraction"""
    
    query_filter = None
    if filters:
        must_conditions = []
        for key, value in filters.items():
            must_conditions.append(
                FieldCondition(key=key, match=MatchValue(value=value))
            )
        query_filter = Filter(must=must_conditions)
    
    search_result = self.client.query_points(
        collection_name=self.collection_name,
        query=query_vector,
        using=self.vector_name,
        query_filter=query_filter,
        limit=search_limit,
        ...
    )
```

**No Additional Breaking Points:** Filters are applied as-is to Qdrant

---

## Part 7: Ingestion System - Metadata Schema

**File:** `/home/axp/projects/fleet/hangar/code/aura/main/imem/src/imem/ingest.py` (partial view)

### Collection Creation (Lines 334+)
```python
def create_collection(self, config: SearchConfig, recreate: bool = False):
    """Create collection for given configuration"""
    
    # E5-Large-v2 vector config:
    client.create_collection(
        collection_name=collection_name,
        vectors_config={
            "e5-large-v2": VectorParams(
                size=1024,
                distance=Distance.COSINE,
                hnsw_config=HnswConfigDiff(m=16, ef_construct=100)
            )
        }
    )
```

### Document Ingestion Metadata Fields
(From comments and imports, schema includes):
- `content` or `information` or `document` - text content
- `file_path` - source file path
- `file_hash` - MD5 content hash
- `phase` - one of ['develop', 'designate', 'document', 'design']
- `source` - one of ['changelog', 'conversation']
- `section_type` - one of ['Decisions', 'Constraints', 'Failures', 'Patterns', 'Implementation', ...]
- `layer` - one of ['pattern', 'implementation']
- `section_level` - numeric hierarchical level
- `timestamp` - ISO 8601 datetime
- `has_rationale` - boolean
- `has_alternatives` - boolean
- `session_id` - conversation session UUID
- `chunk_type` - one of ['message', 'patch']
- `role` - one of ['user', 'assistant'] (for messages)
- `ingestion_timestamp` - when document was indexed

**Breaking Point #5:** Ingester assumes all fields must be present. Different collection with different schema → search filters return no results silently.

---

## Part 8: Cross-Cutting Collection Dependencies

### 8.1 Vector Model Assumptions

**Config File:** `/home/axp/projects/fleet/hangar/code/aura/main/imem/src/imem/config.py`

```python
default_vector_name: str = 'e5-large-v2'
default_model: str = 'intfloat/e5-large-v2'
default_dimensions: int = 1024
```

**Breaking Point #6:** All searches assume E5-Large-v2 model:
```python
# Enhanced.py:30
self.vector_name = "e5-large-v2"

# Compose.py:140
query=config.default_vector_name

# Primitives:220
query=target_vector.get(config.default_vector_name)
```

If collection was created with different model:
- Vector query will fail with "named vector not found"
- Falls back to unnamed vector (might work or fail silently)
- No schema validation during search initialization

### 8.2 Qdrant Connection Coupling

**All collection operations assume single Qdrant instance:**
```python
# Config.py
qdrant_port: int = 6334
qdrant_host: str = 'localhost'

# All files: QdrantClient(host=config.qdrant_host, port=config.qdrant_port)
```

**Breaking Point #7:** Can't query multiple Qdrant instances (e.g., for federation or backup systems)

---

## Summary: Breaking Points Matrix

| # | Breaking Point | Scope | Severity | Multi-Collection Impact |
|---|---|---|---|---|
| 1 | Collection name generation (MD5 hash) | Registry | Medium | Path changes orphan data |
| 2 | Metadata schema assumptions (session_id, phase, section_type) | Primitives | Critical | Cross-collection queries fail silently |
| 3 | Temporal position detection (Failures detection) | Compose/Enrich | High | Wrong position detection |
| 4 | Template variable dependencies | Render | Medium | Template rendering fails with missing fields |
| 5 | Ingestion schema assumptions | Ingest | Critical | New collections need migration |
| 6 | Vector model hardcoding (e5-large-v2) | Config | High | Named vector queries fail |
| 7 | Single Qdrant instance assumption | Config | High | Can't federate/replicate |
| 8 | Phase/source taxonomy CLI (hardcoded choices) | CLI | Low | New taxonomies need CLI changes |

---

## Recommendations for Multi-Collection Support

### 1. Schema Validation Framework
```python
class CollectionSchema:
    """Describe expected metadata for a collection"""
    def __init__(self, collection_name: str):
        self.name = collection_name
        self.required_fields = []
        self.optional_fields = []
        self.taxonomy = {}  # phase, source, section_type allowed values
```

### 2. Metadata Adapter Pattern
```python
def adapt_payload(payload: dict, schema: CollectionSchema) -> dict:
    """Normalize payload across different collection schemas"""
    # Map session_id -> conversation_id if needed
    # Map section_type -> topic_type if needed
    # Handle missing timestamp fields
```

### 3. Primitive Configuration
```python
async def _enrich_with_discovery(collection_name, results, discovery_config, schema):
    """Use schema to skip inapplicable primitives"""
    if 'session_id' in schema.required_fields:
        await get_genealogy(...)  # Only if schema supports it
```

### 4. Template Versioning
```python
def render_template(results, template_name, schema):
    """Load schema-aware template variant"""
    template = env.get_template(f"{template_name}-{schema.version}.j2")
```

---

## Configuration Override Path

Current working flow:
```
Project Root → Registry → Collection Name → Searcher → Results
    ↓
    └─→ All metadata filters hardcoded in CLI
```

Required for multi-collection:
```
Project Root → Registry → Collection Name → Schema Resolver → Adaptive Filters → Searcher → Schema-Aware Render
    ↓
    └─→ Dynamic taxonomy mapping
    └─→ Optional field handling
    └─→ Version-aware template selection
```

