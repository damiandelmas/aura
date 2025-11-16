# Architectural Principles: graphiti

## Executive Summary

Graphiti is a **temporally-aware knowledge graph framework** that builds dynamic graphs from episodic data. Its architecture reveals a mature pattern: **provider-agnostic abstraction through interface delegation**, **composable search pipelines through recipe configuration**, **intelligence encapsulation in prompt versioning**, and **dual-phase processing (extraction → deduplication)**. These aren't theoretical patterns—they're operational choices that enable graphiti to support 4 different graph databases, 5+ LLM providers, and multiple embedding backends while maintaining a single coherent API. For IMEM, this translates to: separate storage interfaces from business logic, compose queries from primitives, version intelligence externally, and defer expensive operations.

---

## System Overview

**What graphiti does:** Builds real-time knowledge graphs from episodic input (messages, text, JSON). Extracts entities and relationships via LLM, deduplicates them, stores in graph database (Neo4j, FalkorDB, Kuzu, Neptune), and provides hybrid search (semantic + BM25 + graph traversal).

**Architectural approach:**
- **Provider abstraction** — Abstract `GraphDriver`, `LLMClient`, `EmbedderClient` with multiple concrete implementations
- **Intelligence as configuration** — Prompts versioned in `prompts/` library, search strategies as recipe objects
- **Dual-phase processing** — Extract first (broad), deduplicate second (precise)
- **Bi-temporal tracking** — `created_at` (when ingested) vs `valid_at` (when event occurred)
- **Composition over inheritance** — Search configs compose methods + rerankers, clients injected at runtime

---

## Principle 1: Provider-Agnostic Abstraction via Abstract Interfaces

**Observed in:** `driver/driver.py`, `llm_client/client.py`, `embedder/client.py`, `cross_encoder/client.py`

**The Principle:**

Core business logic depends on **abstract base classes** (ABC), not concrete implementations. Graph operations, LLM calls, embedding generation all flow through interfaces. Concrete providers (Neo4j, OpenAI, FalkorDB, Gemini) implement these interfaces independently. The `Graphiti` class accepts interface instances at construction, never imports provider-specific code.

**How It Works:**

```python
# graphiti_core/driver/driver.py
class GraphDriver(ABC):
    provider: GraphProvider

    @abstractmethod
    def execute_query(self, cypher_query: str, **kwargs) -> Coroutine: ...

    @abstractmethod
    def session(self, database: str | None = None) -> GraphDriverSession: ...

# graphiti_core/llm_client/client.py
class LLMClient(ABC):
    @abstractmethod
    async def _generate_response(
        self, messages: list[Message],
        response_model: type[BaseModel] | None = None,
        ...
    ) -> dict[str, Any]: ...

# graphiti_core/graphiti.py
class Graphiti:
    def __init__(
        self,
        llm_client: LLMClient | None = None,
        embedder: EmbedderClient | None = None,
        cross_encoder: CrossEncoderClient | None = None,
        graph_driver: GraphDriver | None = None,
    ):
        # Defaults to OpenAI/Neo4j if None, but accepts ANY implementation
        self.driver = graph_driver or Neo4jDriver(...)
        self.llm_client = llm_client or OpenAIClient()
```

Concrete implementations:
- **Graph:** `Neo4jDriver`, `FalkorDriver`, `KuzuDriver`, `NeptuneDriver`
- **LLM:** `OpenAIClient`, `AnthropicClient`, `GeminiClient`, `GroqClient`, `AzureOpenAIClient`
- **Embedder:** `OpenAIEmbedder`, `VoyageEmbedder`, `GeminiEmbedder`

**Why It Matters:**

- **Portability:** Users swap Neo4j → FalkorDB via config, no code change
- **Testability:** Mock interfaces for unit tests (no database/API required)
- **Extensibility:** New providers require zero changes to core logic
- **Provider evolution:** OpenAI API changes isolated to `OpenAIClient`

**Application to IMEM:**

- **Where:** `storage/`, `retrieve/`, `compile/Templates/`
- **How:** Define abstract interfaces, inject at runtime
- **Example:**
  ```python
  # storage/interface.py
  class ChunkStore(ABC):
      @abstractmethod
      async def store_chunks(self, chunks: list[Chunk]) -> None: ...

      @abstractmethod
      async def query_chunks(self, filters: dict) -> list[Chunk]: ...

  # storage/sqlite.py
  class SQLiteStore(ChunkStore):
      async def store_chunks(self, chunks):
          # SQLite-specific implementation

  # storage/qdrant.py
  class QdrantStore(ChunkStore):
      async def store_chunks(self, chunks):
          # Qdrant-specific implementation

  # retrieve/orchestrator.py
  class Orchestrator:
      def __init__(self, store: ChunkStore):  # Abstract dependency
          self.store = store
  ```

