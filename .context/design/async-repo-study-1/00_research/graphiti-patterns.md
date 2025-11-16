# Pattern Extraction: graphiti

## Executive Summary

Graphiti is a temporal knowledge graph system that ingests episodic data (conversations, documents) and extracts entity-relationship triplets. Its architecture excels at **client abstraction through ABC interfaces**, **prompt versioning as data structures**, **multi-strategy hybrid search with configurable rerankers**, and **bulk deduplication using union-find compression**. These patterns are directly applicable to IMEM's compiler (template-based parsing), manager (entity resolution), and retriever (query composition) subsystems.

---

## Pattern 1: Provider Abstraction via ABC Interfaces + Runtime Strategy Selection

**Location:** `graphiti_core/driver/driver.py:49-116`, `graphiti_core/llm_client/client.py:66-243`, `graphiti_core/embedder/client.py:30-39`

**Description:**

Graphiti abstracts database drivers (Neo4j, FalkorDB, Kuzu, Neptune), LLM clients (OpenAI, Anthropic, Gemini), and embedding providers through ABC base classes. Each provider implements the same interface, enabling runtime swapping without core logic changes. The system uses:

1. **Abstract base classes** defining contracts (`execute_query()`, `generate_response()`, `create()`)
2. **Provider enum** for type detection and telemetry
3. **Shallow cloning** (`copy.copy()`) to create driver instances with different databases while reusing connections
4. **Dependency injection** — clients passed to `Graphiti.__init__()`, defaulting to OpenAI implementations

**Code Example:**

```python
# Base contract
class GraphDriver(ABC):
    provider: GraphProvider

    @abstractmethod
    def execute_query(self, cypher_query: str, **kwargs) -> Coroutine:
        raise NotImplementedError()

    def with_database(self, database: str) -> 'GraphDriver':
        """Shallow copy with different database, reuses connection"""
        cloned = copy.copy(self)
        cloned._database = database
        return cloned

# Concrete implementations
class Neo4jDriver(GraphDriver):
    provider = GraphProvider.NEO4J

class FalkorDBDriver(GraphDriver):
    provider = GraphProvider.FALKORDB

# Runtime selection
def __init__(self, graph_driver: GraphDriver | None = None, ...):
    if graph_driver:
        self.driver = graph_driver
    else:
        self.driver = Neo4jDriver(uri, user, password)
```

**Relevance to IMEM:**

- **Module:** storage/
- **Use case:** Backend adapter pattern for SQLite, Qdrant, and future stores (Postgres, Weaviate)
- **Why useful:**
  - IMEM must support multiple storage backends (SQLite for metadata, Qdrant for vectors)
  - Enables testing with in-memory stores without modifying compile/manage logic
  - Provider-specific optimizations (fulltext syntax, batch operations) isolated in implementations

**Adoption Strategy:**

- [x] Adopt directly
  - Create `StorageDriver(ABC)` with `save_chunks()`, `query_metadata()`, `vector_search()` methods
  - Implement `SQLiteDriver`, `QdrantDriver`, `HybridDriver` (delegates metadata → SQLite, vectors → Qdrant)
  - Use dependency injection in `compile/Parser` to make storage swappable
  - Add `with_collection()` shallow clone pattern for multi-tenant scenarios

**Implementation Priority:** High

---

## Pattern 2: Prompt Registry with Versioned Functions

**Location:** `graphiti_core/prompts/extract_nodes.py:66-319`, `graphiti_core/prompts/models.py`

**Description:**

Prompts are **versioned functions** returning `list[Message]`, not hardcoded strings. Each prompt function:

1. Accepts a typed context dictionary
2. Returns structured `Message` objects (system + user roles)
3. Lives in a `versions: dict[str, PromptFunction]` registry
4. Uses source-specific templates (`extract_message`, `extract_json`, `extract_text`) for different episode types

This enables A/B testing, audit trails, and domain-specific extraction without monolithic prompt strings.

**Code Example:**

```python
# Typed context and response model
def extract_nodes(context: dict[str, Any]) -> list[Message]:
    sys_prompt = "You are an AI that extracts entities from conversations."

    user_prompt = f"""
<ENTITY TYPES>
{context['entity_types']}
</ENTITY TYPES>

<EPISODE>
{context['episode_content']}
</EPISODE>

Extract entities explicitly or implicitly mentioned in EPISODE.
{context['custom_prompt']}
"""
    return [
        Message(role='system', content=sys_prompt),
        Message(role='user', content=user_prompt),
    ]

# Registry enabling versioning
versions: Versions = {
    'extract_message': extract_message,
    'extract_json': extract_json,
    'extract_text': extract_text,
    'reflexion': reflexion,
    'classify_nodes': classify_nodes,
}

# Usage
prompt_messages = versions['extract_message'](context)
response = await llm_client.generate_response(prompt_messages)
```

