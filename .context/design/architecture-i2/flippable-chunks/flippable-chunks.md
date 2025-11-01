---
session_id: "090c7e16-cb85-45e5-a1f0-8dd53f191a40"
---

# Flippable Chunks: Dual-Face Architecture

**Same chunk, two faces.**

---

## The Concept

Pattern layer created via separate .pattern.md files, not dual storage in same chunk.

**Pattern extraction workflow:**

```
Write changelog normally (.md)
    ↓
Single LLM pass (10% cost)
    ↓
Generate .pattern.md (language-agnostic abstraction)
    ↓
Both files indexed with layer='implementation' or layer='pattern'
```

**Layer filtering determines what serves:**
- Same project, active → implementation layer (.md files)
- Superseded → pattern layer (.pattern.md files)
- Cross-project → pattern layer only (.pattern.md files)

---

## Serving Logic

**Query context determines face:**

```
Recent chunk + same project → Serve implementation
Superseded chunk → Serve pattern (default)
Cross-project query → Serve pattern only
Explicit request → Serve either face
```

**Property:** Zero re-indexing. Metadata toggle, not data change.

---

## Storage Topology

```
Same chunk ID
  ├── Implementation content (expires with tech)
  └── Pattern content (eternal principles)

Metadata flag: Which face to serve by default
```

**Both preserved. Context selects.**

---

## The Value

**Enables two use cases:**

1. **Decaying memories** - Serve abstractions for old decisions, preserve implementation archaeology
2. **Cross-project knowledge** - Query patterns across projects without code pollution

**Property:** Progressive disclosure. Recent = specific, old = abstract. Full fidelity always available.

---

## Related Concepts

See: [decaying-memories.md](./decaying-memories.md) - Progressive abstraction use case
See: [cross-project-knowledge.md](./cross-project-knowledge.md) - Pattern bridging use case
See: [../database/type-system.md](../database/type-system.md) - Base type system
