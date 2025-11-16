# Architectural Principles: llamaindex

## Executive Summary

LlamaIndex achieves massive extensibility through **interface-first design with dependency injection**. Core abstractions (BaseRetriever, BaseQueryEngine, BasePydanticVectorStore) remain stable while 70+ vector stores and diverse query strategies plug in seamlessly. The architecture separates **retrieval from synthesis**, **storage from indexing**, and **transformation from execution** through minimal, composable interfaces. Configuration flows through a global Settings singleton that provides lazy defaults while allowing local overrides. This enables users to swap storage backends, compose custom pipelines, and extend functionality without modifying core logic—precisely the flexibility IMEM needs for storage-agnostic compilation with pluggable templates and multiple backend support.

---

## System Overview

LlamaIndex is a data framework for LLM applications that ingests, structures, and retrieves context for language models. Its architecture centers on **nodes** (atomic text chunks with metadata) that flow through **transformation pipelines** (parsing, embedding, enrichment), get stored in **pluggable backends** (vector stores, document stores, graph stores), and are retrieved via **composable query engines** that separate retrieval logic from response synthesis. The system achieves extreme extensibility through abstract base classes with narrow interfaces, dependency injection throughout, and a separation between "what to retrieve" (retrievers) and "how to respond" (synthesizers).

---

## Principle 1: Interface-First Storage Abstraction

**Observed in:** `llama_index/core/storage/`, `llama_index/core/vector_stores/types.py`, `llama-index-integrations/vector_stores/*`

**The Principle:**

Storage implementation is completely decoupled from business logic through narrow abstract base classes. All storage backends (docstore, vector store, graph store, index store) implement minimal interfaces. Query engines and retrievers depend only on these interfaces, never concrete implementations. Storage backends register as plugins in separate packages, enabling 70+ vector stores without core changes.

**How It Works:**

```python
# Core defines interface (llama_index/core/vector_stores/types.py)
class BasePydanticVectorStore(BaseComponent):
    @abstractmethod
    def add(self, nodes: List[BaseNode], **kwargs) -> List[str]: ...

    @abstractmethod
    def delete(self, ref_doc_id: str, **kwargs) -> None: ...

    @abstractmethod
    def query(self, query: VectorStoreQuery, **kwargs) -> VectorStoreQueryResult: ...

# Integrations implement interface (llama-index-integrations/vector_stores/llama-index-vector-stores-qdrant/)
class QdrantVectorStore(BasePydanticVectorStore):
    def add(self, nodes: List[BaseNode], **kwargs) -> List[str]:
        # Qdrant-specific implementation

    def query(self, query: VectorStoreQuery, **kwargs) -> VectorStoreQueryResult:
        # Qdrant-specific query translation

# Business logic depends on interface only
class VectorStoreIndex(BaseIndex):
    def __init__(self, storage_context: StorageContext, ...):
        self._vector_store = storage_context.vector_store  # Any BasePydanticVectorStore

    def _insert(self, nodes: List[BaseNode]):
        self._vector_store.add(nodes)  # Works with any implementation
```

**Storage Context Pattern:**
```python
@dataclass
class StorageContext:
    docstore: BaseDocumentStore
    index_store: BaseIndexStore
    vector_stores: Dict[str, BasePydanticVectorStore]
    graph_store: GraphStore

    @classmethod
    def from_defaults(cls, vector_store=None, docstore=None, ...):
        # Inject any implementation
        return cls(
            docstore=docstore or SimpleDocumentStore(),
            vector_store=vector_store or SimpleVectorStore()
        )
```

**Why It Matters:**

- **Storage agnostic by default:** Swap SQLite → Postgres → Qdrant without changing index/query code
- **Backend explosion:** 70+ vector stores exist as independent packages
- **Testing simplicity:** Mock storage with in-memory implementations
- **No vendor lock-in:** Storage choice is runtime configuration, not architectural decision

**Application to IMEM:**

- **Where:** `storage/` layer interfacing with `compile/` and `retrieve/`
- **How:** Define minimal `ChunkStore` and `VectorStore` interfaces that SQLite/Qdrant implement
- **Example:**

```python
# imem/storage/types.py
class ChunkStore(ABC):
    @abstractmethod
    def put_chunks(self, chunks: List[Chunk]) -> None: ...

    @abstractmethod
    def query(self, filters: MetadataFilters) -> List[Chunk]: ...

# imem/storage/sqlite.py
class SQLiteChunkStore(ChunkStore):
    def put_chunks(self, chunks: List[Chunk]):
        # SQLite-specific bulk insert

# imem/storage/qdrant.py
class QdrantChunkStore(ChunkStore):
    def put_chunks(self, chunks: List[Chunk]):
        # Qdrant-specific vector upsert

# imem/retrieve/orchestrator.py
class Orchestrator:
    def __init__(self, store: ChunkStore):  # Dependency injection
        self.store = store

    def compose(self, query: dict):
        results = self.store.query(query['search'])  # Works with any store
```

