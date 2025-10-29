---
date: 2025-10-27
type: pattern.reusable
status: current
keywords: "parallelization infrastructure composition fan-out-fan-in"
---

# Pattern: Generic Parallelization Primitive

## Problem

System has multiple independent operations.
Executing sequentially: Total time = sum of operation times.
Need: Execute in parallel for performance.

**Common scenario:**
```
Task: Gather data from 3 sources
Operations:
  - Query database
  - Fetch from API
  - Read from cache
Sequential: 300ms (100ms × 3)
Desired: ~100ms (parallel execution)
```

---

## Anti-Pattern: Operation-Specific Parallelization

```
# Anti-pattern: Custom parallel wrappers

function parallel_database_and_api():
    thread1 = spawn(query_database)
    thread2 = spawn(fetch_api)
    return [thread1.result(), thread2.result()]

function parallel_all_three():
    thread1 = spawn(query_database)
    thread2 = spawn(fetch_api)
    thread3 = spawn(read_cache)
    return [thread1.result(), thread2.result(), thread3.result()]

# N operations → N² wrapper functions
```

**Problems:**
- Explosion: Every operation combination needs custom wrapper
- Duplication: Parallelization logic repeated
- Maintenance: Adding operation requires new wrappers

---

## Pattern: Infrastructure Primitive

### Core Abstraction

```
execute_parallel(operations: List[Operation]) -> List[Result]
```

**Property:** Works with ANY operation conforming to signature.

### Generic Implementation (pseudocode)

```
function execute_parallel(operations):
    # 1. Spawn concurrent execution contexts
    contexts = []
    for op in operations:
        context = spawn_async(op.function, op.parameters)
        contexts.append(context)

    # 2. Wait for all to complete
    results = []
    for context in contexts:
        result = context.await()
        results.append(result)

    return results
```

### Operation Dispatch Pattern

```
function execute_parallel(operation_specs):
    # 1. Resolve operation specs to functions
    operations = []
    for spec in operation_specs:
        function = REGISTRY[spec.type]  # Lookup by type
        operation = (function, spec.parameters)
        operations.append(operation)

    # 2. Execute all concurrently
    contexts = [spawn_async(fn, params) for fn, params in operations]
    results = [ctx.await() for ctx in contexts]

    return results
```

**Key:** Registry maps operation types to functions.
Adding new operation = register function, no dispatch changes.

---

## Interface Pattern: Structured Data as CLI Argument

**Anti-pattern:** File-based config
```
# Step 1: Write config
write_file("config.json", serialize(config))

# Step 2: Execute
execute("command --config config.json")

# Step 3: Cleanup
delete_file("config.json")
```

**Pattern:** Inline structured argument
```
# Single step
execute("command '" + serialize(config) + "'")
```

**Benefits:**
- Atomic: Single operation
- No state: No temp files
- Observable: Config visible in logs
- Reproducible: Command captures everything

**Structure format:** JSON (universal, human-readable, programmatically constructible)

---

## Composition Pattern: Prompt-Level vs Code-Level

### Code-Level Composition (Anti-Pattern)

```
# Application layer: Multiple wrapper functions

function search_and_rank(query):
    results1 = search(query + " decisions")
    results2 = search(query + " failures")
    combined = merge(results1, results2)
    ranked = apply_algorithm(combined, "pagerank")
    return ranked

function explain_with_context(query):
    decision = search(query, filters={"decisions"})
    siblings = get_siblings(decision.id)
    conversation = filter_by_session(decision.session_id)
    return [decision, siblings, conversation]

# N use cases → N wrapper functions
```

### Prompt-Level Composition (Pattern)

```
# Infrastructure layer: Single parallelization primitive

function execute_parallel(operations):
    # Generic implementation (unchanged for any use case)
    ...

# Orchestrator constructs operation specs

// Use case 1: Search and rank
operations = [
    {type: "search", query: "auth decisions"},
    {type: "search", query: "auth failures"}
]
results = execute_parallel(operations)
ranked = apply_algorithm(merge(results), "pagerank")

// Use case 2: Explain with context
decision = search("JWT")
operations = [
    {type: "siblings", result_id: decision.id},
    {type: "filter", session: decision.session_id}
]
context = execute_parallel(operations)
```

