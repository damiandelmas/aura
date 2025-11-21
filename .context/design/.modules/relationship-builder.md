# Relationship Builder: What Layer Does It Belong To?

**You're identifying a critical architectural question.**

---

## The Three Layers You're Seeing

### Layer 1: COMPILE (Structural Metadata)
```
PROJECT → DOCUMENT → PHASE → CHUNKS

Metadata:
  phase: "design" | "designate" | "develop" | "document"
  section_type: "Decision" | "Pattern" | "Context"
  file_path: ".context/design/auth-exploration.md"
  timestamp: "2025-11-18T10:30:00"
  
This is DETERMINISTIC from document structure.
Parser extracts it. Resolver normalizes it.
```

**Nature:** Inherent to document. Doesn't require analysis.

---

### Layer 2: MANAGE (Entity/Concept Metadata)
```
PROJECT → CHUNKS → ENTITIES

Metadata:
  entities: ["jwt", "authentication", "redis"]
  concepts: ["security-pattern", "caching-strategy"]
  
This is PROJECT-SCOPED normalization.
"JWT" = "jwt" = "Json Web Token" → canonical "jwt"
```

**Nature:** Requires project-specific learning. Entity resolution tables.

---

### Layer 3: EMERGENT (Graph Relationships)
```
CHUNKS → RELATIONSHIPS → GRAPH

Edges:
  chunk_A --[decision_implements]--> chunk_B
  chunk_C --[spatial_proximity]--> chunk_D
  chunk_E --[conversation_continues]--> chunk_F
  
This is RELATIONAL between chunks.
Not metadata OF a chunk, but edges BETWEEN chunks.
```

**Nature:** Detected from patterns across chunks. Graph structure.

---

## Your Question: Where Does relationship_builder Fit?

**Three possibilities:**

### Option A: Part of COMPILE (Structural Detection)
```
During indexing:
  Parse markdown → chunks[]
  For each chunk, detect:
    - spatial_proximity: "this chunk follows previous chunk in document"
    - Same as detecting section_type from header
    
Structural relationships = part of compilation.
```

**Argument FOR:**
- Spatial proximity is deterministic (chunk N+1 follows chunk N)
- Document hierarchy is structural (H3 under H2)
- Conversation flow is structural (message N+1 follows message N)

**Argument AGAINST:**
- Relationships are BETWEEN chunks, metadata is OF chunk
- Creates coupling (compiler now knows about graph)

---

### Option B: Part of MANAGE (Post-Indexing Analysis)
```
After indexing:
  Chunks exist in storage
  Run analysis:
    - Detect temporal clusters (chunks from same time window)
    - Detect decision→implementation links (pattern matching)
    - Populate relationships table
    
Enrichment happens after compilation.
```

**Argument FOR:**
- MANAGE is "intelligence layer" (introspection, analysis)
- Relationships require looking across chunks (project-scope)
- Separates concerns (COMPILE = structure, MANAGE = meaning)

**Argument AGAINST:**
- Some relationships ARE structural (spatial, conversational)
- Delaying detection = can't query relationships immediately after index

---

### Option C: Separate GRAPH Domain (New Layer)
```
COMPILE → chunks with metadata
GRAPH → detect relationships, populate edges
MANAGE → entity normalization
RETRIEVE → query using chunks + relationships
```

**Argument FOR:**
- Graph operations are distinct concern
- Could have graph-specific algorithms (PageRank, clustering)
- Clean separation: structure vs entities vs relationships

**Argument AGAINST:**
- Adds complexity (4 domains instead of 3)
- Some relationships are simple (spatial = just sequential chunks)

---

## Let's Reason Through Relationship Types

### Spatial Proximity
```
chunk_1 (line 1-50 of document)
chunk_2 (line 51-100 of document)

Relationship: chunk_1 --[spatial_proximity]--> chunk_2
```

**Detection:** Sequential in parse order
**When:** During parsing (deterministic)
**Layer:** COMPILE (structural)

---

### Conversation Continues
```
Message 5: USER: "How do we handle auth?"
Message 6: ASSISTANT: "Use JWT tokens..."

Relationship: msg_5 --[conversation_continues]--> msg_6
```

