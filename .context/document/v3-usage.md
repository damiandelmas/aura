# IMEM v3 Usage (SQLite-First)

## Activate v3

```bash
source ~/.bashrc
imem_v3
```

## Commands (9 total)

```bash
imem init                           # Initialize project
imem index-metadata develop --limit 20   # Fast SQLite indexing
imem query-metadata --phase develop     # Query metadata
imem stats-metadata                 # Show stats
imem introspect                     # Corpus introspection
imem compose '{"search": {...}}'    # Processor pipeline
imem index develop                  # Full vector indexing (Qdrant)
imem index-conversations            # Index Claude convos
imem service start                  # Qdrant service
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

## Compare with v2

```bash
# v2 baseline
imem_v2
imem search develop "pattern" > /tmp/v2.txt

# v3 test
imem_v3
imem query-metadata --phase develop > /tmp/v3.txt

diff /tmp/v2.txt /tmp/v3.txt
```

## Environment

- **Data:** `~/.context_v3/`
- **Port:** 6335
- **Venv:** `worktrees/sql-first/imem/venv_v3/`

Switch back: `imem_v2`