**Relevance to IMEM:**

- **Module:** compile/Templates
- **Use case:** Domain-specific parsers for changelog, conversation, ADR, spec files
- **Why useful:**
  - IMEM's template system needs versioned extraction prompts
  - Each document type (changelog, conversation) requires different parsing strategies
  - Enables telemetry on which prompt versions perform best for schema evolution
  - Context injection (`custom_prompt` field) allows project-specific customization

**Adoption Strategy:**

- [x] Adapt
  - Create `compile/Templates/prompts/` directory
  - Build registry: `template_changelog`, `template_conversation`, `template_adr`
  - Each function accepts `TemplateContext(content, phase, session_id, custom_rules)`
  - Registry enables prompt versioning: `extract_changelog_v1`, `extract_changelog_v2`
  - Add telemetry: track which template versions yield highest chunk quality scores

**Implementation Priority:** High

---

## Pattern 3: Multi-Strategy Hybrid Search with Configurable Rerankers

**Location:** `graphiti_core/search/search.py:68-518`, `graphiti_core/search/search_config.py`

**Description:**

Search is a **composition pipeline** where:

1. **Multiple search methods** execute in parallel (BM25 fulltext, cosine similarity, BFS graph traversal)
2. **Results are merged** via configurable rerankers (RRF, MMR, cross-encoder, node distance)
3. **Configuration objects** (`SearchConfig`, `EdgeSearchConfig`, `NodeSearchConfig`) define which strategies to use
4. **Pre-built recipes** (`COMBINED_HYBRID_SEARCH_CROSS_ENCODER`, `EDGE_HYBRID_SEARCH_RRF`) provide sensible defaults

The pattern separates **what to search** (strategies), **how to rank** (rerankers), and **what to filter** (search filters).

**Code Example:**

```python
# Configuration-driven multi-strategy search
async def edge_search(
    driver, query, query_vector, config: EdgeSearchConfig, ...
) -> tuple[list[EntityEdge], list[float]]:

    # Build tasks for configured search methods
    search_tasks = []
    if EdgeSearchMethod.bm25 in config.search_methods:
        search_tasks.append(edge_fulltext_search(driver, query, ...))
    if EdgeSearchMethod.cosine_similarity in config.search_methods:
        search_tasks.append(edge_similarity_search(driver, query_vector, ...))
    if EdgeSearchMethod.bfs in config.search_methods:
        search_tasks.append(edge_bfs_search(driver, origin_nodes, ...))

    # Execute in parallel
    search_results = await semaphore_gather(*search_tasks)

    # Apply configured reranker
    if config.reranker == EdgeReranker.rrf:
        reranked, scores = rrf(search_results)
    elif config.reranker == EdgeReranker.cross_encoder:
        reranked, scores = await cross_encoder.rank(query, candidates)

    return reranked[:config.limit], scores[:config.limit]

# Recipe-based configuration
COMBINED_HYBRID_SEARCH = SearchConfig(
    edge_config=EdgeSearchConfig(
        search_methods=[EdgeSearchMethod.bm25, EdgeSearchMethod.cosine_similarity],
        reranker=EdgeReranker.cross_encoder,
    ),
    limit=10,
)
```

**Relevance to IMEM:**

- **Module:** retrieve/Orchestrator, retrieve/Primitives
- **Use case:** Multi-stage query composition (metadata filter → semantic search → graph traversal → ranking)
- **Why useful:**
  - IMEM's retrieval needs composable primitives (siblings, genealogy, temporal, cross-phase)
  - Different queries need different strategies (code lineage = temporal + graph, pattern discovery = semantic + authority)
  - Configuration objects enable preset libraries ("Show me design decisions for feature X" → predefined SearchConfig)
  - Separates query logic (WHAT) from execution strategy (HOW)

**Adoption Strategy:**