**Trade-offs:**

- **Pros:**
  - Perfect storage abstraction matching IMEM's "storage agnostic" principle
  - Easy to add new backends (future: Neo4j graph store)
  - Backend-specific optimizations stay isolated

- **Cons:**
  - Interface must be expressive enough for all backends
  - Some backend-specific features require lowest-common-denominator interface
  - Hybrid queries (metadata → vector) need careful interface design

**Adoption Recommendation:** **Adopt** — Critical foundation for IMEM's storage-agnostic architecture.

---

## Principle 2: Retrieve-Synthesize Separation

**Observed in:** `llama_index/core/base/base_retriever.py`, `llama_index/core/base/base_query_engine.py`, `llama_index/core/query_engine/retriever_query_engine.py`, `llama_index/core/response_synthesizers/`

**The Principle:**

Query execution is factored into two independent concerns: **retrieval** (what nodes to fetch) and **synthesis** (how to format/generate response). Retrievers return `List[NodeWithScore]`. Synthesizers accept nodes and produce responses. Query engines compose them via dependency injection. This separation enables mixing arbitrary retrievers with arbitrary response strategies.

**How It Works:**

```python
# Retrieval interface (base_retriever.py)
class BaseRetriever(ABC):
    @abstractmethod
    def _retrieve(self, query_bundle: QueryBundle) -> List[NodeWithScore]:
        """Return scored nodes. No response formatting."""

# Synthesis interface (response_synthesizers/base.py)
class BaseSynthesizer(ABC):
    @abstractmethod
    def synthesize(self, query: str, nodes: List[NodeWithScore]) -> Response:
        """Generate response from nodes. No retrieval."""

# Composition (retriever_query_engine.py)
class RetrieverQueryEngine(BaseQueryEngine):
    def __init__(self, retriever: BaseRetriever, response_synthesizer: BaseSynthesizer):
        self._retriever = retriever
        self._response_synthesizer = response_synthesizer

    def _query(self, query_bundle: QueryBundle) -> Response:
        # Step 1: Retrieve (WHAT to return)
        nodes = self._retriever.retrieve(query_bundle)

        # Step 2: Synthesize (HOW to format)
        return self._response_synthesizer.synthesize(query_bundle, nodes)
```

**Concrete example:**
```python
# Vector retriever + tree-summarize synthesizer
retriever = VectorIndexRetriever(index=vector_index, similarity_top_k=5)
synthesizer = get_response_synthesizer(response_mode="tree_summarize")
query_engine = RetrieverQueryEngine(retriever, synthesizer)

# Same retriever, different synthesizer (compact mode)
compact_engine = RetrieverQueryEngine(retriever, get_response_synthesizer("compact"))

# Different retriever (keyword), same synthesizer
keyword_retriever = KeywordTableRetriever(index=keyword_index)
keyword_engine = RetrieverQueryEngine(keyword_retriever, synthesizer)
```

**Why It Matters:**

- **Composability:** N retrievers × M synthesizers = N×M query strategies without code duplication
- **Testing:** Test retrieval quality independently from synthesis
- **Specialization:** Swap retrieval (vector, keyword, graph) without changing response logic
- **Reusability:** Same retriever used for chat, single-query, streaming responses

**Application to IMEM:**

- **Where:** `retrieve/Orchestrator` currently mixes "what to return" with "how to format"
- **How:** Split into `retrieve/Retriever` (discovery primitives) and `structure/Renderer` (presentation)
- **Example:**

```python
# Current IMEM (mixed concerns)
def compose(query: dict):
    results = search(query['search'])  # WHAT
    results = add_siblings(results, query['discovery'])  # WHAT
    results = enrich_metadata(results)  # HOW (presentation)
    return format_lineage(results)  # HOW (presentation)

# Proposed separation
class ChunkRetriever:
    def retrieve(self, query: dict) -> List[Chunk]:
        """Pure retrieval logic. Returns chunks with metadata."""
        results = self.search(query['search'])
        results = self.add_siblings(results, query.get('discovery', {}))
        return results

class ResponseRenderer:
    def render(self, chunks: List[Chunk], template: str) -> dict:
        """Pure presentation logic. Formats chunks for consumption."""
        enriched = self.contextualize(chunks)  # Add graph metadata
        return self.apply_template(enriched, template)

class Orchestrator:
    def __init__(self, retriever: ChunkRetriever, renderer: ResponseRenderer):
        self.retriever = retriever
        self.renderer = renderer

    def compose(self, query: dict) -> dict:
        chunks = self.retriever.retrieve(query)  # WHAT
        return self.renderer.render(chunks, query.get('template', 'default'))  # HOW
```

