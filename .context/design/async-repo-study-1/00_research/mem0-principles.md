# Architectural Principles: mem0

## Executive Summary

mem0 is a **memory layer for AI applications** built on factory-based abstraction, config-driven assembly, dual-interface design, and strict separation of storage from business logic. The architecture prioritizes **provider pluggability over monolithic design**, using Pydantic configs + factory classes to enable runtime backend swapping without touching core logic. Key insight: **configuration is code** - topology decisions (which LLM, which vector store, which graph DB) are declarative, validated at config time, and assembled at initialization. This enables mem0 to support 25+ vector stores, 15+ LLM providers, and multiple graph backends through a unified Memory interface.

---

## System Overview

**What mem0 Does:**
Intelligent memory management for AI applications - extracting facts from conversations, storing in vector databases, maintaining entity graphs, and updating/deleting memories over time.

**Architectural Approach:**
- **Factory Pattern** for all backend integrations (LLM, embedder, vector store, graph)
- **Config-Driven Assembly** using Pydantic validation
- **Interface Abstraction** (MemoryBase, VectorStoreBase) for polymorphism
- **Separation of Concerns** - storage implementation never leaks into memory logic
- **Dual Interface** (Memory + client wrapper) for different consumption patterns

---

## Principle 1: Factory-Based Provider Abstraction

**Observed in:** `mem0/utils/factory.py`, `mem0/vector_stores/`, `mem0/llms/`, `mem0/embeddings/`

**The Principle:**

All external integrations (LLMs, vector stores, embeddings, graph stores) are instantiated through Factory classes that map provider names to implementation classes. Configuration objects (Pydantic models) validate parameters before instantiation. The Memory class receives **instances** (not provider names), achieving complete decoupling from provider-specific details.

**How It Works:**

```python
# Factory pattern
class VectorStoreFactory:
    provider_to_class = {
        "qdrant": "mem0.vector_stores.qdrant.Qdrant",
        "chroma": "mem0.vector_stores.chroma.ChromaDB",
        "pgvector": "mem0.vector_stores.pgvector.PGVector",
        # ... 25+ providers
    }

    @classmethod
    def create(cls, provider_name, config):
        class_type = cls.provider_to_class.get(provider_name)
        vector_store_instance = load_class(class_type)
        return vector_store_instance(**config)

# Usage in Memory class initialization
self.vector_store = VectorStoreFactory.create(
    config.vector_store.provider,
    config.vector_store.config
)

# All vector stores implement VectorStoreBase
class VectorStoreBase(ABC):
    @abstractmethod
    def insert(self, vectors, payloads, ids): pass

    @abstractmethod
    def search(self, query, vectors, limit, filters): pass
```

**Why It Matters:**

- **Extensibility:** Add new provider = new file + registry entry, zero core changes
- **Testability:** Mock factories return test doubles without environment setup
- **Configuration Clarity:** Provider choice is declarative, not scattered in conditionals
- **Zero Coupling:** Memory class never imports provider-specific modules

**Application to IMEM:**

- **Where:** `storage/` backends (SQLite, Qdrant), `compile/Templates/` parsers
- **How:** Define `StorageBackendFactory`, `ParserFactory` with provider registry
- **Example:**

```python
# storage/factory.py
class StorageBackendFactory:
    backends = {
        "sqlite": "imem.storage.sqlite.SQLiteBackend",
        "qdrant": "imem.storage.qdrant.QdrantBackend",
    }

    @classmethod
    def create(cls, provider: str, config: StorageConfig):
        backend_class = load_class(cls.backends[provider])
        return backend_class(config)

# compile/factory.py
class ParserFactory:
    templates = {
        "changelog": "imem.compile.templates.changelog.ChangelogParser",
        "conversation": "imem.compile.templates.conversation.ConversationParser",
        "adr": "imem.compile.templates.adr.ADRParser",
    }

    @classmethod
    def create(cls, template_type: str):
        parser_class = load_class(cls.templates[template_type])
        return parser_class()

# Usage
storage = StorageBackendFactory.create("sqlite", config.storage)
parser = ParserFactory.create("changelog")
```

**Trade-offs:**

- **Pros:** Perfect pluggability, clean provider addition, runtime swapping
- **Cons:** Indirection complexity, factory registry maintenance, dynamic imports slower

