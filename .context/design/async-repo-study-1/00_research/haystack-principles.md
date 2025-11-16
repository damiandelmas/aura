# Architectural Principles: haystack

## Executive Summary

Haystack implements a **declarative, protocol-based component architecture** for AI pipelines. Its core philosophy: business logic lives in lightweight, serializable components while a graph-based orchestrator handles execution. Protocol-first design enables storage-agnostic retrieval, decorator-driven component registration, and pipeline-as-data patterns. Key lesson for IMEM: **separate orchestration from execution**, use **protocols over inheritance**, and make **pipelines themselves components** for fractal composition.

---

## System Overview

**Haystack** is a framework for building production-ready LLM applications. It provides:
- Component-based pipeline architecture for RAG, search, and agent workflows
- Storage-agnostic document stores (in-memory, Elasticsearch, Qdrant, etc.)
- Graph-based orchestration engine (NetworkX MultiDiGraph)
- Type-safe socket system for component I/O
- Full serialization/deserialization (pipelines as YAML/JSON)

**Architectural approach:** Declarative composition with runtime graph execution, protocol-first extensibility, and zero-inheritance component model.

---

## Principle 1: Protocol-First Storage Abstraction

**Observed in:**
- `haystack/document_stores/types/protocol.py`
- `haystack/components/retrievers/*`
- `haystack/components/writers/document_writer.py`

**The Principle:**

Storage backends are defined as **runtime-checkable Protocols** (structural typing), not base classes. Any object implementing `DocumentStore` methods can be used interchangeably. Retrieval components accept protocol types, never concrete implementations. This achieves **true storage agnosticism** without inheritance hierarchies.

**How It Works:**

```python
# haystack/document_stores/types/protocol.py:14-139
class DocumentStore(Protocol):
    def to_dict(self) -> dict[str, Any]: ...
    def count_documents(self) -> int: ...
    def filter_documents(filters: Optional[dict]) -> list[Document]: ...
    def write_documents(docs: list[Document], policy: DuplicatePolicy) -> int: ...
    def delete_documents(ids: list[str]) -> None: ...
```

Components declare dependency on the protocol:

```python
# haystack/components/retrievers/in_memory/bm25_retriever.py:40-79
@component
class InMemoryBM25Retriever:
    def __init__(self, document_store: InMemoryDocumentStore, ...):
        if not isinstance(document_store, InMemoryDocumentStore):
            raise ValueError("...")
        self.document_store = document_store
```

Filter syntax is **standardized across all backends**:

```python
# Nested filter DSL (haystack/document_stores/types/protocol.py:83-105)
filters = {
    "operator": "AND",
    "conditions": [
        {"field": "meta.type", "operator": "==", "value": "article"},
        {"field": "meta.date", "operator": ">=", "value": 1420066800},
        {
            "operator": "OR",
            "conditions": [
                {"field": "meta.genre", "operator": "in", "value": ["economy"]},
                {"field": "meta.publisher", "operator": "==", "value": "nytimes"}
            ]
        }
    ]
}
```

**Why It Matters:**

- **Zero coupling**: Retrieval logic never imports specific backends
- **Runtime flexibility**: Swap storage without code changes
- **Testability**: Mock stores trivially with protocol compliance
- **Extensibility**: New backends require zero framework changes
- **Standardization**: Filter DSL enforced by protocol contract

**Application to IMEM:**

- **Where:** `storage/` boundary with `retrieve/Orchestrator` and `manage/` intelligence layers
- **How:** Define `ChunkStore` protocol with methods: `query_metadata()`, `query_semantic()`, `write_chunks()`, `count_chunks()`
- **Example:**
  ```python
  # storage/protocol.py
  class ChunkStore(Protocol):
      def query_metadata(self, filters: dict) -> list[Chunk]: ...
      def query_semantic(self, embedding: list[float], top_k: int) -> list[Chunk]: ...
      def write_chunks(self, chunks: list[Chunk]) -> int: ...
      def count_chunks(self, filters: Optional[dict] = None) -> int: ...

  # storage/sqlite.py
  class SQLiteChunkStore:  # No inheritance
      def query_metadata(self, filters):
          # SQL implementation

  # storage/qdrant.py
  class QdrantChunkStore:  # No inheritance
      def query_metadata(self, filters):
          # Qdrant implementation

  # retrieve/orchestrator.py
  def compose(store: ChunkStore, config: dict):
      results = store.query_metadata(config['search'])
      # Orchestration logic never knows backend
  ```

**Trade-offs:**

- **Pros:** Perfect storage abstraction, trivial backend swapping, zero inheritance complexity, enforces interface consistency
- **Cons:** Protocol must be expressive enough for all backends, can't enforce compile-time checks without type checkers, backend-specific optimizations require careful API design

**Adoption Recommendation:** **Adopt** — Critical for IMEM's "storage agnostic" principle. Directly enables SQLite/Qdrant interchangeability.

---

## Principle 2: Decorator-Driven Component Registration