**Trade-offs:**

- **Pros:** Perfect backend swapping, testing simplicity, parallel development of providers
- **Cons:** Interface must be rich enough for all backends (lowest common denominator risk), some provider-specific optimizations harder to expose

**Adoption Recommendation:** **Adopt** — Essential for IMEM's "storage agnostic" mandate. Define `ChunkStore`, `TemplateParser`, `VectorBackend` abstractions.

---

## Principle 2: Composable Search via Recipe Configuration Objects

**Observed in:** `search/search_config.py`, `search/search_config_recipes.py`, `search/search.py`

**The Principle:**

Search strategies are **data structures**, not code. A `SearchConfig` object declares **which search methods** to run (BM25, cosine similarity, BFS) and **which reranker** to apply (RRF, MMR, cross-encoder, node distance). Pre-built recipes live in `search_config_recipes.py`. The `search()` function interprets the config and orchestrates execution. Users compose custom searches by constructing config objects.

**How It Works:**

```python
# search/search_config.py
class EdgeSearchConfig(BaseModel):
    search_methods: list[EdgeSearchMethod]  # [bm25, cosine_similarity, bfs]
    reranker: EdgeReranker  # rrf | mmr | cross_encoder | node_distance

class SearchConfig(BaseModel):
    edge_config: EdgeSearchConfig | None = None
    node_config: NodeSearchConfig | None = None
    episode_config: EpisodeSearchConfig | None = None
    community_config: CommunitySearchConfig | None = None
    limit: int = 10

# search/search_config_recipes.py
EDGE_HYBRID_SEARCH_RRF = SearchConfig(
    edge_config=EdgeSearchConfig(
        search_methods=[EdgeSearchMethod.bm25, EdgeSearchMethod.cosine_similarity],
        reranker=EdgeReranker.rrf,
    )
)

NODE_HYBRID_SEARCH_CROSS_ENCODER = SearchConfig(
    node_config=NodeSearchConfig(
        search_methods=[NodeSearchMethod.bm25, NodeSearchMethod.cosine_similarity, NodeSearchMethod.bfs],
        reranker=NodeReranker.cross_encoder,
    ),
    limit=10,
)

# search/search.py
async def search(
    clients: GraphitiClients,
    query: str,
    config: SearchConfig,  # <- Declarative strategy
    ...
) -> SearchResults:
    # Interprets config, runs methods, applies reranker
    if EdgeSearchMethod.bm25 in config.edge_config.search_methods:
        bm25_results = await edge_fulltext_search(...)
    if EdgeSearchMethod.cosine_similarity in config.edge_config.search_methods:
        semantic_results = await edge_similarity_search(...)

    # Apply configured reranker
    if config.edge_config.reranker == EdgeReranker.rrf:
        final_results = rrf(bm25_results, semantic_results)
```

**Why It Matters:**

- **Composability:** Mix-and-match search methods without writing code
- **Presets:** Common patterns (`EDGE_HYBRID_SEARCH_RRF`) reusable across codebase
- **Runtime flexibility:** Same search function, different strategies per query
- **Testability:** Verify search orchestration independent of method implementations

**Application to IMEM:**

- **Where:** `retrieve/Orchestrator`, `retrieve/Primitives`
- **How:** Define `RetrievalConfig` objects that declare multi-stage pipeline
- **Example:**
  ```python
  # retrieve/config.py
  class DiscoveryConfig(BaseModel):
      siblings: SiblingConfig | None  # {"section_types": ["Pattern"], "limit": 3}
      genealogy: bool = False
      temporal: TemporalConfig | None  # {"direction": "after", "threshold": 0.7}

  class RetrievalConfig(BaseModel):
      search: SearchConfig  # {"text": "auth", "filters": {"phase": "design"}}
      discovery: DiscoveryConfig | None
      graph: GraphConfig | None  # {"algorithm": "authority", "top": 5}

  # retrieve/orchestrator.py
  async def compose(config: RetrievalConfig, store: ChunkStore) -> Results:
      # Stage 1: Search
      chunks = await store.query_chunks(config.search)

      # Stage 2: Discovery (if configured)
      if config.discovery and config.discovery.siblings:
          chunks += await discover_siblings(chunks, config.discovery.siblings)

      # Stage 3: Graph (if configured)
      if config.graph:
          chunks = await apply_graph_ranking(chunks, config.graph)

      return chunks

  # Recipes
  DESIGN_LINEAGE_TRACE = RetrievalConfig(
      search={"text": "...", "filters": {"phase": "design"}},
      discovery={"genealogy": True, "temporal": {"direction": "after"}},
      graph={"algorithm": "authority"}
  )
  ```

**Trade-offs:**

