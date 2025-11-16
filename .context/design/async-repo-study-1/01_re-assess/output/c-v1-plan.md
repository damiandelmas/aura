# v1 Completion Plan

## v1 Scope Definition

**Core capabilities for v1:**
- Graph operations (PageRank authority scoring) — Fulfills vision of retrieve/Graph, enables pattern discovery
- Git validation (temporal intelligence) — Grounds documented decisions in commit history, drift detection
- Entity resolution basics — Normalizes terminology variations for reliable cross-query consistency
- Namespace alignment — Wrappers to expose compile/, manage/, retrieve/ without refactoring

**Explicitly out of scope (post-v1):**
- Cross-project Registry (Tier 1 objective facts)
- Qualification layer (Tier 2 usage metadata, preset library from observable patterns)
- SQLite backend (JSONL → SQLite → Qdrant vision)
- Multi-label type classification (chunks with multiple section_types)
- Schema evolution observer (auto-discover canonical section types)
- Graph-informed template selection (adaptive rendering based on PageRank + temporal chains)

---

## Implementation Plan

### Phase 1: Graph Operations (Foundation for Authority Scoring)

**File:** `imem/src/imem/graph.py`
**Purpose:** Enable PageRank-based authority scoring and graph-based pattern discovery
**Functions:**
```python
def build_graph_from_chunks(chunks: List[Dict[str, Any]]) -> nx.DiGraph:
    """
    Materialize directed graph from metadata predicates
    Edges: file_path (parent-child), session_id (conversation flow), timestamp (temporal)
    Returns NetworkX DiGraph with chunk IDs as nodes
    """
    # Uses existing: chunk['file_path'], chunk['session_id'], chunk['timestamp']

def apply_pagerank(graph: nx.DiGraph, chunks: List[Dict[str, Any]],
                   alpha: float = 0.85) -> List[Dict[str, Any]]:
    """
    Add 'authority_score' to chunks based on PageRank
    Mutates chunks in-place, returns for chaining
    """
    # Uses: networkx.pagerank(graph, alpha=alpha)

def detect_communities(graph: nx.DiGraph) -> Dict[str, int]:
    """
    Detect pattern communities via Louvain algorithm
    Returns: {chunk_id: community_id}
    """
    # Uses: networkx.community.louvain_communities()
```
**Leverages:** Existing metadata (file_path, session_id, timestamp), compose.py orchestrator placeholder (line 66-73)

---

### Phase 2: Git Validation (Temporal Intelligence)

**File:** `imem/src/imem/temporal.py`
**Purpose:** Validate documented decisions against commit history, enable drift detection
**Functions:**
```python
def validate_against_git(chunk: Dict[str, Any], repo_path: str) -> Dict[str, Any]:
    """
    Compare chunk timestamp to git commits
    Returns: {
        'validated': bool,          # Found matching commit
        'commit_sha': Optional[str], # SHA if validated
        'drift_score': float,       # 0.0 (perfect) to 1.0 (high drift)
        'commit_message': Optional[str]
    }
    """
    # git log --since={chunk.timestamp} --until={next_chunk.timestamp} --oneline
    # Match commit messages to chunk section_name via fuzzy match
    # Uses existing: chunk['timestamp'], chunk['section_name']

def enrich_temporal_metadata(chunks: List[Dict[str, Any]], repo_path: str) -> List[Dict[str, Any]]:
    """
    Batch validation wrapper for compose.py integration
    Calls validate_against_git() for each chunk, adds git_validation metadata
    """
    # Uses existing: compose._enrich_metadata() pattern (compose.py:62)

def detect_drift(chunk: Dict[str, Any], validation: Dict[str, Any]) -> str:
    """
    Classify drift severity based on validation metadata
    Returns: 'none' | 'low' | 'medium' | 'high'
    """
    # Compare timestamp gap, commit message similarity
```
**Leverages:** Existing timestamp metadata, subprocess.run() for git commands, compose.py enrichment pipeline

---

### Phase 3: Entity Resolution (Query Normalization)

