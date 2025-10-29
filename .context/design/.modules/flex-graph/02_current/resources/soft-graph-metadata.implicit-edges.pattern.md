---
session_id: ca22384b-3a6d-4821-8b70-2aa1a89ea4ba
date: 2025-10-27
level: architecture-pattern
innovation: soft-graph-metadata
---

# Soft-Graph via Metadata: Architecture Pattern

## Core Mechanism

**Metadata fields define implicit relationship types:**

```
Sibling relationship:
- Shared: file_path
- Query: filter(file_path=X)
- Result: All chunks from same changelog

Genealogy relationship:
- Shared: session_id
- Query: filter(session_id=Y)
- Result: All chunks from same conversation

Temporal relationship:
- Constraint: timestamp>Z AND semantic_similarity>0.7
- Query: filter(timestamp>Z) + semantic search
- Result: Evolution chain

Pattern relationship:
- Naming: .md → .pattern.md
- Query: search(file_path.replace('.md', '.pattern.md'))
- Result: Abstraction variant
```

## Relationship Discovery

**Query-time traversal:**

```
Start: Decision chunk
Navigate siblings: filter(file_path=decision.path)
Navigate genealogy: filter(session_id=decision.session)
Navigate temporal: filter(timestamp>decision.time, semantic_similar)
Navigate pattern: search(decision.path.replace('.md', '.pattern.md'))
```

**No edges stored. All relationships discovered via metadata queries.**

## Key Properties

**Zero precomputation:** Relationships don't exist until queried
**Zero maintenance:** Metadata changes auto-update relationships
**Flexible:** New relationship types = new metadata fields
**Context-adaptive:** Relationships discovered per query context

## Trade-Offs

**Slower:** Metadata query slower than indexed edge traversal
**Flexible:** Can define new relationships without migration
**Ideal for:** Evolving knowledge, AI agent memory
**Not ideal for:** High-frequency graph analytics
