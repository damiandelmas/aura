# Pattern Extraction: haystack

## Executive Summary

Haystack is a production-grade LLM orchestration framework that excels in **component-based pipeline architecture**. Its standout patterns include: (1) decorator-based component registration with automatic socket introspection, (2) graph-based execution using NetworkX with type validation, (3) Protocol-based abstraction layers (DocumentStore, Marshaller), and (4) dynamic socket generation for runtime-flexible components. These patterns are directly applicable to IMEM's compilation infrastructure, especially for template plugins, multi-stage query orchestration, and storage abstraction.

---

## Pattern 1: Decorator-Based Component Registry with Metaclass Introspection

**Location:** `haystack/core/component/component.py:558-631`

**Description:**

Haystack uses the `@component` decorator to register classes in a global registry (`component.registry`). The decorator applies a custom metaclass (`ComponentMeta`) that:

1. **Auto-introspects `run()` method signatures** to derive input/output sockets
2. **Validates component contract** (requires `run()` method, optional `warm_up()`)
3. **Creates new class with ComponentMeta** to intercept `__call__` and populate sockets
4. **Registers fully-qualified class path** (`module.ClassName`) in global registry

This enables:
- **Lazy discovery**: Components auto-register on import
- **Serialization**: Pipeline can reconstruct components from `type` field via registry lookup
- **Zero boilerplate**: No manual registration calls needed

**Code Example:**

```python
# From haystack/core/component/component.py:558-597
class _Component:
    def __init__(self):
        self.registry = {}

    def _component(self, cls: type[T]) -> type[T]:
        logger.debug("Registering {component} as a component", component=cls)

        # Check for required methods
        if not hasattr(cls, "run"):
            raise ComponentError(f"{cls.__name__} must have a 'run()' method")

        # Recreate class with ComponentMeta metaclass
        new_cls: type[T] = new_class(
            cls.__name__, cls.__bases__,
            {"metaclass": ComponentMeta},
            copy_class_namespace
        )

        # Save in registry for deserialization
        class_path = f"{new_cls.__module__}.{new_cls.__name__}"
        self.registry[class_path] = new_cls

        return new_cls

component = _Component()

# Usage:
@component
class MyParser:
    @component.output_types(chunks=list[Chunk])
    def run(self, source: str) -> dict:
        return {"chunks": parse(source)}
```

**Relevance to IMEM:**

- **Module:** `compile/Templates`
- **Use case:** Template parser plugins (changelog, conversation, ADR) auto-register via naming convention or decorator
- **Why useful:**
  - No central hardcoded list of templates
  - Extensible without core changes
  - Enables dynamic template discovery for schema evolution

**Adoption Strategy:**

- [x] **Adapt** — Create similar decorator for IMEM template parsers:
  - Templates register via `@template` decorator
  - Standard interface: `parse(source: str, context: dict) -> list[Chunk]`
  - Registry enables introspection for `compile/Observer` to discover available parsers
  - Example: `@template(name="changelog", handles=["changelog.md", "CHANGELOG.md"])`

**Implementation Priority:** **High** — Core to template plugin architecture

---

## Pattern 2: Graph-Based Pipeline Composition with NetworkX

**Location:** `haystack/core/pipeline/base.py:99-102, 137-161`

**Description:**

Haystack models pipelines as **directed multi-graphs** using NetworkX, where:

- **Nodes** = component instances (with metadata: name, instance)
- **Edges** = data flow connections (with metadata: `from_socket`, `to_socket`, `conn_type`)
- **Execution** = topological traversal with greedy/variadic socket logic

Key features:
- **Type validation on connection**: Checks socket types before adding edges
- **Serialization-friendly**: Graph structure → dict → YAML/JSON
- **Multi-stage queries**: Same graph infrastructure handles branching/merging pipelines

**Code Example:**