**Adoption Recommendation:** **Adopt** - Critical for IMEM's "storage agnostic" and "template-based" principles. Essential for onboarding diverse codebases.

---

## Principle 2: Config-Driven System Assembly

**Observed in:** `mem0/configs/base.py`, `mem0/memory/main.py` (initialization), all config modules

**The Principle:**

System topology is declared through nested Pydantic configs that validate structure at instantiation time. The Memory class receives a single `MemoryConfig` object containing all backend configurations. Factories consume these validated configs to assemble the runtime system. **Configuration is the dependency injection mechanism.**

**How It Works:**

```python
# Nested config structure
class MemoryConfig(BaseModel):
    vector_store: VectorStoreConfig = Field(default_factory=VectorStoreConfig)
    llm: LlmConfig = Field(default_factory=LlmConfig)
    embedder: EmbedderConfig = Field(default_factory=EmbedderConfig)
    graph_store: GraphStoreConfig = Field(default_factory=GraphStoreConfig)
    reranker: Optional[RerankerConfig] = Field(default=None)
    history_db_path: str = Field(default=os.path.join(mem0_dir, "history.db"))

class VectorStoreConfig(BaseModel):
    provider: str = Field(default="qdrant")
    config: Optional[dict] = Field(default={})

# Assembly at initialization
class Memory:
    def __init__(self, config: MemoryConfig):
        self.vector_store = VectorStoreFactory.create(
            config.vector_store.provider,
            config.vector_store.config
        )
        self.llm = LlmFactory.create(
            config.llm.provider,
            config.llm.config
        )
        self.embedding_model = EmbedderFactory.create(
            config.embedder.provider,
            config.embedder.config,
            config.vector_store.config
        )
```

**Why It Matters:**

- **Validation:** Pydantic catches invalid configs at instantiation, not runtime
- **Discoverability:** Config structure documents system dependencies
- **Testability:** Inject test configs without environment variables
- **Environment Separation:** Dev/prod/test = different config objects

**Application to IMEM:**

- **Where:** `imem/config.py` - root configuration for entire system
- **How:** Define `IMEMConfig` with nested configs for each layer
- **Example:**

```python
# imem/config.py
class CompileConfig(BaseModel):
    templates: List[str] = Field(default=["changelog", "conversation"])
    resolver_mode: str = Field(default="infer")  # infer | explicit

class StorageConfig(BaseModel):
    backend: str = Field(default="sqlite")
    config: dict = Field(default_factory=dict)

class RetrieveConfig(BaseModel):
    default_limit: int = Field(default=10)
    enable_graph: bool = Field(default=False)

class IMEMConfig(BaseModel):
    compile: CompileConfig = Field(default_factory=CompileConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    retrieve: RetrieveConfig = Field(default_factory=RetrieveConfig)
    git_root: Path = Field(...)

# Usage
config = IMEMConfig(
    git_root=Path("."),
    storage=StorageConfig(backend="qdrant", config={"url": "localhost:6333"}),
)
imem = IMEM(config)
```

**Trade-offs:**

- **Pros:** Type-safe configuration, environment decoupling, clear dependencies
- **Cons:** Config sprawl, nested validation complexity, migration when schemas change

**Adoption Recommendation:** **Adopt** - Essential for managing IMEM's multi-layer complexity and enabling flexible deployment (local SQLite vs cloud Qdrant).

---

## Principle 3: Storage-Agnostic Memory Interface

**Observed in:** `mem0/memory/base.py`, `mem0/vector_stores/base.py`, Memory class never imports provider modules

**The Principle:**

Memory operations (add, search, update, delete) are defined against abstract interfaces (`VectorStoreBase`, `MemoryBase`). The Memory class holds instances implementing these interfaces but **never depends on concrete implementations**. Storage backends are fully swappable at initialization without changing memory logic.

**How It Works:**