**Detection:** Sequential in session
**When:** During parsing (deterministic)
**Layer:** COMPILE (structural)

---

### Temporal Cluster
```
chunk_A (timestamp: 2025-11-18 10:00)
chunk_B (timestamp: 2025-11-18 10:15)

Relationship: chunk_A --[temporal_cluster]--> chunk_B
```

**Detection:** Timestamp proximity analysis
**When:** After indexing (requires comparing across chunks)
**Layer:** MANAGE or GRAPH (analytical)

---

### Decision Implements
```
chunk_decision: "We decided to use JWT for auth"
chunk_code: "class JWTAuthenticator..."

Relationship: chunk_decision --[decision_implements]--> chunk_code
```

**Detection:** Pattern matching (keywords + entity overlap)
**When:** After indexing (requires corpus analysis)
**Layer:** MANAGE or GRAPH (semantic)

---

## My Interpretation of Your Layers

**You're saying:**

```
Layer 1 (COMPILE - Document Structure):
  ├─ Phases (design/develop/document)
  ├─ Section types (Decision/Pattern/Context)
  └─ Document hierarchy

Layer 2 (MANAGE - Project Knowledge):
  ├─ Entities (jwt, redis, authentication)
  ├─ Concepts (security-pattern, caching-strategy)
  └─ Project-specific normalization

Layer 3 (EMERGENT - Graph):
  ├─ Relationships between chunks
  ├─ Graph structure
  └─ Discovered through analysis, not parsing
```

**This makes sense.**

---

## Proposed Architecture

### COMPILE Domain
**Responsibility:** Extract chunks + deterministic structural relationships

```python
# compile/indexer.py
def index_phase(phase, files):
    chunks = []
    for file in files:
        file_chunks = parser.parse_file(file)
        chunks.extend(file_chunks)
    
    # Detect STRUCTURAL relationships (deterministic)
    structural_edges = detect_structural_relationships(chunks)
    # Returns: [(chunk_i, chunk_i+1, "spatial_proximity"), ...]
    
    store.upsert(chunks)
    store.upsert_relationships(structural_edges)
```

**Relationships detected:**
- `spatial_proximity` - sequential chunks in document
- `conversation_continues` - sequential messages in session
- `document_hierarchy` - H3 under H2 parent

**Characteristics:** Fast, deterministic, local to document.

---

### MANAGE Domain
**Responsibility:** Analyze corpus + detect semantic relationships

```python
# manage/relationship_detector.py
def analyze_corpus(project_id):
    chunks = store.query(filters={"project_id": project_id})
    
    # Detect SEMANTIC relationships (analytical)
    semantic_edges = []
    
    # Temporal clustering
    semantic_edges.extend(detect_temporal_clusters(chunks))
    
    # Decision → implementation links
    semantic_edges.extend(detect_decision_implements(chunks))
    
    # Pattern → usage links
    semantic_edges.extend(detect_pattern_applied(chunks))
    
    store.upsert_relationships(semantic_edges)
```

**Relationships detected:**
- `temporal_cluster` - chunks from similar timeframe
- `decision_implements` - decision text → code chunk
- `pattern_applied` - pattern description → usage example
- `entity_cooccurrence` - chunks mentioning same entities

**Characteristics:** Slower, analytical, corpus-wide.

---

### Storage Schema
```sql
-- Chunks (metadata OF chunk)
CREATE TABLE chunks (
    id TEXT PRIMARY KEY,
    content TEXT,
    phase TEXT,              -- COMPILE metadata
    section_type TEXT,       -- COMPILE metadata
    file_path TEXT,          -- COMPILE metadata
    timestamp TEXT,          -- COMPILE metadata
    entities JSON,           -- MANAGE metadata
    concepts JSON,           -- MANAGE metadata
    ...
);

-- Relationships (edges BETWEEN chunks)
CREATE TABLE relationships (
    source_id TEXT,
    target_id TEXT,
    type TEXT,               -- spatial_proximity, decision_implements, etc.
    layer TEXT,              -- "structural" | "semantic"
    confidence REAL,         -- 1.0 for structural, <1.0 for detected
    metadata JSON,
    PRIMARY KEY (source_id, target_id, type)
);
```