**Observed in:**
- `haystack/core/component/component.py:392-631` (`@component` decorator)
- `haystack/core/component/component.py:133-182` (Component Protocol)
- `haystack/core/serialization.py:37-79` (automatic serialization)

**The Principle:**

Components are **decorated classes**, not subclasses. The `@component` decorator introspects the class, validates its contract, and registers it in a global registry. No inheritance required. Serialization parameters are automatically extracted from `__init__` signatures. This achieves **zero-boilerplate component creation** with full framework integration.

**How It Works:**

**Component contract** (haystack/core/component/component.py:4-69):
```python
@component
class MyComponent:
    def __init__(self, param: str):
        # Lightweight config only, stored automatically for serialization
        self.param = param

    def warm_up(self):
        # Optional: Heavy initialization (models, backends)
        pass

    @component.output_types(result=str)
    def run(self, input: str):
        # Mandatory: Execution logic
        return {"result": input + self.param}
```

**Decorator mechanics** (haystack/core/component/component.py:392-475):
```python
def component(_cls=None, *, serialization_class=None):
    """
    Marks a class as a component.
    - Validates presence of run() method
    - Introspects input/output sockets from type hints
    - Registers in global component.registry
    - Enables automatic serialization
    """
    def decorator(cls):
        # Validate contract
        if not hasattr(cls, "run"):
            raise ComponentError(f"{cls.__name__} must have a run() method")

        # Register for discovery
        qualified_name = generate_qualified_class_name(cls)
        component.registry[qualified_name] = cls

        # Set socket metadata
        cls.__haystack_input__ = _extract_input_sockets(cls.run)
        cls.__haystack_output__ = _extract_output_sockets(cls.run)

        return cls

    # Support both @component and @component()
    return decorator if _cls is None else decorator(_cls)
```

**Automatic serialization** (haystack/core/serialization.py:37-79):
```python
def component_to_dict(obj: Any, name: str) -> dict[str, Any]:
    if hasattr(obj, "to_dict"):
        return obj.to_dict()

    # Auto-extract init parameters from instance attributes
    init_parameters = {}
    for param_name, param in inspect.signature(obj.__init__).parameters.items():
        try:
            param_value = getattr(obj, param_name)  # Convention: self.param = param
        except AttributeError:
            param_value = param.default  # Use default if not assigned
        init_parameters[param_name] = param_value

    return {
        "type": generate_qualified_class_name(obj.__class__),
        "init_parameters": init_parameters
    }
```

**Why It Matters:**

- **Zero boilerplate**: No base class imports, no super() calls, no manual registry management
- **Introspection-driven**: Framework learns component structure from code, not declarations
- **Convention over configuration**: `self.param = param` enables auto-serialization
- **Dynamic discovery**: Global registry enables `Pipeline.from_dict()` to resolve component types
- **Separation of concerns**: Component code focuses on domain logic, decorator handles framework integration

**Application to IMEM:**

- **Where:** `compile/Templates`, `retrieve/Primitives`, `manage/` intelligence components
- **How:** Define `@template`, `@primitive`, `@validator` decorators for plugin registration
- **Example:**
  ```python
  # compile/template.py
  template_registry = {}

  def template(doc_type: str):
      def decorator(cls):
          template_registry[doc_type] = cls
          # Auto-extract section_patterns from class
          cls.__section_patterns__ = _introspect_patterns(cls)
          return cls
      return decorator

  # compile/templates/changelog.py
  @template(doc_type="changelog")
  class ChangelogTemplate:
      def __init__(self, phase_mapping: dict):
          self.phase_mapping = phase_mapping

      def parse(self, content: str) -> list[Chunk]:
          # Domain-specific parsing logic
          pass

  # Usage
  parser = template_registry["changelog"](phase_mapping={...})
  chunks = parser.parse(markdown_content)
  ```

**Trade-offs:**

- **Pros:** Minimal component code, automatic serialization, dynamic extensibility, no inheritance coupling
- **Cons:** Convention reliance (`self.param = param`), decorator magic can obscure flow, global registry requires careful namespace management

**Adoption Recommendation:** **Adopt** — Perfect for IMEM's template plugin system. Enables `compile/Templates/` to be purely declarative domain parsers without framework pollution.

---

## Principle 3: Graph-Based Execution Orchestration

**Observed in:**
- `haystack/core/pipeline/base.py:69-135` (PipelineBase with NetworkX graph)
- `haystack/core/pipeline/base.py:1078-1223` (execution engine)
- `haystack/core/pipeline/base.py:420-601` (connection management)

**The Principle:**

Pipeline orchestration is **separate from component execution**. A NetworkX MultiDiGraph represents the computation graph (nodes = components, edges = data flow). The execution engine implements a **priority queue scheduler** that resolves inputs, executes components, and distributes outputs based on socket readiness. Components remain stateless; the graph holds execution state.

**How It Works:**

