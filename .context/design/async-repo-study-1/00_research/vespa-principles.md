# Architectural Principles: vespa

## Executive Summary

Vespa is a distributed search and storage platform (~1.7M lines, Java/C++) that demonstrates **configuration-driven architecture at scale**. Its core philosophy: **minimize hard-coded dependencies, maximize declarative structure**. System topology, component wiring, and even code generation flow from **typed configuration schemas** (.def files) that propagate through a **generation-based subscription system**. Components extend via **plugin chains** (Searchers, DocumentProcessors) that compose declaratively, not imperatively. The **Java/C++ language boundary** is managed through **shared document models** and **RPC-based message passing**, never direct linking. For IMEM: this shows how to build **template-driven compilation** where schema evolves from observation, how to separate **intelligence layers** through clean interfaces, and how to make **storage backends** truly swappable through abstract retrieval contracts.

---

## System Overview

**Vespa** = Search + Storage + ML Serving Platform

**Core Use Case**: Select subset of massive corpus (billions of docs), evaluate ML models, rank/aggregate results in <100ms, while corpus continuously changes.

**Three-Tier Architecture**:
- **Stateless Container (Java)**: jDisc framework for HTTP handling, query execution, document processing, component lifecycle
- **Content Nodes (C++)**: Distributed storage, indexing, matching, ranking on disk
- **Config System (Java)**: Centralized configuration generation/distribution, code generation from schemas

**Scale**: 147 modules organized as flat structure. Handles hundreds of thousands of queries/second in production.

---

## Principle 1: Configuration as Code Generation Schema

**Observed in:** `configdefinitions/`, `config-class-plugin/`, `config-model/`, `configserver/`, `config/`

### The Principle

**All system structure, component wiring, and topology flows from typed configuration definitions (.def files) that generate type-safe Java config classes, propagate through a versioned distribution system, and drive runtime component instantiation via dependency injection.**

Configuration is not key-value pairs or YAML. It's **typed schemas** that generate **code**, ensuring compile-time safety and runtime hot-swapping.

### How It Works

**Pipeline**:

```
1. Author .def file (config schema):
   package=vespa.config.search
   namespace=config

   rankingExpression[].name string
   rankingExpression[].expression string
   maxHitsPerNode int default=1000

2. configgen Maven plugin generates Java config class:
   RankingConfig extends ConfigInstance
   ├── getRankingExpression() → List<RankingExpression>
   ├── getMaxHitsPerNode() → int
   └── Nested RankingExpression class with getName(), getExpression()

3. config-model parses vespa-services.xml application package:
   <container>
     <search>
       <ranking-expression name="bm25">...</ranking-expression>
     </search>
   </container>

4. TreeConfigProducer generates ConfigInstance payloads:
   config-model traverses service tree, calls getConfig() on each producer
   → Serializes to binary config format with generation number

5. configserver distributes via JRT RPC:
   Nodes poll configserver for configs matching (ConfigKey, ConfigId)
   → Server pushes new generations when available

6. Components subscribe and reconstruct:
   ConfigSubscriber.subscribe(RankingConfig.class, "search/container.0")
   → Blocks until config available
   → DI framework injects config into component constructors
```

**Example from codebase**:

`configdefinitions/src/vespa/ranking-constants.def`:
```
namespace=vespa.config.search.core

constant[].name string
constant[].fileref reference
constant[].type string
```

Generated `RankingConstantsConfig.java` (in `target/generated-sources/`):
```java
public final class RankingConstantsConfig extends ConfigInstance {
    public List<Constant> constant() { ... }

    public static class Constant {
        public String name() { ... }
        public FileReference fileref() { ... }
        public String type() { ... }
    }
}
```

Component consumption (`container-search/src/main/java/.../RankProfilesEvaluator.java`):
```java
public class RankProfilesEvaluator {
    @Inject
    public RankProfilesEvaluator(RankingConstantsConfig config) {
        for (var constant : config.constant()) {
            loadConstant(constant.name(), constant.fileref());
        }
    }
}
```

**Files**:
- `config-class-plugin/src/main/java/com/yahoo/vespa/configdefinition/ConfigDefinitionClass.java` — Plugin orchestrator
- `config/src/main/java/com/yahoo/config/subscription/ConfigSubscriber.java:23-93` — Subscription API
- `config-lib/src/main/java/com/yahoo/config/ConfigInstance.java` — Base for all generated configs
- `configserver/src/main/java/com/yahoo/vespa/config/server/rpc/RpcServer.java` — Distribution server

### Why It Matters

**Maintainability**:
- Config changes = schema changes → Type errors caught at compile time
- No string-based config keys that break silently
- Generated code ensures consistency across Java/C++ boundary

**Extensibility**:
- New config types = add .def file → Auto-generates class
- Components declare config dependencies via constructor injection
- No centralized registry to update

**Hot Deployment**:
- Generation numbers enable atomic config updates
- Components poll for new generations
- Safe concurrent reads during updates (old generation still valid)

**Testability**:
- Config classes are POJOs — easy to mock
- Builder pattern for test config construction
- No need for config server in unit tests

### Application to IMEM

**Where**: `compile/Templates` plugin registration, `storage/` backend configuration, `manage/` intelligence layer config

**How**:
- **Schema Evolution as Config**: Define `.imem.def` files for chunk schemas, template registrations, storage backend configs
- **Code Generation**: Generate Python dataclasses/Pydantic models from .def → Type-safe chunk metadata
- **Template Registry**: Templates declare what they parse via config (not hardcoded registry)

**Example**:

```python
# Define: compile/schemas/chunk-schema.def
namespace=imem.compile

phase enum { design, designate, develop, document }
sectionType[] string
metadataFields[].name string
metadataFields[].type string

# Generated: compile/schemas/chunk_schema.py (via code generator)
from dataclasses import dataclass
from enum import Enum

class Phase(Enum):
    DESIGN = "design"
    DESIGNATE = "designate"
    DEVELOP = "develop"
    DOCUMENT = "document"

@dataclass
class ChunkSchema:
    phase: Phase
    section_types: List[str]
    metadata_fields: List[MetadataField]

# Usage: compile/observer.py
def observe_corpus(config: ChunkSchema):
    for section_type in config.section_types:
        discover_instances(section_type)
```

**Template Registration**:

```python
# Define: compile/templates/template-registry.def
template[].name string
template[].document_types[] string
template[].parser_class string
template[].schema_version int

# Generated config drives template loader:
class TemplateLoader:
    def __init__(self, config: TemplateRegistryConfig):
        for tmpl in config.templates:
            self.register(tmpl.name,
                         import_class(tmpl.parser_class),
                         tmpl.document_types)
```

**Storage Backend Config**:

```python
# Define: storage/backends.def
backend[].name string
backend[].type enum { sqlite, qdrant, neo4j }
backend[].connection_string string
backend[].capabilities[] enum { metadata, semantic, graph }

# Usage: retrieve/orchestrator.py
def select_backend(query_type: str, config: BackendsConfig):
    for backend in config.backends:
        if query_type in backend.capabilities:
            return get_backend(backend.name)
```

### Trade-offs

**Pros**:
- **Type safety across system** — Config errors caught early
- **Self-documenting** — .def files are the spec
- **Hot reload** — Update configs without code deploy
- **Cross-language consistency** — Java/C++ share same config definitions

**Cons**:
- **Tooling dependency** — Need code generator in build pipeline
- **Learning curve** — Developers must learn .def syntax
- **Generation overhead** — Adds build step (minimal in practice)
- **Schema migration** — Changing .def requires coordinated rollout

**Adoption Recommendation**: **Adapt**

Use for **template registry** and **storage backend configuration**, but leverage **Python metaprogramming** (Pydantic models with validators) instead of separate code generation step. Python's dynamic nature allows runtime schema validation that's equally type-safe without build complexity.

**Adapted Pattern**:
```python
# imem/compile/schemas.py
from pydantic import BaseModel, Field
from typing import List, Literal

class TemplateConfig(BaseModel):
    name: str
    document_types: List[str]
    parser_class: str
    schema_version: int = 1

    def load_parser(self):
        """Dynamic import based on config"""
        module, cls = self.parser_class.rsplit('.', 1)
        return getattr(__import__(module), cls)

# Templates defined in YAML/TOML (not .def), validated at load
templates = [
    TemplateConfig(
        name="changelog",
        document_types=["changelog", "release-notes"],
        parser_class="imem.compile.templates.ChangelogParser"
    )
]
```