```python
# From haystack/core/pipeline/base.py:99-102
class PipelineBase:
    def __init__(self, metadata=None, max_runs_per_component=100):
        self.metadata = metadata or {}
        self.graph = networkx.MultiDiGraph()  # Directed multi-graph
        self._max_runs_per_component = max_runs_per_component

    def to_dict(self) -> dict[str, Any]:
        components = {}
        for name, instance in self.graph.nodes(data="instance"):
            components[name] = component_to_dict(instance, name)

        connections = []
        for sender, receiver, edge_data in self.graph.edges.data():
            sender_socket = edge_data["from_socket"].name
            receiver_socket = edge_data["to_socket"].name
            connections.append({
                "sender": f"{sender}.{sender_socket}",
                "receiver": f"{receiver}.{receiver_socket}"
            })

        return {
            "metadata": self.metadata,
            "components": components,
            "connections": connections
        }
```

**Relevance to IMEM:**

- **Module:** `retrieve/Orchestrator`
- **Use case:** Multi-stage query composition (search → discovery → graph → ranking)
- **Why useful:**
  - Supports branching (parallel discovery operations)
  - Topological sort ensures correct execution order
  - Same pattern for both simple and complex query pipelines
  - NetworkX already planned for `retrieve/Graph` authority scoring

**Adoption Strategy:**

- [x] **Adopt directly** — Use NetworkX MultiDiGraph for query orchestration:
  - Nodes = query stages (SearchStage, DiscoveryStage, GraphStage)
  - Edges = data dependencies (which stage feeds which)
  - Enables preset library: "authority query" = pre-built graph template
  - Serializable to JSON for introspection API

**Implementation Priority:** **High** — Directly supports designed multi-stage retrieval

---

## Pattern 3: Protocol-Based Backend Abstraction

**Location:** `haystack/document_stores/types/protocol.py:14-139`

**Description:**

Haystack defines storage backends via **Protocol classes** (Python 3.8+ structural subtyping), not ABCs. This:

1. **Decouples interface from implementation** — any class matching the protocol works
2. **No inheritance required** — third-party stores can be compatible without extending base class
3. **Type-checkable** — mypy validates implementations without runtime overhead
4. **Minimal contract** — only 5 methods required: `to_dict`, `from_dict`, `count_documents`, `filter_documents`, `write_documents`

**Code Example:**

```python
# From haystack/document_stores/types/protocol.py:14-43
class DocumentStore(Protocol):
    """
    Stores Documents to be used by pipeline components.
    """

    def to_dict(self) -> dict[str, Any]:
        """Serializes this store to a dictionary."""
        ...

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DocumentStore":
        """Deserializes the store from a dictionary."""
        ...

    def count_documents(self) -> int:
        """Returns the number of documents stored."""
        ...

    def filter_documents(self, filters: Optional[dict[str, Any]] = None) -> list[Document]:
        """Returns documents matching the filters."""
        ...

    def write_documents(self, documents: list[Document], policy: DuplicatePolicy) -> int:
        """Writes documents with specified duplicate handling."""
        ...

# Any class implementing these methods is a valid DocumentStore
# No explicit inheritance needed
```

**Relevance to IMEM:**

- **Module:** `storage/`
- **Use case:** Backend adapters (SQLite, Qdrant) share common interface
- **Why useful:**
  - Extensibility without modifying core
  - Third-party backends (e.g., ChromaDB, Pinecone) can plug in
  - Type-safe without ABC overhead
  - Supports IMEM's "storage agnostic" design principle

**Adoption Strategy:**

- [x] **Adopt directly** — Define storage protocols:
  ```python
  class ChunkStore(Protocol):
      def write_chunks(self, chunks: list[Chunk]) -> int: ...
      def query_metadata(self, filters: dict) -> list[Chunk]: ...
      def count_chunks(self) -> int: ...

  class VectorStore(Protocol):
      def embed_chunks(self, chunks: list[Chunk]) -> None: ...
      def semantic_search(self, query: str, limit: int) -> list[Chunk]: ...
  ```
  - SQLiteStore and QdrantStore independently implement protocols
  - No shared base class, just contract adherence

**Implementation Priority:** **Medium** — Important for extensibility, but SQLite already committed

---