**Graph structure** (haystack/core/pipeline/base.py:76-100):
```python
class PipelineBase:
    def __init__(self, ...):
        self.graph = networkx.MultiDiGraph()  # Directed edges for data flow
        self._max_runs_per_component = max_runs_per_component

    def add_component(self, name: str, instance: Component):
        self.graph.add_node(
            name,
            instance=instance,
            input_sockets=instance.__haystack_input__,   # From @component
            output_sockets=instance.__haystack_output__, # From @component
            visits=0  # Execution counter
        )

    def connect(self, sender: str, receiver: str):
        sender_name, sender_socket = parse_connect_string(sender)
        receiver_name, receiver_socket = parse_connect_string(receiver)

        # Type compatibility check
        if not _types_are_compatible(sender_type, receiver_type):
            raise PipelineConnectError(f"Type mismatch: {sender_type} -> {receiver_type}")

        self.graph.add_edge(
            sender_name, receiver_name,
            from_socket=sender_socket_obj,
            to_socket=receiver_socket_obj,
            conn_type="...")
```

**Execution engine** (haystack/core/pipeline/base.py:1078-1223):
```python
def run(self, data: dict) -> dict:
    # 1. Prepare: Convert input data to socket format
    inputs_per_component = self._prepare_component_input_data(data)

    # 2. Priority Queue: Components sorted by readiness
    priority_queue = FIFOPriorityQueue()
    for component_name in self.graph.nodes:
        priority = self._calculate_priority(component_name, inputs_per_component)
        priority_queue.add(component_name, priority)

    # 3. Execution Loop
    while not priority_queue.is_empty():
        component_name = priority_queue.pop()
        component = self.graph.nodes[component_name]["instance"]

        # Consume inputs from queue
        component_inputs = self._consume_component_inputs(
            component_name, inputs_per_component
        )

        # Execute
        outputs = component.run(**component_inputs)

        # Distribute outputs to downstream components
        self._write_component_outputs(
            component_name, outputs, inputs_per_component
        )

        # Update priority queue with downstream components
        for successor in self.graph.successors(component_name):
            priority = self._calculate_priority(successor, inputs_per_component)
            priority_queue.add(successor, priority)

    # 4. Return final outputs
    return self._collect_outputs(inputs_per_component)
```

**Priority calculation** (haystack/core/pipeline/base.py:61-67):
```python
class ComponentPriority(IntEnum):
    HIGHEST = 1      # Greedy variadic sockets ready
    READY = 2        # All required inputs available
    DEFER = 3        # Some inputs missing but have defaults
    DEFER_LAST = 4   # Lazy variadic waiting for all inputs
    BLOCKED = 5      # Missing required inputs
```

**Why It Matters:**

- **Clean separation**: Components know nothing about pipeline structure or peers
- **Declarative composition**: Pipeline structure is data (serializable to YAML/JSON)
- **Intelligent scheduling**: Priority system handles complex fan-in/fan-out patterns
- **Variadic flexibility**: Lazy vs greedy sockets enable different aggregation strategies
- **Cycle detection**: Graph algorithms validate pipeline correctness
- **Stateless components**: All execution state in graph, enabling component reuse

**Application to IMEM:**

- **Where:** `retrieve/Orchestrator` multi-stage composition pipeline
- **How:** Represent query stages as graph nodes, data flow as edges, use priority queue for stage execution
- **Example:**
  ```python
  # retrieve/orchestrator.py
  class QueryGraph:
      def __init__(self):
          self.graph = networkx.DiGraph()

      def add_stage(self, name: str, primitive: Callable):
          self.graph.add_node(name, primitive=primitive, results=None)

      def connect(self, from_stage: str, to_stage: str):
          self.graph.add_edge(from_stage, to_stage)

      def execute(self, initial_data: dict) -> dict:
          # Topological sort ensures correct execution order
          execution_order = networkx.topological_sort(self.graph)

          for stage_name in execution_order:
              stage = self.graph.nodes[stage_name]

              # Gather inputs from predecessors
              inputs = self._gather_inputs(stage_name, initial_data)

              # Execute stage primitive
              results = stage["primitive"](**inputs)

              # Store results for downstream stages
              stage["results"] = results

          return self._collect_outputs()

  # Usage
  graph = QueryGraph()
  graph.add_stage("search", search_primitive)
  graph.add_stage("siblings", sibling_discovery)
  graph.add_stage("temporal", temporal_discovery)
  graph.add_stage("rank", authority_ranking)

  graph.connect("search", "siblings")
  graph.connect("search", "temporal")
  graph.connect("siblings", "rank")
  graph.connect("temporal", "rank")

  results = graph.execute({"query": "auth decisions"})
  ```

**Trade-offs:**

- **Pros:** Clear orchestration/execution separation, declarative composition, intelligent scheduling, cycle prevention, easy visualization
- **Cons:** Graph overhead for simple linear pipelines, priority logic can be complex, requires NetworkX dependency

**Adoption Recommendation:** **Adopt** — Directly addresses IMEM's "How should query primitives compose?" question. Enables `retrieve/Orchestrator` to be a generic graph executor, not hardcoded pipeline stages.

---

## Principle 4: Lazy Initialization Pattern (Warm-Up)

**Observed in:**
- `haystack/core/component/component.py:43-50` (warm_up contract)
- Component implementations with `warm_up()` methods
- `haystack/core/pipeline/base.py` (pipeline.warm_up() invocation)

