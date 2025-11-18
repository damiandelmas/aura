# IMEM Runbook - What Actually Works

## Introspection (Start Here)

### Check What's Indexed
```bash
imem introspect --status
# Shows: 3608 context chunks, 1357 conversation chunks, which phases indexed
```

### Discover Available Filters
```bash
imem introspect --fields
# Shows all filterable metadata fields, what values exist, what you can filter on
```

### System Overview
```bash
imem introspect
# Shows: primitives, coverage stats, top concepts, quick start examples
```

**Use case:** Run `imem introspect --fields` before writing queries to see available filters

---

## Single Queries (Primary Usage)

### Find Decisions
```bash
imem search develop "multi-source routing" --section Decisions --limit 3
imem search design "architecture" --section Decisions
```

### Find Patterns
```bash
imem search develop "primitives" --section Patterns --limit 5
```

### Find Implementation Details
```bash
imem search develop "compose pipeline" --section Implementation
```

### Find Code Changes
```bash
imem search conversations "routing" --chunk-type patch --limit 3
```

---

## Multi-Query (Advanced Usage)

### Cross-Phase Understanding
```bash
imem compose '{
  "search": {
    "queries": [
      {"text": "routing", "filters": {"source": "context", "phase": "develop"}, "limit": 2},
      {"text": "routing", "filters": {"source": "context", "phase": "design"}, "limit": 2}
    ]
  }
}'
```

### Get Context + Related Decisions
```bash
imem compose '{
  "search": {
    "text": "FlexGraph primitives",
    "filters": {"source": "context", "phase": "develop"},
    "limit": 1
  },
  "discovery": {
    "siblings": {"limit": 3, "section_types": ["Decisions", "Patterns"]}
  }
}'
```

---

## Discovery Primitives (Compose Only)

### Get Related Sections (Siblings)
```bash
imem compose '{
  "search": {"text": "FlexGraph primitives", "limit": 1},
  "discovery": {
    "siblings": {"limit": 3, "section_types": ["Decisions", "Patterns"]}
  }
}'
# Returns primary result + related Decisions/Patterns from same file
# Works: Returns empty [] when target is only section in file (not a bug)
```

### Trace Conversation Origins (Genealogy)
```bash
imem compose '{
  "search": {"text": "routing decision", "filters": {"phase": "develop"}, "limit": 1},
  "discovery": {"genealogy": {"direction": "ancestors", "limit": 5}}
}'
# Returns conversation chunks from same session_id
```

### Track Evolution (Temporal)
```bash
imem compose '{
  "search": {"text": "routing", "limit": 1},
  "discovery": {
    "temporal": {"direction": "both", "limit": 3}
  }
}'
# Returns semantically similar chunks before/after in time
# Works: Uses 0.65 score threshold, filters by timestamp direction
# Coverage: 54% of context chunks have timestamps, 100% conversations
```

### Cross-Phase Discovery
```bash
imem compose '{
  "search": {"text": "FlexGraph", "filters": {"phase": "design"}, "limit": 1},
  "discovery": {"cross_phase": {"phase": "develop"}}
}'
# Find related content in different phase (design → develop)
# Note: Must use dict format {"phase": "develop"}, not boolean
```

---

## Discovery Requirements & Coverage

### What Makes Primitives Work

**Siblings** (same file_path):
- Requires: `file_path` metadata (100% coverage)
- Returns: Sections from same document
- Empty when: Target is only section in file (expected behavior)

**Genealogy** (conversation links):
- Requires: `session_id` in both context and conversation collections
- Current: 2/38 sessions linked (5% coverage)
- **Action needed**: Run `imem sync conversations` to index missing sessions
- Expected: 38/38 coverage after sync (~10 min indexing)

**Temporal** (time-based):
- Requires: `timestamp` field for ordering
- Current: 54% context chunks, 100% conversations
- Works: Returns semantically similar + chronologically filtered
- Missing timestamps: Chunks without timestamps still returned (no time filtering)

**Cross-Phase** (design ↔ develop):
- Requires: `phase` metadata (100% coverage)
- Works: Semantic search across phases
- Syntax: `{"phase": "target_phase"}` (dict required, not boolean)

---

## When to Use What

**Use `imem search`** when:
- Simple keyword lookup
- Single source/phase filter
- Just need top results

**Use `imem compose`** when:
- Cross-phase queries (design + develop)
- Need graph relationships (siblings, genealogy, cross_phase)
- Multi-source batch queries
- Tracing decision lineage

---

## Don't Use

**Thinking chunks** - useless noise:
```bash
imem search conversations "topic" --chunk-type thinking  # ❌ NEVER
```

---

## Quality Hierarchy

**Best:** develop/design docs with `--section Decisions|Patterns|Implementation`
**Good:** Code patches from conversations
**Bad:** User messages (hit or miss)
**Useless:** Thinking chunks

---

## Quick Reference

```bash
# Fast decision lookup
imem search develop "topic" --section Decisions --limit 3

# Fast pattern lookup
imem search develop "topic" --section Patterns --limit 5

# Cross-phase batch
imem compose '{"search": {"queries": [
  {"text": "topic", "filters": {"source": "context", "phase": "develop"}},
  {"text": "topic", "filters": {"source": "context", "phase": "design"}}
]}}'

# Check what's indexed
imem introspect --status

# See available filters
imem introspect --fields
```

**Golden rule:** Context docs > Patches > Everything else
