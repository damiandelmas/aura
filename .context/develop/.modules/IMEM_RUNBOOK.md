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

## Discovery Primitives (Advanced)

### Trace Decision Origins
```bash
imem compose '{
  "search": {"text": "routing decision", "filters": {"phase": "develop"}, "limit": 1},
  "discovery": {"genealogy": {"direction": "ancestors", "limit": 5}}
}'
```

### Design→Implementation Trail
```bash
imem compose '{
  "search": {"text": "FlexGraph", "filters": {"phase": "design"}, "limit": 1},
  "discovery": {"cross_phase": {"target_phases": ["develop"]}}
}'
```

### Find Semantic Neighbors
```bash
imem compose '{
  "search": {"text": "primitives", "limit": 1},
  "discovery": {"similar": {"limit": 3, "score_threshold": 0.7}}
}'
```

### Multi-Discovery Pattern
```bash
imem compose '{
  "search": {"text": "compose pipeline", "limit": 1},
  "discovery": {
    "siblings": {"section_types": ["Decisions"], "limit": 3},
    "similar": {"limit": 3, "score_threshold": 0.7},
    "genealogy": {"direction": "ancestors", "limit": 2}
  }
}'
```

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