**The Principle:**

Component initialization is **split into two phases**: `__init__()` for lightweight configuration (must be fast, JSON-serializable), and `warm_up()` for heavy resource loading (models, database connections, embeddings). This enables **fast pipeline construction/serialization** while deferring expensive operations until execution time.

**How It Works:**

**Contract definition** (haystack/core/component/component.py:43-50):
```python
"""
warm_up(self)

Optional method.

This method is called by Pipeline before the graph execution. Make sure to avoid
double-initializations, because Pipeline will not keep track of which components
it called `warm_up()` on.
"""
```

**Pattern in components**:
```python
@component
class EmbeddingRetriever:
    def __init__(self, document_store: DocumentStore, model_name: str = "..."):
        # Fast: Only store config
        self.document_store = document_store
        self.model_name = model_name
        self.model = None  # Not loaded yet

    def warm_up(self):
        # Expensive: Load model once before execution
        if self.model is None:
            self.model = load_embedding_model(self.model_name)

    def run(self, query: str):
        if self.model is None:
            raise RuntimeError("Call warm_up() first")
        embeddings = self.model.encode(query)
        return self.document_store.query_semantic(embeddings)
```

**Pipeline orchestration**:
```python
# Fast: Construct pipeline (no models loaded)
pipeline = Pipeline()
pipeline.add_component("embedder", EmbeddingRetriever(...))
pipeline.add_component("ranker", CrossEncoderRanker(...))
pipeline.connect("embedder", "ranker")

# Fast: Serialize to YAML (only config, no models)
pipeline_yaml = pipeline.dumps()

# Expensive: Load resources once
pipeline.warm_up()  # Calls warm_up() on all components

# Fast: Execute multiple times (models already loaded)
pipeline.run({"query": "..."})
pipeline.run({"query": "..."})
```

**Why It Matters:**

- **Fast serialization**: Pipelines with large models can be saved as small YAML files
- **Deferred loading**: Resources loaded only when needed, not during configuration
- **Reusability**: Same component config can be instantiated in different contexts
- **Separation of concerns**: Configuration logic separate from resource management
- **Idempotency**: Components handle double-warm_up gracefully

**Application to IMEM:**

- **Where:** `compile/Templates` (language models for schema resolution), `retrieve/` (embedding models, graph algorithms), `manage/Temporal` (git repository access)
- **How:** Split initialization into config (`__init__`) and resource loading (`warm_up`)
- **Example:**
  ```python
  # compile/resolver.py
  @template
  class SchemaResolver:
      def __init__(self, model_name: str = "gpt-4", corpus_path: str = "."):
          # Fast: Config only
          self.model_name = model_name
          self.corpus_path = corpus_path
          self.llm = None
          self.corpus_index = None

      def warm_up(self):
          # Expensive: Load once
          if self.llm is None:
              self.llm = load_llm(self.model_name)
          if self.corpus_index is None:
              self.corpus_index = build_corpus_index(self.corpus_path)

      def resolve_type(self, header: str) -> str:
          if self.llm is None:
              raise RuntimeError("Call warm_up() first")
          return self.llm.classify(header, self.corpus_index)

  # manage/temporal.py
  class GitValidator:
      def __init__(self, repo_path: str):
          self.repo_path = repo_path
          self.repo = None  # Not loaded

      def warm_up(self):
          if self.repo is None:
              self.repo = pygit2.Repository(self.repo_path)

      def validate_chunk(self, chunk: Chunk) -> bool:
          # Heavy git operations
          pass
  ```

**Trade-offs:**

- **Pros:** Fast construction/serialization, resource control, clear lifecycle, component reusability
- **Cons:** Requires manual state checking (`if self.model is None`), no automatic tracking of warm_up calls, can forget to call warm_up

**Adoption Recommendation:** **Adapt** — IMEM doesn't need full pipeline serialization, but the pattern applies to `compile/` and `manage/` components with heavy resources. Separate config from resource loading.

---

## Principle 5: Declarative Pipeline Serialization

**Observed in:**
- `haystack/core/pipeline/base.py:136-241` (to_dict/from_dict)
- `haystack/core/serialization.py` (component serialization)
- `haystack/marshal/` (YAML/JSON marshalling)

**The Principle:**

Pipelines are **data structures**, not code. A pipeline's complete specification (components, connections, config) serializes to a dictionary, then to YAML/JSON. Deserialization reconstructs the pipeline using dynamic component imports and the global registry. This enables **pipelines as configuration files**, version control of workflows, and dynamic composition.

**How It Works:**

**Serialization** (haystack/core/pipeline/base.py:136-161):
```python
def to_dict(self) -> dict[str, Any]:
    components = {}
    for name, instance in self.graph.nodes(data="instance"):
        components[name] = component_to_dict(instance, name)

    connections = []
    for sender, receiver, edge_data in self.graph.edges(data=True):
        connections.append({
            "sender": f"{sender}.{edge_data['from_socket'].name}",
            "receiver": f"{receiver}.{edge_data['to_socket'].name}"
        })

    return {
        "metadata": self.metadata,
        "max_runs_per_component": self._max_runs_per_component,
        "components": components,
        "connections": connections
    }
```

