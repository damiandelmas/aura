# IMEM v2 Legacy Code (Qdrant-Hardcoded)

**Status:** Reference implementation (imports still work but should migrate to protocol)
**Purpose:** Preserve v2 capabilities as specification for future v3 features

---

## What v2 Provided

### Rich Metadata Extraction (ingest.py)
- Structured field detection: `has_rationale`, `has_solution`, `has_alternatives`
- Header hierarchy extraction (H2 parent tracking)
- Session linking for conversations
- Category/subtype parsing from frontmatter

### Advanced Search (search.py, enhanced.py)
- Multi-term boolean search (AND/OR operators)
- Hybrid scoring: 0.6 x similarity + 0.4 x recency
- Multi-model support (MiniLM, MPNet, E5-Large)
- Timestamp parsing (6 different formats)

### Discovery Primitives (discovery.py)
- Semantic + temporal hybrid queries
- Cross-collection genealogy lookup
- Quality filters (`has_rationale=True`)
- Spatial proximity with section type filtering

### Service Management (qdrant_service.py)
- Docker container lifecycle
- Health checks and status reporting

---

## Why Isolated

**Coupling issues:**
- Hardcoded QdrantClient initialization (no abstraction)
- Host/port hardcoded (`localhost:6334`)
- Bypasses VectorStore protocol
- Cannot swap backends

**Architecture issues:**
- Indexing directly creates Qdrant collections
- Search duplicates functionality in compose/processors
- Discovery not wired to orchestrator

---

## How to Use This Code

**As Specification:**
1. Read patterns and logic
2. Port to v3 protocol-based implementation
3. Test against same inputs/outputs

**Examples:**
- Field detection -> Add columns to SQLite schema
- Hybrid scoring -> Implement in RankingProcessor
- Discovery -> Query SQL directly when patterns emerge

**Do NOT:**
- Import directly from active code (except temporary bridge)
- Copy hardcoded patterns
- Bypass protocol abstraction

---

## Files

| File | Purpose | Key Logic |
|------|---------|-----------|
| `ingest.py` | Qdrant ingestion | Lines 734-741: Field detection, Lines 851-937: Conversation parsing |
| `search.py` | Multi-collection search | Lines 216-227: Filter construction, Lines 286-370: Boolean search |
| `enhanced.py` | Hybrid search | Lines 84-144: Timestamp parsing, Lines 255-281: Hybrid scoring |
| `discovery.py` | Graph queries | Lines 14-107: get_siblings(), Lines 188-269: get_temporal() |
| `qdrant_service.py` | Service management | Docker/process management |

---

## Migration Status

- [x] Moved to legacy/v2/
- [x] Imports updated in active code
- [ ] Features ported to protocol-based implementations
- [ ] Legacy code can be deleted (when v3 feature-complete)