## Pattern 4: Dynamic Socket Generation for Runtime Flexibility

**Location:** `haystack/components/routers/metadata_router.py:108`, `haystack/testing/sample_components/remainder.py:14`

**Description:**

Components can **dynamically generate output sockets at init time** using `component.set_output_types()`. This enables:

1. **Branching based on init parameters** — e.g., router creates one socket per rule
2. **Conditional pipeline structure** — pipeline shape adapts to component config
3. **Type safety preserved** — dynamically created sockets still type-checked

Haystack uses this for:
- **Routers**: MetadataRouter creates one output per routing rule + "unmatched"
- **Variadic outputs**: Remainder component creates `remainder_is_0`, `remainder_is_1`, etc.

**Code Example:**

```python
# From haystack/components/routers/metadata_router.py:59-108
@component
class MetadataRouter:
    def __init__(self, rules: dict[str, dict], output_type: type = list[Document]):
        self.rules = rules
        self.output_type = output_type

        # Dynamically create one output socket per rule + "unmatched"
        component.set_output_types(
            self,
            unmatched=self.output_type,
            **dict.fromkeys(rules, self.output_type)
        )

    def run(self, documents: list[Document]):
        output = {edge: [] for edge in self.rules}
        unmatched = []

        for doc in documents:
            matched = False
            for edge, rule in self.rules.items():
                if document_matches_filter(filters=rule, document=doc):
                    output[edge].append(doc)
                    matched = True
            if not matched:
                unmatched.append(doc)

        output["unmatched"] = unmatched
        return output

# Usage:
router = MetadataRouter(rules={
    "recent": {"field": "meta.year", "operator": ">=", "value": 2020},
    "archived": {"field": "meta.year", "operator": "<", "value": 2020}
})
# Creates sockets: "recent", "archived", "unmatched"
```

**Relevance to IMEM:**

- **Module:** `retrieve/Primitives`, `structure/`
- **Use case:** Discovery primitives that create one output per section_type requested
- **Why useful:**
  - Query: "Get siblings of type Pattern, Implementation, Context"
  - Component creates 3 outputs: `pattern_siblings`, `implementation_siblings`, `context_siblings`
  - Enables parallel downstream processing
  - Type-safe routing based on metadata predicates

**Adoption Strategy:**

- [ ] **Avoid (for now)** — IMEM retrieval currently returns unified result sets
  - Dynamic sockets add complexity without clear current benefit
  - Future consideration: If preset library grows to complex branching queries
  - Alternative: Return dict with dynamic keys, let orchestrator handle routing

**Implementation Priority:** **Low** — Not critical for current design

---

## Pattern 5: Marshaller Protocol for Format-Agnostic Serialization

**Location:** `haystack/marshal/protocol.py:11-18`, `haystack/core/pipeline/base.py:243-263`

**Description:**

Haystack separates **serialization logic** (dict ↔ object) from **format encoding** (dict ↔ string) via the `Marshaller` protocol:

1. **Core uses `to_dict()`/`from_dict()`** — components know how to serialize themselves
2. **Marshaller handles format** — YAML, JSON, TOML, etc. interchangeable
3. **Default marshaller injected** — `YamlMarshaller` unless overridden
4. **Zero coupling** — changing format doesn't touch component code

**Code Example:**

```python
# From haystack/marshal/protocol.py:11-18
class Marshaller(Protocol):
    def marshal(self, dict_: dict[str, Any]) -> str:
        """Convert a dictionary to its string representation"""
        ...

    def unmarshal(self, data_: Union[str, bytes, bytearray]) -> dict[str, Any]:
        """Convert a marshalled object to its dictionary representation"""
        ...

# From haystack/core/pipeline/base.py:243-273
DEFAULT_MARSHALLER = YamlMarshaller()

class PipelineBase:
    def dumps(self, marshaller: Marshaller = DEFAULT_MARSHALLER) -> str:
        return marshaller.marshal(self.to_dict())

    def dump(self, fp: TextIO, marshaller: Marshaller = DEFAULT_MARSHALLER):
        fp.write(marshaller.marshal(self.to_dict()))

    @classmethod
    def loads(cls, data: str, marshaller: Marshaller = DEFAULT_MARSHALLER):
        return cls.from_dict(marshaller.unmarshal(data))

    @classmethod
    def load(cls, fp: TextIO, marshaller: Marshaller = DEFAULT_MARSHALLER):
        return cls.from_dict(marshaller.unmarshal(fp.read()))

# Usage:
pipeline.dumps()  # YAML by default
pipeline.dumps(JsonMarshaller())  # JSON if needed
```

