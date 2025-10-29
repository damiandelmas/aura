---
session_id: eee3b7a5-3870-4b50-984c-19eb2e2fa729
date: 2025-10-27
type: pattern.architecture
resolution: level-2a
keywords: "multi-collection pattern-isolation authority-ranking"
---

# Cross-Project Patterns: Architecture Pattern

## The Pattern

**Multi-collection architecture with pattern layer isolation.**

Each project → separate collection:
- Implementation chunks (project-specific)
- Pattern chunks (cross-project queryable)

Cross-project queries → pattern layer only (anti-contamination).

Authority ranking → pattern frequency across collections.

---

## The Mechanism

**Storage architecture:**
```
Qdrant collections:
├─ imem_typescript_project
│   ├─ layer=implementation (TypeScript code)
│   └─ layer=pattern (language-agnostic)
│
├─ imem_python_project
│   ├─ layer=implementation (Python code)
│   └─ layer=pattern (language-agnostic)
│
└─ imem_rust_project
    ├─ layer=implementation (Rust code)
    └─ layer=pattern (language-agnostic)
```

**Query routing:**
```
# Single-project (implementation + pattern)
query(collection=current_project)

# Cross-project (pattern-only)
for project in all_projects:
    query(collection=project, filter={layer: 'pattern'})
merge_results()
```

---

## The Operations

**1. Pattern extraction:**
- Write implementation in project A
- Extract pattern (strip tech-specific details)
- Index both: impl (local) + pattern (global)

**2. Cross-project query:**
- Working in project B
- Query: "How did we solve X?"
- Search: All projects, pattern layer only
- Returns: Principles, not code

**3. Authority ranking:**
- Pattern appears in N projects
- Authority score = f(N, quality, recency)
- PageRank on pattern graph: most connected = most validated

**4. Application:**
- Receive pattern (principle)
- Choose implementation (project-specific tools)
- Validate pattern in current project (increases authority)

---

## The Filters

**Layer isolation:**
```
layer=implementation  # Project-specific code
layer=pattern         # Cross-project principles
```

**Scope control:**
```
--current-project     # This project only
--all-projects        # All projects
--projects=[A,B,C]    # Specific subset
```

**Contamination prevention:**
```
# Default: Safe
query --all-projects --pattern-only

# Explicit override required for cross-project implementations
query --all-projects --include-implementations --confirm-contamination
```

---

## The Benefits

**Zero code leakage:**
- Pattern queries: Tech details stripped
- Implementation queries: Project-scoped
- No accidental framework confusion

**Wisdom accumulation:**
- Same principle, multiple validations
- Authority compounds across projects
- Best practices emerge naturally

**No manual curation:**
- Extract patterns when valuable
- System detects reuse opportunities
- Progressive, not prescriptive

---

## The Anti-Pattern

**Don't:**
- Query implementations across projects (contamination)
- Skip pattern extraction (lose reuse opportunity)
- Premature abstraction (extract when validated, not speculatively)

**Do:**
- Query patterns across projects (safe)
- Extract patterns after 2nd use (validated reuse)
- Keep implementations isolated (project-specific)