**Key distinction:**
- COMPILE populates: `phase`, `section_type`, `file_path`, structural relationships
- MANAGE populates: `entities`, `concepts`, semantic relationships

---

## Relationship Builder Placement

### Option 1: Split by Layer

```
compile/
  └── structural_relationships.py
      - detect_spatial_proximity()
      - detect_conversation_flow()
      - detect_hierarchy()

manage/
  └── semantic_relationships.py
      - detect_temporal_clusters()
      - detect_decision_implements()
      - detect_pattern_applied()
```

**Flow:**
```
Index → COMPILE detects structural → store chunks + structural edges
Later → MANAGE analyzes corpus → detect semantic → store semantic edges
```

---

### Option 2: Unified Builder (Layer-Aware)

```
relationships/
  ├── builder.py           - orchestrates
  ├── structural.py        - deterministic detection
  └── semantic.py          - analytical detection
```

**Flow:**
```
Index → builder.detect_structural() → immediate
Later → builder.detect_semantic() → corpus analysis
```

---

### Option 3: No Separate Component (Inline)

```
compile/indexer.py
  - Detects spatial_proximity inline during parse

manage/analyzer.py
  - Detects semantic relationships as separate command
```

**Flow:**
```
Index → spatial edges created automatically
imem analyze → runs semantic relationship detection
```

---

## My Recommendation

**Don't create `relationship_builder.py` yet.**

### Phase 1 (Now): Spatial Only, Inline
```python
# compile/indexer.py
def index_phase(...):
    chunks = parser.parse_file(file)
    
    # Inline: detect spatial_proximity
    for i in range(len(chunks) - 1):
        edge = {
            "source_id": chunks[i]["id"],
            "target_id": chunks[i+1]["id"],
            "type": "spatial_proximity",
            "layer": "structural",
            "confidence": 1.0
        }
        # Store with chunk
    
    store.upsert(chunks, relationships=edges)
```

**Why:** Simplest. Proves relationships table works. No new component.

---

### Phase 2 (Later): Extract Structural

When you have 2+ structural relationship types:

```python
# compile/relationships.py
def detect_structural(chunks):
    edges = []
    edges.extend(detect_spatial_proximity(chunks))
    edges.extend(detect_conversation_flow(chunks))
    edges.extend(detect_hierarchy(chunks))
    return edges
```

**Why:** Abstract when you have multiple examples. Not before.

---

### Phase 3 (Future): Add Semantic

When corpus analysis becomes valuable:

```python
# manage/relationships.py
def analyze_semantic(project_id, store):
    chunks = store.query(project_id=project_id)
    
    edges = []
    edges.extend(detect_temporal_clusters(chunks))
    edges.extend(detect_decision_implements(chunks))
    return edges
```

**Why:** Separate concern. Different timing. Different domain.

---

## The Layers Clarified

**Your intuition is correct:**

### COMPILE (Universal Structure)
- Phases: design/designate/develop/document
- Section types: Decision/Pattern/Context
- **Structural relationships:** spatial_proximity, conversation_continues

**Populated:** During indexing, deterministic

---

### MANAGE (Project Knowledge)
- Entities: jwt, redis, authentication
- Concepts: security-pattern, caching-strategy
- **Semantic relationships:** decision_implements, temporal_cluster

**Populated:** After indexing, analytical

---

### EMERGENT (Graph Analysis) - Future
- PageRank scores
- Community detection
- Influence propagation
- **Graph-derived metadata:** authority_score, centrality

**Populated:** On demand, computational

---

## Answer Your Question

**Where does relationship_builder fit?**

**Not one place.** It's a responsibility split across layers:

- **COMPILE** detects structural (during parse)
- **MANAGE** detects semantic (after index)
- **GRAPH** computes emergent (on demand) - future

**Don't build `relationship_builder.py` as single component.** Build:
1. Inline spatial detection in indexer (Phase 1)
2. Extract to `compile/relationships.py` when you have 2+ types (Phase 2)
3. Add `manage/relationships.py` for semantic detection (Phase 3)

**Start minimal. Abstract when patterns emerge.**

Does this match your mental model?