```python
# Abstract interface
class VectorStoreBase(ABC):
    @abstractmethod
    def search(self, query, vectors, limit=5, filters=None): pass

    @abstractmethod
    def insert(self, vectors, payloads=None, ids=None): pass

# Memory class depends only on interface
class Memory(MemoryBase):
    def __init__(self, config: MemoryConfig):
        self.vector_store: VectorStoreBase = VectorStoreFactory.create(...)

    def add(self, messages, ...):
        # Uses interface methods - no provider-specific logic
        existing_memories = self.vector_store.search(
            query=new_mem,
            vectors=embeddings,
            limit=5,
            filters=search_filters
        )

# 25+ implementations of same interface
class Qdrant(VectorStoreBase):
    def search(self, query, vectors, limit=5, filters=None):
        # Qdrant-specific implementation
        ...

class ChromaDB(VectorStoreBase):
    def search(self, query, vectors, limit=5, filters=None):
        # ChromaDB-specific implementation
        ...
```

**Why It Matters:**

- **Maintainability:** Memory logic evolves independently of storage implementations
- **Extensibility:** New backends require zero changes to memory operations
- **Testability:** Mock vector stores for fast unit tests
- **Flexibility:** Swap storage backend via config change only

**Application to IMEM:**

- **Where:** Boundary between `retrieve/` and `storage/`
- **How:** Define `ChunkRetriever` interface, all storage backends implement it
- **Example:**

```python
# storage/interface.py
class ChunkRetriever(ABC):
    @abstractmethod
    def search(self, config: dict) -> List[Chunk]: pass

    @abstractmethod
    def filter(self, metadata: dict) -> List[Chunk]: pass

    @abstractmethod
    def get_by_id(self, chunk_id: str) -> Optional[Chunk]: pass

# storage/sqlite.py
class SQLiteRetriever(ChunkRetriever):
    def search(self, config: dict) -> List[Chunk]:
        # SQLite full-text search
        ...

# storage/qdrant.py
class QdrantRetriever(ChunkRetriever):
    def search(self, config: dict) -> List[Chunk]:
        # Qdrant vector search
        ...

# retrieve/orchestrator.py
class Orchestrator:
    def __init__(self, retriever: ChunkRetriever):
        self.retriever = retriever  # Interface, not concrete type

    def compose(self, config: dict):
        results = self.retriever.search(config['search'])
        # ... orchestration logic ...
```

**Trade-offs:**

- **Pros:** Perfect storage abstraction, easy backend swapping, clean architecture
- **Cons:** Interface must be expressive enough for all backends, some optimizations harder

**Adoption Recommendation:** **Adopt** - Non-negotiable for IMEM's "storage agnostic" principle. Foundational for supporting SQLite + Qdrant.

---

## Principle 4: Metadata-First Filtering Architecture

**Observed in:** `mem0/memory/main.py` (`_build_filters_and_metadata`), vector store filtering, storage.py

**The Principle:**

All memory operations carry **session identifiers** (`user_id`, `agent_id`, `run_id`) and **actor metadata** that flow from API to storage. Filtering is metadata-driven, not query-driven. Storage backends receive structured filters (dicts) that map to provider-specific filter syntax. Metadata is both stored (for provenance) and used for scoping queries.

**How It Works:**

```python
# Metadata construction helper
def _build_filters_and_metadata(
    user_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    run_id: Optional[str] = None,
    input_metadata: Optional[Dict] = None,
    input_filters: Optional[Dict] = None,
) -> tuple[Dict, Dict]:
    """
    Returns: (metadata_for_storage, filters_for_query)
    """
    metadata = deepcopy(input_metadata) if input_metadata else {}
    filters = deepcopy(input_filters) if input_filters else {}

    # Add session identifiers to both
    if user_id:
        metadata["user_id"] = user_id
        filters["user_id"] = user_id
    # ... same for agent_id, run_id

    return metadata, filters

# Memory.add() uses this
def add(self, messages, user_id=None, agent_id=None, run_id=None, metadata=None):
    metadata_to_store, query_filters = _build_filters_and_metadata(
        user_id=user_id,
        agent_id=agent_id,
        run_id=run_id,
        input_metadata=metadata
    )

    # Store with metadata
    self._create_memory(content, embeddings, metadata_to_store)

    # Query with filters
    existing = self.vector_store.search(
        query=new_mem,
        vectors=embeddings,
        filters=query_filters  # Scoped to session
    )

# Vector stores map generic filters to provider syntax
class Qdrant(VectorStoreBase):
    def _create_filter(self, filters: dict) -> Filter:
        conditions = []
        for key, value in filters.items():
            conditions.append(FieldCondition(key=key, match=MatchValue(value=value)))
        return Filter(must=conditions)
```