**Component serialization** (haystack/core/serialization.py:37-79):
```python
def component_to_dict(obj: Any, name: str) -> dict[str, Any]:
    # Extract init parameters from instance attributes
    init_parameters = {
        param_name: getattr(obj, param_name)
        for param_name in inspect.signature(obj.__init__).parameters
        if param_name not in ("args", "kwargs")
    }

    return {
        "type": f"{obj.__class__.__module__}.{obj.__class__.__name__}",
        "init_parameters": init_parameters
    }
```

**Deserialization** (haystack/core/pipeline/base.py:165-241):
```python
@classmethod
def from_dict(cls, data: dict, callbacks: DeserializationCallbacks = None):
    pipe = cls(
        metadata=data.get("metadata", {}),
        max_runs_per_component=data.get("max_runs_per_component", 100)
    )

    # Recreate components from registry
    for name, component_data in data["components"].items():
        component_class = thread_safe_import(component_data["type"])

        # Optional callback to modify init_parameters
        if callbacks and callbacks.component_pre_init:
            callbacks.component_pre_init(name, component_class, component_data["init_parameters"])

        instance = component_class(**component_data["init_parameters"])
        pipe.add_component(name, instance)

    # Recreate connections
    for conn in data["connections"]:
        pipe.connect(conn["sender"], conn["receiver"])

    return pipe
```

**YAML roundtrip**:
```python
# Define pipeline in code
pipeline = Pipeline()
pipeline.add_component("retriever", InMemoryBM25Retriever(doc_store))
pipeline.add_component("prompt", PromptBuilder(template="..."))
pipeline.connect("retriever.documents", "prompt.documents")

# Save to YAML
with open("rag_pipeline.yaml", "w") as f:
    pipeline.dump(f)

# Load from YAML (different process/machine)
with open("rag_pipeline.yaml") as f:
    loaded_pipeline = Pipeline.load(f)

loaded_pipeline.run({"query": "..."})
```

**Example YAML output**:
```yaml
metadata:
  name: "RAG Pipeline"
max_runs_per_component: 100
components:
  retriever:
    type: "haystack.components.retrievers.in_memory.InMemoryBM25Retriever"
    init_parameters:
      document_store:
        type: "haystack.document_stores.in_memory.InMemoryDocumentStore"
        init_parameters: {}
      top_k: 10
  prompt:
    type: "haystack.components.builders.PromptBuilder"
    init_parameters:
      template: "Context: {{documents}}\nQuestion: {{query}}"
connections:
  - sender: "retriever.documents"
    receiver: "prompt.documents"
```

**Why It Matters:**

- **Pipelines as config**: Define workflows declaratively, not imperatively
- **Version control**: Track pipeline evolution in git alongside code
- **Dynamic composition**: Load different pipelines based on runtime config
- **Reproducibility**: Exact pipeline specification for experiment tracking
- **Portability**: Share pipelines without sharing code (via YAML)
- **A/B testing**: Swap pipeline variants without code changes

**Application to IMEM:**

- **Where:** `retrieve/Orchestrator` query composition, `compile/` indexing pipelines
- **How:** Define query strategies as YAML configs, load appropriate orchestration graph at runtime
- **Example:**
  ```yaml
  # .context/queries/feature_lineage.yaml
  metadata:
    name: "Feature Lineage Query"
    description: "Trace design → develop → document for a feature"

  stages:
    search:
      primitive: "metadata_search"
      config:
        filters:
          section_type: "Decision"

    genealogy:
      primitive: "session_genealogy"
      depends_on: ["search"]
      config:
        direction: "forward"

    cross_phase:
      primitive: "phase_discovery"
      depends_on: ["genealogy"]
      config:
        phases: ["design", "designate", "develop", "document"]

    rank:
      primitive: "authority_rank"
      depends_on: ["cross_phase"]
      config:
        algorithm: "pagerank"

  # Python
  query_spec = yaml.safe_load(open("feature_lineage.yaml"))
  graph = build_query_graph(query_spec)
  results = graph.execute({"query": "authentication"})
  ```

**Trade-offs:**

- **Pros:** Declarative workflow definition, config-driven composition, version control, A/B testing, reproducibility
- **Cons:** YAML complexity for deeply nested configs, requires careful namespace management for component types, debugging harder with dynamic construction

**Adoption Recommendation:** **Consider** — Not critical for IMEM MVP, but valuable for `retrieve/` query presets. Users could define common query patterns as YAML configs that orchestrator loads dynamically.

---

## Principle 6: Composable SuperComponents (Fractal Architecture)

**Observed in:**
- `haystack/core/super_component/super_component.py:34-99`
- Pipeline wrapping with input/output mapping
- Pipeline-as-component pattern

**The Principle:**

