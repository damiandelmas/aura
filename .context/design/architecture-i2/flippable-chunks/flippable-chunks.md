---
session_id: "090c7e16-cb85-45e5-a1f0-8dd53f191a40"
---

# Flippable Chunks: Dual-Face Architecture

**Same chunk, two faces.**

---

## The Concept

Single chunk stores both implementation (tech-specific) and pattern (language-agnostic) content.

**Metadata flag determines which face serves:**

```typescript
{
  section_type: "Decision",
  section_name: "Async Processing",

  // Dual content
  implementation: "Use Python asyncio with event loop...",
  pattern: "Non-blocking I/O with callback queue...",

  // Serving control
  serving_mode: "implementation" | "pattern",
  superseded: false,

  // Standard metadata
  session_id: "...",
  timestamp: "..."
}
```

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
