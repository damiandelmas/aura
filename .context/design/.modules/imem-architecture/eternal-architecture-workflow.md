# Eternal Architecture Documentation Workflow

## Vision

Integrate living architecture documents into IMEM's vector search system, enabling semantic queries across system designs while maintaining freshness through update timestamps.

## Current State (This Session's Work)

### Schema Design
```yaml
# Architecture document frontmatter
schema_version: "v3_adaptive"
type: "architecture.{system}-{scope}"
status: "stable" | "draft" | "deprecated"
keywords: "space separated terms"
timestamp: "YYYY-MM-DDTHH:MM:SS-0700"  # Last refresh time
```

**Type Pattern:** `architecture.{system}-{scope}`
- **System**: Codebase name (imem, trace, aura)
- **Scope**: Aspect/subsystem/depth (overview, indexing, search, dataflow, patterns)
- **Examples**:
  - `architecture.imem-overview` - High-level introduction
  - `architecture.imem-indexing` - Deep dive into indexing subsystem
  - `architecture.trace-parsing` - How TRACE parsing works

### Template Structure (6 Required Sections)

1. **Purpose** - What the system does, what problem it solves
2. **Components** - What exists (modules, files, classes)
3. **Data Flow** - How it works (pipeline, sequence)
4. **Integration Points** - How it connects to external systems
5. **Patterns & Principles** - Why it's designed this way
6. **Usage** - How to interact with it (commands, API, integration)

**Key Constraint:** Present tense only, no temporal content in body. Dates only in `timestamp` field.

### Agents Created

**architecture-capture** - Creates new architecture docs from codebase
- Input: Codebase path, system name, scope
- Output: Eternal architecture document
- Sets: `type`, `timestamp`, `status`, `keywords`

**architecture-convert** - Converts existing temporal docs to eternal format
- Strips: "Recent Changes", dates in content, before/after comparisons, future plans
- Keeps: Components, flows, patterns, integration points, usage
- Infers: System name, scope from content

### Template Location
`/home/axp/projects/fleet/hangar/code/aura/main/assets/changelogs/document/template/00_TEMPLATE.md`

## The Gap: Indexing Into IMEM

### What Works Today (Changelogs)

**IMEM can index changelogs:**
```python
# Changelog indexing flow
1. Read markdown from .context/develop/.changes/*.md
2. LlamaIndex MarkdownNodeParser chunks at H3 level
3. Extract metadata: phase, section_type, session_id, timestamp
4. Generate E5-Large-v2 embeddings (1024D)
5. Store in Qdrant with rich metadata
6. Query: imem develop search "authentication" --decisions
```

**Why it works:**
- H3-level chunking (each Decision/Constraint = 1 vector)
- Rich metadata from frontmatter + structure
- Section-type filtering (Decisions, Constraints, Failures)
- Progressive disclosure (variable structure handled)

### What Doesn't Work Yet (Architecture Docs)

**Architecture docs have different structure:**
- H2 sections (Purpose, Components, Data Flow)
- Not H3 items like changelogs
- Each section is large (30-100 lines)
- Components listed within section, not as separate H3s

**Current IMEM parser expects:**
```python
## Decisions          # H2 parent
### Decision 1        # H3 → 1 vector
### Decision 2        # H3 → 1 vector
```

**Architecture docs provide:**
```markdown
## Components        # H2 section
**config.py** - Centralized configuration...
**registry.py** - Project tracking...
**cli.py** - Command interface...
```

**Mismatch:** Components listed as paragraphs, not H3 subsections.

## Solution Path (Not Yet Implemented)

### Option 1: H2-Level Chunking for Architecture

**Approach:**
- Detect document type from frontmatter: `type: "architecture.*"`
- Use different chunking strategy: H2-level instead of H3-level
- Each H2 section becomes one searchable node

**Query patterns:**
```python
# Find all Components sections across systems
filter={'type': {'$glob': 'architecture.*'}, 'section_type': 'Components'}

# Find IMEM's data flow
filter={'type': 'architecture.imem-*', 'section_type': 'Data Flow'}
```