---

## Principle 2: Dependency Injection via Constructor Inference

**Observed in:** `component/`, `container-core/`, `container-di/`

### The Principle

**Components declare dependencies through constructor parameters. The DI framework infers the dependency graph from constructor signatures, resolves configs by type, and constructs the component graph in topological order—all without explicit XML wiring or annotations.**

No `@Inject` spam. No XML beans. Constructor signature **is** the dependency declaration.

### How It Works

**Component Discovery & Graph Construction**:

```
1. Component Declaration (in services.xml):
   <searcher id="mySearcher" class="com.foo.MySearcher" bundle="my-bundle"/>

2. DI Framework Scans Constructor:
   public MySearcher(RankingConfig config, ComponentRegistry<Executor> executors)

3. ComponentNode Construction:
   - Identifies RankingConfig as config dependency (extends ConfigInstance)
   - Identifies ComponentRegistry<Executor> as component collection
   - Adds edges in dependency graph: MySearcher → RankingConfig, Executors

4. Graph Resolution:
   - Topological sort ensures configs loaded before components
   - Cycles detected and rejected
   - Missing dependencies fail fast with clear error

5. Instantiation:
   - ConfigSubscriber fetches RankingConfig
   - ComponentRegistry<Executor> injected from platform
   - Constructor invoked: new MySearcher(rankingConfig, executors)
```

**Constructor Selection Priority** (from `Searcher.java` javadoc):

```
1. (ComponentId, ...configs) — most specific
2. (String id, ...configs)
3. (...configs only)
4. (ComponentId only)
5. (String id only)
6. () — default constructor
```

Highest number of `ConfigInstance` parameters wins. This allows components to opt-in to configs without changing framework.

**Example from codebase**:

`container-core/src/main/java/com/yahoo/container/di/componentgraph/core/ComponentNode.java`:
```java
private void addConfigOrComponentDependency(Class<?> parameterType) {
    if (ConfigInstance.class.isAssignableFrom(parameterType)) {
        addConfigDependency(parameterType);  // Subscribe to config
    } else if (ComponentRegistry.class.isAssignableFrom(parameterType)) {
        addComponentRegistryDependency(parameterType);  // Inject collection
    } else {
        addComponentDependency(parameterType);  // Inject single component
    }
}
```

`container-search/src/main/java/com/yahoo/search/searchchain/model/federation/FederationSearcher.java`:
```java
@Inject
public FederationSearcher(FederationConfig config,
                          StrictContractsConfig strict) {
    // Config automatically subscribed and injected
    this.federationOptions = new FederationOptions(config);
    this.enforceStrictContracts = strict.enabled();
}
```

**Files**:
- `container-core/src/main/java/com/yahoo/container/di/componentgraph/core/ComponentGraph.java:47-100` — Graph construction
- `component/src/main/java/com/yahoo/component/ComponentId.java` — Component identity
- `container-core/src/main/java/com/yahoo/container/di/ConfigRetriever.java:26-80` — Config subscription management

### Why It Matters

**Maintainability**:
- Constructor **is** the contract — No hidden dependencies
- Refactoring safe — Change constructor, graph rebuilds
- No separate wiring file to update

**Extensibility**:
- Add new component → Declare constructor → Done
- No central registry update
- Framework discovers dependencies automatically

**Testability**:
- Mock configs in tests: `new MyComponent(mockConfig)`
- No DI framework needed in unit tests
- Integration tests can override specific configs

**Developer Experience**:
- **Discoverability**: IntelliJ autocompletes available configs
- **Type safety**: Wrong config type = compile error
- **Explicit**: Reading constructor tells you all dependencies

### Application to IMEM

**Where**: `compile/Templates`, `retrieve/Primitives`, `manage/` intelligence layers

**How**:
- **Template plugins** declare dependencies on `ChunkSchema`, `EntityResolver` via `__init__`
- **Retrieval primitives** (siblings, genealogy) inject `StorageBackend` interface
- **Intelligence layers** compose via dependency graph (Temporal depends on GitValidator, Registry)

**Example**:

```python
# imem/compile/templates/base.py
from abc import ABC, abstractmethod
from typing import Protocol

class ChunkSchema(Protocol):
    """Config interface for chunk structure"""
    def validate(self, chunk: dict) -> bool: ...

class EntityResolver(Protocol):
    """Normalize entities to canonical form"""
    def resolve(self, entity: str) -> str: ...

class TemplateParser(ABC):
    """Base for all template parsers"""

    def __init__(self,
                 schema: ChunkSchema,           # Config dependency
                 resolver: EntityResolver):     # Component dependency
        self.schema = schema
        self.resolver = resolver

    @abstractmethod
    def parse(self, content: str) -> List[Chunk]:
        pass

# imem/compile/templates/changelog.py
class ChangelogParser(TemplateParser):
    def __init__(self,
                 schema: ChunkSchema,
                 resolver: EntityResolver,
                 observer: PatternObserver):    # Additional dependency
        super().__init__(schema, resolver)
        self.observer = observer

    def parse(self, content: str) -> List[Chunk]:
        chunks = self._extract_chunks(content)
        for chunk in chunks:
            self.observer.record_pattern(chunk)  # Use injected dependency
        return chunks

# imem/compile/loader.py (DI framework)
from inspect import signature, Parameter
from typing import get_type_hints

class ComponentLoader:
    def __init__(self):
        self.instances = {}
        self.configs = {}

    def register_config(self, interface: type, instance: object):
        """Register config implementation"""
        self.configs[interface] = instance

    def load(self, component_class: type):
        """Construct component with dependency injection"""
        sig = signature(component_class.__init__)
        hints = get_type_hints(component_class.__init__)

        kwargs = {}
        for param_name, param in sig.parameters.items():
            if param_name == 'self':
                continue

            param_type = hints[param_name]

            # Check if it's a registered config
            if param_type in self.configs:
                kwargs[param_name] = self.configs[param_type]
            # Check if it's a component we can construct
            elif hasattr(param_type, '__init__'):
                kwargs[param_name] = self.load(param_type)  # Recursive
            else:
                raise ValueError(f"Cannot resolve {param_name}: {param_type}")

        return component_class(**kwargs)

# Usage:
loader = ComponentLoader()
loader.register_config(ChunkSchema, DefaultChunkSchema())
loader.register_config(EntityResolver, GitBasedResolver())

# Automatically resolves: ChangelogParser needs ChunkSchema, EntityResolver, PatternObserver
# PatternObserver needs ChunkSchema → loader constructs in correct order
parser = loader.load(ChangelogParser)
```

**Retrieval Primitive Injection**:

```python
# imem/retrieve/primitives/siblings.py
from imem.storage.interface import ChunkRetriever

class SiblingDiscovery:
    def __init__(self,
                 retriever: ChunkRetriever,      # Storage backend abstraction
                 ranker: AuthorityRanker):       # manage/ intelligence layer
        self.retriever = retriever
        self.ranker = ranker

    def discover(self, chunk_id: str, filters: dict) -> List[Chunk]:
        siblings = self.retriever.query(
            filters={'file_path': chunk_id.file_path, **filters}
        )
        return self.ranker.rank(siblings)

# Storage backend is swappable — SQLite vs Qdrant same interface
```

### Trade-offs

**Pros**:
- **Zero boilerplate** — No annotations, no XML
- **Constructor documents dependencies** — Self-documenting
- **Type-safe** — Python type hints enable static analysis
- **Testable** — Direct instantiation in tests

**Cons**:
- **Implicit framework** — Magic can be confusing to newcomers
- **Constructor signature limits** — Can't have optional dependencies easily
- **Circular dependencies** — Must be detected and rejected
- **Global state for singletons** — Need lifecycle management

**Adoption Recommendation**: **Adopt**

Python's **type hints** + **inspect module** make this pattern natural. Use **Protocol** for interfaces, **signature inspection** for dependency discovery.

---

## Principle 3: Plugin Chains as Composable Pipelines

**Observed in:** `container-search/`, `docproc/`, `processing/`

### The Principle

**Processing logic (queries, documents, generic data) flows through ordered chains of processors. Each processor in the chain can inspect, modify, or short-circuit the flow. Chains compose declaratively in config, not imperatively in code, enabling runtime reconfiguration without recompilation.**

Not middleware (HTTP-specific). Not inheritance (too rigid). **Composable processing chains** with explicit flow control.