**Why It Matters:**

- **Scoping:** Queries automatically scoped to user/agent/run without manual filter construction
- **Multi-Tenancy:** Session identifiers enable safe isolation between users/agents
- **Provenance:** Metadata records who/what/when for every memory
- **Backend Agnostic:** Generic filter dict adapts to Qdrant/Chroma/Pinecone syntax

**Application to IMEM:**

- **Where:** All chunk storage/retrieval operations
- **How:** Define standard metadata schema, build filters from query config
- **Example:**

```python
# imem/schema.py
class ChunkMetadata(BaseModel):
    file_path: str
    session_id: Optional[str]
    phase: str  # design | designate | develop | document
    section_type: str
    timestamp: datetime
    project_id: str

# retrieve/orchestrator.py
def compose(self, config: dict):
    # Config contains declarative filters
    filters = {
        "phase": config.get("phase", "develop"),
        "section_type": config.get("section_type"),
        "project_id": self.project_id,  # Implicit scoping
    }

    # Filters passed to storage backend
    results = self.retriever.search(
        text=config["search"]["text"],
        filters=filters  # Storage backend adapts to its syntax
    )

# storage/sqlite.py
class SQLiteRetriever:
    def search(self, text: str, filters: dict):
        conditions = []
        for key, value in filters.items():
            if value is not None:
                conditions.append(f"{key} = ?")
        where_clause = " AND ".join(conditions)
        # ... execute query ...
```

**Trade-offs:**

- **Pros:** Automatic scoping, multi-tenancy support, provider-agnostic filtering
- **Cons:** Metadata schema must be comprehensive, filter translation complexity

**Adoption Recommendation:** **Adopt** - Essential for IMEM's multi-project, multi-session, multi-type queries. Metadata IS the query substrate.

---

## Principle 5: Dual Storage for Operational History

**Observed in:** `mem0/memory/storage.py` (SQLiteManager), `mem0/memory/main.py` (history tracking), separate from vector store

**The Principle:**

Memory history (add/update/delete events) is stored in a **separate operational database** (SQLite) from the vector store. Vector stores hold current state (embeddings + metadata), while the history DB records the **event log** (old_memory → new_memory transitions). This separates transactional history from queryable content.

**How It Works:**

```python
# Separate SQLite database for history
class SQLiteManager:
    def __init__(self, db_path: str):
        self.connection = sqlite3.connect(db_path)
        self._create_history_table()

    def add_history(
        self,
        memory_id: str,
        old_memory: Optional[str],
        new_memory: Optional[str],
        event: str,  # ADD | UPDATE | DELETE
        created_at: str,
        actor_id: Optional[str],
        role: Optional[str]
    ):
        # Records event in separate table
        ...

# Memory class coordinates both
class Memory:
    def __init__(self, config: MemoryConfig):
        self.vector_store = VectorStoreFactory.create(...)  # Current state
        self.db = SQLiteManager(config.history_db_path)      # Event log

    def _update_memory(self, existing_id, new_content, metadata):
        # Get old content
        old_memory = self.vector_store.get(existing_id)

        # Update in vector store (current state)
        embeddings = self.embedding_model.embed(new_content)
        self.vector_store.update(existing_id, embeddings, {...})

        # Record event in history DB
        self.db.add_history(
            memory_id=existing_id,
            old_memory=old_memory.payload["data"],
            new_memory=new_content,
            event="UPDATE",
            created_at=datetime.now().isoformat(),
            actor_id=metadata.get("actor_id"),
            role=metadata.get("role")
        )
```

**Why It Matters:**

- **Audit Trail:** Complete event log of all memory changes
- **Storage Separation:** Vector store optimized for search, SQLite for transactions
- **History Queries:** Retrieve memory evolution without burdening vector store
- **Backend Independence:** History DB works regardless of vector store choice

**Application to IMEM:**

- **Where:** manage/Temporal validation layer
- **How:** Separate event log for chunk lifecycle (add/update/supersede/validate)
- **Example:**