- [x] Adapt
  - Create `retrieve/SearchConfig` with `MetadataFilter`, `SemanticSearch`, `GraphTraversal` strategies
  - Implement rerankers: `AuthorityRanker`, `TemporalRanker`, `RecencyRanker`
  - Build recipes: `DESIGN_LINEAGE_SEARCH`, `PATTERN_DISCOVERY_SEARCH`, `FEATURE_HISTORY_SEARCH`
  - Add telemetry to track which search recipes yield highest user satisfaction
  - Modify: IMEM's graph is runtime-materialized from metadata, not stored edges

**Implementation Priority:** High

---

## Pattern 4: Bulk Deduplication via Union-Find with Path Compression

**Location:** `graphiti_core/utils/bulk_utils.py:287-399`, `graphiti_core/utils/bulk_utils.py:69-98`

**Description:**

When ingesting bulk episodes, duplicate entities are resolved in two passes:

1. **First pass:** Each episode's nodes are deduped against the live graph (parallel)
2. **Second pass:** Cross-episode duplicates within the batch are found via similarity heuristics (MinHash LSH)
3. **UUID map compression:** All duplicate pairs `(alias_uuid, canonical_uuid)` are compressed using union-find with path compression to produce a **transitive canonical map**

This ensures `entity_A → entity_B` and `entity_B → entity_C` resolves to `entity_A → entity_C`, preventing dangling alias chains.

**Code Example:**

```python
def _build_directed_uuid_map(pairs: list[tuple[str, str]]) -> dict[str, str]:
    """Collapse alias → canonical chains with union-find path compression."""
    parent: dict[str, str] = {}

    def find(uuid: str) -> str:
        """Iterative path compression to root"""
        parent.setdefault(uuid, uuid)
        root = uuid
        while parent[root] != root:
            root = parent[root]

        # Path compression: repoint all nodes in chain to root
        while parent[uuid] != root:
            next_uuid = parent[uuid]
            parent[uuid] = root
            uuid = next_uuid

        return root

    # Union all pairs
    for source_uuid, target_uuid in pairs:
        parent.setdefault(source_uuid, source_uuid)
        parent.setdefault(target_uuid, target_uuid)
        parent[find(source_uuid)] = find(target_uuid)

    return {uuid: find(uuid) for uuid in parent}

# Usage in bulk dedupe
duplicate_pairs = [(node1.uuid, canonical1.uuid), (node2.uuid, canonical2.uuid), ...]
compressed_map = _build_directed_uuid_map(duplicate_pairs)

# Update edge pointers
for edge in edges:
    edge.source_node_uuid = compressed_map.get(edge.source_node_uuid, edge.source_node_uuid)
    edge.target_node_uuid = compressed_map.get(edge.target_node_uuid, edge.target_node_uuid)
```

**Relevance to IMEM:**

- **Module:** manage/Resolver (entity resolution)
- **Use case:** Normalizing entity variations ("jwt", "JWT", "jwt-tokens" → canonical `jwt`)
- **Why useful:**
  - IMEM's entity resolver must handle transitive aliases across documents
  - Prevents dangling references when `doc1: "JWT" → "jwt"` and `doc2: "jwt-auth" → "jwt"` should both point to same canonical entity
  - Efficient O(α(n)) amortized lookup with path compression (nearly constant time)
  - Handles batch imports (onboarding 20 legacy projects) without quadratic deduplication cost

**Adoption Strategy:**

- [x] Adopt directly
  - Use in `manage/Resolver.normalize_entities(chunks: list[Chunk])`
  - First pass: dedupe each document's entities against project-wide entity registry
  - Second pass: cross-document dedupe using string normalization + embedding similarity
  - Apply union-find compression to produce canonical entity map
  - Update chunk metadata: replace all entity references with canonical UUIDs

**Implementation Priority:** Medium

---

## Pattern 5: Bounded Concurrency via Semaphore-Wrapped Gather

**Location:** `graphiti_core/helpers.py:106-116`

**Description:**

All parallel operations use `semaphore_gather()` instead of `asyncio.gather()` to bound concurrency. A semaphore limits active coroutines to prevent:

- API rate limit violations (LLM, embedding providers)
- Database connection pool exhaustion
- Memory overflow from unbounded parallelism

The pattern wraps each coroutine in a semaphore-acquiring wrapper before gathering.

**Code Example:**