- **Pros:** Declarative pipeline, easy to reason about, config-driven customization, recipe library emerges naturally
- **Cons:** Config schema becomes complex for sophisticated strategies, runtime interpretation overhead (negligible), debugging harder (config → execution mapping)

**Adoption Recommendation:** **Adopt** — Maps perfectly to IMEM's `compose()` pipeline. Convert current procedural composition into declarative `RetrievalConfig`.

---

## Principle 3: Intelligence as Versioned External Configuration

**Observed in:** `prompts/lib.py`, `prompts/extract_nodes.py`, `prompts/dedupe_edges.py`, `llm_client/client.py`

**The Principle:**

LLM prompts are **versioned modules in a library**, not inline strings. Each operation (extract nodes, dedupe edges, invalidate relationships) has a dedicated prompt module with multiple versions. The `prompt_library` provides namespaced access (`prompt_library.extract_nodes.v1(context)`). Prompts accept **context dictionaries**, return **structured messages**. LLM client logs **prompt name** for observability. Prompts evolve independently of business logic.

**How It Works:**

```python
# prompts/lib.py
class PromptLibrary(Protocol):
    extract_nodes: ExtractNodesPrompt
    dedupe_nodes: DedupeNodesPrompt
    extract_edges: ExtractEdgesPrompt
    invalidate_edges: InvalidateEdgesPrompt
    ...

prompt_library: PromptLibrary = PromptLibraryWrapper(PROMPT_LIBRARY_IMPL)

# prompts/extract_nodes.py
def extract_message_v1(context: dict[str, Any]) -> list[Message]:
    return [
        Message(
            role='system',
            content=f"""Extract entities from this message.
            Episode: {context['episode_content']}
            Previous context: {context['previous_episodes']}
            Entity types: {context['entity_types']}"""
        )
    ]

versions = {
    'v1': extract_message_v1,
    'extract_message': extract_message_v1,  # Default
}

# utils/maintenance/node_operations.py
async def extract_nodes(clients, episode, previous_episodes, ...):
    context = {
        'episode_content': episode.content,
        'previous_episodes': [ep.content for ep in previous_episodes],
        'entity_types': entity_types_context,
    }

    llm_response = await llm_client.generate_response(
        prompt_library.extract_nodes.extract_message(context),
        response_model=ExtractedEntities,
        prompt_name='extract_nodes.extract_message',  # Logged for observability
    )

# llm_client/client.py
async def generate_response(
    self, messages, response_model, prompt_name: str | None = None, ...
):
    with self.tracer.start_span('llm.generate') as span:
        if prompt_name:
            span.add_attributes({'prompt.name': prompt_name})  # Telemetry
```

**Why It Matters:**

- **Prompt evolution:** Improve prompts without touching business logic
- **A/B testing:** Run multiple prompt versions, compare quality
- **Observability:** Telemetry tracks which prompts are slow/expensive
- **Modularity:** Prompts as first-class modules, not buried strings
- **Context contracts:** `context: dict` makes dependencies explicit

**Application to IMEM:**

- **Where:** `compile/Templates/`, `manage/Resolver/`, schema evolution prompts
- **How:** Extract prompts from template parsers into versioned library
- **Example:**
  ```python
  # compile/prompts/lib.py
  class TemplatePromptLibrary(Protocol):
      parse_changelog: ParseChangelogPrompt
      resolve_schema: ResolveSchemaPrompt
      extract_patterns: ExtractPatternsPrompt

  template_prompts = TemplatePromptLibraryWrapper(...)

  # compile/templates/changelog.py
  async def parse_changelog(content: str, resolver: SchemaResolver):
      context = {
          'raw_content': content,
          'known_section_types': resolver.get_known_types(),
      }

      llm_response = await llm_client.generate_response(
          template_prompts.parse_changelog.v2(context),  # Versioned
          response_model=ParsedSections,
          prompt_name='parse_changelog.v2',
      )

  # Later: improve prompt without changing parser
  # compile/prompts/parse_changelog.py
  def parse_changelog_v3(context):
      # Better instructions, examples
      ...

  versions = {
      'v2': parse_changelog_v2,
      'v3': parse_changelog_v3,
      'parse_changelog': parse_changelog_v3,  # Update default
  }
  ```

**Trade-offs:**

- **Pros:** Rapid prompt iteration, clear separation of concerns, testable prompts, telemetry integration
- **Cons:** Indirection (one more layer), context dict contracts need documentation, versioning overhead for simple prompts

**Adoption Recommendation:** **Adopt** — Critical for IMEM's schema evolution and template parsing. Prompts WILL evolve frequently; external versioning prevents code churn.

---

## Principle 4: Dual-Phase Processing: Broad Extraction → Precise Deduplication