**Trade-offs:**

- **Pros:**
  - `retrieve/` focuses purely on WHAT (discovery primitives)
  - `structure/` focuses purely on HOW (templates, formatting)
  - Same retrieval used for different presentations (lineage view, story context)
  - Testable: retrieval quality vs presentation quality measured separately

- **Cons:**
  - Extra abstraction layer (but matches IMEM's existing architecture)
  - Need clear contract for what metadata retriever must provide to renderer

**Adoption Recommendation:** **Adopt** — Already implied by IMEM's retrieve/structure split, but make it explicit with interfaces.

---

## Principle 3: Pipeline Composition via Transform Components

**Observed in:** `llama_index/core/schema.py` (TransformComponent), `llama_index/core/ingestion/pipeline.py`, `llama_index/core/node_parser/interface.py`

**The Principle:**

Data transformations (parsing, chunking, enrichment, embedding) implement a universal `TransformComponent` interface: `__call__(nodes: Sequence[BaseNode]) -> Sequence[BaseNode]`. Pipelines chain transformations sequentially with automatic caching. Each stage is stateless, composable, and independently testable. Configuration specifies pipeline order; runtime executes chain with hash-based deduplication.

**How It Works:**

```python
# Universal transformation interface (schema.py)
class TransformComponent(BaseComponent):
    @abstractmethod
    def __call__(self, nodes: Sequence[BaseNode], **kwargs) -> Sequence[BaseNode]:
        """Transform nodes."""

# Concrete examples
class SentenceSplitter(NodeParser):  # inherits TransformComponent
    def __call__(self, nodes: Sequence[BaseNode]) -> Sequence[BaseNode]:
        return self._parse_nodes(nodes)

class TitleExtractor(TransformComponent):
    def __call__(self, nodes: Sequence[BaseNode]) -> Sequence[BaseNode]:
        for node in nodes:
            node.metadata['title'] = self._extract_title(node.text)
        return nodes

# Pipeline execution (ingestion/pipeline.py)
def run_transformations(
    nodes: Sequence[BaseNode],
    transformations: Sequence[TransformComponent],
    cache: Optional[IngestionCache] = None
) -> Sequence[BaseNode]:
    for transform in transformations:
        if cache:
            hash = get_transformation_hash(nodes, transform)
            cached_nodes = cache.get(hash)
            if cached_nodes:
                nodes = cached_nodes
                continue
        nodes = transform(nodes)  # Just call it
        if cache:
            cache.put(hash, nodes)
    return nodes
```

**Configuration-driven composition:**
```python
# Settings defines default pipeline
Settings.transformations = [
    SentenceSplitter(chunk_size=1024),
    TitleExtractor(),
    KeywordExtractor(),
    EmbeddingExtractor(embed_model=Settings.embed_model)
]

# Index uses configured pipeline
index = VectorStoreIndex.from_documents(
    documents,
    transformations=Settings.transformations  # Or override locally
)
```

**Why It Matters:**

- **Declarative pipelines:** Define transformation order without writing orchestration code
- **Stateless stages:** Each transform pure function (nodes in → nodes out), easy to test
- **Automatic caching:** Hash-based deduplication prevents re-running expensive operations
- **Composability:** Mix built-in transformations with custom ones seamlessly

**Application to IMEM:**

- **Where:** `compile/` layer (Parser → Resolver → Observer → storage)
- **How:** Define `ChunkTransform` interface, make all compilation stages implement it
- **Example:**

```python
# imem/compile/types.py
class ChunkTransform(ABC):
    @abstractmethod
    def __call__(self, chunks: List[Chunk]) -> List[Chunk]:
        """Transform chunks, return transformed chunks."""

# imem/compile/parser.py
class TemplateParser(ChunkTransform):
    def __call__(self, chunks: List[Chunk]) -> List[Chunk]:
        # Parse markdown → extract sections → create typed chunks
        return parsed_chunks

# imem/compile/resolver.py
class SchemaResolver(ChunkTransform):
    def __call__(self, chunks: List[Chunk]) -> List[Chunk]:
        # Map heterogeneous headers → canonical types
        for chunk in chunks:
            chunk.section_type = self.resolve_type(chunk.raw_header)
        return chunks

# imem/compile/observer.py
class PatternObserver(ChunkTransform):
    def __call__(self, chunks: List[Chunk]) -> List[Chunk]:
        # Detect patterns, update chunk metadata
        return chunks

# Declarative pipeline configuration
compile_pipeline = [
    TemplateParser(template_dir=".context/templates"),
    SchemaResolver(taxonomy_path=".context/taxonomy.yaml"),
    PatternObserver(),
    EntityResolver()
]

# Execute pipeline
def compile(documents: List[Document]) -> List[Chunk]:
    chunks = initial_chunks(documents)
    for transform in compile_pipeline:
        chunks = transform(chunks)
    return chunks
```

**Trade-offs:**

- **Pros:**
  - Clear separation of concerns (each stage = one transformation)
  - Easy to test each stage independently
  - Simple to reorder or add new stages
  - Caching prevents redundant work

- **Cons:**
  - All data passes through every stage (might copy large chunk lists)
  - Intermediate state must serialize to chunks (no out-of-band context)
  - Linear pipeline only (no branching/merging)

**Adoption Recommendation:** **Adopt with modification** — Use interface for composability, but IMEM's stages may need bidirectional communication (e.g., Observer → Resolver feedback). Consider allowing stages to access shared context object.

---

## Principle 4: Dependency Injection with Global Defaults

**Observed in:** `llama_index/core/settings.py`, `llama_index/core/indices/base.py`, `llama_index/core/query_engine/retriever_query_engine.py`

**The Principle:**

All components accept dependencies via constructor injection, enabling local overrides. Global `Settings` singleton provides lazy defaults when dependencies not specified. Components query `Settings.llm` or `Settings.callback_manager` if user doesn't provide instance. This balances convenience (works out-of-box) with flexibility (override anywhere).

**How It Works:**

```python
# Global settings (settings.py)
@dataclass
class _Settings:
    _llm: Optional[LLM] = None
    _embed_model: Optional[BaseEmbedding] = None
    _transformations: Optional[List[TransformComponent]] = None

    @property
    def llm(self) -> LLM:
        if self._llm is None:
            self._llm = resolve_llm("default")  # Lazy initialization
        return self._llm

    @llm.setter
    def llm(self, llm: LLMType) -> None:
        self._llm = resolve_llm(llm)

Settings = _Settings()  # Global singleton

# Components use dependency injection with defaults
class RetrieverQueryEngine(BaseQueryEngine):
    def __init__(
        self,
        retriever: BaseRetriever,
        response_synthesizer: Optional[BaseSynthesizer] = None,
        callback_manager: Optional[CallbackManager] = None
    ):
        self._retriever = retriever
        # Use provided or fall back to global default
        self._response_synthesizer = (
            response_synthesizer or
            get_response_synthesizer(llm=Settings.llm, callback_manager=Settings.callback_manager)
        )
        self.callback_manager = callback_manager or Settings.callback_manager

# User code: convenient defaults
query_engine = RetrieverQueryEngine(retriever)  # Uses Settings.llm

# User code: explicit override
custom_llm = OpenAI(model="gpt-4", temperature=0.7)
query_engine = RetrieverQueryEngine(
    retriever,
    response_synthesizer=get_response_synthesizer(llm=custom_llm)
)

# User code: set global default once
Settings.llm = custom_llm
Settings.embed_model = OpenAIEmbedding(model="text-embedding-3-large")
# Now all components use custom_llm by default
```

**Pattern in action:**
```python
class BaseIndex:
    def __init__(
        self,
        storage_context: Optional[StorageContext] = None,
        callback_manager: Optional[CallbackManager] = None,
        transformations: Optional[List[TransformComponent]] = None,
        **kwargs
    ):
        # Fallback to global defaults
        self._storage_context = storage_context or StorageContext.from_defaults()
        self._callback_manager = callback_manager or Settings.callback_manager
        self._transformations = transformations or Settings.transformations
```

**Why It Matters:**

- **Progressive disclosure:** Beginners use defaults, experts override everything
- **Consistency:** Global defaults ensure consistent behavior across application
- **Testing:** Inject mocks without touching global state
- **No framework magic:** Dependencies explicit in constructors, defaults just convenience

**Application to IMEM:**

- **Where:** Global configuration for template paths, storage backends, logging
- **How:** Create `imem.settings.Settings` singleton with lazy defaults
- **Example:**

```python
# imem/settings.py
@dataclass
class _Settings:
    _chunk_store: Optional[ChunkStore] = None
    _vector_store: Optional[VectorStore] = None
    _template_dir: Optional[Path] = None

    @property
    def chunk_store(self) -> ChunkStore:
        if self._chunk_store is None:
            self._chunk_store = SQLiteChunkStore.from_defaults()
        return self._chunk_store

    @chunk_store.setter
    def chunk_store(self, store: ChunkStore):
        self._chunk_store = store

    @property
    def template_dir(self) -> Path:
        if self._template_dir is None:
            self._template_dir = Path(".context/templates")
        return self._template_dir

Settings = _Settings()

# imem/compile/parser.py
class TemplateParser(ChunkTransform):
    def __init__(self, template_dir: Optional[Path] = None):
        self.template_dir = template_dir or Settings.template_dir

# Usage: convenient defaults
parser = TemplateParser()  # Uses Settings.template_dir

# Usage: explicit override
parser = TemplateParser(template_dir=Path("custom/templates"))

# Usage: set global default
Settings.template_dir = Path("/project/.context/templates")
Settings.chunk_store = QdrantChunkStore(url="http://localhost:6333")
```

**Trade-offs:**

- **Pros:**
  - Zero-config default experience
  - Explicit overrides when needed (no hidden magic)
  - Easy to change defaults for entire application
  - Testing friendly (inject mocks)

- **Cons:**
  - Global state can cause surprises (changing Settings affects all components)
  - Need discipline to avoid implicitly depending on Settings everywhere
  - Lazy initialization hides dependencies (harder to see what component needs)

**Adoption Recommendation:** **Adapt** — Use for storage backends and template paths, but keep compilation logic explicit. Avoid using Settings inside critical compilation stages (Parser, Resolver) to keep dependencies visible.

---

## Principle 5: Recursive Composition via Index Nodes

**Observed in:** `llama_index/core/base/base_retriever.py` (_handle_recursive_retrieval), `llama_index/core/schema.py` (IndexNode)

**The Principle:**

Nodes can reference other retrievable objects (indices, retrievers, query engines) via `IndexNode`. When retriever encounters IndexNode during retrieval, it recursively calls the referenced object's retrieve method. This enables hierarchical composition: summary nodes link to detail retrievers, creating multi-level retrieval without hardcoded orchestration.

**How It Works:**

```python
# Schema (schema.py)
class IndexNode(TextNode):
    """Node that references another index/retriever."""
    index_id: str
    obj: Optional[Union[BaseRetriever, BaseQueryEngine]] = None

# Recursive retrieval (base_retriever.py)
class BaseRetriever:
    def _retrieve_from_object(self, obj: Any, query: QueryBundle) -> List[NodeWithScore]:
        if isinstance(obj, BaseRetriever):
            return obj.retrieve(query)  # Recursive call
        elif isinstance(obj, BaseQueryEngine):
            response = obj.query(query)
            return [NodeWithScore(node=TextNode(text=str(response)))]
        elif isinstance(obj, BaseNode):
            return [NodeWithScore(node=obj)]

    def _handle_recursive_retrieval(self, query: QueryBundle, nodes: List[NodeWithScore]):
        for node in nodes:
            if isinstance(node.node, IndexNode):
                obj = node.node.obj or self.object_map.get(node.node.index_id)
                if obj:
                    # Recursively retrieve from referenced object
                    return self._retrieve_from_object(obj, query)
        return nodes
```

**Pattern enables:**
```python
# Level 1: Summary index returns high-level nodes
summary_index = SummaryIndex.from_documents(summaries)

# Level 2: Each summary node references detailed retriever
for summary_node in summary_index.nodes:
    detail_retriever = VectorIndexRetriever(index=detailed_indices[summary_node.id])
    index_node = IndexNode(
        text=summary_node.text,
        index_id=summary_node.id,
        obj=detail_retriever  # Reference to drill down
    )

# Query: Retrieves summary, automatically drills into details
retriever = summary_index.as_retriever()
results = retriever.retrieve("detailed question")
# 1. Gets summary nodes
# 2. Detects IndexNode
# 3. Recursively calls detail_retriever.retrieve()
# 4. Returns detail nodes
```

**Why It Matters:**

- **Hierarchical retrieval:** Drill from coarse to fine without manual orchestration
- **Lazy loading:** Don't fetch details until summary retrieved
- **Composability:** Any retrievable (index, retriever, query engine) can reference others
- **No hardcoded flows:** Composition structure encoded in data (IndexNode), not code

**Application to IMEM:**

- **Where:** Genealogy queries (session → chunks), cross-phase lineage (design → develop)
- **How:** Chunks can reference "detail retrievers" for siblings, genealogy, temporal context
- **Example:**

```python
# Current IMEM: Hardcoded orchestration
def compose(query: dict):
    results = search(query['search'])
    if query.get('discovery', {}).get('genealogy'):
        for chunk in results:
            siblings = get_siblings(chunk)  # Hardcoded lookup

# With recursive composition
class ChunkNode:
    content: str
    metadata: dict
    # Optional: Reference to retriever for more context
    genealogy_retriever: Optional[ChunkRetriever] = None
    sibling_retriever: Optional[ChunkRetriever] = None

class Retriever:
    def retrieve(self, query: dict) -> List[ChunkNode]:
        chunks = self.search(query['search'])

        if query.get('discovery', {}).get('genealogy'):
            for chunk in chunks:
                if chunk.genealogy_retriever:
                    # Recursive: Chunk knows how to get its genealogy
                    detail_chunks = chunk.genealogy_retriever.retrieve({})
                    chunks.extend(detail_chunks)
        return chunks

# Chunk creation encodes retrieval strategy
def create_chunk_with_context(content: str, session_id: str) -> ChunkNode:
    return ChunkNode(
        content=content,
        genealogy_retriever=GenealogyRetriever(session_id=session_id),
        sibling_retriever=SiblingRetriever(file_path=chunk.file_path)
    )
```

**Trade-offs:**

- **Pros:**
  - Retrieval structure self-describing (encoded in data)
  - No hardcoded "if genealogy requested" logic
  - Easy to add new retrieval dimensions (just attach retriever)

- **Cons:**
  - Chunk objects become heavier (carry retriever references)
  - Circular reference risk (chunk → retriever → chunks)
  - Harder to debug (retrieval path implicit in data structure)
  - May not fit IMEM's "chunks carry metadata" philosophy

**Adoption Recommendation:** **Consider** — Interesting for complex multi-hop queries, but IMEM's explicit orchestration (search → discovery → enrich) may be clearer than implicit recursive retrieval. Useful if adding very deep hierarchies (pattern → instances → details).

---

## Principle 6: Monorepo with Modular Integrations

**Observed in:** Repository structure (`llama-index-core/`, `llama-index-integrations/`, `llama-index-packs/`)

**The Principle:**

Core framework and integrations live in same repository but separate packages. Core (`llama-index-core`) defines interfaces and base implementations. Integrations (`llama-index-integrations/*`) provide concrete implementations as independent packages with own dependencies. This enables stable core with flexible ecosystem—users install only what they need.

**How It Works:**

```
llama-index/
├── llama-index-core/           # Core framework (minimal dependencies)
│   ├── llama_index/core/
│   │   ├── base/               # Abstract base classes
│   │   ├── storage/            # Storage interfaces
│   │   ├── vector_stores/      # VectorStore interface + SimpleVectorStore
│   │   └── indices/            # Index abstractions
│   └── pyproject.toml          # Core dependencies only
│
├── llama-index-integrations/   # Concrete implementations
│   ├── vector_stores/
│   │   ├── llama-index-vector-stores-qdrant/     # Separate package
│   │   │   ├── llama_index/vector_stores/qdrant/
│   │   │   └── pyproject.toml                    # qdrant-client dependency
│   │   ├── llama-index-vector-stores-pinecone/
│   │   ├── llama-index-vector-stores-chroma/
│   │   └── ...                                   # 70+ vector stores
│   └── llms/
│       ├── llama-index-llms-openai/
│       ├── llama-index-llms-anthropic/
│       └── ...
│
└── llama-index-packs/          # Pre-built workflows
```

**Installation pattern:**
```bash
# Core only (minimal dependencies)
pip install llama-index-core

# Core + specific integrations
pip install llama-index-core llama-index-vector-stores-qdrant llama-index-llms-openai

# Everything (convenience)
pip install llama-index
```

**Dependency direction:**
- Core depends on: nothing (defines interfaces)
- Integrations depend on: core (implement interfaces) + external libraries (qdrant-client, pinecone-client)
- User code depends on: core + chosen integrations

**Why It Matters:**

- **Minimal install:** Don't install Qdrant client if using Pinecone
- **Independent versioning:** Update Qdrant integration without core changes
- **Community contributions:** Add integrations without core repo permissions
- **Clear boundaries:** Core stability vs integration experimentation

**Application to IMEM:**

- **Where:** Template plugins, storage backends, output renderers
- **How:** Keep core compilation logic separate from template implementations
- **Example:**

```
imem/
├── imem-core/                  # Core compilation engine
│   ├── imem/
│   │   ├── compile/            # Parser interfaces
│   │   ├── storage/            # Storage interfaces
│   │   └── retrieve/           # Query primitives
│   └── pyproject.toml          # Minimal dependencies
│
├── imem-templates/             # Template plugins (separate package)
│   ├── changelog/
│   ├── conversation/
│   ├── adr/
│   └── rfc/
│
├── imem-storage/               # Storage implementations
│   ├── imem-storage-sqlite/
│   └── imem-storage-qdrant/
│
└── imem-integrations/          # Optional extensions
    ├── imem-git/               # Git validation
    └── imem-graph/             # NetworkX graph operations
```

**Trade-offs:**

- **Pros:**
  - Clean separation of concerns
  - Users install only what they need
  - Easy to add new templates/backends
  - Core remains stable

- **Cons:**
  - More complex packaging/releases
  - Version compatibility matrix (core vs integrations)
  - Harder to refactor across core/integrations boundary
  - May be overkill for single-team project

**Adoption Recommendation:** **Avoid for now** — IMEM is early-stage, single-team project. Monorepo with modules is fine. Consider splitting when: (1) templates become numerous, (2) multiple storage backends stabilize, (3) external contributors add integrations. Until then, keep everything in one package with clear module boundaries.

---

## Synthesis: Implications for IMEM

### Recommended Structural Changes

1. **Define Storage Interfaces** (Principle 1 - High Priority)
   - Create `ChunkStore` and `VectorStore` abstract base classes
   - SQLite and Qdrant implement these interfaces
   - `retrieve/Orchestrator` depends only on interfaces, not implementations
   - Storage choice becomes runtime configuration

2. **Separate Retrieval from Presentation** (Principle 2 - High Priority)
   - `retrieve/` returns `List[Chunk]` with full metadata (WHAT to return)
   - `structure/` accepts `List[Chunk]` and formats output (HOW to present)
   - `Orchestrator` composes them: `retrieve(query) → render(chunks, template)`

3. **Formalize Transform Pipeline** (Principle 3 - Medium Priority)
   - Define `ChunkTransform` interface: `__call__(chunks: List[Chunk]) -> List[Chunk]`
   - Parser, Resolver, Observer, EntityResolver implement this interface
   - Compilation becomes: `run_pipeline([Parser(), Resolver(), Observer()], documents)`

4. **Add Settings Singleton** (Principle 4 - Low Priority)
   - Create `imem.settings.Settings` for global defaults (template_dir, storage backend)
   - Components accept dependencies via constructor but fall back to Settings
   - Enables zero-config usage while allowing explicit overrides

### Directory Structure Implications

```
imem/
├── compile/                    # Parse heterogeneous → canonical chunks
│   ├── types.py                # ChunkTransform interface
│   ├── parser.py               # TemplateParser(ChunkTransform)
│   ├── resolver.py             # SchemaResolver(ChunkTransform)
│   ├── observer.py             # PatternObserver(ChunkTransform)
│   └── pipeline.py             # run_pipeline(transforms, documents)
│
├── manage/                     # Intelligence layers
│   ├── temporal.py             # Git validation
│   ├── resolver.py             # Entity resolution
│   └── registry.py             # Cross-project tier 1
│
├── retrieve/                   # Query primitives (WHAT to return)
│   ├── types.py                # ChunkRetriever interface
│   ├── primitives.py           # search, siblings, genealogy, temporal
│   ├── orchestrator.py         # Multi-stage composition
│   └── graph.py                # Graph algorithms
│
├── structure/                  # Presentation (HOW to format)
│   ├── renderer.py             # ResponseRenderer interface
│   ├── contextualize.py        # Add graph metadata
│   └── templates/              # Jinja2 templates
│
├── storage/                    # Backend adapters
│   ├── types.py                # ChunkStore, VectorStore interfaces
│   ├── sqlite.py               # SQLiteChunkStore(ChunkStore)
│   ├── qdrant.py               # QdrantVectorStore(VectorStore)
│   └── context.py              # StorageContext (inject backends)
│
└── settings.py                 # Global defaults singleton
```

### Key Interfaces to Define

**1. Storage Layer**
```python
class ChunkStore(ABC):
    @abstractmethod
    def put_chunks(self, chunks: List[Chunk]) -> None: ...

    @abstractmethod
    def query(self, filters: MetadataFilters) -> List[Chunk]: ...

    @abstractmethod
    def delete(self, chunk_ids: List[str]) -> None: ...

class VectorStore(ABC):
    @abstractmethod
    def upsert(self, chunks: List[Chunk], embeddings: List[Vector]) -> None: ...

    @abstractmethod
    def search(self, query_vector: Vector, filters: MetadataFilters, top_k: int) -> List[Chunk]: ...
```

**2. Compilation Pipeline**
```python
class ChunkTransform(ABC):
    @abstractmethod
    def __call__(self, chunks: List[Chunk]) -> List[Chunk]:
        """Transform chunks, return modified chunks."""

# Concrete implementations
class TemplateParser(ChunkTransform): ...
class SchemaResolver(ChunkTransform): ...
class PatternObserver(ChunkTransform): ...
```

**3. Retrieval-Synthesis Split**
```python
class ChunkRetriever(ABC):
    @abstractmethod
    def retrieve(self, query: dict) -> List[Chunk]:
        """Return chunks matching query. Pure retrieval, no formatting."""

class ResponseRenderer(ABC):
    @abstractmethod
    def render(self, chunks: List[Chunk], template: str) -> dict:
        """Format chunks for consumption. Pure presentation, no retrieval."""
```

### Extension Points to Establish

1. **Template Plugins** (compile/Templates)
   - Registry pattern: `TemplateRegistry.register("changelog", ChangelogParser)`
   - Auto-discovery: Scan `.context/templates/` for custom parsers
   - Each parser implements `ChunkTransform` interface

2. **Storage Backends** (storage/)
   - Factory pattern: `StorageContext.from_config(backend="sqlite" | "qdrant")`
   - Future additions: Neo4j, PostgreSQL, DuckDB

3. **Discovery Primitives** (retrieve/Primitives)
   - Registry for custom discovery: `Primitives.register("cross_phase", CrossPhaseDiscovery)`
   - Each primitive implements: `discover(chunks: List[Chunk], config: dict) -> List[Chunk]`

4. **Presentation Templates** (structure/Templates)
   - Jinja2 template directory: `.context/templates/render/`
   - Built-in: `lineage.j2`, `story.j2`, `reference.j2`
   - Custom: User-defined templates for project-specific formatting

---

## Summary Table

| Principle | Impact on IMEM | Adoption | Priority |
|-----------|----------------|----------|----------|
| Interface-First Storage Abstraction | Enables SQLite/Qdrant swapping, future Neo4j/Postgres | **Adopt** | High |
| Retrieve-Synthesize Separation | Clear boundary: retrieve/WHAT vs structure/HOW | **Adopt** | High |
| Pipeline Composition | Formalize compile stages as composable transforms | **Adapt** | Medium |
| Dependency Injection with Defaults | Convenient zero-config, flexible overrides | **Adapt** | Low |
| Recursive Composition | Interesting for deep hierarchies, may overcomplicate | **Consider** | Low |
| Monorepo with Modular Integrations | Overkill for early-stage, single-team project | **Avoid** | N/A |

---

## References

### Key Architectural Documents Consulted

- Core abstraction layer: `llama_index/core/base/`
- Storage interfaces: `llama_index/core/storage/`, `llama_index/core/vector_stores/types.py`
- Query composition: `llama_index/core/query_engine/retriever_query_engine.py`
- Ingestion pipeline: `llama_index/core/ingestion/pipeline.py`
- Settings pattern: `llama_index/core/settings.py`

### Critical Modules Examined

- **Interface definitions:** `base_retriever.py`, `base_query_engine.py`, `vector_stores/types.py`, `storage/docstore/types.py`
- **Composition patterns:** `retriever_query_engine.py`, `storage_context.py`, `ingestion/pipeline.py`
- **Extension system:** `llama-index-integrations/vector_stores/*` (70+ implementations)
- **Schema foundation:** `schema.py` (BaseComponent, TransformComponent, BaseNode)

### Design Decisions Observed

1. **Narrow interfaces over feature-rich base classes** — Prefer small abstract methods (3-5) that implementations must provide, rather than large base classes with many methods
2. **Dependency injection everywhere** — All components accept dependencies in constructor, enabling testing and composition
3. **Lazy defaults via Settings** — Global singleton provides conveniences, but always overridable
4. **Separation of concerns via interfaces** — Retrieval, synthesis, storage, transformation each have distinct interface
5. **Storage abstraction as first-class** — Vector stores treated as plugins, not hardcoded dependencies
6. **Transformation pipelines as sequential composition** — Simple `for transform in transforms: nodes = transform(nodes)` pattern with caching