**File:** `imem/src/imem/resolver.py`
**Purpose:** Normalize terminology variations for reliable queries across docs
**Functions:**
```python
def build_entity_map(collection_name: str,
                     client: Optional[QdrantClient] = None) -> Dict[str, str]:
    """
    Scan collection metadata, detect terminology variations
    Returns: {'JWT': 'jwt', 'jwt-tokens': 'jwt', 'Jwt': 'jwt'}

    Detection strategy:
    - Lowercase normalization (JWT, jwt → jwt)
    - Hyphen/underscore variants (jwt-auth, jwt_auth → jwt auth)
    - Count frequency, pick most common as canonical
    """
    # Scroll collection, extract unique terms from section_names and content
    # Uses existing: QdrantClient.scroll(), metadata['section_name']

def normalize_query(query: str, entity_map: Dict[str, str]) -> str:
    """
    Replace variations with canonical forms before search
    Example: "JWT authentication" → "jwt authentication"
    """
    # Simple token replacement via entity_map lookup

def save_entity_map(project_root: str, entity_map: Dict[str, str]):
    """Save entity map to ~/.context/{project_hash}_entities.json"""

def load_entity_map(project_root: str) -> Dict[str, str]:
    """Load cached entity map or return empty dict"""
```
**Leverages:** Existing registry.py patterns (path hashing, JSON storage), QdrantClient.scroll()

---

### Phase 4: Namespace Wrappers (Vision Alignment)

**File:** `imem/src/imem/compile.py`
**Purpose:** Expose compile/ namespace without refactoring ingest.py
```python
"""compile/ namespace - parse heterogeneous sources → canonical typed chunks"""
from .ingest import EnhancedModularIngest as Parser
from .ingest import ingest_markdown_chunked as parse_markdown

__all__ = ['Parser', 'parse_markdown']
```
**Leverages:** Existing ingest.py (1,200 LOC) unchanged

**File:** `imem/src/imem/manage.py`
**Purpose:** Expose manage/ namespace
```python
"""manage/ namespace - intelligence layers (temporal, resolution, registry)"""
from .registry import ProjectRegistry, register_project, get_collection_by_type
from .temporal import validate_against_git, enrich_temporal_metadata  # New in Phase 2
from .resolver import build_entity_map, normalize_query  # New in Phase 3

__all__ = [
    'ProjectRegistry', 'register_project', 'get_collection_by_type',
    'validate_against_git', 'enrich_temporal_metadata',
    'build_entity_map', 'normalize_query'
]
```
**Leverages:** Existing registry.py + new temporal.py + new resolver.py

**File:** `imem/src/imem/retrieve.py`
**Purpose:** Expose retrieve/ namespace
```python
"""retrieve/ namespace - query orchestration, discovery primitives, graph operations"""
from .compose import compose as orchestrate
from .primitives.discovery import (
    get_siblings, get_genealogy, get_temporal, cross_phase_search
)
from .graph import build_graph_from_chunks, apply_pagerank, detect_communities  # New in Phase 1

__all__ = [
    'orchestrate',
    'get_siblings', 'get_genealogy', 'get_temporal', 'cross_phase_search',
    'build_graph_from_chunks', 'apply_pagerank', 'detect_communities'
]
```
**Leverages:** Existing compose.py + primitives/ + new graph.py

---

### Phase 5: Integration (Wire Together)

**File:** `imem/src/imem/compose.py` (modify)
**Purpose:** Integrate graph and temporal enrichment into pipeline
**Changes:**
```python
# Line 66-73: Replace placeholder with real graph operations
def _apply_graph_operations(collection_name: str, results: List[Dict],
                            graph_config: dict, client, encoder) -> List[Dict]:
    """
    Apply graph-based enrichment (PageRank, communities)
    Uses: imem.graph.build_graph_from_chunks, apply_pagerank
    """
    from .graph import build_graph_from_chunks, apply_pagerank, detect_communities

    graph = build_graph_from_chunks(results)

    if graph_config.get('pagerank'):
        results = apply_pagerank(graph, results, alpha=graph_config.get('alpha', 0.85))

    if graph_config.get('communities'):
        communities = detect_communities(graph)
        for r in results:
            r['community_id'] = communities.get(r['id'])

    return results

# Line 62: Add git validation to metadata enrichment
def _enrich_metadata(results: List[Dict], repo_path: Optional[str] = None) -> List[Dict]:
    """
    Add temporal position, confidence signals, and git validation
    Uses: imem.temporal.enrich_temporal_metadata (if repo_path provided)
    """
    # ... existing temporal position detection ...

    if repo_path:
        from .temporal import enrich_temporal_metadata
        results = enrich_temporal_metadata(results, repo_path)

    return results
```
**Leverages:** Existing compose.py orchestrator structure, adds Phase 1 + Phase 2 calls

