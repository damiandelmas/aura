---
session_id: "4073f617-cac9-43a2-9362-de4411e42744"
---

#### Flippable Chunks: Serving-Time Intelligence

**Decision: Pattern chunks hidden from retrieval, served by MIND decision matrix**

**Why:**
- Single retrieval path (implementation embeddings only)
- MIND becomes serving middleware (intelligence layer)
- Zero re-indexing (metadata-driven swap)
- Centralized decay logic (not scattered)

**Storage:**
```typescript
{
  content_impl: "Python asyncio...",
  content_pattern: "Non-blocking I/O...",
  embedding: [...],  // Implementation only
  timestamp, project_id, superseded, cross_project_usage_count
}
```

**MIND serving matrix:**
```
Superseded → pattern
Cross-project → pattern
Old (timestamp > threshold) → pattern
Default → implementation
```

**Flow:**
```
Query → Vector DB (impl) → MIND swap logic → Return content
```

**Result:**
- Template writes both faces (single creation)
- Vector DB retrieves one (implementation embedding)
- MIND swaps content (serving intelligence)
- Observable usage → adaptive thresholds

**Architectural shift: Pattern content is serving-time transformation, not retrieval-time alternative.**