```python
# manage/temporal.py
class TemporalValidator:
    def __init__(self, storage: ChunkRetriever, event_log: EventLog):
        self.storage = storage       # Current state (SQLite/Qdrant)
        self.event_log = event_log   # Separate event database

    def record_validation(self, chunk_id: str, git_diff: str, outcome: str):
        # Record validation event
        self.event_log.add_event(
            chunk_id=chunk_id,
            event="GIT_VALIDATION",
            metadata={"git_diff": git_diff, "outcome": outcome},
            timestamp=datetime.now()
        )

        # Update chunk authority in storage
        chunk = self.storage.get_by_id(chunk_id)
        chunk.metadata["authority"] = self._calculate_authority(outcome)
        self.storage.update(chunk)

# storage/event_log.py
class EventLog:
    """Separate SQLite database for lifecycle events"""
    def add_event(self, chunk_id: str, event: str, metadata: dict, timestamp: datetime):
        # Insert into events table
        ...

    def get_history(self, chunk_id: str) -> List[Event]:
        # Query event log for chunk
        ...
```

**Trade-offs:**

- **Pros:** Clean audit trail, optimized storage per use case, history independence
- **Cons:** Two databases to manage, potential sync issues, more complexity

**Adoption Recommendation:** **Adapt** - Use for manage/Temporal git validation events. Critical for tracking documented decisions vs actual commits.

---

## Principle 6: Pydantic-Driven Configuration Validation

**Observed in:** All `configs/` modules, factory pattern integration, field validators

**The Principle:**

All configuration objects are Pydantic models with validation logic. Provider-specific configs use `@field_validator` to enforce requirements (API keys, endpoints, valid enums). Invalid configs raise errors **at instantiation time**, not during runtime operations. Configuration is both data structure and validation logic.

**How It Works:**

```python
# Provider-specific config with validation
class GraphStoreConfig(BaseModel):
    provider: str = Field(default="neo4j")
    config: Union[Neo4jConfig, MemgraphConfig, NeptuneConfig] = Field(...)
    threshold: float = Field(default=0.7, ge=0.0, le=1.0)

    @field_validator("config")
    def validate_config(cls, v, values):
        provider = values.data.get("provider")
        if provider == "neo4j":
            return Neo4jConfig(**v.model_dump())
        elif provider == "memgraph":
            return MemgraphConfig(**v.model_dump())
        else:
            raise ValueError(f"Unsupported provider: {provider}")

class Neo4jConfig(BaseModel):
    url: Optional[str] = Field(None)
    username: Optional[str] = Field(None)
    password: Optional[str] = Field(None)

    @model_validator(mode="before")
    def check_required(cls, values):
        url, username, password = values.get("url"), values.get("username"), values.get("password")
        if not url or not username or not password:
            raise ValueError("Please provide 'url', 'username' and 'password'.")
        return values

# Usage - fails fast if invalid
config = GraphStoreConfig(
    provider="neo4j",
    config={"url": "bolt://localhost:7687"}  # Missing username/password
)  # Raises ValueError immediately
```

**Why It Matters:**

- **Fail Fast:** Invalid configs rejected before system initialization
- **Discoverability:** Config schema documents requirements (required fields, types, ranges)
- **Type Safety:** Pydantic enforces types, no runtime type errors
- **IDE Support:** Type hints enable autocomplete and static analysis

**Application to IMEM:**

- **Where:** All configuration modules (CompileConfig, StorageConfig, RetrieveConfig)
- **How:** Use Pydantic models with validators for phase enums, file paths, metadata schemas
- **Example:**

```python
# imem/config.py
class PhaseEnum(str, Enum):
    DESIGN = "design"
    DESIGNATE = "designate"
    DEVELOP = "develop"
    DOCUMENT = "document"

class CompileConfig(BaseModel):
    templates: List[str] = Field(...)
    default_phase: PhaseEnum = Field(default=PhaseEnum.DEVELOP)
    git_root: Path = Field(...)

    @field_validator("git_root")
    def validate_git_root(cls, v):
        if not v.exists() or not (v / ".git").exists():
            raise ValueError(f"git_root must be a valid git repository: {v}")
        return v

class SectionTypeEnum(str, Enum):
    DECISION = "Decision"
    PATTERN = "Pattern"
    IMPLEMENTATION = "Implementation"
    CONTEXT = "Context"

class ChunkMetadataSchema(BaseModel):
    file_path: Path
    phase: PhaseEnum
    section_type: SectionTypeEnum
    session_id: Optional[str]
    timestamp: datetime

    @field_validator("file_path")
    def validate_file_exists(cls, v):
        if not v.exists():
            raise ValueError(f"file_path does not exist: {v}")
        return v
```

