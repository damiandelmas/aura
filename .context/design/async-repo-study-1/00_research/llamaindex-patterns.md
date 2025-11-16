# Pattern Extraction: llamaindex

## Executive Summary

LlamaIndex excels at **composable metadata extraction** and **multi-stage query orchestration** through a clean plugin architecture. Key strengths: template-based metadata extraction with inheritance, transformation pipeline caching, sub-question decomposition for complex queries, and static registry pattern for extensibility. Directly applicable to IMEM's compile/manage/retrieve architecture - particularly for domain-specific template plugins, multi-stage discovery pipelines, and metadata enrichment workflows.

---

## Pattern 1: Template-Based Metadata Extraction with Inheritance

**Location:** `llama-index-core/llama_index/core/extractors/interface.py:22-100`, `llama-index-core/llama_index/core/extractors/metadata_extractors.py:55-120`

**Description:**

LlamaIndex separates **metadata extraction logic** from **presentation templates**. The `BaseExtractor` abstract class provides:
- **Pluggable node templates** (`node_text_template` field) for formatting how content + metadata combine
- **Async-first extraction** (`aextract()` abstract method returning `List[Dict]`)
- **Document-level aggregation** (e.g., `TitleExtractor` examines first N nodes, combines into single doc title)
- **Metadata inheritance** (extracted metadata flows into node's `metadata` dict)

Domain-specific extractors (Title, Summary, Keywords, QuestionsAnswered) subclass `BaseExtractor` and override:
1. `aextract()` - Returns metadata dicts for each node
2. Template strings - Node-level and combine-level prompts
3. Filtering logic - Which nodes qualify for extraction

**Code Example:**

```python
# Base abstraction
class BaseExtractor(TransformComponent):
    node_text_template: str = Field(
        default=DEFAULT_NODE_TEXT_TEMPLATE,  # "[Excerpt from document]\n{metadata_str}\nExcerpt:\n{content}"
        description="Template to represent how node text is mixed with metadata text.",
    )

    @abstractmethod
    async def aextract(self, nodes: Sequence[BaseNode]) -> List[Dict]:
        """Returns list of metadata dicts corresponding to each node."""

# Concrete implementation
class TitleExtractor(BaseExtractor):
    nodes: int = Field(default=5, description="Number of nodes to extract titles from.")
    node_template: str = Field(default=DEFAULT_TITLE_NODE_TEMPLATE)
    combine_template: str = Field(default=DEFAULT_TITLE_COMBINE_TEMPLATE)

    async def aextract(self, nodes: Sequence[BaseNode]) -> List[Dict]:
        nodes_by_doc_id = self.separate_nodes_by_ref_id(nodes)  # Group by document
        titles_by_doc_id = await self.extract_titles(nodes_by_doc_id)  # One title per doc
        return [{"document_title": titles_by_doc_id[node.ref_doc_id]} for node in nodes]
```

**Relevance to IMEM:**

- **Module:** compile/Templates
- **Use case:** Domain parsers (changelog, conversation, ADR) inherit from base template class, override extraction logic while sharing template infrastructure
- **Why useful:**
  - Separation of **extraction logic** (what metadata to extract) from **presentation** (how to format for LLM)
  - Document-level aggregation pattern applies to IMEM's session-level metadata (extract session summary from first N chunks)
  - Template inheritance enables consistent metadata schema across heterogeneous sources

**Adoption Strategy:**
- [x] **Adapt** - Create `BaseTemplateParser` with:
  - `node_text_template` → `chunk_template` (how chunk content + metadata combine)
  - `aextract()` → `parse_document()` returning canonical chunks
  - Domain templates (ChangelogTemplate, ConversationTemplate) subclass and override parsing logic
  - Standard interface: `parse(source: str, context: dict) -> List[Chunk]`

**Implementation Priority:** High

---

## Pattern 2: Transformation Pipeline with Content-Based Caching

**Location:** `llama-index-core/llama_index/core/ingestion/pipeline.py:55-103`

**Description:**

LlamaIndex chains transformations (node parsing → metadata extraction → embeddings) through a **functional pipeline** with **deterministic caching**:

- **Content-addressable cache keys** - Hash combines node content + transformation config
- **Incremental processing** - Cache hit = skip transformation, reuse cached nodes
- **Async variants** - Both sync (`run_transformations`) and async (`arun_transformations`)
- **In-place vs copy** - Configurable mutation strategy

Each `TransformComponent` is a callable: `nodes = transform(nodes)`. Pipeline chains them sequentially, checking cache before each step.

**Code Example:**

```python
def get_transformation_hash(
    nodes: Sequence[BaseNode], transformation: TransformComponent
) -> str:
    """Content + config → deterministic hash."""
    nodes_str = "".join([str(node.get_content(metadata_mode=MetadataMode.ALL)) for node in nodes])
    transformation_dict = transformation.to_dict()
    transform_string = remove_unstable_values(str(transformation_dict))  # Remove memory addresses
    return sha256((nodes_str + transform_string).encode("utf-8")).hexdigest()

def run_transformations(
    nodes: Sequence[BaseNode],
    transformations: Sequence[TransformComponent],
    cache: Optional[IngestionCache] = None,
    **kwargs: Any,
) -> Sequence[BaseNode]:
    """Chain transformations with optional caching."""
    for transform in transformations:
        if cache is not None:
            hash = get_transformation_hash(nodes, transform)
            cached_nodes = cache.get(hash, collection=cache_collection)
            if cached_nodes is not None:
                nodes = cached_nodes  # Cache hit
            else:
                nodes = transform(nodes, **kwargs)  # Run transformation
                cache.put(hash, nodes, collection=cache_collection)  # Cache result
        else:
            nodes = transform(nodes, **kwargs)
    return nodes
```

**Relevance to IMEM:**

- **Module:** compile/Parser, manage/Temporal
- **Use case:**
  - Compile pipeline: `parse_markdown → resolve_schema → extract_entities → enrich_metadata`
  - Incremental re-indexing: Only re-parse changed files, reuse cached chunks for unchanged docs
  - Temporal validation: Cache git diff analysis per commit SHA
- **Why useful:**
  - **Deterministic caching** eliminates redundant LLM calls for unchanged content
  - **Sequential pipeline** matches IMEM's staged compilation (parse → resolve → validate)
  - **Async support** enables parallel processing of independent transformations

**Adoption Strategy:**
- [x] **Adopt directly** - Implement `TransformComponent` protocol for IMEM stages:
  - `TemplateParser` (markdown → raw chunks)
  - `SchemaResolver` (raw chunks → typed chunks)
  - `EntityResolver` (typed chunks → normalized entities)
  - `TemporalValidator` (chunks → authority scores)
  - Pipeline: `run_compilation_pipeline(documents, [TemplateParser(), SchemaResolver(), ...])`
  - Hash on: file content + git SHA + template config

**Implementation Priority:** High

---

## Pattern 3: Sub-Question Decomposition for Complex Queries

**Location:** `llama-index-core/llama_index/core/query_engine/sub_question_query_engine.py:37-150`

**Description:**

`SubQuestionQueryEngine` breaks complex queries (e.g., "compare X and Y") into **parallel sub-questions**, each targeting a specialized query engine:

- **Question Generator** - LLM decomposes query into `SubQuestion` objects with target tools
- **Parallel Execution** - Each sub-question routes to appropriate engine (async via `run_async_tasks`)
- **Response Synthesis** - Aggregates sub-answers into final response via `BaseSynthesizer`
- **Tool Routing** - Maps sub-questions to query engines via `QueryEngineTool` metadata

Pattern enables **hierarchical query decomposition** - complex query → sub-questions → retrieval → synthesis.

**Code Example:**

```python
class SubQuestionQueryEngine(BaseQueryEngine):
    def __init__(
        self,
        question_gen: BaseQuestionGenerator,  # Decomposes query
        response_synthesizer: BaseSynthesizer,  # Aggregates answers
        query_engine_tools: Sequence[QueryEngineTool],  # Routing targets
        use_async: bool = False,
    ):
        self._question_gen = question_gen
        self._response_synthesizer = response_synthesizer
        self._query_engines = {tool.metadata.name: tool.query_engine for tool in query_engine_tools}
        self._use_async = use_async

    def _query(self, query_bundle: QueryBundle) -> RESPONSE_TYPE:
        # 1. Decompose query
        sub_questions = self._question_gen.generate(self._metadatas, query_bundle)

        # 2. Execute in parallel
        if self._use_async:
            tasks = [self._aquery_subq(sub_q, color=colors[str(ind)])
                     for ind, sub_q in enumerate(sub_questions)]
            qa_pairs = run_async_tasks(tasks)  # Parallel execution
        else:
            qa_pairs = [self._query_subq(sub_q) for sub_q in sub_questions]

        # 3. Synthesize final answer
        nodes = [node for qa_pair in qa_pairs for node in qa_pair.sources]
        source_nodes = [NodeWithScore(node=node) for node in nodes]
        response = self._response_synthesizer.synthesize(
            query=query_bundle, nodes=source_nodes
        )
        return response
```

**Relevance to IMEM:**

- **Module:** retrieve/Orchestrator
- **Use case:**
  - Complex lineage queries: "Compare auth design decisions vs actual implementations"
    - Sub-Q1: Retrieve design-phase chunks for auth (filter: phase=design, type=decision, topic=auth)
    - Sub-Q2: Retrieve develop-phase chunks for auth (filter: phase=develop, topic=auth)
    - Synthesis: Compare decisions vs implementations, detect drift
  - Cross-session pattern discovery: "How has error handling evolved across sessions?"
    - Decompose by session, retrieve error patterns per session, synthesize evolution
- **Why useful:**
  - **Parallel sub-queries** map to IMEM's discovery primitives (siblings, genealogy, temporal)
  - **Tool routing** enables query-specific backends (metadata-only → SQLite, semantic → Qdrant)
  - **Hierarchical decomposition** supports multi-stage retrieval (search → discovery → graph)

**Adoption Strategy:**
- [x] **Adapt** - Implement `QueryDecomposer` for IMEM orchestration:
  - Define `DiscoveryTool` wrappers for primitives (siblings, genealogy, temporal, cross_phase)
  - Question generator: LLM maps user intent → primitive calls with metadata filters
  - Parallel execution: Run independent primitives async, merge results
  - Synthesis: `structure/Contextualize` adds graph metadata, `structure/Render` formats output
  - Example: "Show design → develop lineage for auth" → [genealogy(session_id), cross_phase(design→develop, topic=auth)]

**Implementation Priority:** Medium

---

## Pattern 4: Static Registry with Enum-Based Dispatch

**Location:** `llama-index-core/llama_index/core/indices/registry.py:19-31`, `llama-index-core/llama_index/core/response_synthesizers/factory.py:33-80`

**Description:**

LlamaIndex uses **static type registries** (dicts) for plugin discovery, not dynamic module loading:

- **Enum keys** - `IndexStructType` enum as registry key (e.g., `TREE`, `VECTOR_STORE`, `KG`)
- **Class values** - Maps enum → concrete implementation class
- **Factory pattern** - `get_response_synthesizer()` uses `ResponseMode` enum to instantiate correct synthesizer
- **Explicit registration** - Plugins imported and registered at module load time

Simpler than dynamic discovery, but requires explicit registration. Trade-off: less magic, more control.

**Code Example:**

```python
# Static registry
INDEX_STRUCT_TYPE_TO_INDEX_CLASS: Dict[IndexStructType, Type[BaseIndex]] = {
    IndexStructType.TREE: TreeIndex,
    IndexStructType.LIST: SummaryIndex,
    IndexStructType.KEYWORD_TABLE: KeywordTableIndex,
    IndexStructType.VECTOR_STORE: VectorStoreIndex,
    IndexStructType.KG: KnowledgeGraphIndex,
    # ... 11 total index types
}

# Factory using enum dispatch
def get_response_synthesizer(
    response_mode: ResponseMode = ResponseMode.COMPACT,  # Enum key
    **kwargs
) -> BaseSynthesizer:
    if response_mode == ResponseMode.REFINE:
        return Refine(**kwargs)
    elif response_mode == ResponseMode.COMPACT:
        return CompactAndRefine(**kwargs)
    elif response_mode == ResponseMode.TREE_SUMMARIZE:
        return TreeSummarize(**kwargs)
    # ... 8 synthesis modes
```

**Relevance to IMEM:**

- **Module:** compile/Templates, storage/ (backend adapters)
- **Use case:**
  - Template registry: `TemplateType.CHANGELOG → ChangelogTemplate`, `TemplateType.CONVERSATION → ConversationTemplate`
  - Storage backend: `StorageType.SQLITE → SQLiteAdapter`, `StorageType.QDRANT → QdrantAdapter`
  - Discovery primitive: `DiscoveryType.SIBLINGS → siblings()`, `DiscoveryType.GENEALOGY → genealogy()`
- **Why useful:**
  - **Explicit > implicit** - Easy to see all registered plugins at a glance
  - **Type safety** - Enum keys prevent typos, enable IDE autocomplete
  - **Serialization** - Enum values serialize cleanly to config files

**Adoption Strategy:**
- [x] **Adopt directly** - Define registries for IMEM extensibility points:
  ```python
  # compile/Templates/registry.py
  TEMPLATE_TYPE_TO_CLASS: Dict[TemplateType, Type[BaseTemplateParser]] = {
      TemplateType.CHANGELOG: ChangelogTemplate,
      TemplateType.CONVERSATION: ConversationTemplate,
      TemplateType.ADR: ADRTemplate,
  }

  # storage/registry.py
  STORAGE_TYPE_TO_ADAPTER: Dict[StorageType, Type[BaseStorageAdapter]] = {
      StorageType.SQLITE: SQLiteAdapter,
      StorageType.QDRANT: QdrantAdapter,
  }

  # retrieve/Primitives/registry.py
  DISCOVERY_TYPE_TO_FUNC: Dict[DiscoveryType, Callable] = {
      DiscoveryType.SIBLINGS: siblings,
      DiscoveryType.GENEALOGY: genealogy,
      DiscoveryType.TEMPORAL: temporal_proximity,
      DiscoveryType.CROSS_PHASE: cross_phase_trace,
  }
  ```

**Implementation Priority:** High

---

## Pattern 5: BaseComponent with Pydantic Serialization

**Location:** `llama-index-core/llama_index/core/schema.py:80-107`

**Description:**

All LlamaIndex components inherit from `BaseComponent`, a Pydantic model that:
- **Injects `class_name` into JSON schema** - Enables polymorphic deserialization
- **Provides `class_name()` classmethod** - Unique ID for serialization (decoupled from actual class name)
- **Supports `to_dict()` / `from_dict()`** - Round-trip serialization for caching and persistence
- **Type-safe configuration** - Pydantic validation for all component configs

This enables **configuration as code** - entire pipelines serializable to JSON/YAML.

**Code Example:**

```python
class BaseComponent(BaseModel):
    """Base component object to capture class names."""

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema, handler):
        json_schema = handler(core_schema)
        # Inject class_name field for polymorphic deserialization
        if "properties" in json_schema:
            json_schema["properties"]["class_name"] = {
                "title": "Class Name",
                "type": "string",
                "default": cls.class_name(),
            }
        return json_schema

    @classmethod
    def class_name(cls) -> str:
        """Unique ID in serialization (decoupled from actual class name)."""
        return "base_component"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize component to dict."""
        return self.model_dump()

# Usage
title_extractor = TitleExtractor(llm=llm, nodes=5)
config = title_extractor.to_dict()  # {"class_name": "TitleExtractor", "nodes": 5, ...}
# ... save config to file ...
restored = TitleExtractor.from_dict(config)  # Round-trip
```

**Relevance to IMEM:**

- **Module:** All modules (compile, manage, retrieve, structure)
- **Use case:**
  - **Pipeline persistence** - Save compilation pipeline config to `.imem/config.yaml`
  - **Preset library** - Observable usage patterns → reusable query presets (serialized as JSON)
  - **Template versioning** - Schema evolution tracks template config changes via `class_name` + version field
- **Why useful:**
  - **Configuration as code** - Entire IMEM pipeline (templates, resolvers, discovery primitives) serializable
  - **Deterministic caching** - `to_dict()` output used in content-addressable hashing
  - **Version migration** - `class_name` decoupling enables refactoring without breaking saved configs

**Adoption Strategy:**
- [x] **Adopt directly** - Make all IMEM components inherit from Pydantic `BaseModel`:
  ```python
  class IMEMComponent(BaseModel):
      @classmethod
      def class_name(cls) -> str:
          return cls.__name__.lower()

      def to_dict(self) -> Dict[str, Any]:
          return self.model_dump()

      @classmethod
      def from_dict(cls, data: Dict[str, Any]) -> "IMEMComponent":
          return cls(**data)

  # All components inherit
  class ChangelogTemplate(IMEMComponent): ...
  class SchemaResolver(IMEMComponent): ...
  class TemporalValidator(IMEMComponent): ...
  ```
  - Store pipeline configs in `.imem/pipelines/{project_name}.yaml`
  - Enable CLI: `imem compile --config .imem/pipelines/my_project.yaml`

**Implementation Priority:** Medium

---

## Summary Table

| Pattern | IMEM Module | Priority | Strategy |
|---------|-------------|----------|----------|
| Template-Based Metadata Extraction | compile/Templates | High | Adapt - Create `BaseTemplateParser` with template inheritance |
| Transformation Pipeline Caching | compile/Parser, manage/Temporal | High | Adopt - Implement `TransformComponent` protocol with content hashing |
| Sub-Question Decomposition | retrieve/Orchestrator | Medium | Adapt - Implement `QueryDecomposer` mapping to discovery primitives |
| Static Registry (Enum Dispatch) | compile/Templates, storage/, retrieve/Primitives | High | Adopt - Define registries for templates, storage, primitives |
| BaseComponent Serialization | All modules | Medium | Adopt - Pydantic `BaseModel` for all components, enable config persistence |

---

## Key Files Examined

- `llama-index-core/llama_index/core/extractors/interface.py` - Base metadata extractor with template system
- `llama-index-core/llama_index/core/extractors/metadata_extractors.py` - Concrete extractors (Title, Summary, Keywords)
- `llama-index-core/llama_index/core/ingestion/pipeline.py` - Transformation pipeline with content-based caching
- `llama-index-core/llama_index/core/query_engine/sub_question_query_engine.py` - Query decomposition pattern
- `llama-index-core/llama_index/core/indices/registry.py` - Static type registry for index types
- `llama-index-core/llama_index/core/response_synthesizers/factory.py` - Factory pattern with enum dispatch
- `llama-index-core/llama_index/core/schema.py` - `BaseComponent` with Pydantic serialization

---

## References

### Architectural Insights Observed

1. **Async-First Design** - All core operations have async variants (`aextract`, `aquery`, `arun_transformations`), enabling parallel processing of independent operations.

2. **Functional Pipeline Composition** - Transformations are composable functions (`TransformComponent` callable protocol), not class hierarchies. Pipeline = sequence of transforms.

3. **Metadata Inheritance Model** - Document-level metadata flows to chunks automatically. LlamaIndex calls this "nodes inherit document metadata" - identical to IMEM's chunk inheritance model.

4. **Storage Abstraction via Protocol** - `VectorStore` defined as Protocol (structural typing), not ABC. Enables third-party implementations without inheritance. Consider for IMEM storage backends.

5. **Factory Pattern Dominance** - Nearly every complex object has `from_defaults()` classmethod for common use cases. Reduces boilerplate for standard configurations.

### Key Differences from IMEM

- **LlamaIndex focus:** Document ingestion → query (RAG-centric)
- **IMEM focus:** Multi-source synthesis (markdown + conversations + git) → knowledge compilation
- **LlamaIndex storage:** Primarily vector-centric (embeddings as first-class)
- **IMEM storage:** Metadata-centric (vectors optional, metadata = queryable edges)
- **LlamaIndex queries:** Primarily semantic search + synthesis
- **IMEM queries:** Graph traversal + discovery primitives + temporal validation

### Applicability to IMEM

**High-Value Patterns:**
1. Template-based extraction (compile/)
2. Pipeline caching (compile/, manage/)
3. Static registries (all modules)

**Medium-Value Patterns:**
1. Sub-question decomposition (retrieve/)
2. Pydantic serialization (config persistence)

**Low-Value Patterns:**
- Vector store abstractions (IMEM is metadata-first, vectors optional)
- Response synthesis modes (IMEM returns structured chunks, not LLM-generated text)

---

## Implementation Roadmap

### Phase 1: Foundation (High Priority)
1. Implement `IMEMComponent(BaseModel)` base class with serialization
2. Define static registries for templates, storage, primitives
3. Create `BaseTemplateParser` with template inheritance

### Phase 2: Pipeline (High Priority)
1. Implement `TransformComponent` protocol
2. Build `run_compilation_pipeline()` with content-based caching
3. Add hash function for deterministic cache keys

### Phase 3: Query Orchestration (Medium Priority)
1. Design `QueryDecomposer` for IMEM primitives
2. Implement parallel execution via `asyncio.gather()`
3. Build synthesis layer (structure/Contextualize + structure/Render)

### Phase 4: Configuration (Medium Priority)
1. Add `.imem/pipelines/*.yaml` config persistence
2. Implement CLI: `imem compile --config <path>`
3. Build preset library for common query patterns