**Observed in:** `utils/maintenance/node_operations.py`, `utils/maintenance/edge_operations.py`, `utils/bulk_utils.py`

**The Principle:**

Processing happens in **two distinct phases** with different goals:

1. **Extraction** (broad, inclusive) — LLM extracts all plausible entities/relationships, erring on over-extraction. Fast, parallel.
2. **Deduplication** (precise, conservative) — LLM compares candidates, resolves duplicates via similarity + semantic judgment. Slower, careful.

Extraction uses **small/fast models**, deduplication uses **larger/smarter models**. This separates recall (phase 1) from precision (phase 2), optimizing cost and latency.

**How It Works:**

```python
# utils/maintenance/node_operations.py
async def extract_nodes(clients, episode, ...):
    # PHASE 1: Broad extraction (fast model)
    llm_response = await llm_client.generate_response(
        prompt_library.extract_nodes.extract_message(context),
        response_model=ExtractedEntities,
        model_size=ModelSize.medium,  # gpt-4o-mini
    )
    entities = llm_response['entities']  # Over-extracted, many duplicates

    # Reflexion loop: "Did we miss anything?"
    missed_entities = await extract_nodes_reflexion(...)

    return [EntityNode(name=e.name, ...) for e in entities]

# utils/bulk_utils.py
async def dedupe_nodes_bulk(
    llm_client: LLMClient,
    extracted_nodes: list[EntityNode],
    existing_nodes: list[EntityNode],
):
    # PHASE 2: Precise deduplication (smart model)
    # 1. Similarity-based candidate filtering
    candidate_indexes = _build_candidate_indexes(extracted_nodes, existing_nodes)

    # 2. LLM-based resolution for ambiguous cases
    for extracted_node in extracted_nodes:
        candidates = existing_nodes[candidate_indexes[extracted_node.uuid]]

        if len(candidates) > 0:
            # Ask LLM: "Are these the same entity?"
            resolution = await llm_client.generate_response(
                prompt_library.dedupe_nodes.dedupe(context),
                response_model=NodeResolutions,
                model_size=ModelSize.large,  # gpt-4o (smarter, more expensive)
            )

# graphiti.py: The orchestration
async def add_episode(self, content, ...):
    # Extract (broad)
    extracted_nodes = await extract_nodes(clients, episode, previous_episodes)
    extracted_edges = await extract_edges(clients, episode, extracted_nodes)

    # Deduplicate (precise)
    resolved_nodes = await dedupe_nodes_bulk(llm_client, extracted_nodes, existing_nodes)
    resolved_edges = await dedupe_edges_bulk(llm_client, extracted_edges, existing_edges)

    # Store
    await add_nodes_and_edges_bulk(driver, resolved_nodes, resolved_edges)
```

**Why It Matters:**

- **Cost optimization:** Cheap model for bulk work, expensive model for critical decisions
- **Latency:** Parallel extraction fast, sequential dedup acceptable (fewer operations)
- **Accuracy:** Over-extract prevents misses, dedup removes noise
- **Separation of concerns:** Extraction logic independent of dedup logic

**Application to IMEM:**

- **Where:** `compile/Parser` (extract) vs `manage/Resolver` (deduplicate)
- **How:** Parse broadly, resolve conservatively
- **Example:**
  ```python
  # compile/parser.py
  async def parse_document(content: str, template: Template):
      # PHASE 1: Broad extraction
      raw_sections = await template.extract_sections(content)  # Over-parse
      chunks = [Chunk(content=s.content, ...) for s in raw_sections]
      return chunks

  # manage/resolver.py
  async def resolve_entities(chunks: list[Chunk], registry: EntityRegistry):
      # PHASE 2: Precise resolution
      for chunk in chunks:
          entities = extract_entities(chunk)  # "jwt", "JWT tokens", "jwt-auth"

          for entity in entities:
              # Check registry for canonical form
              canonical = registry.get_canonical(entity)
              if not canonical:
                  # LLM resolution: "Is 'jwt-auth' the same as 'jwt'?"
                  canonical = await resolve_entity_llm(entity, registry.similar(entity))

              chunk.add_canonical_entity(canonical)

  # Compilation flow
  async def compile_repository(repo_path: str):
      # Extract all documents (broad, parallel)
      all_chunks = await asyncio.gather(*[
          parse_document(doc.content, templates.get(doc.type))
          for doc in discover_documents(repo_path)
      ])

      # Resolve entities (precise, sequential where needed)
      resolved_chunks = await resolve_entities(all_chunks, entity_registry)

      # Store
      await chunk_store.save(resolved_chunks)
  ```

**Trade-offs:**

- **Pros:** Cost-efficient, high recall + high precision, clear phase separation, parallelizable extraction
- **Cons:** Two-pass overhead (not real-time), dedup can be slow for large sets, requires maintaining two prompt sets

