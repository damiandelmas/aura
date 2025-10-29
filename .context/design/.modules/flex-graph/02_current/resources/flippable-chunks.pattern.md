---
session_id: eee3b7a5-3870-4b50-984c-19eb2e2fa729
date: 2025-10-27
type: pattern.architecture
resolution: level-2a
keywords: "dual-chunk-indexing metadata-flip serving-strategy"
---

# Flippable Chunks: Architecture Pattern

## The Pattern

**Dual-chunk indexing with runtime serving strategy.**

Every knowledge artifact → 2 indexed chunks:
1. Implementation chunk (tech-specific)
2. Pattern chunk (abstraction)

Supersession → Metadata flip, not deletion.

Serving → Query-time decision based on metadata state.

---

## The Mechanism

**Storage (both indexed):**
```
Chunk A: implementation.md
  metadata: {superseded_by: chunk_B_id, pattern_chunk: chunk_A_pattern_id}

Chunk A_pattern: implementation.pattern.md
  metadata: {source_impl: chunk_A_id, layer: 'pattern'}

Chunk B: new_implementation.md
  metadata: {supersedes: chunk_A_id}
```

**Serving logic:**
```
if chunk.superseded AND chunk.pattern_exists:
    serve(chunk.pattern)  # Abstraction
else:
    serve(chunk.impl)     # Current

# Override:
serve(chunk.impl, force=true)  # Archaeological mode
```

---

## The Operations

**1. Create decision:**
- Index implementation chunk
- Optionally index pattern chunk
- Link via metadata

**2. Supersede decision:**
- Set `superseded_by` on old chunk
- Set `supersedes` on new chunk
- No deletion, no re-index

**3. Query decision:**
- Retrieve chunk
- Check supersession state
- Serve pattern or implementation

**4. Force full resolution:**
- Retrieve chunk
- Ignore supersession state
- Serve implementation

---

## The Benefits

**No re-indexing:**
- Supersession = O(1) metadata update
- Both chunks remain indexed
- Serving logic handles flip

**Reversible:**
- Default serves abstraction
- Force flag serves precision
- No information destroyed

**Progressive:**
- Write implementation first
- Extract pattern later (optional)
- System prompts when valuable

---

## The Anti-Pattern

**Don't:**
- Delete superseded chunks
- Re-index on supersession
- Serve only patterns (lose precision)
- Serve only implementations (lose abstraction)

**Do:**
- Index both layers
- Flip at query time
- Preserve full resolution
- Default to abstraction