### How It Works

**Chain Execution Model**:

```
Chain = [Processor1, Processor2, ..., ProcessorN]

Request → Chain.process(request)
  → Processor1.process(request, chain)
      → Modify request
      → chain.next().process(request, chain)  // Explicit pass to next
          → Processor2.process(request, chain)
              → ...
                  → ProcessorN.process(request, chain)
                      → Return result
              ← Result flows back
          ← Processor2 can modify result
      ← Processor1 can modify result
  ← Final result

Short-circuit:
  → Processor can return immediately without calling chain.next()
  → Useful for caching, auth failures, early termination
```

**Searcher Chain Example** (`container-search/src/main/java/com/yahoo/search/searchchain/SearchChain.java`):

```java
public class SearchChain extends Chain<Searcher> {
    public Result search(Query query, Execution execution) {
        return execution.search(query);  // Delegates to first searcher
    }
}

// Individual Searcher:
public abstract class Searcher {
    public Result search(Query query, Execution execution) {
        // Option 1: Modify and pass through
        query.addFilter("status:active");
        return execution.search(query);  // Next in chain

        // Option 2: Short-circuit
        if (cached(query)) {
            return getCachedResult(query);  // Skip rest of chain
        }

        // Option 3: Post-process results
        Result result = execution.search(query);
        result.hits().forEach(hit -> enrich(hit));
        return result;
    }
}
```

**Chain Composition** (in `services.xml`):

```xml
<container>
  <search>
    <chain id="default" inherits="vespa">
      <searcher id="cache" class="com.foo.CacheSearcher"/>
      <searcher id="rewriter" class="com.foo.QueryRewriter"/>
      <searcher id="filter" class="com.foo.FilterSearcher"/>
      <!-- federator: dispatches to backend (implicit) -->
    </chain>
  </search>
</container>
```

**Execution Order**: Config defines order → CacheSearcher → QueryRewriter → FilterSearcher → Backend

**Document Processing Chain** (`docproc/src/main/java/com/yahoo/docproc/DocumentProcessor.java:44-72`):

```java
public abstract class DocumentProcessor {
    public Progress process(Processing processing) {
        for (DocumentOperation op : processing.getDocumentOperations()) {
            // Modify documents before indexing
            if (op instanceof DocumentPut) {
                Document doc = ((DocumentPut) op).getDocument();
                processDocument(doc);
            }
        }
        return Progress.DONE;  // Or LATER (async), FAILED
    }
}
```

**Flow Control**:
- `Progress.DONE` → Continue to next processor
- `Progress.LATER` → Pause, resume after async op
- `Progress.FAILED` → Abort chain
- `return result` → Short-circuit

**Files**:
- `container-search/src/main/java/com/yahoo/search/Searcher.java:73-80` — Base searcher interface
- `processing/src/main/java/com/yahoo/processing/execution/Chain.java` — Generic chain executor
- `docproc/src/main/java/com/yahoo/docproc/Processing.java` — Document processing context

### Why It Matters

**Maintainability**:
- Each processor has single responsibility
- Easy to understand linear flow (even with branching)
- Modify one processor without touching others

**Extensibility**:
- Add processor → Insert in chain config → Done
- Remove processor → Delete from config
- No code changes to chain executor

**Reusability**:
- Same processor can appear in multiple chains
- Chains can inherit from base chains
- Generic processing framework (not search-specific)

**Runtime Reconfiguration**:
- Update chain order in config
- New config generation distributed
- Next request uses new chain (no restart)

### Application to IMEM

**Where**: `compile/` parsing stages, `retrieve/Orchestrator` multi-stage pipeline, `structure/` presentation chain

**How**:
- **Compilation chain**: Raw content → Template parser → Schema resolver → Entity normalizer → Observer → Storage
- **Retrieval chain**: Query → Search → Discovery (siblings, genealogy) → Graph (authority) → Contextualize → Render
- **Storage chain**: Chunk → Metadata extractor → Embedder → SQLite writer → Qdrant writer

**Example**:

```python
# imem/core/chain.py
from abc import ABC, abstractmethod
from typing import Generic, TypeVar, List, Optional
from dataclasses import dataclass

T = TypeVar('T')

class Processor(ABC, Generic[T]):
    """Base processor in a chain"""

    @abstractmethod
    def process(self, data: T, execution: 'Execution[T]') -> T:
        """Process data, optionally calling execution.next()"""
        pass

@dataclass
class Execution(Generic[T]):
    """Chain execution context"""
    chain: 'Chain[T]'
    index: int = 0

    def process(self, data: T) -> T:
        """Execute next processor in chain"""
        if self.index >= len(self.chain.processors):
            return data  # End of chain

        processor = self.chain.processors[self.index]
        next_execution = Execution(self.chain, self.index + 1)
        return processor.process(data, next_execution)

class Chain(Generic[T]):
    """Ordered chain of processors"""

    def __init__(self, processors: List[Processor[T]]):
        self.processors = processors

    def execute(self, data: T) -> T:
        """Execute full chain"""
        execution = Execution(self)
        return execution.process(data)

# imem/compile/processors.py
from imem.core.chain import Processor, Execution
from typing import Dict

@dataclass
class CompilationContext:
    """Data flowing through compilation chain"""
    raw_content: str
    metadata: Dict
    chunks: List[Dict]
    entities: Set[str]

class TemplateParser(Processor[CompilationContext]):
    def process(self, ctx: CompilationContext, exec: Execution) -> CompilationContext:
        # Extract chunks from raw content
        ctx.chunks = self.parse_template(ctx.raw_content)
        return exec.process(ctx)  # Pass to next processor

class SchemaResolver(Processor[CompilationContext]):
    def process(self, ctx: CompilationContext, exec: Execution) -> CompilationContext:
        # Map heterogeneous headers to canonical types
        for chunk in ctx.chunks:
            chunk['section_type'] = self.resolve_type(chunk['raw_type'])
        return exec.process(ctx)

class EntityNormalizer(Processor[CompilationContext]):
    def process(self, ctx: CompilationContext, exec: Execution) -> CompilationContext:
        # Normalize entity references
        for chunk in ctx.chunks:
            entities = self.extract_entities(chunk['content'])
            chunk['entities'] = [self.normalize(e) for e in entities]
            ctx.entities.update(chunk['entities'])
        return exec.process(ctx)

class PatternObserver(Processor[CompilationContext]):
    def process(self, ctx: CompilationContext, exec: Execution) -> CompilationContext:
        # Record patterns for schema evolution
        for chunk in ctx.chunks:
            self.observe_pattern(chunk)
        return exec.process(ctx)  # Continue even if observation fails

# Usage: imem/compile/pipeline.py
compilation_chain = Chain([
    TemplateParser(),
    SchemaResolver(),
    EntityNormalizer(),
    PatternObserver()
])

ctx = CompilationContext(raw_content=file_content, metadata={}, chunks=[], entities=set())
result = compilation_chain.execute(ctx)
# result.chunks ready for storage
```

**Retrieval Orchestrator Chain**:

```python
# imem/retrieve/processors.py
from imem.core.chain import Processor, Execution

@dataclass
class RetrievalContext:
    query: Dict
    results: List[Chunk]
    metadata: Dict

class SearchProcessor(Processor[RetrievalContext]):
    def __init__(self, retriever: ChunkRetriever):
        self.retriever = retriever

    def process(self, ctx: RetrievalContext, exec: Execution) -> RetrievalContext:
        # Initial search
        ctx.results = self.retriever.search(ctx.query['search'])
        return exec.process(ctx)

class SiblingDiscovery(Processor[RetrievalContext]):
    def process(self, ctx: RetrievalContext, exec: Execution) -> RetrievalContext:
        if 'discovery' not in ctx.query:
            return exec.process(ctx)  # Skip if not requested

        # Expand results with siblings
        expanded = []
        for chunk in ctx.results:
            siblings = self.find_siblings(chunk, ctx.query['discovery'])
            expanded.extend(siblings)
        ctx.results.extend(expanded)
        return exec.process(ctx)

class AuthorityRanker(Processor[RetrievalContext]):
    def process(self, ctx: RetrievalContext, exec: Execution) -> RetrievalContext:
        # Rank by authority (from manage/ layer)
        ctx.results.sort(key=lambda c: self.authority_score(c), reverse=True)
        return exec.process(ctx)

class ContextEnricher(Processor[RetrievalContext]):
    def process(self, ctx: RetrievalContext, exec: Execution) -> RetrievalContext:
        # Add graph metadata
        for chunk in ctx.results:
            chunk.metadata['position'] = self.temporal_position(chunk)
            chunk.metadata['authority'] = self.authority_score(chunk)
        return exec.process(ctx)

# Orchestrator uses chain
retrieval_chain = Chain([
    SearchProcessor(sqlite_retriever),
    SiblingDiscovery(),
    AuthorityRanker(),
    ContextEnricher()
])

ctx = RetrievalContext(query=user_query, results=[], metadata={})
result = retrieval_chain.execute(ctx)
# result.results contains enriched, ranked chunks
```

