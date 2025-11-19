# v2/v3 Data Audit - Current State

## Registry Analysis

### Shared Registry (`~/.context/imem_registry.json`)
**Status:** Still in use (pre-isolation)

**Registered Projects (8 total):**

1. **`/home/axp/projects/fleet/hangar/code/aura/main`** (v2 repo)
   - Collections: `imem_1ba1fff1_context`, `imem_1ba1fff1_conversation`
   - Indexed: 2025-11-17 17:06
   - Registry claims: 207 context, 8541 conversation docs

2. **`/home/axp/projects/fleet/hangar/code/aura`** (aura parent)
   - Collections: `imem_0cfe416f_context`, `imem_0cfe416f_conversation`
   - Indexed: 2025-11-17 21:18
   - Registry claims: 0 context, 0 conversation docs

3. **`/home/axp/projects/fleet/hangar/code/aura/worktrees/sql-first/imem`** (v3 repo)
   - Collections: `imem_7dbad2f0_context`, `imem_7dbad2f0_conversation`
   - Indexed: 2025-11-17 21:17
   - Registry claims: 0 context, 0 conversation docs

4-8. Other projects (npta, sandbox) - not relevant to v2/v3 testing

### Isolated Registries (New)
- `~/.context_v2/`: **Empty** (isolation setup complete, never used)
- `~/.context_v3/`: **Empty** (isolation setup complete, never used)

## Qdrant Analysis

### Port 6334 (Shared - Pre-Isolation)
**Collections (5 total):**

1. **`imem_1ba1fff1_context_impl`** (v2 main - actual data)
   - Points: **3,409**
   - Source: aura/main repo
   - Pattern: `_impl` suffix (new indexing format)

2. **`imem_1ba1fff1_conversation`** (v2 main)
   - Points: **10,276**
   - Source: aura/main conversations

3. **`imem_1ba1fff1_context_pattern`** (v2 main)
   - Points: Unknown (pattern collection)

4. **`imem_0cfe416f_context_impl`** (aura parent - UNEXPECTED)
   - Points: **1,356**
   - Source: aura parent directory
   - **Issue:** Registry says 0 docs, but Qdrant has 1,356 points
   - **Likely:** Test indexing from Nov 17 21:18

5. **`imem_0cfe416f_context_pattern`** (aura parent)
   - Points: Unknown

### Port 6335 (Isolated v3)
**Status:** Not running (no Qdrant service started on this port)

## SQLite Analysis

### v2 Main (`/home/axp/projects/fleet/hangar/code/aura/main/.imem/metadata.db`)
- **Size:** 5.5 MB
- **Chunks:** 2,455
- **Breakdown:**
  - design: 1,063
  - develop: 743
  - designate: 601
  - document: 46
  - unknown: 2
- **Source:** Indexed from v2 main repo `.context/` directories

### Aura Parent (`/home/axp/projects/fleet/hangar/code/aura/.imem/metadata.db`)
- **Size:** 148 KB
- **Chunks:** 40
- **Breakdown:**
  - develop: 40
- **Source:** Test indexing from aura parent (Nov 17 smoke tests)
- **Issue:** This is from v3 testing! (imem index-metadata develop --limit 5)

### v3 sql-first (`/home/axp/projects/fleet/hangar/code/aura/worktrees/sql-first/imem/.imem/metadata.db`)
- **Size:** 36 KB
- **Chunks:** 0
- **Status:** Never indexed to

## Cross-Contamination Found

### Issue 1: Aura Parent Has v3 Test Data
**What happened:**
1. During v3 smoke testing (Nov 17 21:18)
2. Ran: `cd /home/axp/projects/fleet/hangar/code/aura && imem index-metadata develop --limit 5`
3. This indexed aura **parent** directory, not sql-first branch
4. Created 40 chunks in SQLite
5. Created 1,356 points in Qdrant (collection `imem_0cfe416f_context_impl`)

**Impact:**
- Registry shows aura parent as "0 docs" but Qdrant has 1,356 points
- SQLite shows 40 chunks
- This is orphaned test data

**Root cause:** Ran test from wrong directory (aura parent vs aura/worktrees/sql-first)

### Issue 2: All Using Shared Registry
**What happened:**
- Both v2 and v3 still writing to `~/.context/imem_registry.json`
- Isolated registries (`~/.context_v2/`, `~/.context_v3/`) created but never used
- Environment variable fixes committed but not tested end-to-end

**Impact:**
- No actual isolation yet
- All versions see all projects
- Can't tell which version indexed what (except by timestamp)

## Clean Data (v2 Main)

✅ **v2 main repository data is clean:**
- SQLite: 2,455 chunks across all phases
- Qdrant: 3,409 context + 10,276 conversation points
- Collections properly prefixed: `imem_1ba1fff1_*`
- Indexed: Nov 17 17:06 (before v3 testing)

## What Needs Cleaning

1. **Aura parent orphaned data:**
   - Delete `imem_0cfe416f_*` collections from Qdrant
   - Delete `/home/axp/projects/fleet/hangar/code/aura/.imem/metadata.db`
   - Remove from registry

2. **Test isolation properly:**
   - Actually use `imem_v2` / `imem_v3` shell functions
   - Verify data goes to `~/.context_v2/` and `~/.context_v3/`
   - Confirm separate Qdrant services on different ports

3. **Registry cleanup:**
   - Migrate v2 main data to `~/.context_v2/imem_registry.json`
   - Start fresh with v3 in `~/.context_v3/imem_registry.json`
   - Keep old registry as backup

## Recommendations

### Option A: Clean Slate
1. Stop Qdrant
2. Delete aura parent orphaned data
3. Test v2 with isolation: `imem_v2 && cd ~/test-project && imem init`
4. Test v3 with isolation: `imem_v3 && cd ~/test-project && imem init`
5. Verify separate registries created

### Option B: Migrate v2, Fresh v3
1. Copy `~/.context/imem_registry.json` → `~/.context_v2/imem_registry.json`
2. Update v2 paths to use `~/.context_v2/`
3. Delete aura parent data
4. Start v3 fresh with proper isolation

### Option C: Accept Current State
- v2 main data is clean and usable
- Ignore aura parent orphaned data (harmless)
- Start using isolation going forward
- Old data stays in `~/.context/`, new data in isolated dirs

## Next Steps

1. **Choose cleanup strategy** (A, B, or C)
2. **Test isolation end-to-end:**
   ```bash
   imem_v2
   cd ~/test-project
   imem init
   ls ~/.context_v2/  # Should have registry

   imem_v3
   cd ~/test-project
   imem init
   ls ~/.context_v3/  # Should have separate registry
   ```
3. **Verify no cross-talk** between versions
4. **Document final state**
