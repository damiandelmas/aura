# Pattern Extraction: vespa

## Executive Summary

Vespa is a large-scale search and serving platform (~1.7M LOC) with **exceptional architectural patterns for composable infrastructure**. Its strength lies in: (1) **type-safe expression pipelines** with compile-time validation, (2) **annotation-driven dependency chains** that auto-order processing stages, (3) **multi-phase ranking** with profile inheritance, and (4) **subscription-based configuration** for zero-downtime updates. These patterns are highly relevant to IMEM's need for extensible query composition, template-based parsing, and multi-stage retrieval pipelines.

---

## Pattern 1: Composable Expression Pipeline with Type Inference

**Location:** `indexinglanguage/src/main/java/com/yahoo/vespa/indexinglanguage/expressions/`

### Description

Vespa's indexing language implements a **composable expression pipeline** where transformation operations are chained together. Each `Expression` is a typed transformation with:
- Input/output type validation at compile-time
- Bidirectional type inference (propagates both forward and backward)
- Immutable expression trees that can be composed and transformed
- Standard interface for all operations: `execute(ExecutionContext) → FieldValue`

**Key architectural choice:** Types are resolved *before* execution, catching errors at parse/deployment time rather than runtime. Expressions are immutable and can be freely reordered via `ExpressionConverter`.

### Code Example

```java
// Base expression with type inference
public abstract class Expression extends Selectable {
    private DataType inputType;
    private DataType outputType;

    /** Returns whether this expression requires an input value. */
    public boolean requiresInput() { return true; }

    /** Returns whether this expression modifies its input */
    public boolean isMutating() { return true; }

    /** Bidirectional type resolution */
    public DataType setInputType(DataType inputType, TypeContext context) {
        return assignInputType(inputType);
    }

    /** Convert expression tree structure */
    public Expression convertChildren(ExpressionConverter converter) {
        return this;
    }
}

// Script composes multiple statements
public final class ScriptExpression extends ExpressionList<StatementExpression> {
    @Override
    public DataType setInputType(DataType inputType, TypeContext context) {
        super.setInputType(inputType, context);
        DataType currentOutput = null;
        // Propagate types through pipeline
        for (var expression : expressions())
            currentOutput = expression.setInputType(inputType, context);
        return currentOutput != null ? currentOutput : getOutputType(context);
    }

    @Override
    public boolean requiresInput() {
        return expressions().stream().anyMatch(statement -> statement.requiresInput());
    }
}

// Example: input | lowercase | tokenize | index
// Parser validates types match at parse time, not execution time
```

### Relevance to IMEM

- **Module:** `compile/Templates` + `retrieve/Primitives`
- **Use case:**
  - **Compile:** Template-based parsing can be implemented as composable extractors. Each extractor (`input → sections → metadata → chunks`) is a typed transformation. Schema evolution resolves types backward from target.
  - **Retrieve:** Discovery operations (siblings, genealogy, temporal) compose like expressions. `search → filter_phase → enrich_metadata → apply_graph` validates metadata availability at construction time.
- **Why useful:**
  - Type safety prevents invalid query compositions at build time
  - Bidirectional inference enables partial specification (system fills in missing types)
  - Immutable trees enable optimization passes (like `ExpressionConverter`)

### Adoption Strategy

- **[x] Adapt** — Create `Operation` base class for IMEM discovery primitives:
  ```python
  class Operation(ABC):
      input_metadata: Set[str]  # Required metadata fields
      output_metadata: Set[str]  # Produced metadata fields

      @abstractmethod
      def execute(self, chunks: List[Chunk], context: Context) -> List[Chunk]:
          pass

      def validate_chain(self, prior_ops: List[Operation]) -> bool:
          """Check if required metadata is available from prior operations"""
          available = set()
          for op in prior_ops:
              available.update(op.output_metadata)
          return self.input_metadata.issubset(available)

  # Usage:
  # search = SearchOp(output={'session_id', 'file_path'})
  # siblings = SiblingsOp(input={'file_path'}, output={'sibling_count'})
  # chain = [search, siblings]  # Validates at construction
  ```