**Conditional Execution** (short-circuit):

```python
class CacheProcessor(Processor[RetrievalContext]):
    def process(self, ctx: RetrievalContext, exec: Execution) -> RetrievalContext:
        cache_key = hash_query(ctx.query)
        if cached := self.cache.get(cache_key):
            ctx.results = cached
            return ctx  # SHORT-CIRCUIT: Skip rest of chain

        # Cache miss: continue chain
        result = exec.process(ctx)
        self.cache.set(cache_key, result.results)
        return result
```

### Trade-offs

**Pros**:
- **Composability** — Mix/match processors freely
- **Declarative config** — Chain order in config, not code
- **Testability** — Test processors in isolation
- **Clear flow** — Easy to trace request path

**Cons**:
- **Implicit execution order** — Must read config to understand flow
- **Context object grows** — Can become bag of state
- **Error handling complexity** — Need consistent error propagation
- **Performance overhead** — Function call per processor (minimal in practice)

**Adoption Recommendation**: **Adopt**

Perfect fit for IMEM's **multi-stage pipelines**. Compilation has clear stages (parse → resolve → normalize → observe). Retrieval orchestrates search → discovery → ranking → enrichment. Chains make this explicit and reconfigurable.

---

## Principle 4: Generation-Based Configuration Hot-Swap

**Observed in:** `config/`, `configserver/`, `config-proxy/`

### The Principle

**Configuration changes propagate through a monotonically increasing generation number. Components poll for new generations, receive atomic snapshots of all related configs, and apply changes without restarts. The system supports concurrent use of multiple generations during rollout, ensuring zero-downtime reconfiguration.**

Not file watching. Not service restart. **Versioned configuration** with **atomic updates** and **graceful transition**.

### How It Works

**Generation Lifecycle**:

```
1. Developer deploys new application package to configserver:
   vespa-deploy prepare app/
   vespa-deploy activate

2. Configserver increments generation (e.g., 42 → 43):
   - Parses vespa-services.xml
   - Generates all ConfigInstance payloads
   - Stamps with generation=43
   - Stores in cache

3. Components poll via ConfigSubscriber:
   subscriber.nextConfig(timeout=60000)  // Blocks until new gen

   ConfigSubscriber sends:
     GET /config/v2/tenant/default/config/ranking-constants/search.container.0
     X-Current-Generation: 42

   Configserver responds:
     X-Vespa-Config-Generation: 43
     { "constant": [...] }  // New config payload

4. Component receives new generation:
   ConfigHandle.isChanged() → true if this specific config changed
   handle.getConfig() → New ConfigInstance for generation 43

5. Component applies changes:
   if (handle.isChanged()) {
       reloadModels(handle.getConfig());
   }

6. Multiple generations coexist during rollout:
   - Node A: Still using gen 42
   - Node B: Upgraded to gen 43
   - Both valid simultaneously
   - No coordination required

7. Old generation garbage collected after all nodes upgrade
```

**Atomic Config Sets** (`ConfigRetriever.java:26-80`):

```java
public class ConfigRetriever {
    private final ConfigSubscriber subscriber = new ConfigSubscriber();

    public ConfigSnapshot getConfigs() {
        // Subscribe to MULTIPLE configs
        ConfigHandle<RankingConfig> ranking =
            subscriber.subscribe(RankingConfig.class, configId);
        ConfigHandle<ClusterConfig> cluster =
            subscriber.subscribe(ClusterConfig.class, configId);

        // Wait for same generation across ALL configs
        if (!subscriber.nextGeneration(timeout)) {
            throw new TimeoutException();
        }

        // All configs guaranteed same generation
        return new ConfigSnapshot(
            ranking.getConfig(),
            cluster.getConfig(),
            subscriber.getGeneration()  // e.g., 43
        );
    }
}
```

**Why Atomic Sets Matter**:
- RankingConfig references model files
- ClusterConfig specifies node topology
- Both must change together (model + nodes)
- Generation ensures consistency

**Files**:
- `config/src/main/java/com/yahoo/config/subscription/ConfigSubscriber.java:23-93` — Subscription & polling
- `config/src/main/java/com/yahoo/config/subscription/ConfigHandle.java` — Per-config handle with isChanged()
- `configserver/src/main/java/com/yahoo/vespa/config/server/ApplicationRepository.java` — Generation management
- `config-proxy/src/main/java/com/yahoo/vespa/config/proxy/ConfigProxyRpcServer.java` — Node-local proxy for config caching

### Why It Matters

**Zero-Downtime Updates**:
- No restarts required for most config changes
- Old generation remains valid during transition
- Components apply changes when ready

**Consistency**:
- Atomic snapshots across related configs
- No partial updates (all-or-nothing)
- Generation number is global clock

**Rollback Safety**:
- Old generation still cached
- Rollback = revert to previous generation
- No state corruption from partial rollout

**Auditability**:
- Generation numbers track deployment history
- Can query "what config was active at generation X"
- Debugging: "This issue started at generation 47"

### Application to IMEM

**Where**: Template registry updates, storage backend config, schema evolution triggers

**How**:
- **Schema versions** — Each schema evolution gets version number
- **Template hot-reload** — Add new template without restart
- **Storage backend switching** — Atomic swap SQLite ↔ Qdrant

**Example**:

```python
# imem/core/config.py
from dataclasses import dataclass
from typing import Dict, Any, Optional
import threading
import time

@dataclass
class ConfigSnapshot:
    """Atomic snapshot of configs at specific generation"""
    generation: int
    configs: Dict[str, Any]
    timestamp: float

class ConfigSubscriber:
    """Subscribe to versioned configuration"""

    def __init__(self, config_source: str):
        self.config_source = config_source
        self.current_generation = 0
        self.handles: Dict[str, 'ConfigHandle'] = {}
        self._lock = threading.Lock()

    def subscribe(self, config_name: str, config_id: str) -> 'ConfigHandle':
        """Subscribe to a configuration"""
        handle = ConfigHandle(config_name, config_id, self)
        self.handles[config_name] = handle
        return handle

    def next_generation(self, timeout: float = 60.0) -> bool:
        """Block until new generation available"""
        start = time.time()
        while time.time() - start < timeout:
            snapshot = self._fetch_snapshot()
            if snapshot.generation > self.current_generation:
                with self._lock:
                    self.current_generation = snapshot.generation
                    for name, config in snapshot.configs.items():
                        if name in self.handles:
                            self.handles[name]._update(config, snapshot.generation)
                return True
            time.sleep(1.0)
        return False

    def _fetch_snapshot(self) -> ConfigSnapshot:
        """Fetch configs from source (file, server, etc)"""
        # In production: HTTP GET to configserver
        # Returns configs stamped with same generation
        ...

class ConfigHandle:
    """Handle to a specific configuration subscription"""

    def __init__(self, name: str, config_id: str, subscriber: ConfigSubscriber):
        self.name = name
        self.config_id = config_id
        self._subscriber = subscriber
        self._config: Optional[Any] = None
        self._generation: int = 0
        self._changed: bool = False

    def _update(self, config: Any, generation: int):
        """Internal: Update from subscriber"""
        if generation > self._generation:
            self._config = config
            self._generation = generation
            self._changed = True

    def is_changed(self) -> bool:
        """Check if config changed since last get_config()"""
        return self._changed

    def get_config(self) -> Any:
        """Get current config and mark as seen"""
        self._changed = False
        return self._config

# imem/compile/template_loader.py
class TemplateRegistry:
    """Hot-reloadable template registry"""

    def __init__(self, config_subscriber: ConfigSubscriber):
        self.subscriber = config_subscriber
        self.templates: Dict[str, TemplateParser] = {}

        # Subscribe to template config
        self.template_handle = subscriber.subscribe(
            "template-registry",
            "compile"
        )

        # Start background polling
        self._start_polling()

    def _start_polling(self):
        """Background thread polls for config changes"""
        def poll():
            while True:
                if self.subscriber.next_generation(timeout=60.0):
                    self._reload_if_changed()

        threading.Thread(target=poll, daemon=True).start()

    def _reload_if_changed(self):
        """Reload templates if config changed"""
        if self.template_handle.is_changed():
            config = self.template_handle.get_config()

            print(f"Template config changed (gen {self.subscriber.current_generation})")

            # Atomic update: Build new registry
            new_templates = {}
            for tmpl in config['templates']:
                parser_class = self._load_class(tmpl['parser_class'])
                new_templates[tmpl['name']] = parser_class()

            # Swap (atomic in Python due to GIL)
            self.templates = new_templates

            print(f"Loaded {len(new_templates)} templates")

    def get_parser(self, name: str) -> Optional[TemplateParser]:
        """Get template parser (thread-safe read)"""
        return self.templates.get(name)

# Usage:
subscriber = ConfigSubscriber(config_source="file://config/")
registry = TemplateRegistry(subscriber)

# Later: Update config/template-registry.yaml → generation incremented
# Background thread detects change → reloads templates
# Next parse() call uses new templates (no restart)
```

