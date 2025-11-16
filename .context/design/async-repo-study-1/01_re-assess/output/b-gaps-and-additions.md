# Gaps and Additions

## Functional Gaps (Missing Capabilities)

### Gap: Graph Operations (NetworkX Integration)
**Blocks:** Authority ranking, pattern discovery via graph communities
**Current state:** Placeholder in compose.py:66-73 (`_apply_graph_operations` not implemented)
**Needed:** NetworkX wrapper that materializes graph from metadata predicates
**Leverages:** Existing metadata (file_path, session_id, timestamp as edges), compose.py orchestrator

```python
# Minimal wrapper
def build_graph_from_chunks(chunks: List[Dict]) -> nx.DiGraph:
    """Materialize graph from metadata predicates (file_path, session_id)"""

def apply_pagerank(graph: nx.DiGraph, chunks: List[Dict]) -> List[Dict]:
    """Add authority scores to chunks based on PageRank"""
```

**Lines:** ~50 LOC (graph construction + PageRank wrapper)

---

### Gap: Git Validation (Temporal Intelligence)
**Blocks:** Authority scoring from ground truth, drift detection
**Current state:** Temporal position detection exists (compose.py:63), but no git diff comparison
**Needed:** Git wrapper that validates documented decisions vs actual commits
**Leverages:** Existing timestamp metadata, git subprocess calls

```python
# Minimal wrapper
def validate_against_git(chunk: Dict, repo_path: str) -> Dict:
    """Compare chunk timestamp to git commits, return validation metadata"""
    # git log --since={chunk.timestamp} --until={next_chunk.timestamp}
    # Match commit messages to chunk content
    # Return: {validated: bool, commit_sha: str, drift_score: float}
```

**Lines:** ~80 LOC (git log parsing, timestamp matching, drift scoring)

---

### Gap: Entity Resolution (Manage Layer)
**Blocks:** Reliable queries across terminology variations
**Current state:** No normalization of "jwt", "JWT", "jwt-tokens" → canonical
**Needed:** Simple entity map per project
**Leverages:** Existing metadata payloads, registry.py for project isolation

```python
# Minimal implementation
def build_entity_map(collection_name: str) -> Dict[str, str]:
    """Scan collection, detect variations, return normalization map"""
    # "jwt" appears 15x, "JWT" appears 8x → canonical: "jwt"

def normalize_query(query: str, entity_map: Dict) -> str:
    """Replace variations with canonical forms before search"""
```

**Lines:** ~60 LOC (entity detection, map building, query normalization)

---

### Gap: Schema Evolution Observer (Compile Layer)
**Blocks:** Onboarding arbitrary markdown structures
**Current state:** Fixed to LlamaIndex MarkdownNodeParser (H2/H3 chunking)
**Needed:** Observer that discovers section types from corpus patterns
**Leverages:** Existing ingest.py, metadata extraction logic

```python
# Minimal observer
def discover_section_types(collection_name: str) -> Dict[str, int]:
    """Scan all headers in corpus, return frequency distribution"""
    # "Decision:" → 45, "Choice:" → 12, "We Decided:" → 8
    # Suggest canonical mapping: all → "Decision"
```

**Lines:** ~40 LOC (corpus scan, pattern clustering)

---

## Organizational Gaps (Naming/Wrappers)

### Gap: compile/ Namespace
**Issue:** Vision uses compile/Parser, compile/Resolver but code is ingest.py
**Current state:** ingest.py does template parsing + metadata extraction
**Needed:** Wrapper module or rename for alignment
**Leverages:** Existing ingest.py implementation (no changes)

```python
# Option 1: Wrapper (preferred - no refactor)
# imem/compile.py
from .ingest import EnhancedModularIngest as Parser
from .ingest import ingest_markdown_chunked as parse_markdown

# Option 2: Documentation update
# Update architecture docs to reference ingest.py explicitly
```

**Lines:** 5 LOC (import wrapper) OR documentation update

---

### Gap: manage/ Namespace
**Issue:** Vision uses manage/Temporal, manage/Resolver, manage/Registry
**Current state:** registry.py exists, temporal is inline in compose.py:63, resolver missing
**Needed:** Organize into manage/ subpackage
**Leverages:** Existing registry.py, compose._enrich_metadata

```python
# imem/manage/__init__.py
from .registry import ProjectRegistry  # existing
from .temporal import enrich_temporal_metadata  # extract from compose.py
from .resolver import normalize_entities  # new, see functional gap above
```

**Lines:** 10 LOC (module organization) + extraction of existing code