```python
# Bounded concurrency primitive
async def semaphore_gather(
    *coroutines: Coroutine,
    max_coroutines: int | None = None,
) -> list[Any]:
    semaphore = asyncio.Semaphore(max_coroutines or SEMAPHORE_LIMIT)

    async def _wrap_coroutine(coroutine):
        async with semaphore:
            return await coroutine

    return await asyncio.gather(*(_wrap_coroutine(c) for c in coroutines))

# Usage throughout codebase
# Extract nodes from 100 episodes in parallel, but max 20 concurrent LLM calls
extracted_nodes = await semaphore_gather(
    *[extract_nodes(clients, episode, ...) for episode in episodes],
    max_coroutines=20
)

# Search multiple strategies in parallel (metadata, semantic, graph)
search_results = await semaphore_gather(
    edge_fulltext_search(driver, query, ...),
    edge_similarity_search(driver, vector, ...),
    edge_bfs_search(driver, nodes, ...),
)
```

**Relevance to IMEM:**

- **Module:** All modules (compile, manage, retrieve)
- **Use case:** Parallel parsing, entity resolution, discovery primitives
- **Why useful:**
  - IMEM will parse 100s of documents, resolve 1000s of entities, execute complex multi-stage queries
  - Unbounded parallelism would exhaust LLM rate limits, database connections, memory
  - Environment-driven concurrency limit (`SEMAPHORE_LIMIT=20`) enables tuning per deployment
  - Single primitive (`semaphore_gather`) replaces all `asyncio.gather()` calls with bounded version

**Adoption Strategy:**

- [x] Adopt directly
  - Create `imem/utils/async_helpers.py` with identical `semaphore_gather()` implementation
  - Use for:
    - `compile/Parser.parse_repository()`: parallel document parsing
    - `manage/Resolver.resolve_entities()`: parallel embedding similarity checks
    - `retrieve/Primitives.genealogy()`: parallel session chunk retrieval
  - Set `IMEM_SEMAPHORE_LIMIT=30` in production, `IMEM_SEMAPHORE_LIMIT=5` in CI tests

**Implementation Priority:** High

---

## Summary Table

| Pattern | IMEM Module | Priority | Strategy |
|---------|-------------|----------|----------|
| Provider Abstraction via ABC Interfaces | storage/ | High | Adopt directly — create `StorageDriver(ABC)` with SQLite/Qdrant/Hybrid implementations |
| Prompt Registry with Versioned Functions | compile/Templates | High | Adapt — build template registry for changelog/conversation/ADR with versioning |
| Multi-Strategy Hybrid Search | retrieve/Orchestrator | High | Adapt — composable primitives + rerankers, but runtime graph materialization |
| Bulk Deduplication via Union-Find | manage/Resolver | Medium | Adopt directly — transitive entity alias resolution with path compression |
| Bounded Concurrency via Semaphore | All modules | High | Adopt directly — replace all `asyncio.gather()` with `semaphore_gather()` |

---

## Key Files Examined

- `graphiti_core/graphiti.py` — Main orchestrator, dependency injection
- `graphiti_core/driver/driver.py` — ABC for database providers
- `graphiti_core/llm_client/client.py` — ABC for LLM providers, retry logic, caching
- `graphiti_core/embedder/client.py` — ABC for embedding providers
- `graphiti_core/prompts/extract_nodes.py` — Versioned prompt functions registry
- `graphiti_core/search/search.py` — Multi-strategy hybrid search composition
- `graphiti_core/search/search_config.py` — Configuration objects and recipes
- `graphiti_core/utils/bulk_utils.py` — Bulk ingestion, union-find deduplication
- `graphiti_core/helpers.py` — Bounded concurrency primitive
- `graphiti_core/driver/search_interface/search_interface.py` — Provider-specific search overrides

---

## References

**Architectural Decisions Observed:**

1. **Separation of concerns:** Search strategies, rerankers, and filters are separate configuration objects
2. **Runtime polymorphism:** Provider selection via ABC + dependency injection, not factory pattern
3. **Prompt as data:** Functions returning structured messages, not strings, enabling versioning
4. **Lazy loading:** Embeddings only generated if search config requires semantic search
5. **Telemetry-aware:** Provider detection from class names for analytics without coupling

**Graphiti's Design Philosophy:**

- **Configuration over code:** SearchConfig recipes vs hardcoded query logic
- **Composability:** Parallel search strategies merged via pluggable rerankers
- **Testability:** ABC abstractions enable mock drivers/LLMs in tests
- **Performance:** Semaphore-bounded parallelism prevents resource exhaustion
- **Extensibility:** New providers implement ABC, no core changes required
