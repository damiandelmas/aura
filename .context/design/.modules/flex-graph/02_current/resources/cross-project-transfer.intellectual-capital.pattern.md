---
session_id: ca22384b-3a6d-4821-8b70-2aa1a89ea4ba
date: 2025-10-27
level: architecture-pattern
innovation: cross-project-transfer
---

# Cross-Project Transfer: Architecture Pattern

## Core Mechanism

**Multi-collection query with layer filtering:**

1. **Storage:** Each project = separate Qdrant collection
2. **Pattern layer:** Indexed in all collections (language-agnostic chunks)
3. **Query mode:** Filter by layer=pattern across collections
4. **Result:** Zero code contamination, pure principles

**Collection structure:**
```
Collection: imem_typescript_project
├─ Implementation chunks (TypeScript code)
└─ Pattern chunks (language-agnostic)

Collection: imem_python_project
├─ Implementation chunks (Python code)
└─ Pattern chunks (language-agnostic)

Collection: imem_rust_project
├─ Implementation chunks (Rust code)
└─ Pattern chunks (language-agnostic)
```

## Query Modes

**Single-project (default):**
```
Query: "authentication"
Collection: Current project only
Layer: Implementation + patterns
Result: Project-specific code + abstractions
```

**Cross-project pattern search:**
```
Query: "authentication"
Collections: All registered projects
Layer: Pattern only (filter)
Result: Language-agnostic principles from all projects
```

**Cross-project with authority ranking:**
```
Query: "provider agnostic design"
Collections: All projects
Layer: Pattern only
Graph: Build from results
Algorithm: PageRank on patterns
Result: Most validated cross-project solutions
```

## Authority Metrics

**Pattern validation score:**

```
Pattern appears in N projects:
N=1: Hypothesis (unvalidated)
N=2-3: Validated (proven in multiple contexts)
N=4+: Institutional wisdom (cross-domain proven)

Ranking factor:
score = base_similarity × (1 + log(N_projects))
```

**Cross-project graph edges:**
```
Same pattern in different projects = bridge edge
Weight = semantic similarity between pattern instances
Centrality = patterns connecting most projects
```

## Anti-Contamination Guarantee

**Enforcement via layer filtering:**

```
Implementation query:
- filter: {layer: 'implementation'}
- scope: Current project only
- Result: Project-specific code

Pattern query:
- filter: {layer: 'pattern'}
- scope: All projects
- Result: Language-agnostic principles

No mixing unless explicit override.
```

**Pattern extraction requirements:**

- ❌ No framework names
- ❌ No library references
- ❌ No code snippets (only pseudocode/principles)
- ❌ No language-specific idioms
- ✅ Context, solution, rationale, constraints
- ✅ Cross-language applicability

## Multi-Collection Query Architecture

**Sequential query pattern:**
```
results = []
for project in registry.list_projects():
    project_results = query(
        collection=project.collection_name,
        filter={layer: 'pattern'},
        query_vector=embed(query),
        limit=10
    )
    results.extend(project_results)

# Merge, deduplicate, rank
merged = deduplicate_by_content(results)
ranked = rank_by_authority(merged)  # N_projects factor
```

**Graph-based ranking:**
```
Build graph from multi-project results
Add edges: Same pattern across projects
Apply PageRank: Patterns bridging most projects rank higher
Return top N by centrality
```

## Use Case Example

**Scenario:** Building Python FastAPI auth

**Wrong approach (code search):**
```
Query: "authentication implementation"
Returns: TypeScript JWT code (useless)
```

**Right approach (pattern search):**
```
Query: "authentication" --pattern --all-projects
Returns:
1. Stateless Auth Pattern (from TypeScript project)
2. Token-Based Auth Pattern (from Rust project)
3. Session-less Design Pattern (from Python project)

Apply: Choose FastAPI-compatible implementation of pattern #1
```

## Key Properties

**Isolation:** Implementations never cross projects
**Abstraction:** Patterns always cross-project compatible
**Authority:** Ranking by multi-project validation
**Applicability:** Zero framework/language leakage
