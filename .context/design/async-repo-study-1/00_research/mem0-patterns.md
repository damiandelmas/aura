# Pattern Extraction: mem0

## Executive Summary

mem0 is a multi-modal memory infrastructure for AI systems that demonstrates exceptional architectural patterns in plugin extensibility, metadata-driven filtering, and dual-store coordination (vector + graph). Most relevant to IMEM is its **factory-based adapter pattern** for backend-agnostic storage, **hierarchical metadata filtering** with session scoping, **structured extraction via LLM tool calling**, and **thread-safe SQLite for operation history**. These patterns directly apply to IMEM's storage/, manage/, and compile/ modules for achieving storage flexibility, metadata-rich queries, and entity extraction without vendor lock-in.

---

## Pattern 1: Factory-Based Backend Adapter Registry

**Location:** `mem0/utils/factory.py:1-284`

**Description:**
mem0 uses a centralized factory pattern to decouple core logic from backend implementations. Four separate factories (LlmFactory, EmbedderFactory, VectorStoreFactory, GraphStoreFactory) map provider names to class paths and configuration schemas. The `load_class()` helper uses importlib to dynamically load implementations at runtime, enabling lazy loading and zero hardcoded dependencies.

**Code Example:**
```python
def load_class(class_type):
    module_path, class_name = class_type.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)

class VectorStoreFactory:
    provider_to_class = {
        "qdrant": "mem0.vector_stores.qdrant.Qdrant",
        "chroma": "mem0.vector_stores.chroma.ChromaDB",
        "pgvector": "mem0.vector_stores.pgvector.PGVector",
        # ... 19 total providers
    }

    @classmethod
    def create(cls, provider_name, config):
        class_type = cls.provider_to_class.get(provider_name)
        if class_type:
            if not isinstance(config, dict):
                config = config.model_dump()
            vector_store_instance = load_class(class_type)
            return vector_store_instance(**config)
        else:
            raise ValueError(f"Unsupported VectorStore provider: {provider_name}")
```

**Key architectural properties:**
- **String-based class registry**: `provider_to_class` dict maps names → class paths
- **Dynamic import**: `importlib.import_module()` delays loading until runtime
- **Uniform interface**: All backends implement `VectorStoreBase` abstract methods
- **Extensible registration**: `register_provider()` allows runtime plugin addition

**Relevance to IMEM:**
- **Module:** storage/
- **Use case:** Backend adapters for SQLite, Qdrant, future stores (Postgres, Chroma)
- **Why useful:** Storage topology reflects query topology (metadata-only → SQLite, semantic → Qdrant). Factory pattern prevents hardcoded backend coupling, enabling users to swap storage without core code changes.

**Adoption Strategy:**
- [x] Adapt — Create `storage/factory.py` with similar pattern:
  ```python
  class StorageFactory:
      backends = {
          "sqlite": "imem.storage.sqlite.SQLiteBackend",
          "qdrant": "imem.storage.qdrant.QdrantBackend",
          # Future: postgres, chroma, typesense
      }

      @classmethod
      def create(cls, backend_name, config):
          backend_class = load_class(cls.backends[backend_name])
          return backend_class(**config)
  ```
- All backends implement `StorageBase` with methods: `insert_chunks()`, `query()`, `get_metadata()`, `index_fields()`
- Config passed via Pydantic models (e.g., `SQLiteConfig`, `QdrantConfig`)
- **Benefit:** Compile once → query via any backend. Users choose storage based on query needs (metadata-only vs semantic).

**Implementation Priority:** High

---

## Pattern 2: Hierarchical Metadata Filter Builder

**Location:** `mem0/memory/main.py:87-165` (helper function)
**Location:** `mem0/vector_stores/qdrant.py:141-160` (filter translation)