Pipelines can be **wrapped as components** (SuperComponents), exposing only selected inputs/outputs. This enables **fractal composition**: complex pipelines can be nested as black boxes within larger pipelines. Internal complexity is hidden behind a component interface, enabling hierarchical decomposition and reusable sub-pipelines.

**How It Works:**

**SuperComponent wrapper** (haystack/core/super_component/super_component.py:34-99):
```python
@component
class _SuperComponent:
    def __init__(
        self,
        pipeline: Pipeline,
        input_mapping: Optional[dict[str, list[str]]] = None,
        output_mapping: Optional[dict[str, str]] = None
    ):
        """
        Wraps a pipeline as a component.

        :param pipeline: The internal pipeline to wrap
        :param input_mapping: Maps super-component inputs to internal component.socket paths
            Example: {"query": ["retriever.query", "prompt_builder.query"]}
        :param output_mapping: Maps internal component.socket paths to super-component outputs
            Example: {"generator.replies": "replies", "retriever.documents": "documents"}
        """
        self.pipeline = pipeline
        self.input_mapping = input_mapping or self._create_default_mapping(...)
        self.output_mapping = output_mapping or self._create_default_mapping(...)

        # Set input/output types on super-component from pipeline structure
        for input_name, socket_paths in self.input_mapping.items():
            component.set_input_type(self, name=input_name, ...)

        for output_path, output_name in self.output_mapping.items():
            component.set_output_types(self, **{output_name: output_type})

    def run(self, **inputs):
        # Convert super-component inputs to internal pipeline format
        pipeline_inputs = self._map_inputs(inputs)

        # Execute internal pipeline
        pipeline_outputs = self.pipeline.run(pipeline_inputs)

        # Convert internal outputs to super-component format
        return self._map_outputs(pipeline_outputs)
```

**Example usage**:
```python
# Define a reusable RAG sub-pipeline
rag_pipeline = Pipeline()
rag_pipeline.add_component("embedder", TextEmbedder())
rag_pipeline.add_component("retriever", InMemoryEmbeddingRetriever(doc_store))
rag_pipeline.add_component("prompt", PromptBuilder(template))
rag_pipeline.add_component("llm", OpenAIGenerator())
rag_pipeline.connect("embedder", "retriever")
rag_pipeline.connect("retriever", "prompt")
rag_pipeline.connect("prompt", "llm")

# Wrap as a component (hide internal complexity)
rag_component = SuperComponent(
    pipeline=rag_pipeline,
    input_mapping={"query": ["embedder.text", "prompt.query"]},
    output_mapping={"llm.replies": "answer"}
)

# Use in larger pipeline
main_pipeline = Pipeline()
main_pipeline.add_component("preprocessor", TextCleaner())
main_pipeline.add_component("rag", rag_component)  # Nested pipeline
main_pipeline.add_component("postprocessor", ResponseFormatter())
main_pipeline.connect("preprocessor", "rag.query")
main_pipeline.connect("rag.answer", "postprocessor")

# Internal RAG complexity hidden
main_pipeline.run({"text": "What is authentication?"})
```

**Why It Matters:**

- **Hierarchical decomposition**: Break complex systems into manageable sub-systems
- **Reusability**: Package common patterns as reusable black boxes
- **Interface isolation**: Hide internal changes from consumers
- **Testing**: Test sub-pipelines independently
- **Modularity**: Mix-and-match validated components
- **Fractal scaling**: Same abstraction at all levels (components and pipelines use same interface)

**Application to IMEM:**

- **Where:** `retrieve/Orchestrator` sub-queries, `compile/` multi-stage parsing
- **How:** Wrap common query patterns (siblings+temporal, genealogy+cross-phase) as composable primitives
- **Example:**
  ```python
  # retrieve/patterns/discovery.py
  def create_discovery_subgraph():
      """Reusable discovery pattern: siblings + temporal + merge"""
      graph = QueryGraph()
      graph.add_stage("siblings", sibling_discovery)
      graph.add_stage("temporal", temporal_discovery)
      graph.add_stage("merge", merge_results)
      graph.connect("siblings", "merge")
      graph.connect("temporal", "merge")
      return graph

  class DiscoveryPrimitive:
      def __init__(self, config: dict):
          self.subgraph = create_discovery_subgraph()
          self.config = config

      def run(self, chunks: list[Chunk]) -> list[Chunk]:
          # Execute internal subgraph
          return self.subgraph.execute({
              "chunks": chunks,
              **self.config
          })

  # Use in larger orchestration
  main_graph = QueryGraph()
  main_graph.add_stage("search", metadata_search)
  main_graph.add_stage("discover", DiscoveryPrimitive(config))  # Nested
  main_graph.add_stage("rank", authority_rank)
  main_graph.connect("search", "discover")
  main_graph.connect("discover", "rank")
  ```

**Trade-offs:**

- **Pros:** Clean abstraction, reusable patterns, hierarchical composition, independent testing
- **Cons:** Additional wrapping complexity, input/output mapping can be verbose, debugging nested pipelines harder

**Adoption Recommendation:** **Consider** — Not critical for IMEM MVP, but useful for `retrieve/` once common query patterns emerge. Enables packaging `siblings+temporal+genealogy` as a reusable "discovery" primitive.