**Implementation Priority:** **High** — This directly addresses query composition validation in `retrieve/Orchestrator`.

---

## Pattern 2: Annotation-Driven Dependency Chain with Auto-Ordering

**Location:**
- `container-core/src/main/java/com/yahoo/component/chain/Chain.java:1-133`
- `container-core/src/main/java/com/yahoo/component/chain/ChainedComponent.java:1-51`
- `container-search/src/main/java/com/yahoo/prelude/searcher/BlendingSearcher.java:1-100`

### Description

Vespa's **chain-of-responsibility pattern** uses annotations to declare dependencies between processing components. Components declare:
- `@Before("phase")` — Must execute before this phase/component
- `@After("phase")` — Must execute after this phase/component
- `@Provides("capability")` — Declares what this component provides

A `ChainBuilder` uses topological sorting to automatically order components based on these constraints, **eliminating manual ordering errors**.

### Code Example

```java
// Base chainable component
public abstract class ChainedComponent extends AbstractComponent {
    private Dependencies dependencies = getAnnotatedDependencies();

    public void initDependencies(Dependencies dependencies) {
        this.dependencies = dependencies.union(getAnnotatedDependencies());
    }

    public Dependencies getDependencies() { return dependencies; }
}

// Concrete processor with ordering annotations
@After(PhaseNames.BLENDED_RESULT)
@Before(PhaseNames.UNBLENDED_RESULT)
@Provides(BlendingSearcher.BLENDING)
public class BlendingSearcher extends Searcher {
    @Override
    public Result search(Query query, Execution execution) {
        Result result = execution.search(query);  // Call next in chain
        Result blended = blendResults(result, query, ...);
        return blended;
    }
}

// Chain auto-orders based on annotations
public Chain(ComponentId id, Collection<COMPONENT> components, Collection<Phase> phases) {
    this(id, buildChain(components, phases).components());
}

private static <T extends ChainedComponent> Chain<T> buildChain(
        Collection<T> components, Collection<Phase> phases) {
    ChainBuilder<T> builder = new ChainBuilder<>(new ComponentId("temp"));
    for (Phase phase : phases) {
        builder.addPhase(phase);
    }
    for (T component : components) {
        builder.addComponent(component);  // Builder sorts via topological order
    }
    return builder.orderNodes();
}
```

### Relevance to IMEM

- **Module:** `retrieve/Orchestrator` + `compile/Templates`
- **Use case:**
  - **Retrieve:** Discovery operations have implicit dependencies (e.g., `enrich_temporal` requires `search` to have run first, `apply_graph` needs `enrich_metadata` results). Annotating dependencies enables flexible composition:
    ```python
    @before("ranking")
    @after("search")
    @provides("metadata_enrichment")
    class EnrichMetadataOp(Operation):
        pass

    @before("ranking")
    @after("metadata_enrichment")
    @provides("graph_scores")
    class ApplyGraphOp(Operation):
        pass
    ```
  - **Compile:** Template parsers can declare dependencies on other parsers. Example: `ConversationTemplate @after(MarkdownTemplate)` if conversations reference markdown files.

- **Why useful:**
  - **Declarative ordering** — No manual sequencing, system computes correct order
  - **Compositional flexibility** — Users can add custom operations without knowing global order
  - **Early validation** — Circular dependencies or missing phases detected at startup

### Adoption Strategy

- **[x] Adapt** — Implement for `retrieve/Orchestrator` pipeline:
  ```python
  class Pipeline:
      def __init__(self, operations: List[Operation]):
          self.operations = self._topological_sort(operations)

      def _topological_sort(self, ops: List[Operation]) -> List[Operation]:
          """Sort operations based on @before/@after constraints"""
          graph = defaultdict(list)
          in_degree = defaultdict(int)

          for op in ops:
              for after in op.after:
                  graph[after].append(op.id)
                  in_degree[op.id] += 1
              for before in op.before:
                  graph[op.id].append(before)
                  in_degree[before] += 1

          # Kahn's algorithm for topological sort
          # ... (standard implementation)
          return sorted_ops
  ```

