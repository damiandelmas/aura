# v2/v3 Isolation Audit

## Problem Identified

**No actual isolation** - both versions share:
- ✅ Separate venvs (works)
- ❌ Same registry: `~/.context/imem_registry.json`
- ❌ Same Qdrant: `localhost:6334` (port 6335 never started)
- ❌ Same data dirs: Project-local `.imem/` (not `~/.context_v2` vs `~/.context_v3`)

## Current State

### Registry (Shared)
```json
~/.context/imem_registry.json
```

Registered projects (8 total):
1. `/home/axp/projects/fleet/hangar/code/aura/main`
   - Collections: `imem_1ba1fff1_context`, `imem_1ba1fff1_conversation`
   - Indexed: 207 context, 8541 conversation docs

2. `/home/axp/projects/fleet/hangar/code/aura/worktrees/sql-first/imem`
   - Collections: `imem_7dbad2f0_context`, `imem_7dbad2f0_conversation`
   - Indexed: 0 context, 0 conversation docs

3. `/home/axp/projects/fleet/hangar/code/aura` (parent dir)
   - Also registered

### Qdrant (Shared - Port 6334 Only)

Collections on port 6334:
```
imem_1ba1fff1_context_impl     3,409 points (v2 main repo)
imem_1ba1fff1_conversation    10,276 points (v2 conversations)
imem_1ba1fff1_context_pattern
imem_0cfe416f_context_impl    (aura parent dir)
imem_0cfe416f_context_pattern
```

Port 6335: **Not running** (no service started)

### SQLite (Project-Local)

**v2 main:**
- Location: `/home/axp/projects/fleet/hangar/code/aura/main/.imem/metadata.db` (5.5MB)
- Chunks: 2,455
- By phase:
  - design: 1,063
  - designate: 601
  - develop: 743
  - document: 46
  - unknown: 2

**v3 sql-first:**
- Location: `/home/axp/projects/fleet/hangar/code/aura/worktrees/sql-first/imem/.imem/metadata.db` (36KB)
- Chunks: 0

**v2 testing:**
- Location: `/home/axp/projects/fleet/hangar/code/aura/main/.testing/251117-2019_imem/.imem/metadata.db`

### Missing Isolation Directories

```bash
ls ~/.context_v2/  # Does not exist
ls ~/.context_v3/  # Empty (created but unused)
```

## Root Cause

**Environment variables not read by IMEM code:**

The shell functions set:
```bash
export IMEM_CONTEXT_DIR="$HOME/.context_v2"
export IMEM_QDRANT_PORT="6334"
```

But IMEM code likely:
1. Hardcodes `~/.context/` for registry
2. Hardcodes port `6334` for Qdrant
3. Uses project-local `.imem/` for SQLite (not `IMEM_CONTEXT_DIR`)

## Actual Behavior

When you run `imem_v2` or `imem_v3`:
- ✅ Correct Python venv activated
- ✅ Environment variables set
- ❌ IMEM code ignores `IMEM_CONTEXT_DIR`
- ❌ IMEM code ignores `IMEM_QDRANT_PORT`
- ❌ Both versions use same registry
- ❌ Both versions use same Qdrant instance

## What's "Working"

The different **venvs** mean:
- v2 uses `imem.cli:imem` (legacy CLI, 14 commands)
- v3 uses `imem.cli_new:imem` (new CLI, 9 commands)

But both versions:
- Register to same file
- Query same Qdrant
- Have separate SQLite DBs (only because they're project-local)

## Why Confusion

1. **Registry shows both repos:**
   - `aura/main` (v2)
   - `aura/worktrees/sql-first/imem` (v3)
   - Both in same file → looks like overlap

2. **Qdrant shows mixed collections:**
   - `imem_1ba1fff1_*` (v2 main)
   - `imem_0cfe416f_*` (aura parent)
   - No `imem_7dbad2f0_*` yet (v3 never indexed to Qdrant)

3. **SQLite works independently:**
   - v2: 2,455 chunks in `main/.imem/`
   - v3: 0 chunks in `sql-first/imem/.imem/`
   - Appears isolated (by accident, not design)

## What Needs Fixing

### Option A: Make Environment Variables Work

Update IMEM code to respect:
```python
# In config.py or wherever paths are set
CONTEXT_DIR = os.getenv("IMEM_CONTEXT_DIR", Path.home() / ".context")
QDRANT_PORT = int(os.getenv("IMEM_QDRANT_PORT", "6334"))
```

Then:
- Registry: `$IMEM_CONTEXT_DIR/imem_registry.json`
- Qdrant: `localhost:$IMEM_QDRANT_PORT`

### Option B: Accept Shared State

Since SQLite is already project-local:
- Keep shared registry (harmless)
- Keep shared Qdrant (collections don't collide due to hash)
- Only isolation needed: separate venvs (already works)

Result: "Good enough" for testing if you don't mind seeing all projects in both versions.

### Option C: Namespace by Version

Add version prefix to collections:
```python
# v2
collection_name = f"imem_v2_{hash}_context"

# v3
collection_name = f"imem_v3_{hash}_context"
```

Allows shared Qdrant, clear separation in registry.

## Recommendation

**Option A** (proper isolation) if you want true v2/v3 separation for production.

**Option B** (accept shared state) if just testing and SQLite isolation is enough.

**Option C** (namespace) as middle ground - shared infra, logical separation.

## Current Risk

Low - because:
- Collection names are hashed (unlikely collision)
- SQLite is project-local (actual data isolated)
- Venvs prevent code mixing

But confusing because registry shows "everything everywhere."