**Trade-offs:**

- **Pros:** Type safety, fail-fast validation, self-documenting schemas
- **Cons:** Verbose model definitions, migration complexity when schemas evolve

**Adoption Recommendation:** **Adopt** - Essential for IMEM's complex metadata schemas and multi-backend configurations. Validation is insurance.

---

## Synthesis: Implications for IMEM

### Recommended Structural Changes

1. **Introduce Factory Pattern for All Backends**
   - `StorageBackendFactory` for SQLite/Qdrant
   - `ParserFactory` for template-based parsers (changelog/conversation/ADR)
   - `RendererFactory` for structure/Templates (Jinja2 templates)

2. **Config-Driven Initialization**
   - Root `IMEMConfig` object with nested layer configs
   - All factories consume validated Pydantic configs
   - Environment-specific configs (dev/prod) as separate instances

3. **Define Layer Interfaces**
   - `ChunkRetriever` interface for storage/ backends
   - `TemplateParser` interface for compile/Templates
   - `DiscoveryPrimitive` interface for retrieve/Primitives

4. **Separate Operational Event Log**
   - manage/Temporal uses separate SQLite event log
   - Records git validation events (chunk vs diff comparison)
   - Independent of main storage backend

5. **Metadata-Driven Query Architecture**
   - All queries carry `project_id`, `phase`, `section_type` filters
   - Storage backends adapt generic filters to their syntax
   - Chunks inherit document metadata (eliminate joins)

### Directory Structure Implications

```
imem/
├── config.py                           # Root IMEMConfig + Pydantic models
├── compile/
│   ├── factory.py                      # ParserFactory registry
│   ├── interface.py                    # TemplateParser ABC
│   ├── templates/
│   │   ├── changelog.py                # implements TemplateParser
│   │   ├── conversation.py             # implements TemplateParser
│   │   └── adr.py                      # implements TemplateParser
│   ├── resolver.py                     # Schema evolution (structure → types)
│   └── observer.py                     # Pattern discovery
├── manage/
│   ├── temporal/
│   │   ├── validator.py                # Git validation logic
│   │   └── event_log.py                # Separate SQLite for events
│   ├── resolver.py                     # Entity resolution
│   └── registry.py                     # Cross-project tier 1
├── storage/
│   ├── factory.py                      # StorageBackendFactory
│   ├── interface.py                    # ChunkRetriever ABC
│   ├── sqlite.py                       # implements ChunkRetriever
│   └── qdrant.py                       # implements ChunkRetriever
├── retrieve/
│   ├── orchestrator.py                 # Depends on ChunkRetriever interface
│   ├── primitives/
│   │   ├── interface.py                # DiscoveryPrimitive ABC
│   │   ├── siblings.py                 # implements DiscoveryPrimitive
│   │   ├── genealogy.py                # implements DiscoveryPrimitive
│   │   └── temporal.py                 # implements DiscoveryPrimitive
│   └── graph.py                        # Runtime graph composition
└── structure/
    ├── factory.py                      # RendererFactory
    ├── templates/                      # Jinja2 presentation templates
    └── contextualize.py                # Add graph metadata to chunks
```

### Key Interfaces to Define

**Interface 1: ChunkRetriever (storage abstraction)**

```python
class ChunkRetriever(ABC):
    @abstractmethod
    def search(self, text: str, filters: dict, limit: int) -> List[Chunk]:
        """Metadata-filtered search (text or semantic)"""
        pass

    @abstractmethod
    def filter(self, filters: dict) -> List[Chunk]:
        """Metadata-only filtering (no text search)"""
        pass

    @abstractmethod
    def get_by_id(self, chunk_id: str) -> Optional[Chunk]:
        """Direct ID lookup"""
        pass

    @abstractmethod
    def insert(self, chunks: List[Chunk]) -> None:
        """Bulk insert with metadata"""
        pass
```