**Schema Evolution with Generations**:

```python
# imem/compile/schema_manager.py
class SchemaManager:
    """Manage schema evolution with versions"""

    def __init__(self, subscriber: ConfigSubscriber):
        self.subscriber = subscriber
        self.schema_handle = subscriber.subscribe("chunk-schema", "compile")
        self.current_schema: Optional[ChunkSchema] = None
        self.schema_version: int = 0

    def get_schema(self) -> ChunkSchema:
        """Get current schema, reload if changed"""
        if self.schema_handle.is_changed():
            config = self.schema_handle.get_config()
            self.current_schema = ChunkSchema.from_config(config)
            self.schema_version = config['version']

            print(f"Schema evolved to version {self.schema_version}")

            # Trigger migration if needed
            if self.schema_version > self._last_indexed_version():
                self._migrate_indexed_data(self.schema_version)

        return self.current_schema
```

**Storage Backend Atomic Switch**:

```python
# imem/storage/backend_manager.py
class BackendManager:
    """Atomic storage backend switching"""

    def __init__(self, subscriber: ConfigSubscriber):
        self.subscriber = subscriber
        self.backend_handle = subscriber.subscribe("storage-backends", "storage")

        self.active_backend: Optional[ChunkRetriever] = None
        self._reload_if_changed()

    def _reload_if_changed(self):
        if self.backend_handle.is_changed():
            config = self.backend_handle.get_config()

            # Atomic backend switch
            new_backend = self._construct_backend(config['active_backend'])

            # Swap (reads in-flight use old backend, new reads use new)
            self.active_backend = new_backend

            print(f"Switched to {config['active_backend']} backend")

    def get_backend(self) -> ChunkRetriever:
        self._reload_if_changed()  # Check on each access
        return self.active_backend
```

### Trade-offs

**Pros**:
- **Zero-downtime updates** — No restarts needed
- **Atomic consistency** — All configs same generation
- **Rollback safety** — Previous generation cached
- **Auditability** — Version history tracked

**Cons**:
- **Polling overhead** — Background threads poll for changes
- **Memory overhead** — Multiple generations cached
- **Complexity** — Requires config distribution infrastructure
- **Migration coordination** — Breaking schema changes need careful rollout

**Adoption Recommendation**: **Adapt**

For IMEM: Use **file-based config with mtime polling** instead of separate configserver. Templates/schemas defined in **YAML/TOML**, watched for changes. Simpler than full Vespa config system, retains hot-reload benefit.

**Simplified Pattern**:
```python
# Watch config file mtime, reload on change
# Increment internal generation on each reload
# ConfigHandle.is_changed() based on generation
# No separate server needed
```

---

## Principle 5: Language Boundary via Shared Serialization

**Observed in:** `document/`, `documentapi/`, `jrt/`, `messagebus/`

### The Principle

**Java and C++ subsystems communicate through language-agnostic serialized messages, never direct FFI or linking. Shared document models are defined once (in schema) and implemented identically in both languages. RPC transport (JRT) handles marshaling. This enables independent evolution of Java container and C++ storage layers.**

No JNI. No shared libraries. **Serialization boundary** with **protocol versioning**.

### How It Works

**Document Model Duality**:

```
Schema Definition (vespa-services.xml):
  <document type="product">
    <field name="title" type="string"/>
    <field name="price" type="double"/>
    <field name="embedding" type="tensor<float>(x[384])"/>
  </document>

Java Implementation:
  com.yahoo.document.Document (Java)
  ├── DocumentType type
  ├── DocumentId id
  ├── Map<String, FieldValue> fields
  └── serialize() → byte[]

C++ Implementation:
  document::Document (C++)
  ├── DocumentType& type
  ├── DocumentId id
  ├── map<string, FieldValue::UP> fields
  └── serialize() → vespalib::nbostream

Identical Binary Format:
  Both serialize to same byte stream
  → Java can write, C++ can read (and vice versa)
```

**RPC Communication** (`jrt/` module):

```
Java Container (Searcher):
  Query query = new Query("laptop");

  → JRT encodes query as RPC call:
    Method: "search"
    Params: {queryString: "laptop", hits: 10, timeout: 5000}

  → RPC over TCP to C++ content node

C++ Content Node (Proton):
  ← Receives RPC call, decodes params
  ← Executes search against indices
  ← Serializes results: List<DocumentSummary>
  → RPC reply with byte stream

Java Container:
  ← Receives reply
  ← Deserializes into Result object
  ← Returns to user
```

**MessageBus Pattern** (document operations):

```
Java (Container):
  DocumentPut put = new DocumentPut(document);
  bus.send(put, route="storage/cluster.storage");

MessageBus:
  - Serializes DocumentPut → byte[]
  - Routes based on document ID hash → node
  - Sends async message

C++ (Storage):
  - Receives byte[]
  - Deserializes → document::DocumentPut
  - Indexes document
  - Sends Reply

Java:
  - Receives Reply
  - Async callback invoked
```

**Files**:
- `document/src/main/java/com/yahoo/document/Document.java` — Java document model
- `document/src/vespa/document/base/document.h` — C++ document model (parallel structure)
- `jrt/src/com/yahoo/jrt/` — Java RPC transport
- `messagebus/src/vespa/messagebus/` — Async messaging framework

### Why It Matters

**Independent Evolution**:
- Java container can upgrade without C++ recompile
- C++ storage can optimize without Java changes
- Protocol versioning handles compatibility

**Language Freedom**:
- Use Java for HTTP/component framework (ecosystem)
- Use C++ for indexing/matching (performance)
- No compromise on either

**Clean Boundaries**:
- No shared memory bugs
- No JNI crashes
- Process isolation enforced

**Testability**:
- Mock RPC endpoints in tests
- No need to link C++ in Java tests
- Serialization is the contract

### Application to IMEM

**Where**: Potential future C++/Rust components for performance (embeddings, graph algorithms)

**How**:
- **Not immediately needed** — IMEM is pure Python for now
- **Future-proofing**: If we add Rust module for graph computation, use **MessagePack/Protocol Buffers** serialization
- **Storage abstraction already provides boundary** — SQLite/Qdrant are separate processes

**Example (Future)**:

```python
# If IMEM adds Rust component for fast graph algorithms:

# Python side (imem/retrieve/graph.py)
import msgpack
import socket

class GraphAlgorithm:
    def __init__(self, rust_service_addr: str):
        self.addr = rust_service_addr

    def pagerank(self, edges: List[Tuple[str, str]]) -> Dict[str, float]:
        # Serialize request
        request = msgpack.packb({
            'method': 'pagerank',
            'edges': edges,
            'damping': 0.85
        })

        # RPC call to Rust service
        sock = socket.socket()
        sock.connect(self.addr)
        sock.send(request)
        response = sock.recv(4096)
        sock.close()

        # Deserialize response
        result = msgpack.unpackb(response)
        return result['scores']

# Rust side (separate binary)
// graph_service/src/main.rs
use rmp_serde::{Deserializer, Serializer};
use serde::{Deserialize, Serialize};

#[derive(Deserialize)]
struct PageRankRequest {
    edges: Vec<(String, String)>,
    damping: f64,
}

#[derive(Serialize)]
struct PageRankResponse {
    scores: HashMap<String, f64>,
}

fn handle_request(request_bytes: &[u8]) -> Vec<u8> {
    let request: PageRankRequest = rmp_serde::from_slice(request_bytes).unwrap();

    // Fast graph algorithm in Rust
    let scores = compute_pagerank(&request.edges, request.damping);

    let response = PageRankResponse { scores };
    rmp_serde::to_vec(&response).unwrap()
}
```