**Pros:**
- Works with current architecture template
- Simple parser modification (detect type → choose chunking level)
- Natural granularity for architecture docs

**Cons:**
- Larger chunks (30-100 lines per vector)
- Less surgical retrieval than changelog H3 chunking

### Option 2: Hybrid Chunking

**Approach:**
- Changelogs: H3-level (current)
- Architecture: H2-level with component extraction

**Extract components as pseudo-nodes:**
```python
# Parse Components section
section_text = extract_h2_section("Components")

# Regex extract **ComponentName** blocks
components = re.findall(r'\*\*(\w+)\*\* \([^)]+\) - ([^\n]+)', section_text)

# Create one vector per component + one for full section
for name, desc in components:
    create_node(
        content=f"**{name}** - {desc}",
        metadata={'section_type': 'component', 'component_name': name}
    )
```

**Pros:**
- Surgical component-level retrieval
- Maintains architectural context

**Cons:**
- More complex parsing logic
- Custom extraction for each section type

### Option 3: Semantic Chunking

**Approach:**
- Use LlamaIndex SemanticSplitterNodeParser
- Chunk based on semantic coherence, not headers
- Adaptive chunk sizes (combine paragraphs with high similarity)

**Pros:**
- Flexible, works with any structure
- Intelligent boundary detection

**Cons:**
- Less predictable chunk sizes
- Metadata extraction harder (no structural anchors)

## Metadata Extraction Strategy

### From Frontmatter
```python
frontmatter = extract_frontmatter(doc)

base_metadata = {
    'type': frontmatter['type'],  # "architecture.imem-overview"
    'category': 'architecture',    # Extracted from type
    'system': 'imem',             # Extracted from type
    'scope': 'overview',          # Extracted from type
    'status': frontmatter['status'],
    'timestamp': frontmatter['timestamp'],
    'keywords': frontmatter['keywords'].split()
}
```

### From Structure (H2 sections)
```python
section_metadata = {
    'section_type': 'Components',  # From H2 header
    'section_level': 2,
    'header_path': 'Components'    # No parent for architecture docs
}
```

### Combined Metadata Schema
```python
{
    # Document-level
    'source': 'architecture',
    'type': 'architecture.imem-overview',
    'category': 'architecture',
    'system': 'imem',
    'scope': 'overview',
    'status': 'stable',
    'timestamp': '2025-10-25T14:30:00-0700',

    # Section-level
    'section_type': 'Components',
    'section_level': 2,

    # Content
    'content': 'Full H2 section text...',
    'file_path': 'architecture_imem-overview.md',
    'word_count': 450,
    'char_count': 2800
}
```

## Query Patterns Enabled

### Cross-System Pattern Discovery
```python
# How do all systems handle data flow?
results = imem.search(
    query="data transformation pipeline",
    filters={'section_type': 'Data Flow'}
)
# Returns: Data Flow sections from IMEM, TRACE, AURA architectures
```

### System-Specific Deep Dive
```python
# What are IMEM's design patterns?
results = imem.search(
    query="architectural patterns",
    filters={
        'type': {'$glob': 'architecture.imem-*'},
        'section_type': 'Patterns & Principles'
    }
)
```

### Freshness-Based Discovery
```python
# Find stale architecture docs (>6 months old)
six_months_ago = datetime.now() - timedelta(days=180)
results = imem.search(
    query="*",
    filters={
        'type': {'$glob': 'architecture.*'},
        'timestamp': {'$lt': six_months_ago.isoformat()}
    }
)
```

### Onboarding Query Flow
```python
# Agent onboarding sequence
1. Get system overview
   → filter={'type': 'architecture.imem-overview'}

2. Understand data flow
   → filter={'type': {'$glob': 'architecture.imem-*'},
             'section_type': 'Data Flow'}

3. Learn design patterns
   → filter={'type': {'$glob': 'architecture.imem-*'},
             'section_type': 'Patterns & Principles'}

4. See recent work (changelogs)
   → filter={'phase': 'develop',
             'timestamp': {'$gt': last_week}}
```

## Integration Requirements

### IMEM Parser Modifications