**Implementation Priority:** **Medium** — Improves query composition ergonomics but not critical for MVP.

---

## Pattern 3: Multi-Phase Ranking with Inherited Profiles

**Location:**
- `config-model/src/main/java/com/yahoo/schema/RankProfile.java:1-150`
- `config-model/src/main/java/com/yahoo/schema/RankProfileRegistry.java:1-100`

### Description

Vespa's **ranking system** uses multi-phase evaluation with profile inheritance:
1. **First-phase:** Fast approximate ranking over all candidates (WAND, term matching)
2. **Second-phase:** Expensive ML models on top-k from first phase (configurable rerank count)
3. **Global-phase:** Cross-document re-ranking after distributed merge (optional)

**Profiles inherit settings** — `RankProfile` supports inheritance chains where child profiles extend parent profiles, overriding specific ranking expressions or features. A `RankProfileRegistry` resolves inheritance hierarchies and manages global/schema-specific profiles.

### Code Example

```java
public class RankProfile implements Cloneable {
    private final String name;
    private final ImmutableSchema schema;

    // Inheritance chain
    private final List<String> inheritedNames = new ArrayList<>();
    private List<RankProfile> inherited;  // Resolved at deployment

    // Multi-phase ranking expressions
    private RankingExpressionFunction firstPhaseRanking = null;
    private RankingExpressionFunction secondPhaseRanking = null;
    private RankingExpressionFunction globalPhaseRanking = null;

    // Rerank limits per phase
    private int rerankCount = -1;  // Second-phase top-k
    private int globalPhaseRerankCount = -1;  // Global-phase top-k

    // Features and properties
    private Set<ReferenceNode> summaryFeatures;  // Output features
    private Set<ReferenceNode> matchFeatures;    // Match-time features
    private Map<String, RankingExpressionFunction> functions;  // Reusable functions
}

// Registry with inheritance resolution
public class RankProfileRegistry {
    private final Map<String, Map<String, RankProfile>> rankProfiles;

    public RankProfile resolve(SDDocumentType docType, String name) {
        RankProfile rankProfile = get(docType.getName(), name);
        if (rankProfile != null) return rankProfile;
        // Walk inheritance chain
        for (var parent : docType.getInheritedTypes()) {
            RankProfile parentProfile = resolve(parent, name);
            if (parentProfile != null) return parentProfile;
        }
        return get(globalRankProfilesKey, name);  // Fall back to global
    }
}
```

### Relevance to IMEM

- **Module:** `retrieve/Ranking` + `manage/Qualification`
- **Use case:**
  - **Retrieve:** Authority scoring is currently single-phase (reference counting). Multi-phase ranking enables:
    - **Phase 1:** Fast metadata filters (phase, section_type, recency threshold)
    - **Phase 2:** Reference counting + temporal proximity scoring (top-k from phase 1)
    - **Phase 3:** Graph algorithms (PageRank, authority centrality) on finalists
  - **Manage/Qualification:** Ranking profiles = preset query templates. Example:
    ```python
    # Base profile
    base_profile = RankingProfile(
        name="base",
        phase1_filters={"phase": "designate"},
        phase2_features=["reference_count", "recency_score"],
        rerank_count=100
    )

    # Child profile inherits and overrides
    decision_profile = RankingProfile(
        name="decisions",
        inherits="base",
        phase1_filters={"section_type": "Decision"},  # Override
        phase3_graph="authority_centrality"  # Add phase
    )
    ```

- **Why useful:**
  - **Progressive refinement** — Expensive operations only on finalists
  - **Reusable presets** — Base profiles shared across queries, domain-specific extensions
  - **Cost control** — Explicit rerank counts prevent runaway computation

### Adoption Strategy