**Interface 2: TemplateParser (compilation abstraction)**

```python
class TemplateParser(ABC):
    @abstractmethod
    def can_parse(self, file_path: Path) -> bool:
        """Detect if this parser handles the file"""
        pass

    @abstractmethod
    def parse(self, file_path: Path, metadata: dict) -> List[Chunk]:
        """Extract chunks with section-level metadata"""
        pass

    @abstractmethod
    def get_schema(self) -> dict:
        """Return expected section types for this template"""
        pass
```

**Interface 3: DiscoveryPrimitive (retrieval abstraction)**

```python
class DiscoveryPrimitive(ABC):
    @abstractmethod
    def discover(self, seed_chunks: List[Chunk], config: dict) -> List[Chunk]:
        """Execute discovery operation (siblings/genealogy/temporal)"""
        pass

    @abstractmethod
    def get_metadata_requirements(self) -> List[str]:
        """Return required metadata fields for this primitive"""
        pass
```

### Extension Points to Establish

**Extension 1: Storage Backend Registration**

```python
# User adds new storage backend
class PostgresRetriever(ChunkRetriever):
    def search(self, text, filters, limit):
        # Postgres full-text search implementation
        ...

# Register in factory
StorageBackendFactory.register("postgres", PostgresRetriever)

# Use via config
config = IMEMConfig(
    storage=StorageConfig(backend="postgres", config={"connection_string": "..."})
)
```

**Extension 2: Template Parser Registration**

```python
# User adds RFC parser
class RFCParser(TemplateParser):
    def can_parse(self, file_path):
        return "rfc" in file_path.name.lower()

    def parse(self, file_path, metadata):
        # RFC-specific parsing logic
        ...

# Register in factory
ParserFactory.register("rfc", RFCParser)

# Auto-detected during compilation
imem compile --templates changelog,conversation,rfc
```

**Extension 3: Discovery Primitive Registration**

```python
# User adds custom discovery primitive
class CrossProjectPrimitive(DiscoveryPrimitive):
    def discover(self, seed_chunks, config):
        # Find similar chunks across projects
        ...

# Register in orchestrator
Orchestrator.register_primitive("cross_project", CrossProjectPrimitive)

# Use in query config
imem compose '{
  "discovery": {
    "cross_project": {"similarity_threshold": 0.8}
  }
}'
```

---

## Summary Table

| Principle | Impact on IMEM | Adoption | Priority |
|-----------|----------------|----------|----------|
| Factory-Based Provider Abstraction | Define factories for storage/parsers/renderers. Zero coupling between layers and implementations. | Adopt | High |
| Config-Driven System Assembly | Root IMEMConfig with Pydantic validation. Dev/prod configs as separate instances. | Adopt | High |
| Storage-Agnostic Memory Interface | ChunkRetriever interface. retrieve/ never imports storage backends. | Adopt | Critical |
| Metadata-First Filtering Architecture | All queries scoped by project/phase/type. Storage backends adapt filters to syntax. | Adopt | High |
| Dual Storage for Operational History | Separate event log for manage/Temporal git validations. | Adapt | Medium |
| Pydantic-Driven Configuration Validation | All configs are validated Pydantic models. Phase/type enums enforced. | Adopt | High |

---

## References

**Key Architectural Documents Consulted:**
- `/home/axp/projects/fleet/hangar/code/aura/main/.context/designate/overview.md` - IMEM canonical architecture

**Critical Modules Examined:**
- `mem0/utils/factory.py` - Factory pattern implementation
- `mem0/configs/base.py` - Config-driven assembly
- `mem0/vector_stores/base.py` - Storage abstraction
- `mem0/memory/main.py` - Memory coordination logic
- `mem0/memory/storage.py` - Dual storage (event log)
- `mem0/vector_stores/qdrant.py` - Concrete backend implementation

**Design Decisions Observed:**
- Factory pattern for all external integrations (25+ vector stores, 15+ LLM providers)
- Pydantic configs as dependency injection mechanism
- Metadata-driven filtering across all storage backends
- Separate operational history database (SQLiteManager)
- Abstract interfaces for complete backend decoupling