**Difference:**
- Code-level: Wrapper functions encode use cases
- Prompt-level: Orchestrator constructs operation specs

**Benefit:** Infinite use cases, one infrastructure primitive.

---

## Error Isolation Pattern

```
function execute_parallel_with_isolation(operations):
    contexts = [spawn_async(op) for op in operations]

    # Gather results, catch exceptions per-operation
    results = []
    errors = []

    for i, context in enumerate(contexts):
        try:
            result = context.await()
            results.append((i, result))
        except Exception as e:
            errors.append((i, e))

    return {
        successes: results,
        failures: errors
    }
```

**Property:** One operation failure doesn't fail entire batch.

**Trade-off:**
- Resilience: Partial success possible
- Complexity: Caller must handle mixed results

**When to use:** Operations are independent, partial results valuable.

---

## Extension Pattern: Registry-Based Dispatch

```
# Operation registry (extensible)
OPERATION_REGISTRY = {}

function register_operation(type_name, handler_function):
    OPERATION_REGISTRY[type_name] = handler_function

function dispatch(operation_spec):
    handler = OPERATION_REGISTRY[operation_spec.type]
    return handler(operation_spec.parameters)

# Adding new operation
function new_custom_operation(params):
    # Implementation
    ...

register_operation("custom_op", new_custom_operation)

# Now works with parallel execution (zero changes to parallelizer)
execute_parallel([
    {type: "existing_op", ...},
    {type: "custom_op", ...}  # Newly added, works immediately
])
```

**Property:** Adding operations doesn't modify parallelization logic.

---

## When to Use This Pattern

**Use when:**
- Multiple independent operations need parallel execution
- Operation types vary (not all the same)
- New operations will be added over time
- Orchestrator can construct operation specs programmatically

**Don't use when:**
- Operations have dependencies (must be sequential)
- Single operation type (just use native parallel library)
- Fixed, small number of use cases (wrappers acceptable)

---

## Real-World Analogies

**Database query planner:**
- Input: SQL with multiple subqueries
- Planner: Identifies independent subqueries
- Executor: Runs in parallel, combines results

**Build systems (Make, Bazel):**
- Input: Dependency graph
- Planner: Identifies independent build steps
- Executor: Compiles in parallel

**Map-reduce:**
- Input: Data + map function
- Planner: Partitions data
- Executor: Maps in parallel, reduces serially

**This pattern:**
- Input: Operation specs
- Planner: None needed (operations declared independent)
- Executor: Runs all in parallel, returns results

---

## Key Insights

1. **Parallelization is infrastructure, not domain logic**
   - Don't encode use cases in parallelization code
   - Generic primitive + orchestrator composition

2. **Registry pattern enables extensibility**
   - Adding operations doesn't change parallelization logic
   - Type-based dispatch decouples concerns

3. **Inline structured arguments reduce friction**
   - No file I/O ceremony
   - Atomic, observable, reproducible

4. **Prompt-level composition more flexible than code-level**
   - Infinite combinations without code changes
   - Orchestrator intelligence > hardcoded wrappers

---

## Language-Agnostic Implementation Hints

**Python:** `asyncio.gather()`
**JavaScript:** `Promise.all()`
**Go:** Goroutines + WaitGroup
**Rust:** `tokio::join!()` or `futures::join_all()`
**Java:** `CompletableFuture.allOf()`

**Pattern applies regardless of concurrency primitive.**

---

## Bottom Line

**Problem:** Need parallel execution of independent operations.

**Anti-pattern:** Operation-specific wrapper functions (explosion).

**Pattern:** Generic parallelization primitive + registry dispatch.

**Benefits:**
- Extensible (add operations without changing parallelizer)
- Composable (orchestrator constructs specs)
- Observable (structured argument captures intent)
- Performant (~Nx speedup for N operations)

**Essence:** Infrastructure primitive, not domain wrapper.