**File:** `imem/src/imem/cli.py` (modify)
**Purpose:** Add entity resolution to search commands, expose graph options
**Changes:**
```python
# Add to search commands (line ~800)
@click.command()
@click.argument('source', type=click.Choice(['develop', 'design', 'document', 'conversations', 'context']))
@click.argument('query')
@click.option('--normalize/--no-normalize', default=True, help='Normalize query via entity map')
def search(source, query, normalize, ...):
    """Search with optional entity normalization"""
    if normalize:
        from .resolver import load_entity_map, normalize_query
        entity_map = load_entity_map(project_root)
        query = normalize_query(query, entity_map)

    # ... existing search logic ...

# Add entity map builder command
@click.command()
def build_entities():
    """Build entity normalization map for current project"""
    from .resolver import build_entity_map, save_entity_map
    from .registry import get_collection_by_type

    collection = get_collection_by_type(project_root, 'context')
    entity_map = build_entity_map(collection)
    save_entity_map(project_root, entity_map)
    click.echo(f"Built entity map: {len(entity_map)} mappings")
```
**Leverages:** Existing CLI structure, registry patterns

---

## Implementation Order

1. **Phase 1: Graph operations** — Foundational capability, no dependencies, unblocks authority scoring
2. **Phase 2: Git validation** — Independent of graph, adds temporal intelligence to existing metadata
3. **Phase 3: Entity resolution** — Independent utility, improves query reliability immediately
4. **Phase 4: Namespace wrappers** — Depends on Phases 1-3 existing, pure organizational layer (5 minutes)
5. **Phase 5: Integration** — Wire graph.py into compose.py placeholder, add git validation to enrichment, expose CLI commands

**Sequencing rationale:**
- Phases 1-3 can develop in parallel (no cross-dependencies)
- Phase 4 trivial once 1-3 exist (just import statements)
- Phase 5 integration touches existing files, do last to minimize merge conflicts

---

## Success Criteria

**v1 is complete when:**
- [ ] `imem compose` with `"graph": {"pagerank": true}` adds authority_score to results
- [ ] `imem compose` with `"graph": {"communities": true}` adds community_id to results
- [ ] Git validation enriches chunks with commit_sha and drift_score when repo_path provided
- [ ] `imem build-entities` scans corpus and generates normalization map
- [ ] `imem search` with `--normalize` resolves "JWT" → "jwt" before query
- [ ] Namespace imports work: `from imem.compile import Parser`, `from imem.manage import ProjectRegistry`, `from imem.retrieve import orchestrate`
- [ ] All existing tests pass (no regression)
- [ ] Documentation updated to reference graph.py, temporal.py, resolver.py

---

## Post-v1 Considerations

**After v1 ships, consider:**

**Refactoring:**
- Extract compose._enrich_metadata temporal detection logic into manage.temporal
- Unify metadata enrichment pipeline (temporal + git + graph in single pass)

**Enhancements:**
- Schema observer for auto-discovering section types from corpus patterns
- Cross-project Registry (Tier 1 objective facts across projects)
- Observable usage → preset library (detect recurring compose patterns, suggest slash commands)
- Graph-informed template selection (high PageRank + temporal chain → evolution template)

**Performance:**
- Cache entity maps per-project (currently rebuild on each search)
- Batch git validation (single git log call for timestamp range, not per-chunk)
- Incremental graph updates (don't rebuild from scratch on each compose)
