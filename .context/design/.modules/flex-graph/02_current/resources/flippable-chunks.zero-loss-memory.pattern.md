---
session_id: ca22384b-3a6d-4821-8b70-2aa1a89ea4ba
date: 2025-10-27
level: architecture-pattern
innovation: flippable-chunks
---

# Flippable Chunks: Architecture Pattern

## Core Mechanism

**Dual indexing with metadata-based serving:**

1. **Storage:** Both implementation and pattern indexed as separate chunks
2. **Linking:** Bidirectional metadata references
3. **Serving:** Runtime decision based on supersession state

**Metadata structure:**
```
Implementation chunk:
- superseded_by: <new_chunk_id> | null
- pattern_chunk_id: <pattern_id>
- serving_mode: 'implementation' | 'pattern'

Pattern chunk:
- source_impl_id: <impl_id>
- layer: 'pattern'
- applies_to: [languages/frameworks]
```

## Serving Logic

**Query-time decision tree:**

```
retrieve(chunk_id):
  chunk = load_metadata(chunk_id)

  if chunk.superseded_by AND chunk.pattern_chunk_id:
    return load_chunk(chunk.pattern_chunk_id)  # Abstraction
  else:
    return load_chunk(chunk_id)                # Implementation

retrieve_full(chunk_id, force=True):
  return load_chunk(chunk_id)  # Always implementation
```

**No re-indexing required.** Supersession = metadata update, not content change.

## Pattern Extraction

**From implementation to abstraction:**

**Remove:**
- Framework names (Express.js → web framework)
- Library references (jsonwebtoken → token library)
- Code snippets (replace with pseudocode/principle)
- File paths (src/auth.ts → removed)
- Language-specific idioms

**Preserve:**
- Context (why this arose)
- Solution principle (what was done, abstractly)
- Rationale (why this approach)
- Constraints (discovered blockers)
- Alternatives (options rejected)

**Result:** Language-agnostic, cross-project reusable principle.

## Cross-Project Applicability

**Query modes:**

```
Default query (current project):
- Returns: Current implementations + patterns
- Superseded: Serves patterns automatically

Cross-project query:
- Returns: Patterns only (--pattern flag)
- No code contamination
- Applicable across languages
```

## Lifecycle States

```
State 1: Active Implementation
- serving_mode: 'implementation'
- superseded_by: null
- Serves: Full implementation chunk

State 2: Superseded with Pattern
- serving_mode: 'pattern'
- superseded_by: <chunk_id>
- Serves: Pattern chunk (automatically)

State 3: Superseded without Pattern
- serving_mode: 'implementation'
- superseded_by: <chunk_id>
- Serves: Implementation (with deprecation note)
- Ranked lower in results
```

## Key Properties

**Reversibility:** Force flag retrieves original implementation
**Efficiency:** O(1) metadata lookup, not O(n) search
**Preservation:** No deletion, no re-indexing
**Authority:** Patterns validated by supersession events
