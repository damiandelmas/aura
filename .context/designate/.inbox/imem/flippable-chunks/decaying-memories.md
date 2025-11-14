---
session_id: "090c7e16-cb85-45e5-a1f0-8dd53f191a40"
---

# Decaying Memories: Progressive Abstraction

**Old decisions serve as principles, not outdated code.**

---

## The Problem

Superseded decisions contain valuable insights but outdated specifics.

**Traditional approach:**
- Keep everything → Noise (AI sees deprecated tech)
- Delete old → Loss (principles discarded with code)

**Conflict:** Want principles preserved, implementation details faded.

---

## The Solution

Serve different faces based on currency:

```
Current decision → Implementation face (active tech details)
Superseded decision → Pattern face (principles remain relevant)
Ancient decision → Pattern face (archaeology on explicit request)
```

**Implementation preserved. Pattern served by default.**

---

## Lifecycle Flow

```
Write time:
  Changelog created → .md file
  LLM pass → .pattern.md file (10% cost)
  Both indexed with layer metadata

Active period:
  Queries → implementation layer (.md files)

Supersession:
  New decision replaces old
  → Metadata: superseded=true
  → Queries: pattern layer (.pattern.md files)

Archive period:
  Queries → pattern layer (abstraction)
  Explicit layer filter → implementation available
```

**Property:** Natural decay without information loss.

---

## Example

**Implementation layer (.md file - when current):**
```
Decision: Async Processing
- Context: Need non-blocking API calls
- Solution: Python asyncio with event loop and coroutines
- Code: async/await syntax, asyncio.gather()
```

**Pattern layer (.pattern.md file - LLM extracted):**
```
Pattern: Non-Blocking I/O
- When: Concurrent API calls without threads
- Approach: Event loop with callback queue
- Why: Single-threaded concurrency model
```

**When superseded:**
- BRAIN intelligence routes queries to pattern layer (.pattern.md)
- Implementation layer (.md) still queryable with explicit filter

---

## The Value

**Reduced noise:**
- AI doesn't wade through deprecated asyncio syntax
- Sees principle: "non-blocking I/O pattern"

**No loss:**
- Full implementation archaeology available
- Explicit query: `serve_mode=implementation`

**Natural decay:**
- Recent = specific tech details
- Old = timeless principles
- Ancient = abstraction (unless digging)

**Progressive disclosure by age.**

---

## BRAIN Integration

**Supersession detection:**
- Temporal edges + semantic similarity
- Metadata update: `superseded=true`

**Default serving mode:**
- `superseded=false` → implementation
- `superseded=true` → pattern

**Explicit override:**
- Query parameter forces face selection
- Archaeology mode retrieves old implementation

---

## Related Concepts

See: [flippable-chunks.md](./flippable-chunks.md) - Dual-face architecture
See: [cross-project-knowledge.md](./cross-project-knowledge.md) - Pattern bridging
See: [../brain/runtime-graph-composition.md](../brain/runtime-graph-composition.md) - Supersession detection