- **[x] Adopt** — Implement for `retrieve/Ranking`:
  ```python
  class RankingPhase:
      def __init__(self, name: str, scorer: Callable, rerank_count: int = None):
          self.name = name
          self.scorer = scorer
          self.rerank_count = rerank_count

      def apply(self, chunks: List[Chunk]) -> List[Chunk]:
          scored = [(chunk, self.scorer(chunk)) for chunk in chunks]
          sorted_chunks = sorted(scored, key=lambda x: x[1], reverse=True)
          if self.rerank_count:
              sorted_chunks = sorted_chunks[:self.rerank_count]
          return [chunk for chunk, score in sorted_chunks]

  class RankingProfile:
      def __init__(self, name: str, phases: List[RankingPhase], parent: 'RankingProfile' = None):
          self.name = name
          self.phases = parent.phases + phases if parent else phases

      def rank(self, chunks: List[Chunk]) -> List[Chunk]:
          for phase in self.phases:
              chunks = phase.apply(chunks)
          return chunks
  ```

**Implementation Priority:** **High** — Multi-phase ranking is core to `retrieve/` performance.

---

## Pattern 4: Type-Safe Config Subscription with Hot Reload

**Location:**
- `config/src/main/java/com/yahoo/config/subscription/ConfigSubscriber.java:1-120`
- `config-model/src/main/java/com/yahoo/schema/parser/` (schema parsing)

### Description

Vespa's **configuration system** decouples config definition from deployment:
1. **Config definitions** (`.def` files) define typed schemas
2. **ConfigGenerator** generates type-safe Java/C++ classes from definitions
3. **ConfigSubscriber** polls for config updates and notifies subscribers
4. **Zero-downtime reload** — new configs activate atomically, old generation kept until components migrate

**Key properties:**
- **Generational versioning** — Each config change increments generation number
- **Lazy application** — Subscribers receive `nextConfig()` notification but apply on their schedule
- **Rollback support** — Previous generations cached for rollback

### Code Example

```java
public class ConfigSubscriber implements AutoCloseable {
    private final List<ConfigHandle<? extends ConfigInstance>> subscriptionHandles;
    private long generation = -1;  // Current generation
    private boolean applyOnRestart = false;  // Defer application flag

    /** Subscribe to a typed config */
    public <T extends ConfigInstance> ConfigHandle<T> subscribe(
            Class<T> configClass, String configId) {
        ConfigKey<T> configKey = new ConfigKey<>(configClass, configId);
        ConfigSubscription<T> sub = ConfigSubscription.get(
            configKey, requesters, source, timingValues);
        ConfigHandle<T> handle = new ConfigHandle<>(sub);
        subscribeAndHandleErrors(sub, configKey, handle, timingValues);
        return handle;
    }

    /**
     * Block until next generation available.
     * Returns true if config changed, false if timeout.
     */
    public boolean nextConfig(boolean timeout) {
        // ... poll logic
    }
}

// Usage pattern:
ConfigSubscriber subscriber = new ConfigSubscriber();
ConfigHandle<MyConfig> handle = subscriber.subscribe(MyConfig.class, "myservice");

while (subscriber.nextConfig()) {
    MyConfig config = handle.getConfig();
    // Apply new config atomically
    applyConfig(config);
}
```

### Relevance to IMEM

- **Module:** `compile/Resolver` + `manage/Registry`
- **Use case:**
  - **Compile/Resolver:** Schema evolution needs live updates without recompilation. When new section types discovered (`Decision:`, `Choice:`, `Verdict:` → canonical `decision`), parsers subscribe to schema updates:
    ```python
    schema_subscriber = SchemaSubscriber()
    schema_handle = schema_subscriber.subscribe("project_schema")

    while schema_subscriber.next_generation():
        schema = schema_handle.get_schema()
        parser.update_resolvers(schema)  # Hot-reload resolvers
    ```
  - **Manage/Registry:** Cross-project registry serves as config server. Local projects subscribe to global entity mappings, authority scores, and qualification metadata. Updates propagate without service restart.

- **Why useful:**
  - **Zero-downtime updates** — Critical for long-running knowledge compilation
  - **Generational rollback** — If new schema breaks parsing, rollback to prior generation
  - **Type safety** — Generated classes prevent invalid config at compile time

### Adoption Strategy

