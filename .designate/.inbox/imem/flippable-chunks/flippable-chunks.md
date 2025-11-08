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

**BRAIN intelligence (planned):**

Query context automatically determines layer:

```
Recent chunk + same project → Serve implementation layer
Superseded chunk → Serve pattern layer (default)
Cross-project query → Serve pattern layer only
Explicit request → Override automatic selection
```

**Current implementation:** Manual layer filtering via metadata (--pattern flag)

**Property:** Both layers indexed. Intelligence layer adds automatic selection.

---

## Storage Topology

```
changelog.md → layer='implementation', indexed
changelog.pattern.md → layer='pattern', indexed
```

**Both preserved as separate files. Query filter selects.**

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
