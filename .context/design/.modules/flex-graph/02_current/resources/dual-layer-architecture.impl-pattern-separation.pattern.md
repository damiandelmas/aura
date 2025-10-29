---
session_id: ca22384b-3a6d-4821-8b70-2aa1a89ea4ba
date: 2025-10-27
level: architecture-pattern
innovation: dual-layer-architecture
---

# Dual-Layer Architecture: Architecture Pattern

## Core Mechanism

**Naming convention defines layer:**

```
Implementation: 251011-1200_auth.md
Pattern: 251011-1200_auth.pattern.md

Both indexed as separate chunks
Both queryable independently
Bidirectionally linked via metadata
```

**Layer metadata:**
```json
Implementation chunk:
{
  "file_path": "...auth.md",
  "layer": "implementation",
  "pattern_chunk_id": "abc_pattern"
}

Pattern chunk:
{
  "file_path": "...auth.pattern.md",
  "layer": "pattern",
  "source_impl_id": "abc"
}
```

## Query Modes

**Implementation query (default):**
```
filter: {layer: 'implementation'}
scope: Current project
Returns: Code, frameworks, tech stack
```

**Pattern query:**
```
filter: {layer: 'pattern'}
scope: All projects (cross-project compatible)
Returns: Principles, no code
```

**Dual query:**
```
filter: None (both layers)
Returns: Both if available
```

## Pattern Extraction Rules

**Strip from pattern layer:**
- Framework names (Express.js → web framework)
- Library references (jsonwebtoken → token system)
- Code snippets (replace with pseudocode)
- File paths (src/auth.ts → removed)
- Language idioms (async/await → asynchronous)

**Preserve in pattern layer:**
- Context (why decision arose)
- Solution principle (abstractly)
- Rationale (reasoning)
- Constraints (discovered blockers)
- Alternatives (options rejected)

## Use Cases

**In-project debugging:**
```
Query: "JWT implementation details"
Mode: Implementation layer
Returns: Full TypeScript code with imports
```

**Cross-project learning:**
```
Query: "authentication patterns" --all-projects
Mode: Pattern layer
Returns: Stateless auth principle (no TypeScript)
```

**Supersession serving:**
```
Implementation superseded → Auto-serve pattern
Pattern preserved → Reusable across projects
```

## Key Properties

**Isolation:** Layers never mix unless explicit
**Bidirectionality:** Navigate impl ↔ pattern
**Independence:** Can exist without the other
**Optional:** Pattern layer not required
