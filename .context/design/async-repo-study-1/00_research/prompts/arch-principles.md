# Agent Prompt: Architectural Principles from $REPO_NAME

## Mission
Extract **holistic architectural principles** from $REPO_NAME that inform how we structure IMEM's codebase.

Focus on **system organization** - not specific code patterns, but how modules relate and responsibilities separate.

---

## Context: IMEM Architecture

Read this first: `/home/axp/projects/fleet/hangar/code/aura/main/.context/designate/overview.md`

**TL;DR:**
IMEM is a **universal knowledge compiler** with three layers:
- **compile/** — Parse heterogeneous sources → canonical chunks
- **manage/** — Intelligence (entity resolution, temporal validation, authority)
- **retrieve/** — Query orchestration (search → discovery → graph → render)

**Current questions:**
- How should compilation stages separate? (parser vs resolver vs observer)
- How should storage backends plug in? (SQLite, Qdrant, future additions)
- How should query primitives compose? (siblings, genealogy, temporal, graph)
- How should intelligence layers interact? (manage/ internal boundaries)
- How should template plugins register and execute? (compile/Templates)

---

## Your Task

**1. Identify Structural Principles**

Look for:
- **Layer separation** — How do indexing and querying stay independent?
- **Dependency direction** — What depends on what? How are cycles avoided?
- **Extension points** — Where can new functionality plug in without core changes?
- **Interface boundaries** — What are the key abstractions? How do modules communicate?
- **Configuration vs code** — What's declarative, what's imperative?
- **Storage abstraction** — How is business logic separated from storage implementation?
- **Pipeline composition** — How do multi-stage operations orchestrate?

**2. Document 4-6 Principles**

For each principle:

```markdown
## Principle: {Name}

**Observed in:** {Component/module names}

**The Principle:**
{Core idea in 2-3 sentences}

**How It Works:**
{Concrete examples from the codebase showing this principle in action}

**Why It Matters:**
{Benefits this provides - maintainability, extensibility, testability, etc}

**Application to IMEM:**
- **Where:** {Which IMEM layer(s) benefit}
- **How:** {Specific structural decision we should make}
- **Example:** {Concrete change to our architecture}

**Trade-offs:**
- **Pros:** {...}
- **Cons:** {...}

**Adoption Recommendation:** Adopt | Adapt | Consider | Avoid
```

**3. Map to IMEM Structure**

How does this inform:
- **Codebase layout** — Directory structure, module organization
- **Dependency graph** — What imports what, flow of control
- **Extension strategy** — Plugin systems, configuration points
- **Interface design** — Key abstractions, API boundaries
- **Testing approach** — Unit vs integration boundaries
- **Configuration management** — What's hardcoded vs configurable

---

## Constraints

- **System-level thinking** — Not individual functions, but how subsystems relate
- **Justify with evidence** — Show where you see this principle in the code
- **IMEM-specific recommendations** — Don't just describe, prescribe
- **Consider our constraints** — Git-centric, template-driven, storage-agnostic
- **Practical over theoretical** — We're building this now, not planning for someday

---

## Output Format

Save to: `/home/axp/projects/fleet/hangar/code/aura/main/.context/design/async-repo-study-1/$REPO_NAME-principles.md`

```markdown
# Architectural Principles: $REPO_NAME

## Executive Summary
4-5 sentences: Overall architectural philosophy of this system and key lessons for IMEM.

---

## System Overview
Brief description of what $REPO_NAME does and its architectural approach.

---

## Principle 1: {Name}
{Full principle documentation as specified above}

---

## Principle 2: {Name}
{Full principle documentation as specified above}

---

## Synthesis: Implications for IMEM

### Recommended Structural Changes
1. {...}
2. {...}
3. {...}

### Directory Structure Implications
```
imem/
├── compile/
│   └── {specific organization based on principles}
├── manage/
│   └── {specific organization based on principles}
└── retrieve/
    └── {specific organization based on principles}
```

### Key Interfaces to Define
- Interface 1: {...}
- Interface 2: {...}

### Extension Points to Establish
- Extension 1: {...}
- Extension 2: {...}

---

## Summary Table

| Principle | Impact on IMEM | Adoption | Priority |
|-----------|----------------|----------|----------|
| ...       | ...            | ...      | ...      |

---

## References
- Key architectural documents consulted
- Critical modules examined
- Design decisions observed
```

---

## Example Principle (for reference)

**Principle: Storage-Agnostic Query Abstraction (LlamaIndex)**

**Observed in:** `llama_index/core/storage/`, `llama_index/core/query_engines/`

**The Principle:**
Query execution logic is completely separated from storage implementation. Query engines work with abstract `BaseRetriever` interface. Storage backends (vector stores, document stores) implement standard interfaces independently.

**How It Works:**
- Query engine receives `BaseRetriever` instance (dependency injection)
- Retriever interface defines: `retrieve(query_str) -> List[NodeWithScore]`
- VectorStoreIndex, KeywordIndex, GraphIndex all implement this interface
- Query logic never imports specific storage implementations
- Storage backends swappable at runtime via configuration

**Why It Matters:**
- **Maintainability:** Query logic evolves independently of storage
- **Extensibility:** New storage backends require zero query engine changes
- **Testability:** Query engines testable with mock retrievers
- **Flexibility:** Users switch storage without code changes

**Application to IMEM:**
- **Where:** retrieve/Orchestrator and storage/ boundary
- **How:** Define `ChunkRetriever` interface, SQLite/Qdrant both implement it
- **Example:**
  ```python
  # retrieve/orchestrator.py
  def compose(retriever: ChunkRetriever, config: dict):
      results = retriever.search(config['search'])
      # ... orchestration logic ...

  # storage/sqlite.py
  class SQLiteRetriever(ChunkRetriever):
      def search(self, config): ...

  # storage/qdrant.py
  class QdrantRetriever(ChunkRetriever):
      def search(self, config): ...
  ```

**Trade-offs:**
- **Pros:** Perfect storage abstraction, easy backend swapping
- **Cons:** Interface must be expressive enough for all backends, some backend-specific optimizations harder

**Adoption Recommendation:** Adopt — Critical for our "storage agnostic" principle

---

Begin analysis of $REPO_NAME.