---

### Gap: retrieve/ Namespace
**Issue:** Vision uses retrieve/Orchestrator, retrieve/Primitives, retrieve/Graph
**Current state:** compose.py is orchestrator, primitives/discovery.py exists, graph missing
**Needed:** Naming alignment via imports
**Leverages:** Existing compose.py and primitives/

```python
# imem/retrieve/__init__.py
from ..compose import compose as orchestrate
from ..primitives.discovery import *
# from .graph import build_graph, apply_pagerank  # when functional gap filled
```

**Lines:** 5 LOC (import organization)

---

### Gap: Compose Documentation
**Issue:** compose.py is underdocumented for declarative config patterns
**Current state:** Working implementation, no examples in architecture docs
**Needed:** Document common composition patterns as examples
**Leverages:** Existing compose.py functionality

**Examples to document:**
- Narrative reconstruction: genealogy + siblings + temporal
- Anti-pattern discovery: siblings filtered to Failures section
- Authority ranking: graph PageRank + reference counting
- Timeline evolution: temporal both directions

**Lines:** 0 code, ~30 lines markdown in architecture_imem-i2.md

---

## Minimal Additions List

### High Priority (v1 Blockers)

1. **NetworkX graph wrapper** — Enables authority ranking (PageRank), wraps compose.py placeholder
   - `build_graph_from_chunks()` materializes graph from metadata
   - `apply_pagerank()` adds authority scores
   - **Lines:** ~50 LOC

2. **Git validation wrapper** — Grounds truth via commit comparison, adds drift detection
   - `validate_against_git()` compares chunk timestamps to git log
   - Returns validation metadata (commit_sha, drift_score)
   - **Lines:** ~80 LOC

3. **Entity resolution basics** — Enables reliable queries ("jwt" vs "JWT")
   - `build_entity_map()` scans corpus for variations
   - `normalize_query()` replaces with canonical forms
   - **Lines:** ~60 LOC

4. **Namespace wrappers** — Aligns code to vision terminology (compile/, manage/, retrieve/)
   - Import wrappers for existing modules
   - No refactoring, just organization
   - **Lines:** ~20 LOC across 3 files

**Total v1 additions: ~210 LOC**

---

### Medium Priority (v1 Polish)

1. **Schema observer** — Auto-discovers section types from corpus
   - `discover_section_types()` scans headers, suggests canonical mappings
   - Enables onboarding arbitrary markdown structures
   - **Lines:** ~40 LOC

2. **Compose pattern documentation** — Examples of common composition patterns
   - Narrative reconstruction, anti-pattern discovery, etc.
   - Markdown documentation, no code
   - **Lines:** 0 code, ~30 lines docs

3. **Template selection logic** — Graph-informed template routing
   - If high PageRank + temporal chain → evolution template
   - If many failures → anti-pattern template
   - **Lines:** ~30 LOC wrapper around existing render

**Total v1 polish: ~70 LOC + docs**

---

### Low Priority (Post-v1)

1. **Cross-project Registry (Tier 1)** — Objective facts across projects
   - Requires design for cross-project data model
   - Defer until multi-project usage patterns emerge

2. **Qualification layer (Tier 2)** — Usage metadata, authority across projects
   - Depends on cross-project registry
   - Observable usage → preset library feature

3. **SQLite backend** — Metadata-only queries without Qdrant
   - Vision mentions JSONL → SQLite → Qdrant
   - Current: Markdown → Qdrant directly (works)
   - Defer until performance needs dictate

4. **Multi-label type classification** — Chunks with multiple section_types
   - Current: single section_type per chunk
   - Vision: chunks can be "Decision + Pattern"
   - Defer until corpus examples justify complexity

---

## Key Insights

**The system is ~90% complete for v1.**

**Missing pieces are bounded enhancements:**
- Graph operations: ~50 LOC NetworkX wrapper
- Git validation: ~80 LOC subprocess wrapper
- Entity resolution: ~60 LOC normalization map
- Namespace organization: ~20 LOC imports

**No refactoring required.** Existing code (ingest.py, compose.py, primitives/) implements vision concepts under different names.

**Documentation gap > code gap.** Architecture doc should cite compose.py as "retrieve/Orchestrator implemented", primitives/ as "retrieve/Primitives implemented".

**Priority: Fill functional gaps (graph, git, entities) before organizational polish (namespaces, docs).**

**Observable pattern:** Vision documents describe ideal end-state, implementation built pragmatically toward same goals. Convergence via minimal additions, not rewrites.