**Current Approach (Python-only)**:

IMEM doesn't need this pattern yet. SQLite/Qdrant already provide serialization boundaries (SQL/HTTP). Pattern is **reserved for future performance optimization** if needed.

### Trade-offs

**Pros**:
- **Clean language boundaries** — No JNI complexity
- **Independent deployment** — Java/C++ services separate
- **Crash isolation** — Process crash doesn't affect other language
- **Protocol versioning** — Backward compatibility easier

**Cons**:
- **Serialization overhead** — Copy/marshal cost (mitigated by binary formats)
- **Latency** — Network hop vs in-memory (mitigated by localhost RPC)
- **Debugging** — Cross-process harder to debug
- **Data model duplication** — Must implement same structure in both languages

**Adoption Recommendation**: **Consider**

Not needed for current IMEM (pure Python). But **storage backends already provide this boundary** (SQLite/Qdrant communicate via SQL/HTTP, not Python FFI). Pattern is correct if we ever add native components.

---

## Principle 6: Config-Driven Component Discovery (No Central Registry)

**Observed in:** `component/`, `container-core/src/main/java/com/yahoo/container/di/`

### The Principle

**Components are discovered and wired via config, not registered in code. No central ComponentRegistry that components must import. Instead, config declares what exists, DI framework constructs dependency graph, and components lookup dependencies via injected registries. Adding a component requires only config change, never touching framework code.**

No `ComponentRegistry.register(this)` in constructor. No static registration blocks. **Config declares existence**, framework does the rest.

### How It Works

**Component Declaration Flow**:

```
1. Component Implementation (no registration code):
   package com.foo;
   public class CustomSearcher extends Searcher {
       public CustomSearcher(RankingConfig config) {
           // Just use dependencies, no registration
       }
   }

2. Config Declaration (services.xml):
   <container>
     <search>
       <searcher id="custom" class="com.foo.CustomSearcher" bundle="my-bundle"/>
     </search>
   </container>

3. Config Model Generates components.cfg:
   components[0].id "custom"
   components[0].classId "com.foo.CustomSearcher"
   components[0].bundle "my-bundle"
   components[0].configId "custom"

4. DI Framework Reads components.cfg:
   - Loads bundle my-bundle
   - Reflects on com.foo.CustomSearcher constructor
   - Discovers RankingConfig dependency
   - Subscribes to ranking.cfg with configId="custom"

5. ComponentGraph Construction:
   - Adds ComponentNode for CustomSearcher
   - Adds ConfigNode for RankingConfig
   - Adds edge: CustomSearcher depends on RankingConfig
   - Topological sort determines construction order

6. Instantiation:
   - RankingConfig fetched from configserver
   - CustomSearcher constructed: new CustomSearcher(rankingConfig)
   - Added to SearchChainRegistry (automatically)

7. Runtime Lookup (if needed):
   public class OtherSearcher extends Searcher {
       @Inject
       public OtherSearcher(ComponentRegistry<Searcher> searchers) {
           // Can lookup custom searcher by ID
           Searcher custom = searchers.getComponent("custom");
       }
   }
```

**Key Pattern**: **Component doesn't register itself, config registers it.**

**ComponentRegistry Injection** (`component/src/main/java/com/yahoo/component/provider/ComponentRegistry.java`):

```java
// Components that need to discover others inject ComponentRegistry
public class FederationSearcher extends Searcher {
    private final Map<String, Searcher> sources;

    @Inject
    public FederationSearcher(ComponentRegistry<Searcher> allSearchers,
                              FederationConfig config) {
        // Lookup searchers by ID from config
        this.sources = new HashMap<>();
        for (var source : config.sources()) {
            Searcher searcher = allSearchers.getComponent(source.id());
            sources.put(source.name(), searcher);
        }
    }
}
```

**Registry is injected, not imported**. Component never calls `static Registry.getInstance()`.

**Files**:
- `container-core/src/main/java/com/yahoo/container/di/componentgraph/core/ComponentGraph.java:47-100` — Graph construction from config
- `component/src/main/java/com/yahoo/component/provider/ComponentRegistry.java` — Generic registry (injected)
- `container-core/src/main/java/com/yahoo/container/di/Container.java:1-102` — Orchestrates config → graph → instantiation

### Why It Matters

**Extensibility**:
- Add component → Edit config → Deploy
- No code changes to framework
- No recompilation of core

**Decoupling**:
- Components don't depend on framework registration APIs
- Framework doesn't depend on component implementations
- Config is the only contract

**Testability**:
- Instantiate components directly in tests (no framework)
- Mock ComponentRegistry for lookup tests
- No global state to reset between tests

**Dynamic Reconfiguration**:
- Config change → New component graph built
- Old components garbage collected
- Hot-swappable components (when possible)

### Application to IMEM

**Where**: Template registration, storage backend discovery, retrieval primitive composition

**How**:
- **Templates declared in config**, not hardcoded imports
- **Storage backends declared in config**, retrieved via registry
- **Retrieval primitives discovered** from config (enable/disable features)

**Example**:

```python
# imem/core/registry.py
from typing import Dict, TypeVar, Generic, Optional, Type

T = TypeVar('T')

class ComponentRegistry(Generic[T]):
    """Generic component registry (injected, not global)"""

    def __init__(self):
        self._components: Dict[str, T] = {}

    def register(self, component_id: str, component: T):
        """Internal: Called by framework, not components"""
        self._components[component_id] = component

    def get(self, component_id: str) -> Optional[T]:
        """Lookup component by ID"""
        return self._components.get(component_id)

    def all(self) -> Dict[str, T]:
        """Get all components"""
        return self._components.copy()

# imem/compile/template_loader.py (framework side)
from imem.core.registry import ComponentRegistry

class TemplateLoader:
    """Builds template registry from config"""

    def __init__(self, config: TemplateConfig):
        self.registry = ComponentRegistry[TemplateParser]()
        self._load_from_config(config)

    def _load_from_config(self, config: TemplateConfig):
        """Read config, instantiate templates, populate registry"""
        for tmpl_def in config.templates:
            # Load class
            parser_class = self._import_class(tmpl_def.parser_class)

            # Instantiate (DI resolves dependencies)
            parser = self._instantiate(parser_class, tmpl_def.config)

            # Register (framework does this, not component)
            self.registry.register(tmpl_def.name, parser)

    def get_registry(self) -> ComponentRegistry[TemplateParser]:
        """Expose registry for injection into other components"""
        return self.registry

# imem/compile/multi_template_parser.py (component side)
class MultiTemplateParser:
    """Component that uses multiple templates"""

    def __init__(self,
                 template_registry: ComponentRegistry[TemplateParser],
                 config: MultiTemplateConfig):
        self.templates = template_registry  # INJECTED, not global
        self.config = config

    def parse(self, file_path: str, content: str) -> List[Chunk]:
        """Select template based on file type"""
        file_type = self._detect_type(file_path)

        # Lookup template by ID (from injected registry)
        template_id = self.config.type_mappings[file_type]
        parser = self.templates.get(template_id)

        if not parser:
            raise ValueError(f"No parser for {file_type}")

        return parser.parse(content)

# Config-driven (templates.yaml):
templates:
  - name: changelog
    parser_class: imem.compile.templates.ChangelogParser
    document_types: [changelog, release-notes]

  - name: conversation
    parser_class: imem.compile.templates.ConversationParser
    document_types: [jsonl, claude-conv]

type_mappings:
  changelog: changelog
  release-notes: changelog
  .jsonl: conversation

# Framework wiring (done once, in main):
config = load_config('templates.yaml')
loader = TemplateLoader(config)
registry = loader.get_registry()  # Contains all templates

# Inject registry into components that need it
multi_parser = MultiTemplateParser(registry, config)

# Component NEVER does: TemplateRegistry.register(self)
```

**Storage Backend Discovery**:

