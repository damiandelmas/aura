# IMEM v2/v3 Isolation Setup

## Overview

Full isolation between IMEM v2 (Qdrant-first) and v3 (SQLite-first) using:
- Separate Python venvs
- Separate data directories
- Different Qdrant ports
- Shell functions for easy switching

## Architecture

```
v2 (main branch):
- Venv: ~/projects/fleet/hangar/code/aura/main/imem/venv_v2
- Data: ~/.context_v2/
- Port: 6334
- Entry: imem.cli:imem (legacy CLI, 14 commands)

v3 (sql-first branch):
- Venv: ~/projects/fleet/hangar/code/aura/worktrees/sql-first/imem/venv_v3
- Data: ~/.context_v3/
- Port: 6335
- Entry: imem.cli_new:imem (new CLI, 9 commands)
```

## Shell Functions

Added to `~/.bashrc`:

```bash
# IMEM v2 - Main branch
imem_v2() {
    export IMEM_CONTEXT_DIR="$HOME/.context_v2"
    export IMEM_QDRANT_PORT="6334"
    export VIRTUAL_ENV="/home/axp/projects/fleet/hangar/code/aura/main/imem/venv_v2"
    export PATH="$VIRTUAL_ENV/bin:$PATH"
    export PS1="(imem-v2) \u@\h:\w\$ "
    echo "✅ Switched to IMEM v2"
}

# IMEM v3 - SQL-first branch
imem_v3() {
    export IMEM_CONTEXT_DIR="$HOME/.context_v3"
    export IMEM_QDRANT_PORT="6335"
    export VIRTUAL_ENV="/home/axp/projects/fleet/hangar/code/aura/worktrees/sql-first/imem/venv_v3"
    export PATH="$VIRTUAL_ENV/bin:$PATH"
    export PS1="(imem-v3) \u@\h:\w\$ "
    echo "✅ Switched to IMEM v3"
}

# Check current config
imem_status() {
    echo "Current IMEM Configuration:"
    echo "  IMEM_CONTEXT_DIR: ${IMEM_CONTEXT_DIR:-not set}"
    echo "  IMEM_QDRANT_PORT: ${IMEM_QDRANT_PORT:-not set}"
    echo "  VIRTUAL_ENV: ${VIRTUAL_ENV:-not set}"
}
```

## Usage

### Switch Versions

```bash
# In new terminal (source ~/.bashrc first if needed)
imem_v2      # Activate v2
imem --help  # Shows v2 commands (14 total)

imem_v3      # Activate v3
imem --help  # Shows v3 commands (9 total)

imem_status  # Check which version active
```

### Verify Isolation

```bash
# Test v2
imem_v2
which imem     # → .../main/imem/venv_v2/bin/imem
echo $IMEM_CONTEXT_DIR  # → ~/.context_v2

# Test v3
imem_v3
which imem     # → .../sql-first/imem/venv_v3/bin/imem
echo $IMEM_CONTEXT_DIR  # → ~/.context_v3
```

### Development Workflow

Both use **editable installs** (`pip install -e`), so changes are instant:

```bash
# Work on v3
imem_v3
cd ~/projects/fleet/hangar/code/aura/worktrees/sql-first/imem

# Edit code
vim src/imem/compose/orchestrator.py

# Test immediately (no reinstall)
cd ~/some-project
imem compose '{"search": {"mode": "metadata"}}'  # Uses edited code
```

### A/B Testing

```bash
# Test v2 on a project
imem_v2
cd ~/my-project
imem search develop "routing" > /tmp/v2-results.txt

# Test v3 on same project
imem_v3
cd ~/my-project
imem query-metadata --phase develop --limit 10 > /tmp/v3-results.txt

# Compare
diff /tmp/v2-results.txt /tmp/v3-results.txt
```

## Command Differences

### v2 (14 commands - legacy CLI)
- `search`, `retrieve`, `serve`, `init`, `index`, `collections`, `introspect`
- `dedupe`, `compose`, `query-metadata`, `stats-metadata`, `index-metadata`
- `conversations`, `index-conversations`

### v3 (9 commands - new CLI)
- `init`, `index`, `index-conversations`, `index-metadata`
- `query-metadata`, `stats-metadata`, `introspect`
- `compose`, `service`

## Data Isolation

Each version maintains separate:
- **Registry**: `~/.context_v2/imem_registry.json` vs `~/.context_v3/imem_registry.json`
- **SQLite**: `~/.context_v2/metadata.db` vs `~/.context_v3/metadata.db`
- **Qdrant**: Different ports (6334 vs 6335) → different Docker volumes
- **Corpus**: `~/.context_v2/corpus.db` (v2) vs none (v3 uses SQLite VectorStore)

## Running Simultaneously

Because different ports:
```bash
# Terminal 1
imem_v2
imem service start  # Port 6334

# Terminal 2
imem_v3
imem service start  # Port 6335

# Both Qdrant services running on different ports
```

## Cleanup

```bash
# Remove v2 isolation
rm -rf ~/projects/fleet/hangar/code/aura/main/imem/venv_v2
rm -rf ~/.context_v2

# Remove v3 isolation
rm -rf ~/projects/fleet/hangar/code/aura/worktrees/sql-first/imem/venv_v3
rm -rf ~/.context_v3

# Remove shell functions (edit ~/.bashrc)
```

## Iteration Workflow

### Scenario: Testing v3 changes against v2 baseline

1. **Baseline with v2**
```bash
imem_v2
cd ~/test-project
imem search develop "architecture" > /tmp/baseline.txt
```

2. **Edit v3 code**
```bash
imem_v3
cd ~/projects/fleet/hangar/code/aura/worktrees/sql-first/imem
vim src/imem/compose/processors/search.py  # Make changes
```

3. **Test v3 instantly**
```bash
cd ~/test-project
imem compose '{"search": {"mode": "metadata"}}' > /tmp/experimental.txt
```

4. **Compare**
```bash
diff /tmp/baseline.txt /tmp/experimental.txt
```

5. **Iterate** - Edit code, test immediately (no reinstall needed)

## Notes

- **Zero conflicts**: Separate venvs, data dirs, ports
- **Instant iteration**: Editable installs (`pip install -e`)
- **Easy comparison**: Same command name, switch with shell function
- **Parallel execution**: Different ports allow simultaneous use
- **Clean isolation**: No shared state except code (which is in separate worktrees)

## Verification

Setup verified:
- ✅ v2 venv created: `main/imem/venv_v2/`
- ✅ v3 venv created: `worktrees/sql-first/imem/venv_v3/`
- ✅ v2 CLI works: 14 commands shown
- ✅ v3 CLI works: 9 commands shown (after entry point fix)
- ✅ Shell functions added to `~/.bashrc`
- ✅ Editable installs configured