**Description:**
mem0 separates **session scoping** (user_id, agent_id, run_id) from **query filtering** (metadata constraints) and constructs two distinct metadata dictionaries: (1) `base_metadata_template` for storage, (2) `effective_query_filters` for retrieval. A dedicated `_build_filters_and_metadata()` helper enforces that at least one session ID must be provided, preventing unbounded queries. The Qdrant adapter then translates generic filter dicts into vendor-specific filter objects (Qdrant's `FieldCondition` with `MatchValue` or `Range`).

**Code Example:**
```python
# Generic filter builder (storage-agnostic)
def _build_filters_and_metadata(
    *,
    user_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    run_id: Optional[str] = None,
    actor_id: Optional[str] = None,
    input_metadata: Optional[Dict[str, Any]] = None,
    input_filters: Optional[Dict[str, Any]] = None,
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    base_metadata_template = deepcopy(input_metadata) if input_metadata else {}
    effective_query_filters = deepcopy(input_filters) if input_filters else {}

    # Add session IDs to both
    if user_id:
        base_metadata_template["user_id"] = user_id
        effective_query_filters["user_id"] = user_id
    # ... agent_id, run_id similarly

    if not any([user_id, agent_id, run_id]):
        raise ValidationError("At least one session ID required")

    # Actor filtering only affects queries, not storage
    if actor_id:
        effective_query_filters["actor_id"] = actor_id

    return base_metadata_template, effective_query_filters

# Backend-specific filter translation (Qdrant)
def _create_filter(self, filters: dict) -> Filter:
    if not filters:
        return None
    conditions = []
    for key, value in filters.items():
        if isinstance(value, dict) and "gte" in value and "lte" in value:
            conditions.append(FieldCondition(key=key, range=Range(gte=value["gte"], lte=value["lte"])))
        else:
            conditions.append(FieldCondition(key=key, match=MatchValue(value=value)))
    return Filter(must=conditions) if conditions else None
```

**Relevance to IMEM:**
- **Module:** manage/Resolver (entity resolution), retrieve/Primitives (query filtering)
- **Use case:**
  - Session scoping: `session_id` in IMEM analogous to `user_id|agent_id|run_id` in mem0
  - Metadata filtering: `phase`, `section_type`, `file_path` predicates for discovery primitives
  - Backend translation layer: Generic filters → SQLite WHERE clauses / Qdrant FieldConditions
- **Why useful:**
  - **Prevents unbounded queries**: Session ID requirement ensures queries are scoped to project/conversation
  - **Separation of storage vs query metadata**: Storage metadata persists full context; query filters narrow retrieval
  - **Backend abstraction**: Core logic uses generic filter dicts; adapters translate to vendor-specific syntax

**Adoption Strategy:**
- [x] Adapt — Implement similar pattern in IMEM:
  ```python
  # imem/retrieve/filters.py
  def build_query_filters(
      session_id: Optional[str] = None,
      phase: Optional[str] = None,
      section_type: Optional[str] = None,
      file_path: Optional[str] = None,
      metadata: Optional[Dict] = None,
  ) -> Dict[str, Any]:
      filters = metadata.copy() if metadata else {}

      if session_id:
          filters["session_id"] = session_id
      if phase:
          filters["phase"] = phase
      if section_type:
          filters["section_type"] = section_type
      if file_path:
          filters["file_path"] = file_path

      # Require at least one scoping predicate
      if not any([session_id, file_path]):
          raise ValueError("Must specify session_id or file_path")

      return filters

  # Backend adapters translate to vendor syntax
  # imem/storage/sqlite.py
  def translate_filters(self, filters: Dict) -> str:
      conditions = []
      for key, value in filters.items():
          if isinstance(value, dict):
              # Handle range operators
              if "gte" in value and "lte" in value:
                  conditions.append(f"{key} BETWEEN ? AND ?")
          else:
              conditions.append(f"{key} = ?")
      return " AND ".join(conditions)
  ```
- **Implementation Priority:** High
- **Key insight:** Generic filter dicts in core → backend-specific translation at storage boundary

---

## Pattern 3: LLM-Driven Structured Extraction via Tool Calling

**Location:** `mem0/graphs/tools.py:124-150` (entity extraction tool schema)
**Location:** `mem0/memory/graph_memory.py:76-94` (extraction orchestration)

**Description:**
mem0 uses LLM function calling (tool schemas) to extract structured entities and relationships from unstructured text. The `EXTRACT_ENTITIES_TOOL` defines a strict JSON schema with nested arrays and required fields. The LLM's structured output is directly usable without regex parsing or brittle heuristics. This pattern separates **what to extract** (schema definition) from **how to extract** (LLM invocation), enabling domain-specific extractors via schema swapping.

**Code Example:**
```python
# Schema definition (declarative)
EXTRACT_ENTITIES_TOOL = {
    "type": "function",
    "function": {
        "name": "extract_entities",
        "description": "Extract entities and their types from the text.",
        "parameters": {
            "type": "object",
            "properties": {
                "entities": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "entity": {"type": "string", "description": "The name or identifier of the entity."},
                            "entity_type": {"type": "string", "description": "The type or category of the entity."},
                        },
                        "required": ["entity", "entity_type"],
                        "additionalProperties": False,
                    },
                    "description": "An array of entities with their types.",
                }
            },
            "required": ["entities"],
            "additionalProperties": False,
        },
    },
}

# Usage (LLM invocation with schema)
def _retrieve_nodes_from_data(self, data, filters):
    """Extract entities from text using LLM tool calling."""
    messages = [
        {"role": "system", "content": "Extract entities from the provided text."},
        {"role": "user", "content": data}
    ]

    # LLM returns structured JSON matching schema
    response = self.llm.generate_response(
        messages=messages,
        tools=[EXTRACT_ENTITIES_TOOL],
        tool_choice="required"
    )

    # Direct usage of structured output (no parsing needed)
    entities = response["entities"]
    entity_type_map = {e["entity"]: e["entity_type"] for e in entities}
    return entity_type_map
```

**Relevance to IMEM:**
- **Module:** compile/Parser, compile/Templates
- **Use case:**
  - Extract structured metadata from markdown sections (decisions, patterns, context)
  - Resolve section types from heterogeneous headers ("Decision:", "We Decided:", "Choice:") → canonical `decision`
  - Entity extraction for manage/Resolver (normalize "jwt", "JWT", "jwt-tokens" → canonical `jwt`)
- **Why useful:**
  - **No brittle regex**: LLM-based extraction adapts to variations in formatting
  - **Schema-driven**: Define extraction requirements declaratively, not procedurally
  - **Domain-agnostic**: Swap schemas for different document types (changelog vs conversation vs ADR)

**Adoption Strategy:**
- [x] Adapt — Use for compile/Resolver (schema evolution):
  ```python
  # Define schema for section type resolution
  RESOLVE_SECTION_TYPE_TOOL = {
      "type": "function",
      "function": {
          "name": "classify_section",
          "description": "Classify markdown section header into canonical lifecycle type.",
          "parameters": {
              "type": "object",
              "properties": {
                  "section_type": {
                      "type": "string",
                      "enum": ["decision", "pattern", "implementation", "context", "failure"],
                      "description": "Canonical section type"
                  },
                  "confidence": {"type": "number", "description": "Confidence score 0-1"},
              },
              "required": ["section_type", "confidence"],
          },
      },
  }

  # Invoke during parsing
  def resolve_section_type(self, header: str) -> str:
      response = self.llm.generate_response(
          messages=[{"role": "user", "content": f"Classify: {header}"}],
          tools=[RESOLVE_SECTION_TYPE_TOOL],
          tool_choice="required"
      )
      return response["section_type"]
  ```
- Also useful for entity extraction in manage/Resolver to normalize terminology variations
- **Implementation Priority:** Medium (after baseline regex-based parsing works)

---

## Pattern 4: Thread-Safe Operation History with SQLite

**Location:** `mem0/memory/storage.py:10-219`

**Description:**
mem0 maintains a complete audit trail of memory operations (add, update, delete) in a dedicated SQLite table. The `SQLiteManager` class uses thread locks (`threading.Lock()`) to serialize concurrent writes, preventing database corruption. Each operation is recorded with metadata (memory_id, event type, actor_id, timestamps), enabling versioning, rollback, and provenance tracking. The design includes schema migration logic that safely handles breaking changes without data loss.

**Code Example:**
```python
class SQLiteManager:
    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
        self._lock = threading.Lock()
        self._migrate_history_table()  # Handle schema evolution
        self._create_history_table()

    def add_history(
        self,
        memory_id: str,
        old_memory: Optional[str],
        new_memory: Optional[str],
        event: str,
        *,
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
        is_deleted: int = 0,
        actor_id: Optional[str] = None,
        role: Optional[str] = None,
    ) -> None:
        with self._lock:  # Serialize concurrent writes
            try:
                self.connection.execute("BEGIN")
                self.connection.execute(
                    """
                    INSERT INTO history (
                        id, memory_id, old_memory, new_memory, event,
                        created_at, updated_at, is_deleted, actor_id, role
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (str(uuid.uuid4()), memory_id, old_memory, new_memory,
                     event, created_at, updated_at, is_deleted, actor_id, role),
                )
                self.connection.execute("COMMIT")
            except Exception as e:
                self.connection.execute("ROLLBACK")
                logger.error(f"Failed to add history record: {e}")
                raise

    def _migrate_history_table(self) -> None:
        """Safe schema migration without data loss."""
        with self._lock:
            try:
                self.connection.execute("BEGIN")
                cur = self.connection.cursor()

                # Check if migration needed
                cur.execute("PRAGMA table_info(history)")
                old_cols = {row[1] for row in cur.fetchall()}
                expected_cols = {"id", "memory_id", "old_memory", ...}

                if old_cols == expected_cols:
                    self.connection.execute("COMMIT")
                    return  # Already migrated

                # Rename old table, create new schema, copy data
                cur.execute("ALTER TABLE history RENAME TO history_old")
                cur.execute("""CREATE TABLE history (...)""")

                intersecting = list(expected_cols & old_cols)
                if intersecting:
                    cols_csv = ", ".join(intersecting)
                    cur.execute(f"INSERT INTO history ({cols_csv}) SELECT {cols_csv} FROM history_old")

                cur.execute("DROP TABLE history_old")
                self.connection.execute("COMMIT")
            except Exception as e:
                self.connection.execute("ROLLBACK")
                raise
```

**Key architectural properties:**
- **Thread-safe writes**: `threading.Lock()` prevents race conditions
- **Transaction safety**: `BEGIN`/`COMMIT`/`ROLLBACK` ensures atomic operations
- **Schema migration**: Handles breaking changes by renaming old table, copying intersecting columns
- **Lightweight audit trail**: SQLite file-based storage, no external dependencies
- **Versioning support**: Stores old/new values, enabling diff reconstruction

**Relevance to IMEM:**
- **Module:** storage/SQLite, manage/Temporal
- **Use case:**
  - **Operation history**: Track chunk insertions, updates, metadata changes
  - **Git validation**: Compare documented decisions vs actual commits (manage/Temporal needs historical states)
  - **Schema evolution**: Safely migrate chunk metadata as canonical schema evolves
  - **Audit trail**: Provenance tracking for debugging and quality validation
- **Why useful:**
  - Enables temporal queries (what was documented at commit X?)
  - Supports schema evolution without breaking existing databases
  - Lightweight (single SQLite file), no external dependencies

**Adoption Strategy:**
- [x] Adopt directly — Create `storage/history.py`:
  ```python
  class HistoryManager:
      def __init__(self, db_path: str):
          self.db_path = db_path
          self.connection = sqlite3.connect(db_path, check_same_thread=False)
          self._lock = threading.Lock()
          self._create_tables()

      def record_operation(
          self,
          chunk_id: str,
          operation: str,  # INSERT, UPDATE, DELETE
          old_metadata: Optional[Dict] = None,
          new_metadata: Optional[Dict] = None,
          timestamp: Optional[str] = None,
      ):
          with self._lock:
              self.connection.execute("BEGIN")
              try:
                  self.connection.execute(
                      """INSERT INTO operation_history
                         (chunk_id, operation, old_metadata, new_metadata, timestamp)
                         VALUES (?, ?, ?, ?, ?)""",
                      (chunk_id, operation, json.dumps(old_metadata),
                       json.dumps(new_metadata), timestamp)
                  )
                  self.connection.execute("COMMIT")
              except:
                  self.connection.execute("ROLLBACK")
                  raise
  ```
- Use for manage/Temporal validation (compare current vs historical states)
- **Implementation Priority:** Medium (critical for temporal validation, but baseline system works without it)

---

## Pattern 5: Concurrent Dual-Store Orchestration

**Location:** `mem0/memory/main.py:832-856` (search method)

**Description:**
mem0 coordinates queries across two heterogeneous backends (vector store + graph store) concurrently using `concurrent.futures.ThreadPoolExecutor`. Both queries execute in parallel, then results are merged into a unified response. This pattern demonstrates **storage topology composition** — vector store for semantic search, graph store for entity relationships, both queried simultaneously to enrich results.

**Code Example:**
```python
def search(self, query: str, *, filters: dict, limit: int = 100):
    # Build filters once, use for both stores
    effective_filters = self._process_filters(filters)

    with concurrent.futures.ThreadPoolExecutor() as executor:
        # Launch concurrent queries to different backends
        future_memories = executor.submit(
            self._search_vector_store, query, effective_filters, limit
        )
        future_graph_entities = (
            executor.submit(self.graph.search, query, effective_filters, limit)
            if self.enable_graph else None
        )

        # Wait for both to complete
        concurrent.futures.wait(
            [future_memories, future_graph_entities]
            if future_graph_entities else [future_memories]
        )

        # Collect results
        memories = future_memories.result()
        graph_entities = future_graph_entities.result() if future_graph_entities else None

    # Unified response merging both stores
    if self.enable_graph:
        return {"results": memories, "relations": graph_entities}
    return {"results": memories}
```

**Key architectural properties:**
- **Concurrent execution**: ThreadPoolExecutor parallelizes I/O-bound operations
- **Conditional backend use**: Graph store only queried if enabled
- **Unified response format**: Merges heterogeneous results into single structure
- **Shared filter semantics**: Same filter dict works across both stores (abstraction)

**Relevance to IMEM:**
- **Module:** retrieve/Orchestrator, storage/
- **Use case:**
  - Hybrid queries: Metadata filtering (SQLite) + semantic search (Qdrant)
  - Multi-stage composition: Initial search → sibling discovery → temporal filtering
  - Storage topology: Query multiple backends based on query type
- **Why useful:**
  - **Performance**: I/O operations run in parallel (50%+ latency reduction for dual-store queries)
  - **Composability**: Different backends provide different query capabilities
  - **Flexibility**: Enable/disable backends at runtime without code changes

**Adoption Strategy:**
- [x] Adapt — Use for retrieve/Orchestrator multi-stage pipeline:
  ```python
  # imem/retrieve/orchestrator.py
  async def compose(self, query_spec: Dict):
      with ThreadPoolExecutor() as executor:
          # Stage 1: Initial search (vector + metadata)
          future_semantic = executor.submit(
              self.qdrant.search, query_spec["text"], query_spec["filters"]
          )
          future_metadata = executor.submit(
              self.sqlite.query, query_spec["filters"]
          )

          # Stage 2: Discovery primitives (concurrent)
          futures = [future_semantic, future_metadata]
          if query_spec.get("discovery"):
              futures.append(executor.submit(
                  self.discovery.siblings, initial_results, query_spec["discovery"]
              ))

          concurrent.futures.wait(futures)

          # Merge and enrich results
          results = self._merge_results([f.result() for f in futures])
          return results
  ```
- **Implementation Priority:** High (core to multi-stage retrieval architecture)

---

## Summary Table

| Pattern | IMEM Module | Priority | Strategy |
|---------|-------------|----------|----------|
| Factory-Based Backend Adapter Registry | storage/ | High | Adapt — Create `storage/factory.py` for backend abstraction (SQLite, Qdrant, future stores) |
| Hierarchical Metadata Filter Builder | manage/Resolver, retrieve/Primitives | High | Adapt — Generic filter dicts + backend-specific translation layer |
| LLM-Driven Structured Extraction | compile/Parser, compile/Resolver | Medium | Adapt — Use for schema evolution and entity resolution |
| Thread-Safe Operation History | storage/SQLite, manage/Temporal | Medium | Adopt directly — Essential for temporal validation and audit trail |
| Concurrent Dual-Store Orchestration | retrieve/Orchestrator | High | Adapt — Core to multi-stage composition pipeline |

---

## Key Files Examined

- `mem0/utils/factory.py` — Factory pattern for all backend types
- `mem0/memory/main.py` — Core Memory class with filter building and search orchestration
- `mem0/memory/storage.py` — Thread-safe SQLite operation history
- `mem0/vector_stores/base.py` — Abstract interface for vector stores
- `mem0/vector_stores/qdrant.py` — Qdrant implementation with filter translation
- `mem0/embeddings/base.py` — Abstract embedding interface
- `mem0/graphs/tools.py` — LLM tool schemas for structured extraction
- `mem0/memory/graph_memory.py` — Graph store implementation with entity extraction
- `mem0/configs/base.py` — Pydantic configuration models

---

## References

### Documentation Consulted
- mem0 codebase structure analysis (factory patterns, storage adapters, metadata filtering)
- IMEM architecture overview (`/home/axp/projects/fleet/hangar/code/aura/main/.context/designate/overview.md`)

### Key Architectural Decisions Observed

**1. Backend Abstraction via Factory Pattern**
- mem0 supports 19+ vector stores, 13+ LLM providers, 5+ rerankers via factory registration
- All backends share common interface (`VectorStoreBase`, `EmbeddingBase`, etc.)
- Dynamic loading enables zero hardcoded dependencies
- **IMEM application**: Storage topology flexibility (metadata-only → SQLite, semantic → Qdrant)

**2. Metadata-First Query Design**
- Session scoping (user_id/agent_id/run_id) required for all operations
- Metadata filters are storage-agnostic (generic dicts)
- Backend adapters translate to vendor-specific syntax
- **IMEM application**: Chunks carry full metadata; single-level queries without joins

**3. LLM as Structured Extractor**
- Tool calling schemas define extraction contracts
- No regex or heuristic parsing for entity/relationship extraction
- Domain-specific schemas enable template-based parsing
- **IMEM application**: Schema evolution (heterogeneous headers → canonical types), entity resolution

**4. Operation History as First-Class Concern**
- All memory operations recorded in SQLite audit table
- Thread-safe writes with transaction guarantees
- Schema migration logic handles breaking changes
- **IMEM application**: Temporal validation (git diffs vs documented decisions), provenance tracking

**5. Concurrent Multi-Backend Composition**
- Vector store + graph store queried in parallel
- Unified response format merges heterogeneous results
- Conditional backend use (graph optional)
- **IMEM application**: Multi-stage retrieval (search → discovery → graph → ranking)

---

## Implementation Recommendations

**Immediate Priorities (High):**
1. **Factory pattern** for storage backends — Enables SQLite + Qdrant flexibility without hardcoding
2. **Metadata filter builder** — Generic filter dicts + backend translation layer
3. **Concurrent orchestration** — Multi-stage retrieval pipeline with parallel execution

**Medium-Term (Medium):**
1. **LLM-based extraction** — Schema evolution and entity resolution via tool calling
2. **Operation history** — Thread-safe SQLite audit trail for temporal validation

**Architectural Alignment:**
- mem0's dual-store pattern (vector + graph) aligns with IMEM's storage topology (SQLite + Qdrant)
- Session scoping (user_id/agent_id/run_id) parallels IMEM's session_id + file_path scoping
- Metadata-first query design matches IMEM's "chunks carry full lineage" principle
- Factory pattern supports "parse once, storage choice = which queries you need"

**Key Insight:**
mem0 demonstrates that **storage backends can be fully abstracted** via factory pattern + common interface, enabling users to choose backends based on query topology (metadata-only vs semantic vs graph) without core code changes. This directly validates IMEM's "storage agnostic" design principle and provides proven implementation patterns.