**Adoption Recommendation:** **Adopt** — Perfect for IMEM's `compile/` → `manage/` flow. Parse documents broadly, resolve schema/entities precisely.

---

## Principle 5: Backend-Specific Polymorphism via Provider Enum + Conditionals

**Observed in:** `nodes.py`, `edges.py`, `driver/neo4j_driver.py`, `driver/kuzu_driver.py`

**The Principle:**

When abstract interfaces can't hide provider differences (Kuzu represents edges as nodes, Neptune needs AOSS for fulltext), graphiti uses **`GraphProvider` enum + match statements** in entity classes. Nodes/Edges know how to save/delete themselves across providers. This keeps provider logic **localized to domain objects**, not scattered across the codebase.

**How It Works:**

```python
# driver/driver.py
class GraphProvider(Enum):
    NEO4J = 'neo4j'
    FALKORDB = 'falkordb'
    KUZU = 'kuzu'
    NEPTUNE = 'neptune'

class GraphDriver(ABC):
    provider: GraphProvider  # Every driver declares its provider

# nodes.py
class Node(BaseModel, ABC):
    async def delete(self, driver: GraphDriver):
        match driver.provider:
            case GraphProvider.NEO4J:
                await driver.execute_query("""
                    MATCH (n {uuid: $uuid})
                    WHERE n:Entity OR n:Episodic OR n:Community
                    DETACH DELETE n
                """, uuid=self.uuid)

            case GraphProvider.KUZU:
                # Kuzu: Entity edges are nodes, need special handling
                await driver.execute_query("""
                    MATCH (n:Entity {uuid: $uuid})-[:RELATES_TO]->(e:RelatesToNode_)
                    DETACH DELETE e
                """, uuid=self.uuid)
                await driver.execute_query("""
                    MATCH (n:Entity {uuid: $uuid})
                    DETACH DELETE n
                """, uuid=self.uuid)

            case _:  # FalkorDB, Neptune
                await driver.execute_query("""
                    MATCH (n:Entity|Episodic|Community {uuid: $uuid})
                    DETACH DELETE n
                """, uuid=self.uuid)

# edges.py
class EntityEdge(Edge):
    async def save(self, driver: GraphDriver):
        if driver.provider == GraphProvider.KUZU:
            # Kuzu: Create edge as intermediate node
            query = get_entity_edge_save_query_kuzu(...)
        else:
            # Neo4j, FalkorDB, Neptune: Standard relationship
            query = get_entity_edge_save_query_standard(...)

        await driver.execute_query(query, ...)
```

**Why It Matters:**

- **Localized variance:** Provider differences contained in domain objects, not leaked everywhere
- **Single source of truth:** `Node.delete()` handles all providers, callers don't need provider knowledge
- **Explicit contracts:** `match` statements make provider support visible
- **Graceful degradation:** Unsupported providers raise clear errors

**Application to IMEM:**

- **Where:** `storage/ChunkStore` implementations, `retrieve/Primitives`
- **How:** Enum for storage backends, conditional logic where needed
- **Example:**
  ```python
  # storage/interface.py
  class StorageBackend(Enum):
      SQLITE = 'sqlite'
      QDRANT = 'qdrant'
      HYBRID = 'hybrid'

  class ChunkStore(ABC):
      backend: StorageBackend

      async def query_chunks(self, filters: dict) -> list[Chunk]:
          match self.backend:
              case StorageBackend.SQLITE:
                  return await self._query_sqlite(filters)

              case StorageBackend.QDRANT:
                  # Qdrant needs vector conversion
                  vector = await self._filters_to_vector(filters)
                  return await self._query_qdrant(vector, filters)

              case StorageBackend.HYBRID:
                  # Metadata filter in SQLite, semantic in Qdrant
                  metadata_results = await self._query_sqlite(filters)
                  if 'semantic' in filters:
                      vector = await embedder.embed(filters['semantic'])
                      semantic_results = await self._query_qdrant(vector)
                      return merge_results(metadata_results, semantic_results)
                  return metadata_results

  # retrieve/primitives.py
  async def discover_siblings(chunk: Chunk, store: ChunkStore, config: SiblingConfig):
      # File-based relationship depends on storage
      match store.backend:
          case StorageBackend.SQLITE:
              # Can use file_path equality efficiently
              return await store.query_chunks({
                  'file_path': chunk.file_path,
                  'section_type': config.section_types,
              })

          case StorageBackend.QDRANT:
              # No file_path index, use metadata filter
              return await store.query_chunks({
                  'metadata.file_path': chunk.file_path,
                  'metadata.section_type': config.section_types,
              })
  ```

**Trade-offs:**