```python
# imem/storage/backend_loader.py
class BackendLoader:
    """Load storage backends from config"""

    def __init__(self, config: BackendConfig):
        self.registry = ComponentRegistry[ChunkRetriever]()

        for backend_def in config.backends:
            backend_class = self._import_class(backend_def.implementation)
            backend = backend_class(backend_def.connection_string)

            # Framework registers, not backend
            self.registry.register(backend_def.name, backend)

    def get_registry(self) -> ComponentRegistry[ChunkRetriever]:
        return self.registry

# imem/retrieve/orchestrator.py
class RetrievalOrchestrator:
    """Uses storage backends without knowing which ones exist"""

    def __init__(self,
                 backends: ComponentRegistry[ChunkRetriever],
                 config: OrchestratorConfig):
        self.backends = backends  # Injected
        self.config = config

    def search(self, query: Dict) -> List[Chunk]:
        # Config specifies which backend to use for this query type
        backend_id = self.config.query_routing[query['type']]
        backend = self.backends.get(backend_id)

        return backend.search(query)

# Config (storage-backends.yaml):
backends:
  - name: sqlite
    implementation: imem.storage.SQLiteRetriever
    connection_string: chunks.db
    capabilities: [metadata, relational]

  - name: qdrant
    implementation: imem.storage.QdrantRetriever
    connection_string: http://localhost:6333
    capabilities: [semantic, vector]

query_routing:
  metadata: sqlite
  semantic: qdrant
  hybrid: sqlite  # Query sqlite first, then qdrant

# Adding new backend = edit config, no code changes
```

### Trade-offs

**Pros**:
- **Zero framework coupling** — Components don't import framework
- **Config-driven discovery** — All wiring external to code
- **Easy testing** — Direct instantiation, no global state
- **Hot-swappable** — Change config, reload components

**Cons**:
- **Indirection** — Must read config to understand what's loaded
- **Runtime errors** — Missing component → runtime exception (not compile error)
- **Config complexity** — Large systems have large configs
- **Discovery overhead** — Registry lookup vs direct import

**Adoption Recommendation**: **Adopt**

Perfect for IMEM's **template plugin architecture**. Templates should be discovered from config, not hardcoded. Storage backends too. Keeps `compile/`, `storage/`, `retrieve/` layers decoupled.

---

## Synthesis: Implications for IMEM

### Recommended Structural Changes

1. **Adopt Config-Driven Template Registry**
   - Templates declared in `compile/templates.yaml`
   - Loader builds `ComponentRegistry[TemplateParser]` from config
   - `MultiTemplateParser` injects registry, looks up by document type
   - **Enables**: Add new document type without touching code

2. **Implement Processor Chains for Pipelines**
   - **Compilation**: `Chain[CompilationContext]` with stages: Parse → Resolve → Normalize → Observe
   - **Retrieval**: `Chain[RetrievalContext]` with stages: Search → Discovery → Ranking → Enrichment
   - Each processor single-responsibility, testable in isolation
   - **Enables**: Reorder stages, skip optional stages, A/B test processors

3. **Version Chunk Schemas with Generations**
   - Schema changes increment version number (like Vespa generations)
   - Components poll for schema changes
   - Triggers migration when version bumps
   - **Enables**: Schema evolution without breaking existing chunks

4. **Storage Backend as Injected Registry**
   - `BackendRegistry[ChunkRetriever]` injected into orchestrator
   - Config specifies routing (metadata → SQLite, semantic → Qdrant)
   - **Enables**: Add Neo4j backend without changing retrieval logic

5. **Dependency Injection via Constructor Inspection**
   - Components declare dependencies in `__init__` signature
   - Framework uses `inspect.signature()` to resolve
   - Type hints drive DI (Python's equivalent to Vespa's ConfigInstance detection)
   - **Enables**: Clean component boundaries, easy testing

6. **Separate Config from Code**
   - `compile/config/`, `storage/config/`, `retrieve/config/` directories
   - Pydantic models validate config at load time
   - Hot-reload on config file changes (mtime polling)
   - **Enables**: Adjust behavior without code deploy

---

### Directory Structure Implications

```
imem/
├── core/                          # Framework (like Vespa's component/)
│   ├── chain.py                   # Processor chain executor
│   ├── registry.py                # ComponentRegistry[T]
│   ├── config.py                  # Config subscription (generation-based)
│   └── di.py                      # Dependency injection framework
│
├── compile/                       # Parse heterogeneous → canonical chunks
│   ├── config/
│   │   ├── templates.yaml         # Template registry config
│   │   └── schemas.yaml           # Chunk schema definitions
│   ├── templates/                 # Template plugins (like Vespa bundles)
│   │   ├── base.py                # TemplateParser interface
│   │   ├── changelog.py           # ChangelogParser(TemplateParser)
│   │   ├── conversation.py        # ConversationParser(TemplateParser)
│   │   └── __init__.py            # Exports
│   ├── processors/                # Compilation chain processors
│   │   ├── parser.py              # TemplateParser processor
│   │   ├── resolver.py            # SchemaResolver processor
│   │   ├── normalizer.py          # EntityNormalizer processor
│   │   └── observer.py            # PatternObserver processor
│   ├── loader.py                  # TemplateLoader (builds registry from config)
│   ├── pipeline.py                # Compilation chain orchestrator
│   └── __init__.py
│
├── manage/                        # Intelligence layers
│   ├── config/
│   │   └── resolvers.yaml         # Entity resolver configs
│   ├── temporal.py                # Git validation (depends on GitValidator)
│   ├── resolver.py                # Entity resolution (injected into templates)
│   ├── registry.py                # Cross-project tier 1
│   ├── qualification.py           # Cross-project tier 2
│   └── __init__.py
│
├── retrieve/                      # Query orchestration
│   ├── config/
│   │   ├── orchestrator.yaml      # Query routing config
│   │   └── primitives.yaml        # Discovery primitive config
│   ├── primitives/                # Discovery operations
│   │   ├── siblings.py            # SiblingDiscovery(Processor)
│   │   ├── genealogy.py           # GenealogyDiscovery(Processor)
│   │   └── temporal.py            # TemporalDiscovery(Processor)
│   ├── processors/                # Retrieval chain processors
│   │   ├── search.py              # SearchProcessor
│   │   ├── discovery.py           # DiscoveryProcessor (composes primitives)
│   │   ├── ranking.py             # AuthorityRanker
│   │   └── enrichment.py          # ContextEnricher
│   ├── orchestrator.py            # Retrieval chain orchestrator
│   └── __init__.py
│
├── structure/                     # Post-retrieval enrichment
│   ├── config/
│   │   └── templates.yaml         # Jinja2 template configs
│   ├── templates/                 # Presentation templates
│   ├── contextualize.py           # Add graph metadata
│   ├── render.py                  # Format output
│   └── __init__.py
│
├── storage/                       # Backend adapters
│   ├── config/
│   │   └── backends.yaml          # Backend registry config
│   ├── interface.py               # ChunkRetriever protocol
│   ├── sqlite.py                  # SQLiteRetriever(ChunkRetriever)
│   ├── qdrant.py                  # QdrantRetriever(ChunkRetriever)
│   ├── loader.py                  # BackendLoader (builds registry from config)
│   └── __init__.py
│
└── cli/                           # CLI entry points
    ├── compile.py                 # imem compile
    ├── compose.py                 # imem compose
    └── __init__.py
```

**Key Changes from Current Structure**:

1. **Added `core/`** — Framework code extracted (chain, registry, DI)
2. **Config directories** — Separate config from code (`compile/config/`, etc)
3. **Processors organized** — `compile/processors/`, `retrieve/processors/`
4. **Loaders explicit** — `TemplateLoader`, `BackendLoader` own registry construction
5. **Interfaces explicit** — `storage/interface.py`, `compile/templates/base.py`

---

### Key Interfaces to Define

#### 1. ChunkRetriever (Storage Abstraction)

```python
# storage/interface.py
from typing import Protocol, List, Dict, Any

class ChunkRetriever(Protocol):
    """Storage backend interface (like Vespa's Retriever)"""

    def search(self, query: Dict[str, Any]) -> List[Chunk]:
        """Execute search query, return chunks"""
        ...

    def get(self, chunk_id: str) -> Optional[Chunk]:
        """Retrieve single chunk by ID"""
        ...

    def store(self, chunks: List[Chunk]) -> None:
        """Store chunks in backend"""
        ...

    def capabilities(self) -> List[str]:
        """Declare what query types supported (metadata, semantic, graph)"""
        ...
```