**Relevance to IMEM:**

- **Module:** `compile/`, `storage/`
- **Use case:** Persist compiled chunks/metadata in multiple formats
- **Why useful:**
  - Current SQLite schema is one format
  - May need JSON export for cross-project registry
  - Pattern export could be YAML for human readability
  - Separates data structure from encoding

**Adoption Strategy:**

- [ ] **Avoid** — IMEM has clear storage commitments (SQLite primary, Qdrant optional)
  - No current need for multiple serialization formats
  - SQLite schema handles persistence
  - If export needed, can add ad-hoc JSON serializer later
  - Adds abstraction without solving current problem

**Implementation Priority:** **Low** — Not aligned with current needs

---

## Summary Table

| Pattern | IMEM Module | Priority | Strategy |
|---------|-------------|----------|----------|
| Decorator-Based Component Registry | compile/Templates | **High** | **Adapt** — Template auto-registration |
| Graph-Based Pipeline (NetworkX) | retrieve/Orchestrator | **High** | **Adopt** — Multi-stage query composition |
| Protocol-Based Backend Abstraction | storage/ | **Medium** | **Adopt** — SQLite/Qdrant protocols |
| Dynamic Socket Generation | retrieve/Primitives | **Low** | **Avoid** — Adds complexity, no clear benefit |
| Marshaller Protocol | compile/, storage/ | **Low** | **Avoid** — No multi-format requirement |

---

## Key Files Examined

- `haystack/core/component/component.py` — Component decorator, metaclass, registry
- `haystack/core/pipeline/base.py` — NetworkX graph orchestration
- `haystack/core/pipeline/pipeline.py` — Synchronous execution engine
- `haystack/document_stores/types/protocol.py` — DocumentStore protocol
- `haystack/marshal/protocol.py` — Marshaller protocol
- `haystack/components/routers/metadata_router.py` — Dynamic socket example
- `haystack/testing/sample_components/remainder.py` — Dynamic socket example
- `haystack/core/serialization.py` — Component serialization logic

---

## References

- **Component Contract Documentation:** Embedded in `haystack/core/component/component.py:5-70`
- **NetworkX Integration:** Uses `networkx.MultiDiGraph` for pipeline structure
- **Protocol Pattern:** PEP 544 structural subtyping (Python 3.8+)
- **Metaclass Introspection:** Uses `inspect.signature()` to derive sockets from `run()` method
- **Key Architectural Decision:** Separation of orchestration (Pipeline) from execution (Component.run())

---

## Additional Observations

### What Haystack Does Well

1. **Zero-boilerplate component creation** — Decorator + metaclass = no manual registration
2. **Type-safe extensibility** — Protocols enable third-party components/stores without coupling
3. **Graph-native thinking** — NetworkX from the start, not retrofitted
4. **Serialization baked in** — Every component has `to_dict()/from_dict()` contract
5. **Runtime flexibility** — Dynamic sockets enable parameter-driven pipeline structure

### Architectural Alignment with IMEM

- **Template architecture** → Haystack's component registry pattern
- **Multi-stage retrieval** → Haystack's NetworkX pipeline pattern
- **Storage agnostic** → Haystack's Protocol-based backends
- **Metadata as edges** → Haystack's graph-first thinking

### Anti-Patterns Avoided

- **No inheritance hell** — Protocols over ABCs
- **No global state** — Registry owned by decorator instance
- **No tight coupling** — Marshaller protocol separates format from logic
- **No manual wiring** — Metaclass introspection derives sockets automatically