- **Pros:** Backend variance explicit and localized, single call site for operations, easy to add provider support
- **Cons:** Match statements grow with providers (not infinitely scalable), some code duplication, breaks pure abstraction

**Adoption Recommendation:** **Adapt** — Use for IMEM storage backends (SQLite vs Qdrant), but limit to `storage/` layer. Don't let conditionals leak into `retrieve/` or `compile/`.

---

## Principle 6: Dependency Injection via Client Bundles

**Observed in:** `graphiti_types.py`, `graphiti.py`, `search/search.py`, `utils/maintenance/`

**The Principle:**

Instead of passing 4+ client objects to every function, graphiti bundles them into a **`GraphitiClients` dataclass**. Functions accept `clients: GraphitiClients`, extract what they need. This reduces parameter sprawl, clarifies dependencies, and simplifies signature changes.

**How It Works:**

```python
# graphiti_types.py
@dataclass
class GraphitiClients:
    driver: GraphDriver
    llm_client: LLMClient
    embedder: EmbedderClient
    cross_encoder: CrossEncoderClient | None = None

# graphiti.py
class Graphiti:
    def __init__(self, llm_client, embedder, cross_encoder, graph_driver, ...):
        self.driver = graph_driver or Neo4jDriver(...)
        self.llm_client = llm_client or OpenAIClient()
        self.embedder = embedder or OpenAIEmbedder()
        self.cross_encoder = cross_encoder or OpenAIRerankerClient()

    def _get_clients(self) -> GraphitiClients:
        return GraphitiClients(
            driver=self.driver,
            llm_client=self.llm_client,
            embedder=self.embedder,
            cross_encoder=self.cross_encoder,
        )

    async def search(self, query: str, config: SearchConfig, ...):
        return await search(
            clients=self._get_clients(),  # Bundle
            query=query,
            config=config,
            ...
        )

# search/search.py
async def search(
    clients: GraphitiClients,  # Single bundle parameter
    query: str,
    config: SearchConfig,
    ...
) -> SearchResults:
    driver = clients.driver
    embedder = clients.embedder
    cross_encoder = clients.cross_encoder

    search_vector = await embedder.create(input_data=[query])
    edges = await edge_search(driver, cross_encoder, query, ...)
    ...

# utils/maintenance/node_operations.py
async def extract_nodes(
    clients: GraphitiClients,  # Same bundle pattern
    episode: EpisodicNode,
    ...
):
    llm_client = clients.llm_client
    llm_response = await llm_client.generate_response(...)
```

**Why It Matters:**

- **Reduced parameter clutter:** One bundle vs 4+ individual clients
- **Easier refactoring:** Add new client type without changing all signatures
- **Clear dependency groups:** "This function needs graph + LLM" vs "This needs all clients"
- **Testability:** Mock entire bundle or individual clients

**Application to IMEM:**

- **Where:** Across `compile/`, `manage/`, `retrieve/` boundaries
- **How:** Define `IMEMClients` or layer-specific bundles
- **Example:**
  ```python
  # core/clients.py
  @dataclass
  class IMEMClients:
      chunk_store: ChunkStore
      llm_client: LLMClient
      embedder: EmbedderClient
      entity_registry: EntityRegistry
      template_library: TemplateLibrary

  # compile/parser.py
  async def compile_repository(
      repo_path: str,
      clients: IMEMClients,
  ) -> list[Chunk]:
      templates = clients.template_library
      llm = clients.llm_client

      docs = discover_documents(repo_path)
      chunks = await asyncio.gather(*[
          parse_document(doc, templates.get(doc.type), llm)
          for doc in docs
      ])
      return chunks

  # retrieve/orchestrator.py
  async def compose(
      config: RetrievalConfig,
      clients: IMEMClients,
  ) -> Results:
      store = clients.chunk_store
      embedder = clients.embedder

      # Stage 1: Search
      chunks = await store.query_chunks(config.search, embedder)

      # Stage 2: Discovery
      if config.discovery:
          chunks += await discover_siblings(chunks, store, config.discovery)

      return chunks

  # main.py
  def create_imem_clients(config: Config) -> IMEMClients:
      return IMEMClients(
          chunk_store=SQLiteStore(config.db_path) if config.storage == 'sqlite' else QdrantStore(...),
          llm_client=OpenAIClient(config.openai_key),
          embedder=OpenAIEmbedder(...),
          entity_registry=EntityRegistry(config.registry_path),
          template_library=load_templates(config.templates_dir),
      )
  ```

**Trade-offs:**

- **Pros:** Clean signatures, easy client swapping, grouped dependencies
- **Cons:** Bundle grows with system (can split into layer-specific bundles), slight indirection