---

## Synthesis: Implications for IMEM

### Recommended Structural Changes

1. **Storage Layer Protocol-First Design**
   - Define `ChunkStore` protocol in `storage/protocol.py`
   - Implement `SQLiteChunkStore`, `QdrantChunkStore` without inheritance
   - All `retrieve/` and `manage/` code depends on protocol, never concrete implementations
   - Standardize filter DSL across backends (nested dict syntax)

2. **Template Plugin System via Decorators**
   - Create `@template(doc_type="...")` decorator for `compile/Templates/`
   - Global registry: `template_registry[doc_type] = TemplateClass`
   - Templates auto-serialize via introspection (convention: `self.param = param`)
   - Parser discovers templates dynamically from registry

3. **Query Orchestration as Graph Execution**
   - Replace `retrieve/compose.py` linear pipeline with NetworkX graph
   - Nodes = primitive functions (search, siblings, temporal, genealogy, rank)
   - Edges = data dependencies
   - Priority queue scheduler executes stages based on dependency resolution
   - Enables parallel execution of independent stages (siblings + temporal)

4. **Lazy Resource Initialization Pattern**
   - Split `compile/Resolver` into `__init__(config)` + `warm_up()` (load LLM)
   - Split `manage/Temporal` into `__init__(repo_path)` + `warm_up()` (open git repo)
   - Storage backends: `__init__(path)` + `warm_up()` (open connections)
   - Benefits: fast config, deferred heavy operations

5. **Optional: Query Presets as YAML Configs**
   - Define common query patterns in `.context/queries/*.yaml`
   - Graph builder loads YAML, constructs orchestration graph
   - Users can customize presets without code changes

### Directory Structure Implications

```
imem/
├── compile/
│   ├── parser.py                   # Main parsing orchestrator
│   ├── resolver.py                 # Schema evolution (with warm_up)
│   ├── observer.py                 # Pattern discovery
│   └── templates/                  # Plugin templates
│       ├── __init__.py             # @template decorator, registry
│       ├── changelog.py            # @template(doc_type="changelog")
│       ├── conversation.py         # @template(doc_type="conversation")
│       ├── adr.py                  # @template(doc_type="adr")
│       └── spec.py                 # @template(doc_type="spec")
│
├── manage/
│   ├── temporal.py                 # Git validation (with warm_up)
│   ├── resolver.py                 # Entity resolution (with warm_up)
│   ├── registry.py                 # Tier 1 cross-project facts
│   └── qualification.py            # Tier 2 cross-project metadata
│
├── retrieve/
│   ├── orchestrator.py             # Graph-based query executor
│   ├── graph.py                    # QueryGraph class (NetworkX wrapper)
│   ├── primitives/                 # Discovery primitives
│   │   ├── __init__.py
│   │   ├── search.py               # Metadata + semantic search
│   │   ├── siblings.py             # Same-file discovery
│   │   ├── genealogy.py            # Session-based lineage
│   │   ├── temporal.py             # Time-based discovery
│   │   └── cross_phase.py          # Phase lifecycle traversal
│   ├── ranking.py                  # Authority, confidence, recency
│   └── presets/                    # Optional: YAML query configs
│       ├── feature_lineage.yaml
│       ├── pattern_discovery.yaml
│       └── authority_validation.yaml
│
├── structure/
│   ├── templates/                  # Jinja2 presentation templates
│   ├── contextualize.py            # Add graph metadata to chunks
│   └── render.py                   # Format output
│
└── storage/
    ├── protocol.py                 # ChunkStore Protocol definition
    ├── sqlite.py                   # SQLiteChunkStore (no inheritance)
    ├── qdrant.py                   # QdrantChunkStore (no inheritance)
    └── readers.py                  # Markdown + JSONL parsers
```

### Key Interfaces to Define

**1. ChunkStore Protocol** (`storage/protocol.py`)
```python
from typing import Protocol, Optional
from dataclasses import dataclass

class ChunkStore(Protocol):
    """Storage backend protocol for chunk operations."""

    def query_metadata(
        self,
        filters: Optional[dict] = None,
        limit: int = 100
    ) -> list[Chunk]:
        """Query chunks by metadata filters."""
        ...

    def query_semantic(
        self,
        embedding: list[float],
        top_k: int = 10,
        filters: Optional[dict] = None
    ) -> list[Chunk]:
        """Query chunks by semantic similarity."""
        ...

    def write_chunks(
        self,
        chunks: list[Chunk],
        policy: DuplicatePolicy = DuplicatePolicy.OVERWRITE
    ) -> int:
        """Write chunks to storage."""
        ...

    def count_chunks(self, filters: Optional[dict] = None) -> int:
        """Count chunks matching filters."""
        ...

    def to_dict(self) -> dict:
        """Serialize store config."""
        ...

    @classmethod
    def from_dict(cls, data: dict) -> "ChunkStore":
        """Deserialize store from config."""
        ...
```

