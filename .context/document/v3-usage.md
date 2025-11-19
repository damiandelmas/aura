# IMEM v3 Usage (SQLite-First)

## How Version Switching Works

The `imem_v3` shell function sets environment variables that **persist** in your terminal:
- `IMEM_CONTEXT_DIR=~/.context_v3/`
- `IMEM_QDRANT_PORT=6335`
- Activates venv at `worktrees/sql-first/imem/venv_v3/`

Once set, **all subsequent `imem` commands** in that terminal use v3 until you run `imem_v2` to switch back.

## Activate v3

**Important:** Run `imem_v3` first to activate the v3 environment. This sets environment variables that persist for all subsequent `imem` commands in that terminal session.

```bash
source ~/.bashrc
imem_v3  # Activates v3 - stays active until you switch
```

Now all `imem` commands use v3 (port 6335, `~/.context_v3/`).

## Commands (9 total)

```bash
imem init                                # Initialize project
imem index-metadata develop --limit 20   # Fast SQLite indexing
imem query-metadata --phase develop     # Query metadata
imem stats-metadata                      # Show stats
imem introspect                          # Corpus introspection
imem compose '{"search": {...}}'         # Processor pipeline
imem index develop                       # Full vector indexing (Qdrant)
imem index-conversations                 # Index Claude convos
imem service start                       # Qdrant service
```

## Core Workflow

```bash
imem_v3
cd ~/your-project

# Fast metadata-only indexing
imem init
imem index-metadata develop --limit 50

# Query
imem query-metadata --phase develop --limit 10
imem stats-metadata

# Compose pipeline
imem compose '{"search": {"mode": "metadata", "filters": {"phase": "develop"}}}'
```

## Iteration

Editable install - changes are instant:

```bash
cd ~/path/to/sql-first/imem
vim src/imem/compose/orchestrator.py
# Test immediately, no reinstall
imem compose '...'
```

## Switching Between Versions

**Same terminal:**
```bash
# Start with v3
imem_v3
imem query-metadata --phase develop
# All commands use v3...

# Switch to v2
imem_v2
imem search develop "pattern"
# All commands now use v2...

# Switch back
imem_v3
imem stats-metadata
# Back to v3
```

**Parallel terminals:**
```bash
# Terminal 1
imem_v2
imem search develop "pattern"
# Always v2

# Terminal 2
imem_v3
imem query-metadata --phase develop
# Always v3
```

**Check current version:**
```bash
imem_status
# Shows: IMEM_CONTEXT_DIR, IMEM_QDRANT_PORT, VIRTUAL_ENV
```

## Compare Results

```bash
# Index same project with both versions
cd ~/my-project

# v2
imem_v2
imem init
imem index develop --limit 20
imem search develop "pattern" > /tmp/v2.txt

# v3 (same project)
imem_v3
imem init
imem index-metadata develop --limit 20
imem query-metadata --phase develop > /tmp/v3.txt

# Compare
diff /tmp/v2.txt /tmp/v3.txt
```

## Environment

- **Data:** `~/.context_v3/`
- **Port:** 6335
- **Venv:** `worktrees/sql-first/imem/venv_v3/`

Switch back: `imem_v2`