**Adoption Recommendation:** **Adopt** — Define `IMEMClients` or layer-specific bundles (`CompileClients`, `ManageClients`, `RetrieveClients`) to reduce parameter sprawl across IMEM's three layers.

---

## Synthesis: Implications for IMEM

### Recommended Structural Changes

1. **Storage abstraction layer**
   - Define `ChunkStore(ABC)` with `SQLiteStore`, `QdrantStore`, `HybridStore` implementations
   - Never import storage-specific code in `retrieve/` or `compile/`
   - Use `StorageBackend` enum for conditional logic localized to `ChunkStore` methods

2. **Retrieval as configuration**
   - Convert `compose.py` procedural pipeline → `RetrievalConfig` declarative object
   - Build recipe library: `DESIGN_LINEAGE_TRACE`, `PATTERN_DISCOVERY`, `TEMPORAL_VALIDATION`
   - `Orchestrator.compose(config: RetrievalConfig)` interprets and executes

3. **Prompt library**
   - Extract all LLM prompts from inline strings → `compile/prompts/`, `manage/prompts/`
   - Version schema evolution prompts, template parsing prompts
   - Add `prompt_name` to telemetry

4. **Dual-phase compilation**
   - `compile/Parser`: Broad extraction (fast, inclusive)
   - `manage/Resolver`: Precise entity resolution (slow, conservative)
   - Separate small-model parsing from large-model resolution

5. **Client dependency injection**
   - Define `IMEMClients` bundle with `chunk_store`, `llm_client`, `embedder`, `entity_registry`
   - Pass bundles across layer boundaries, not individual clients

### Directory Structure Implications

```
imem/
├── compile/                    # Broad extraction phase
│   ├── parser.py              # Template-based parsing orchestration
│   ├── templates/             # Domain parsers (changelog, conversation, ADR)
│   │   ├── __init__.py
│   │   ├── interface.py       # Template(ABC) with parse() method
│   │   ├── changelog.py
│   │   ├── conversation.py
│   │   └── adr.py
│   └── prompts/               # Versioned prompt library
│       ├── lib.py             # PromptLibrary wrapper
│       ├── parse_changelog.py
│       └── extract_sections.py
│
├── manage/                     # Precise resolution phase
│   ├── temporal.py            # Git validation
│   ├── resolver.py            # Entity resolution (normalize "jwt" variations)
│   ├── registry.py            # Canonical entity registry
│   └── prompts/
│       ├── lib.py
│       └── resolve_entity.py  # "Are 'jwt-auth' and 'jwt' the same?"
│
├── retrieve/                   # Query orchestration
│   ├── orchestrator.py        # compose(config: RetrievalConfig)
│   ├── config.py              # RetrievalConfig, SearchConfig, DiscoveryConfig
│   ├── recipes.py             # DESIGN_LINEAGE_TRACE, PATTERN_DISCOVERY, etc.
│   ├── primitives.py          # discover_siblings, discover_genealogy, etc.
│   └── ranking.py             # Authority, confidence, recency scoring
│
├── structure/                  # Post-retrieval presentation
│   ├── templates/             # Jinja2 presentation (not parsing templates!)
│   ├── contextualize.py       # Add graph metadata to chunks
│   └── render.py              # Format for consumption
│
├── storage/                    # Backend adapters
│   ├── interface.py           # ChunkStore(ABC), StorageBackend enum
│   ├── sqlite.py              # SQLiteStore(ChunkStore)
│   ├── qdrant.py              # QdrantStore(ChunkStore)
│   └── hybrid.py              # HybridStore(ChunkStore) - metadata→SQLite, semantic→Qdrant
│
├── core/
│   ├── clients.py             # IMEMClients bundle
│   ├── models.py              # Chunk, Document, Entity dataclasses
│   └── config.py              # System configuration
│
└── telemetry/
    └── tracing.py             # OpenTelemetry integration
```

### Key Interfaces to Define

**1. ChunkStore (Storage Abstraction)**
```python
class ChunkStore(ABC):
    backend: StorageBackend

    @abstractmethod
    async def store_chunks(self, chunks: list[Chunk]) -> None: ...

    @abstractmethod
    async def query_chunks(
        self,
        filters: dict,
        semantic_query: str | None = None,
        embedder: EmbedderClient | None = None,
    ) -> list[Chunk]: ...

    @abstractmethod
    async def get_chunk_by_id(self, chunk_id: str) -> Chunk: ...

    @abstractmethod
    async def delete_chunks(self, filters: dict) -> int: ...
```

**2. Template (Parser Plugin)**
```python
class Template(ABC):
    @abstractmethod
    async def parse(
        self,
        content: str,
        llm_client: LLMClient,
        context: dict | None = None,
    ) -> list[RawChunk]: ...

    @property
    @abstractmethod
    def supported_types(self) -> list[str]: ...  # ['changelog', 'adr']
```