**Current:** Single chunking strategy (H3-level)
```python
def ingest_markdown(file_path, phase, layer, collection):
    # Always chunks at H3
    nodes = MarkdownNodeParser().get_nodes_from_documents([doc])
```

**Needed:** Type-aware chunking
```python
def ingest_markdown(file_path, collection):
    frontmatter = extract_frontmatter(file_path)

    if frontmatter['type'].startswith('architecture.'):
        # H2-level chunking for architecture
        nodes = chunk_architecture_doc(file_path)
    else:
        # H3-level chunking for changelogs
        nodes = chunk_changelog_doc(file_path)

    # Rest of indexing flow same
    embeddings = encode_batch([n.content for n in nodes])
    upsert_to_qdrant(collection, nodes, embeddings)
```

### New IMEM Commands

**Index architecture docs:**
```bash
imem index-architecture /path/to/architecture_imem-overview.md

# Or auto-discover
imem index-architecture --discover .context/document/
```

**Search architecture specifically:**
```bash
imem architecture search "how does indexing work"
imem architecture search "design patterns" --system imem
```

**Freshness check:**
```bash
imem architecture status
# Output:
# architecture.imem-overview: Last updated 2 days ago ✓
# architecture.trace-parsing: Last updated 4 months ago ⚠
```

## Open Questions

### 1. Chunking Granularity
- **Question:** H2-level (one vector per section) or finer extraction?
- **Trade-off:** Simplicity vs surgical retrieval
- **Decision needed:** Test both approaches with real queries

### 2. Component Extraction
- **Question:** Extract individual components from Components section?
- **Example:** "What does registry.py do?" → Retrieve just that component description
- **Complexity:** Custom parsing per section type
- **Decision needed:** Start simple (H2-level), add component extraction if needed

### 3. Update Workflow
- **Question:** How do we keep architecture docs fresh?
- **Options:**
  - Manual: Developer updates when codebase changes significantly
  - Semi-auto: Detect code changes, remind to update doc
  - Auto: Re-generate sections from codebase (risky - loses human insight)
- **Decision needed:** Start manual, monitor staleness

### 4. Versioning
- **Question:** Do we keep old versions of architecture docs?
- **Current:** Single `timestamp` = last update (overwrites)
- **Alternative:** Version history in IMEM (multiple timestamps)
- **Decision needed:** Single version or history?

### 5. Cross-Document Queries
- **Question:** Query across both changelogs + architecture?
- **Example:** "Find all mentions of JWT" → Returns decisions from changelogs + architecture patterns
- **Complexity:** Need unified filtering (both support `type`, `timestamp`, etc.)
- **Decision needed:** Unified query interface or separate commands?

## Next Steps

1. **Implement H2-level chunking** in IMEM ingest pipeline
2. **Test indexing** existing architecture docs (imem-i2.md, trace-i2.md)
3. **Validate queries** - Can we find Components sections? Data Flow?
4. **Measure freshness** - How often do architecture docs need updates?
5. **Build update workflow** - Reminders, validation, re-indexing
6. **Create unified search** - Query changelogs + architecture together

## Success Criteria

**We'll know this works when:**

1. Agent can onboard by reading: "Show me IMEM architecture overview"
2. Agent can deep-dive: "How does IMEM indexing work?"
3. Agent can discover patterns: "What design patterns does TRACE use?"
4. Agent can check freshness: "Is AURA architecture doc current?"
5. Agent can bridge to changelogs: "Show me recent IMEM changes"

**Target query experience:**
```bash
# Onboarding
imem search "what is IMEM" --in architecture

# Deep dive
imem search "indexing pipeline" --in architecture --system imem

# Pattern discovery
imem search "metadata extraction patterns" --in architecture

# Recent context
imem search "recent indexing improvements" --in develop

# Combined
imem search "authentication" --in architecture,develop
```

## Philosophy

**Architecture docs are eternal maps. Changelogs are temporal deltas.**

Together they enable:
- **Shape**: Architecture docs show current topology
- **Flow**: Changelogs show recent movement
- **Onboarding**: Read architecture → understand system → read changelogs → understand recent work

The architecture workflow we built this session is **step 1** of integrating eternal knowledge into IMEM's vector search.