- **[ ] Adapt** — Implement config subscription for IMEM:
  ```python
  class SchemaSubscriber:
      def __init__(self, registry_url: str):
          self.registry_url = registry_url
          self.current_generation = -1
          self.schema_cache = {}

      def subscribe(self, schema_name: str) -> SchemaHandle:
          """Subscribe to schema updates from registry"""
          handle = SchemaHandle(schema_name, self)
          self._poll_updates(handle)
          return handle

      def next_generation(self) -> bool:
          """Check if new schema generation available"""
          response = requests.get(f"{self.registry_url}/generation")
          remote_gen = response.json()["generation"]
          if remote_gen > self.current_generation:
              self.current_generation = remote_gen
              return True
          return False

  class SchemaHandle:
      def get_schema(self) -> Schema:
          """Fetch latest schema from subscriber cache"""
          return self.subscriber.schema_cache[self.schema_name]
  ```

**Implementation Priority:** **Low** — Useful for multi-project deployments but not MVP-critical.

---

## Pattern 5: Abstract Syntax Tree (AST) Transformation Passes

**Location:**
- `indexinglanguage/src/main/java/com/yahoo/vespa/indexinglanguage/ExpressionConverter.java`
- `config-model/src/main/java/com/yahoo/schema/expressiontransforms/`

### Description

Vespa's indexing language uses **compiler-style transformation passes** over expression ASTs:
1. **Parse** — Source text → immutable expression tree
2. **Transform passes** — Multiple visitors apply optimizations:
   - Constant folding (`2 + 3` → `5`)
   - Dead code elimination
   - Type-specific optimizations (e.g., replace `lowercase | lowercase` → `lowercase`)
3. **Code generation** — Optimized AST → executable bytecode

**`ExpressionConverter`** is a visitor pattern that walks the tree, allowing each node to transform its children recursively.

### Code Example

```java
// Base converter interface
public interface ExpressionConverter {
    Expression convert(Expression expression);
    ExpressionConverter branch();  // Create new converter for subtree
}

// Expression supports conversion
public abstract class Expression {
    /** Transform children via converter */
    public Expression convertChildren(ExpressionConverter converter) {
        return this;
    }
}

// Composite expressions propagate conversion
public final class ScriptExpression extends ExpressionList<StatementExpression> {
    @Override
    public ScriptExpression convertChildren(ExpressionConverter converter) {
        return new ScriptExpression(
            asList().stream()
                .map(child -> (StatementExpression)converter.branch().convert(child))
                .filter(Objects::nonNull)  // Remove optimized-away nodes
                .toList()
        );
    }
}

// Example transformation: Remove redundant operations
class RedundancyEliminator implements ExpressionConverter {
    public Expression convert(Expression expr) {
        if (expr instanceof LowerCaseExpression) {
            // Check if child is also lowercase → eliminate duplicate
            Expression child = expr.getChild();
            if (child instanceof LowerCaseExpression) {
                return child;  // Remove outer lowercase
            }
        }
        return expr.convertChildren(this);  // Recurse
    }
}
```

### Relevance to IMEM

- **Module:** `compile/Resolver` + `retrieve/Orchestrator`
- **Use case:**
  - **Compile/Resolver:** Schema evolution transformations:
    - **Normalization pass:** `"Decision:", "Choice:", "Verdict:"` → `"decision"`
    - **Canonicalization pass:** Resolve abbreviations (`"impl" → "implementation"`)
    - **Validation pass:** Ensure chunk metadata includes required fields
    ```python
    class SchemaTransform(ABC):
        @abstractmethod
        def visit(self, chunk: Chunk) -> Chunk:
            pass

    class NormalizationPass(SchemaTransform):
        def visit(self, chunk: Chunk) -> Chunk:
            chunk.section_type = self.normalize(chunk.section_type)
            return chunk

    # Apply transformations
    pipeline = [NormalizationPass(), CanonicalizePass(), ValidationPass()]
    for transform in pipeline:
        chunk = transform.visit(chunk)
    ```

  - **Retrieve/Orchestrator:** Query optimization:
    - **Filter pushdown:** Move metadata filters before expensive semantic search
    - **Redundant operation removal:** `filter(phase=develop) | filter(phase=develop)` → single filter
    - **Predicate fusion:** Combine multiple filters into single SQL WHERE clause

