---
session_id: "090c7e16-cb85-45e5-a1f0-8dd53f191a40"
---

# Template-as-Type-System

**The template IS the database schema.**

---

## Overview: How Structure Becomes Schema

The system works because of a convergence between **creation-time enforcement** and **parsing-time intelligence**.

AI agents write changelogs following a markdown template. The template isn't just formatting - it's a type system definition. When you write `## Decisions`, you're declaring a Decision type. When you write `### Use JWT`, you're instantiating it with required fields (Context, Solution) as structured bullet points.

LlamaIndex MarkdownNodeParser reads this hierarchy and preserves it. It recognizes H2 headers as semantic sections. It chunks at the right granularity (H3 for instances, H2 for singletons). It automatically extracts metadata from structure - `section_type` flows from H2 parent to H3 children.

The result: **An emergent database schema from document structure.**

No schema migrations. No separate DDL. The template IS the schema. Qdrant stores 15-20 typed vectors per changelog, not 1 blob. Query `section_type='Decision'` returns all Decision instances with guaranteed required fields (Context, Solution) and optional fields when present (Rationale, Alternatives).

The type system emerges from:
1. Template enforcement → AI agents create structured documents
2. Hierarchical parsing → LlamaIndex preserves the structure
3. Metadata extraction → section_type metadata flows from hierarchy

You get a typed vector database by writing markdown. Structure creates schema.

---

## The Actual Type System

**Complete type definitions from template:**

```typescript
// Singleton types (H2 = type declaration + single instance)
type Request = {
  content: string  // User quote
}

type Overview = {
  content: string  // 2-5 sentence narrative
}

// Collection types (H2 = type declaration, H3s = instances)
type Decision = {
  name: string,
  context: string,      // required
  solution: string,     // required
  alternatives?: string,
  rationale?: string,
  trade_offs?: string,
  implications?: string
}

type Constraint = {
  name: string,
  what: string,         // required
  discovery: string,    // required
  workaround: string,   // required
  impact: string,       // required
  why_non_obvious?: string,
  testing?: string
}

type Failure = {
  name: string,
  attempted: string,    // required
  why_failed: string,   // required
  lesson: string,       // required
  hypothesis?: string,
  failure_mode?: string,
  discovery?: string,
  alternative?: string
}

type Pattern = {
  name: string,
  pattern: string,      // required
  when: string,         // required
  approach: string,     // required
  benefit: string,      // required
  why?: string,
  anti_pattern?: string,
  occurrences?: string
}

type Implementation = {
  architecture?: {
    steps: string[]
  },
  code_signatures: {
    name: string,
    file_path: string,
    code: string
  }[]
}

type Audit = {
  created?: string[],
  modified?: string[],
  removed?: string[],
  configuration?: Record<string, string>,
  deployment?: string[]
}
```

---

## Type Instantiation

**Singleton types (0 or 1):**
```markdown
## Request              ← Type declaration
> "User quote"          ← Instance (inline)

## Overview             ← Type declaration
Narrative content...    ← Instance (inline)
```

**Collection types (0 to N):**
```markdown
## Decisions            ← Type declaration (empty H2)
### Use JWT            ← Decision instance 1
- Context: ...
- Solution: ...

### Use Redis          ← Decision instance 2
- Context: ...
- Solution: ...
```

---

## Chunks as Typed Vectors

**Storage:**
```typescript
{
  section_type: "Decision",        // Type from H2 parent
  section_name: "Use JWT",         // Instance name from H3
  content: {
    context: "...",
    solution: "...",
    rationale: "..."
  },
  embedding: [0.234, -0.891, ...]  // Vector
}
```

**Indexing:**
- H2 singleton types (Request, Overview) → Indexed as-is
- H2 collection type declarations → Skipped (empty)
- H3 instances under collections → Indexed with type from parent

---

## Type-Safe Queries

**Query by type:**
```python
section_type='Decision'  # Returns all Decision instances
section_type='Pattern'   # Returns all Pattern instances
section_type='Failure'   # Returns all Failure instances
```

**Type + semantic search:**
```python
section_type='Decision' + vector_similarity("authentication")
= Semantically similar Decision instances about authentication
```

**Type-aware field queries:**
```python
section_type='Decision' WHERE has_alternatives=true
= Decisions that considered alternatives
```

---

## Progressive Instantiation

**Simple changelog:**
```markdown
## Request
## Overview
## Decisions
### One Decision
## Implementation
## Audit
```
Result: Request, Overview, Decision, Implementation, Audit types instantiated

**Complex changelog:**
```markdown
## Request
## Overview
## Decisions
### Decision 1
### Decision 2
## Constraints
### Constraint 1
## Failures
### Failure 1
### Failure 2
## Implementation
## Patterns
### Pattern 1
## Audit
```
Result: All types instantiated, multiple instances of some

**Template defines possible types. Changelog instantiates actual types based on work complexity.**

---

## Why This Works

**Type system for knowledge:**
- Decision, Pattern, Failure are semantic types (not string/int)
- Types have enforced structure (fields)
- Types enable type-safe queries

**Vector + type fusion:**
- Semantic similarity (fuzzy) via vectors
- Type filtering (precise) via metadata
- Combined: "semantically similar Patterns"

**Progressive disclosure:**
- Not every changelog has every type
- Not every instance uses every optional field
- Schema flexible, structure guaranteed when present

---

## The Database

**What you query:**
```sql
-- Not actually SQL, but conceptually:
SELECT * FROM Decisions WHERE context LIKE '%auth%'
SELECT * FROM Patterns WHERE when LIKE '%async%'
SELECT * FROM Failures WHERE lesson LIKE '%race condition%'
```

**What's actually stored:**
- Typed vector chunks in Qdrant
- section_type metadata = table name
- Fields = guaranteed structure
- Embedding = semantic search

**Result:** Type-safe fuzzy search. First vector database with semantic type system.

---

## Related Concepts

See: [phase-lifecycle.md](./phase-lifecycle.md) - Type evolution across phases
See: [../vision/imem.md](../vision/imem.md) - Type system as foundational principle

**Reference:** `assets/context/develop/template/00_TEMPLATE.md` - Complete template specification