**3. RetrievalConfig (Query Composition)**
```python
class SearchConfig(BaseModel):
    text: str
    filters: dict[str, Any]
    semantic: bool = True
    limit: int = 50

class DiscoveryConfig(BaseModel):
    siblings: SiblingConfig | None = None
    genealogy: bool = False
    temporal: TemporalConfig | None = None
    cross_phase: bool = False

class GraphConfig(BaseModel):
    algorithm: Literal['authority', 'pagerank', 'communities']
    top: int = 10

class RetrievalConfig(BaseModel):
    search: SearchConfig
    discovery: DiscoveryConfig | None = None
    graph: GraphConfig | None = None
```

**4. IMEMClients (Dependency Bundle)**
```python
@dataclass
class IMEMClients:
    chunk_store: ChunkStore
    llm_client: LLMClient
    embedder: EmbedderClient
    entity_registry: EntityRegistry
    template_library: dict[str, Template]
    tracer: Tracer | None = None
```

### Extension Points to Establish

1. **Template plugins** — Register new parsers without core changes
   ```python
   # User code
   class RFCTemplate(Template):
       async def parse(self, content, llm_client, context):
           # Custom RFC parsing logic
           ...

   # Registration
   template_library.register('rfc', RFCTemplate())
   ```

2. **Custom retrieval primitives** — Add discovery operations
   ```python
   # User code
   async def discover_dependencies(
       chunks: list[Chunk],
       store: ChunkStore,
       config: DependencyConfig,
   ) -> list[Chunk]:
       # Custom dependency traversal
       ...

   # Orchestrator automatically discovers and uses registered primitives
   ```

3. **Storage backends** — Plug in new databases
   ```python
   class PostgresStore(ChunkStore):
       backend = StorageBackend.POSTGRES
       async def query_chunks(self, filters, ...):
           # Postgres-specific implementation
           ...
   ```

4. **Search rerankers** — Custom ranking strategies
   ```python
   class RecencyReranker(Reranker):
       async def rerank(self, chunks: list[Chunk], config: dict) -> list[Chunk]:
           return sorted(chunks, key=lambda c: c.timestamp, reverse=True)
   ```

---

## Summary Table

| Principle | Impact on IMEM | Adoption | Priority |
|-----------|----------------|----------|----------|
| **Provider-Agnostic Abstraction** | Storage backends (SQLite, Qdrant) swappable via `ChunkStore` interface | Adopt | Critical |
| **Composable Search via Recipes** | `RetrievalConfig` objects replace procedural `compose()` pipeline | Adopt | High |
| **Intelligence as Versioned Config** | Extract prompts to `compile/prompts/`, `manage/prompts/` libraries | Adopt | High |
| **Dual-Phase Processing** | `compile/` (broad extraction) → `manage/` (precise resolution) separation | Adopt | Medium |
| **Backend Polymorphism via Enum** | `StorageBackend` enum + conditionals in `ChunkStore` methods only | Adapt | Medium |
| **Dependency Injection Bundles** | `IMEMClients` bundle reduces parameter sprawl across layers | Adopt | Low |

---

## References

**Key Architectural Documents:**
- `/home/axp/projects/fleet/hangar/code/aura/main/.context/designate/overview.md` — IMEM three-layer architecture

**Critical Modules Examined:**
- `graphiti_core/graphiti.py` — Main orchestration class, client initialization
- `graphiti_core/driver/driver.py` — Abstract driver interface, provider enum
- `graphiti_core/llm_client/client.py` — Abstract LLM client, caching, retry logic
- `graphiti_core/embedder/client.py` — Abstract embedder interface
- `graphiti_core/search/search.py` — Hybrid search orchestration
- `graphiti_core/search/search_config.py` — Declarative search configuration
- `graphiti_core/search/search_config_recipes.py` — Pre-built search strategies
- `graphiti_core/prompts/lib.py` — Versioned prompt library system
- `graphiti_core/utils/maintenance/node_operations.py` — Extraction phase
- `graphiti_core/utils/bulk_utils.py` — Deduplication phase
- `graphiti_core/nodes.py` — Node entity with provider-specific operations
- `graphiti_core/edges.py` — Edge entity with provider-specific operations

**Design Decisions Observed:**
1. **Abstract interfaces over concrete dependencies** — Enables multi-provider support
2. **Configuration objects over code** — Search strategies as data, not logic
3. **External prompt versioning** — Intelligence evolution decoupled from business logic
4. **Two-pass processing** — Optimize for recall first, precision second
5. **Enum-based polymorphism** — Localized provider variance in domain objects
6. **Client bundling** — Reduce parameter sprawl via dependency groups