- **Why useful:**
  - **Optimization without manual tuning** — System auto-optimizes queries
  - **Extensible** — Add new transformation passes without modifying core
  - **Composable** — Passes run independently, order controlled via chain pattern

### Adoption Strategy

- **[ ] Avoid** — AST transformations are powerful but add complexity. For IMEM's current scale, **simpler approaches suffice:**
  - **Compile:** Template-level normalization (single pass during parsing, not multi-pass)
  - **Retrieve:** Query builder with basic optimization (filter deduplication, order optimization)

  **Revisit if:** Future work involves complex query optimizations (e.g., join reordering, index selection).

**Implementation Priority:** **Low** — Over-engineering for current needs.

---

## Summary Table

| Pattern | IMEM Module | Priority | Strategy |
|---------|-------------|----------|----------|
| **Composable Expression Pipeline** | `compile/Templates`, `retrieve/Primitives` | **High** | **Adapt** — Implement `Operation` base class with type validation |
| **Annotation-Driven Dependency Chains** | `retrieve/Orchestrator`, `compile/Templates` | **Medium** | **Adapt** — Topological sort for operation ordering |
| **Multi-Phase Ranking with Inheritance** | `retrieve/Ranking`, `manage/Qualification` | **High** | **Adopt** — Direct implementation for progressive refinement |
| **Config Subscription with Hot Reload** | `compile/Resolver`, `manage/Registry` | **Low** | **Adapt** — Polling-based schema updates for cross-project sync |
| **AST Transformation Passes** | `compile/Resolver`, `retrieve/Orchestrator` | **Low** | **Avoid** — Simpler single-pass optimizations sufficient |

---

## Key Files Examined

**Component Infrastructure:**
- `component/src/main/java/com/yahoo/component/Component.java`
- `container-core/src/main/java/com/yahoo/component/chain/Chain.java`
- `container-core/src/main/java/com/yahoo/component/chain/ChainedComponent.java`

**Indexing Language (Expression Pipeline):**
- `indexinglanguage/src/main/java/com/yahoo/vespa/indexinglanguage/ScriptParser.java`
- `indexinglanguage/src/main/java/com/yahoo/vespa/indexinglanguage/expressions/Expression.java`
- `indexinglanguage/src/main/java/com/yahoo/vespa/indexinglanguage/expressions/ScriptExpression.java`

**Search Chain (Dependency Ordering):**
- `container-search/src/main/java/com/yahoo/prelude/searcher/BlendingSearcher.java`
- `container-core/src/main/java/com/yahoo/processing/execution/chain/ChainRegistry.java`

**Ranking System:**
- `config-model/src/main/java/com/yahoo/schema/RankProfile.java`
- `config-model/src/main/java/com/yahoo/schema/RankProfileRegistry.java`

**Configuration System:**
- `config/src/main/java/com/yahoo/config/subscription/ConfigSubscriber.java`

---

## References

**Documentation Consulted:**
- `Code-map.md` — Architectural overview mapping functional elements to modules
- JavaDoc comments in expression, chain, and ranking files

**Key Architectural Decisions Observed:**

1. **Type safety via generation** — Config definitions and expression types validated at compile/deploy time, not runtime
2. **Immutability for concurrency** — Expressions, chains, and configs are immutable; updates create new instances
3. **Lazy evaluation where possible** — ConfigSubscriber polls but doesn't force application; chains build lazily
4. **Separation of concerns via phases** — Ranking, search, and indexing all use multi-phase approaches to separate fast/slow operations
5. **Registry pattern for discovery** — RankProfileRegistry, ChainRegistry, ComponentRegistry all use same pattern: hierarchical lookup with inheritance resolution

**Surprising Findings:**

- **Bidirectional type inference** — Most systems propagate types forward only; Vespa's backward propagation (from output requirements to input constraints) is rare and powerful
- **Annotation-driven ordering** — Eliminates entire class of ordering bugs in processing pipelines
- **Multi-phase ranking everywhere** — Not just search ranking; document processing, query execution, and indexing all use progressive refinement