**2. Template Plugin Interface** (`compile/templates/__init__.py`)
```python
from typing import Callable, Type
from dataclasses import dataclass

template_registry: dict[str, Type] = {}

def template(doc_type: str):
    """Decorator to register template plugins."""
    def decorator(cls):
        template_registry[doc_type] = cls
        # Optional: Validate template interface
        if not hasattr(cls, "parse"):
            raise ValueError(f"{cls.__name__} must implement parse()")
        return cls
    return decorator

@dataclass
class TemplateResult:
    chunks: list[Chunk]
    metadata: dict
```

**3. Query Primitive Interface** (`retrieve/primitives/__init__.py`)
```python
from typing import Callable, Protocol

class QueryPrimitive(Protocol):
    """Protocol for query stage primitives."""

    def __call__(
        self,
        chunks: list[Chunk],
        store: ChunkStore,
        config: dict
    ) -> list[Chunk]:
        """Execute primitive on chunks."""
        ...
```

**4. QueryGraph Interface** (`retrieve/graph.py`)
```python
import networkx as nx
from typing import Callable

class QueryGraph:
    """Graph-based query orchestration."""

    def __init__(self):
        self.graph = nx.DiGraph()

    def add_stage(
        self,
        name: str,
        primitive: Callable,
        config: dict = None
    ):
        """Add query stage node."""
        self.graph.add_node(
            name,
            primitive=primitive,
            config=config or {},
            results=None
        )

    def connect(self, from_stage: str, to_stage: str):
        """Add dependency edge."""
        self.graph.add_edge(from_stage, to_stage)

    def execute(
        self,
        initial_data: dict,
        store: ChunkStore
    ) -> dict:
        """Execute graph in topological order."""
        # Topological sort for dependency resolution
        # Priority queue for parallel execution of independent stages
        # Return final outputs
        ...
```

### Extension Points to Establish

1. **Template Registry** (`compile/templates/__init__.py`)
   - Entry point: `@template(doc_type="custom")` decorator
   - Interface: `parse(content: str) -> TemplateResult`
   - Discovery: `template_registry[doc_type]`

2. **Primitive Registry** (`retrieve/primitives/__init__.py`)
   - Entry point: `primitive_registry[name] = function`
   - Interface: `Callable[[list[Chunk], ChunkStore, dict], list[Chunk]]`
   - Discovery: Used by query graph builder

3. **Storage Backend Registry** (`storage/__init__.py`)
   - Entry point: `store_registry[backend_type] = StoreClass`
   - Interface: Implements `ChunkStore` protocol
   - Discovery: `create_store(backend_type, config)`

4. **Query Preset Loader** (`retrieve/presets/__init__.py`)
   - Entry point: YAML files in `retrieve/presets/` or user `.context/queries/`
   - Interface: YAML schema with `stages`, `connections`, `metadata`
   - Discovery: `load_preset(name)` scans directories

---

## Summary Table

| Principle | Impact on IMEM | Adoption | Priority |
|-----------|----------------|----------|----------|
| **Protocol-First Storage Abstraction** | Enables SQLite/Qdrant interchangeability, clean retrieve/storage boundary | **Adopt** | **High** — Core architectural decision |
| **Decorator-Driven Component Registration** | Template plugins without boilerplate, auto-serialization | **Adopt** | **High** — Enables compile/Templates/ plugin system |
| **Graph-Based Execution Orchestration** | Query primitives compose declaratively, parallel execution | **Adopt** | **High** — Solves "How should query primitives compose?" |
| **Lazy Initialization Pattern** | Fast config, deferred resource loading (LLMs, git repos) | **Adapt** | **Medium** — Useful for compile/manage/ heavy components |
| **Declarative Pipeline Serialization** | Query presets as YAML configs, A/B testing | **Consider** | **Low** — Nice-to-have for retrieve/ presets |
| **Composable SuperComponents** | Reusable discovery patterns (siblings+temporal+genealogy) | **Consider** | **Low** — Useful after patterns emerge |

---

## References

### Key Architectural Documents Consulted
- `haystack/core/component/component.py` — Component contract and decorator
- `haystack/core/pipeline/base.py` — Graph orchestration engine
- `haystack/document_stores/types/protocol.py` — Storage abstraction
- `haystack/core/serialization.py` — Auto-serialization mechanics
- `haystack/core/super_component/super_component.py` — Fractal composition

### Critical Modules Examined
- Component registration and socket system (`haystack/core/component/`)
- NetworkX-based pipeline execution (`haystack/core/pipeline/`)
- Protocol-based document stores (`haystack/document_stores/`)
- Template-based retrievers (`haystack/components/retrievers/`)
- Marshalling infrastructure (`haystack/marshal/`)

### Design Decisions Observed
1. **Protocols over inheritance** — Runtime-checkable protocols for extensibility
2. **Decorator-driven registration** — Zero-boilerplate component creation
3. **Graph-based orchestration** — NetworkX for declarative composition
4. **Two-phase initialization** — Fast config, lazy resource loading
5. **Serialization-first design** — Pipelines as data structures
6. **Fractal composition** — Pipelines wrap as components for hierarchical decomposition
