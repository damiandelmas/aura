# v2/v3 Cleanup Complete

## Status: ✅ COMPLETE

Both v2 and v3 are now completely isolated and clean.

## Actions Taken

### 1. Deleted Orphaned Aura Parent Data
**Removed:**
- ✅ SQLite: `/home/axp/projects/fleet/hangar/code/aura/.imem/`
- ✅ Qdrant collections:
  - `imem_0cfe416f_context_impl` (1,356 points deleted)
  - `imem_0cfe416f_context_pattern`
  - `imem_0cfe416f_conversation` (didn't exist)

**Verified:** Qdrant now only has v2 main collections (imem_1ba1fff1_*)

### 2. Created v2 Isolated Registry
**Location:** `~/.context_v2/imem_registry.json`

**Contents:**
```json
{
    "projects": {
        "/home/axp/projects/fleet/hangar/code/aura/main": {
            "collections": {
                "context": "imem_1ba1fff1_context",
                "conversation": "imem_1ba1fff1_conversation"
            },
            "indexed_at": "2025-11-17T17:06:35.879981",
            "doc_counts": {
                "context": 207,
                "conversation": 8541
            }
        }
    }
}
```

**Data Intact:**
- SQLite: 2,455 chunks (design: 1,063, develop: 743, designate: 601, document: 46)
- Qdrant port 6334:
  - `imem_1ba1fff1_context_impl`: 3,409 points
  - `imem_1ba1fff1_conversation`: 10,276 points
  - `imem_1ba1fff1_context_pattern`: exists

### 3. Created v3 Fresh Registry
**Location:** `~/.context_v3/imem_registry.json`

**Contents:**
```json
{
    "projects": {}
}
```

**Ready for fresh indexing**

## Current State

### v2 (Qdrant-First)
```bash
imem_v2  # Sets IMEM_CONTEXT_DIR=~/.context_v2, IMEM_QDRANT_PORT=6334

Registry: ~/.context_v2/imem_registry.json
  - aura/main: 207 context, 8541 conversation docs

Qdrant (port 6334):
  - imem_1ba1fff1_context_impl: 3,409 points
  - imem_1ba1fff1_conversation: 10,276 points

SQLite: aura/main/.imem/metadata.db
  - 2,455 chunks across all phases
```

### v3 (SQLite-First)
```bash
imem_v3  # Sets IMEM_CONTEXT_DIR=~/.context_v3, IMEM_QDRANT_PORT=6335

Registry: ~/.context_v3/imem_registry.json
  - Empty (fresh start)

Qdrant (port 6335):
  - Not running (start when needed)

SQLite: Clean (no indexed data)
```

### Shared Registry (Deprecated)
**Location:** `~/.context/imem_registry.json`

**Status:** Still exists but no longer used by v2/v3 when env vars are set

**Contains:** Old data from 8 projects (kept as backup)

## Verification

### v2 Environment Variables Work
```bash
$ IMEM_CONTEXT_DIR=$HOME/.context_v2 python3 -c "from imem.config import config; print(config.context_dir)"
/home/axp/.context_v2

$ IMEM_QDRANT_PORT=6334 python3 -c "from imem.config import config; print(config.qdrant_port)"
6334
```

### v3 Environment Variables Work
```bash
$ IMEM_CONTEXT_DIR=$HOME/.context_v3 python3 -c "from imem.config import config; print(config.context_dir)"
/home/axp/.context_v3

$ IMEM_QDRANT_PORT=6335 python3 -c "from imem.config import config; print(config.qdrant_port)"
6335
```

### Qdrant Collections Clean
```bash
$ curl -s http://localhost:6334/collections
{
  "collections": [
    {"name": "imem_1ba1fff1_conversation"},
    {"name": "imem_1ba1fff1_context_pattern"},
    {"name": "imem_1ba1fff1_context_impl"}
  ]
}
```
✅ Only v2 main collections remain

## Usage

### v2 - Query Existing Data
```bash
source ~/.bashrc
imem_v2
cd /home/axp/projects/fleet/hangar/code/aura/main

# Verify registry
imem collections list

# Query (uses port 6334, ~/.context_v2/ registry)
imem search develop "patterns"
imem query-metadata --phase develop
```

### v3 - Fresh Start
```bash
source ~/.bashrc
imem_v3
cd ~/your-project

# Index fresh
imem init
imem index-metadata develop --limit 20

# Query (uses port 6335, ~/.context_v3/ registry)
imem query-metadata --phase develop --limit 10
```

## Complete Isolation Confirmed

| Resource | v2 | v3 | Isolated? |
|----------|----|----|-----------|
| Python venv | `main/imem/venv_v2/` | `sql-first/imem/venv_v3/` | ✅ |
| Registry | `~/.context_v2/imem_registry.json` | `~/.context_v3/imem_registry.json` | ✅ |
| Qdrant port | 6334 | 6335 | ✅ |
| Qdrant collections | `imem_1ba1fff1_*` (3 colls, 13,685 points) | None (fresh) | ✅ |
| SQLite | `aura/main/.imem/metadata.db` (2,455 chunks) | None (fresh) | ✅ |
| Env vars | `IMEM_CONTEXT_DIR`, `IMEM_QDRANT_PORT` | `IMEM_CONTEXT_DIR`, `IMEM_QDRANT_PORT` | ✅ |

## Next Steps

1. **Test v2 queries:**
   ```bash
   imem_v2
   cd /home/axp/projects/fleet/hangar/code/aura/main
   imem search develop "architecture" --limit 5
   ```

2. **Index fresh data with v3:**
   ```bash
   imem_v3
   cd ~/test-project
   imem init
   imem index-metadata develop --limit 20
   imem query-metadata --phase develop
   ```

3. **Compare results:**
   - Run same queries on both versions
   - Verify no cross-contamination
   - Confirm isolated registries working

## Commits

- Cleanup not yet committed (working state)
- Previous: isolation code fixes committed to both repos

## Notes

- Old registry `~/.context/imem_registry.json` kept as backup
- v2 data fully migrated and queryable
- v3 ready for fresh indexing
- Shell functions (`imem_v2`, `imem_v3`) set env vars automatically