**Why**: Like Vespa's separation of query execution from storage, this allows SQLite/Qdrant/Neo4j to be swappable.

#### 2. TemplateParser (Compilation Extension)

```python
# compile/templates/base.py
from abc import ABC, abstractmethod
from typing import List

class TemplateParser(ABC):
    """Base for all template parsers (like Vespa's Searcher/DocumentProcessor)"""

    @abstractmethod
    def can_parse(self, file_path: str, content: str) -> bool:
        """Check if this parser handles the file"""
        ...

    @abstractmethod
    def parse(self, content: str, metadata: Dict) -> List[Chunk]:
        """Extract chunks from content"""
        ...

    @abstractmethod
    def document_types(self) -> List[str]:
        """Declare what document types this parses"""
        ...
```

**Why**: Like Vespa's plugin chains, this enables declarative template composition.

#### 3. Processor[T] (Chain Processing)

```python
# core/chain.py
from abc import ABC, abstractmethod
from typing import TypeVar, Generic

T = TypeVar('T')

class Processor(ABC, Generic[T]):
    """Base for all chain processors (like Vespa's Chain<T>)"""

    @abstractmethod
    def process(self, data: T, execution: 'Execution[T]') -> T:
        """Process data, optionally calling execution.next()"""
        ...
```

**Why**: Like Vespa's Searcher/DocumentProcessor chains, enables composable pipelines.

#### 4. EntityResolver (Normalization)

```python
# manage/interface.py
from typing import Protocol

class EntityResolver(Protocol):
    """Normalize entity variations to canonical form"""

    def resolve(self, entity: str, context: Dict) -> str:
        """Normalize entity (e.g., 'JWT' → 'jwt')"""
        ...

    def learn(self, entities: List[str]) -> None:
        """Observe new entities for schema evolution"""
        ...
```

**Why**: Like Vespa's schema evolution, separates normalization from parsing.

#### 5. ChunkSchema (Validation)

```python
# compile/interface.py
from typing import Protocol

class ChunkSchema(Protocol):
    """Chunk schema validator (like Vespa's ConfigInstance)"""

    def validate(self, chunk: Dict) -> bool:
        """Check if chunk conforms to schema"""
        ...

    def required_fields(self) -> List[str]:
        """Declare required metadata fields"""
        ...

    def version(self) -> int:
        """Schema version (for migration)"""
        ...
```

**Why**: Like Vespa's typed configs, ensures chunk consistency across system.

---

### Extension Points to Establish

#### 1. Template Plugin System

**Location**: `compile/templates/`

**How to Extend**:
```python
# User creates: my_project/custom_templates/jira.py
from imem.compile.templates import TemplateParser

class JiraParser(TemplateParser):
    def can_parse(self, file_path, content):
        return 'JIRA-' in content

    def parse(self, content, metadata):
        # Custom parsing logic
        return chunks

# User adds to config: compile/config/templates.yaml
templates:
  - name: jira
    parser_class: my_project.custom_templates.JiraParser
    document_types: [jira-ticket, jira-comment]
```

**No code changes to IMEM core**. Framework discovers via config.

#### 2. Storage Backend Plugin

**Location**: `storage/`

**How to Extend**:
```python
# User creates: my_project/backends/neo4j.py
from imem.storage.interface import ChunkRetriever

class Neo4jRetriever(ChunkRetriever):
    def search(self, query):
        # Cypher query execution
        ...

    def capabilities(self):
        return ['graph', 'traversal']

# User adds to config: storage/config/backends.yaml
backends:
  - name: neo4j
    implementation: my_project.backends.Neo4jRetriever
    connection_string: bolt://localhost:7687
    capabilities: [graph]

query_routing:
  graph: neo4j  # Route graph queries to Neo4j
```

#### 3. Retrieval Primitive Plugin

**Location**: `retrieve/primitives/`

**How to Extend**:
```python
# User creates: my_project/primitives/citations.py
from imem.core.chain import Processor

class CitationDiscovery(Processor[RetrievalContext]):
    def process(self, ctx, execution):
        # Find chunks that cite current results
        for chunk in ctx.results:
            citations = self.find_citations(chunk)
            ctx.results.extend(citations)
        return execution.process(ctx)

# User adds to retrieval chain:
retrieval_chain = Chain([
    SearchProcessor(backend),
    CitationDiscovery(),  # Custom primitive
    AuthorityRanker()
])
```

#### 4. Intelligence Layer Plugin

**Location**: `manage/`

**How to Extend**:
```python
# User creates: my_project/intelligence/code_analysis.py
from imem.manage.interface import IntelligenceLayer

class CodeAnalysisLayer(IntelligenceLayer):
    def enrich(self, chunks):
        # Add code complexity metrics
        for chunk in chunks:
            if chunk.metadata['type'] == 'code':
                chunk.metadata['complexity'] = self.analyze(chunk.content)
        return chunks

# Injected into compilation chain:
compilation_chain = Chain([
    TemplateParser(),
    SchemaResolver(),
    EntityNormalizer(),
    CodeAnalysisLayer(),  # Custom intelligence
    PatternObserver()
])
```

---

## Summary Table

| Principle | Impact on IMEM | Adoption | Priority |
|-----------|----------------|----------|----------|
| **Config as Code Generation Schema** | Template registry, schema versioning, backend config via typed definitions. Adapt to Pydantic models instead of .def files. | **Adapt** | **High** |
| **DI via Constructor Inference** | Clean component boundaries, testable in isolation. Use Python type hints + inspect for dependency resolution. | **Adopt** | **High** |
| **Plugin Chains** | Compilation pipeline (parse→resolve→normalize), retrieval pipeline (search→discovery→rank). Critical for compose architecture. | **Adopt** | **Critical** |
| **Generation-Based Hot-Swap** | Schema evolution versioning, template hot-reload. Adapt to file mtime polling instead of separate configserver. | **Adapt** | **Medium** |
| **Language Boundary via Serialization** | Not needed now (pure Python). Future-proof if adding Rust/C++ components. Storage backends already provide boundary. | **Consider** | **Low** |
| **Config-Driven Discovery** | Templates, backends, primitives discovered from config. Zero central registry. Enables plugin ecosystem. | **Adopt** | **High** |

---

## References

### Key Architectural Documents Consulted

- `/home/axp/projects/fleet/hangar/code/vespa/main/Code-map.md` — Module map (147 modules)
- `/home/axp/projects/fleet/hangar/code/vespa/main/README.md` — System overview
- `/home/axp/projects/fleet/hangar/code/aura/main/.context/designate/overview.md` — IMEM architecture

### Critical Modules Examined

**Configuration System**:
- `config/src/main/java/com/yahoo/config/subscription/ConfigSubscriber.java:23-93`
- `config-lib/src/main/java/com/yahoo/config/ConfigInstance.java`
- `configdefinitions/src/vespa/` — .def file examples

**Component Framework**:
- `container-core/src/main/java/com/yahoo/container/di/componentgraph/core/ComponentGraph.java:47-100`
- `component/src/main/java/com/yahoo/component/provider/ComponentRegistry.java`
- `container-core/src/main/java/com/yahoo/container/di/Container.java:1-102`

**Chain Execution**:
- `container-search/src/main/java/com/yahoo/search/Searcher.java:73-80`
- `docproc/src/main/java/com/yahoo/docproc/DocumentProcessor.java:44-72`
- `processing/src/main/java/com/yahoo/processing/execution/Chain.java`

**Storage Abstraction**:
- `document/src/main/java/com/yahoo/document/Document.java`
- `searchcore/` — Java/C++ bridge

### Design Decisions Observed

1. **Flat module structure** (147 modules, no deep nesting) — Simplifies discovery but requires Code-map.md
2. **Config as typed schemas** (.def files generate code) — Compile-time safety, hot-reload capability
3. **Constructor-based DI** (no @Inject spam) — Constructor is the contract
4. **Chains over inheritance** (Searcher chains, DocumentProcessor chains) — Composability
5. **Generation numbers** (atomic config updates) — Zero-downtime reconfiguration
6. **Java/C++ via RPC** (no JNI, no shared libs) — Clean boundaries, independent evolution
7. **Config-driven discovery** (no central registry) — Add component = edit config, not code

---

**END OF DOCUMENT**
