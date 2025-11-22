---
schema_version: "v3_adaptive"
type: "architecture.namespace-isolation"
status: "completed"
keywords: "namespace git-branch storage-isolation v3 sql-first zero-config epic-1"
timestamp: "2025-11-21T15:55:00-0700"
session_id: "6c82f097-5f52-4a0e-9ce2-a85256af2b1b"
---

# Namespace Auto-Detection (v3/sql-first) - EPIC 1

## Request
> "Apply same namespace changes to sql-first branch so v2 and v3 can coexist"

## Overview
Ported namespace auto-detection from main to sql-first. Both branches now detect namespace from git branch and store data in isolated `~/.imem/namespaces/{branch}/` directories. Same project indexed by v2 and v3 = zero collision. Completes EPIC 1 for sql-first branch.

## Decisions

### Same Pattern as v2, Different Codebase
- **Context**: sql-first has different architecture (VectorStore protocol, processor chains, new CLI structure)
- **Solution**: Same `get_namespace()` logic, but applied to sql-first's file structure
- **Rationale**: Consistent isolation mechanism despite different internal architectures
- **Benefit**: Predictable storage behavior across all branches

### Storage Path Changes
- **Context**: sql-first had `project/.imem/metadata.db` conflict point in `storage/sqlite.py`
- **Solution**: `~/.imem/namespaces/sql-first/projects/{hash}/metadata.db`
- **Verification**: Tested - detects "sql-first" namespace correctly from git branch

### Key Insight: Namespace From CWD
- **Context**: If v3 indexes `/project-x/`, where does data go?
- **Solution**: Namespace from CWD's git branch, not target project
- **Implication**: Run from sql-first worktree → namespace "sql-first" regardless of target

## Constraints

### sql-first Has Different File Structure
- **What**: sql-first has `cli_new.py`, `cli/main.py`, VectorStore protocol, processor chains
- **Discovery**: Read 9 changelog files documenting sql-first's architecture evolution
- **Workaround**: Applied changes to same core files (config.py, sqlite.py, registry.py) - the protocol wrappers use these under the hood
- **Impact**: None - namespace changes apply at the storage layer, not the protocol layer

## Implementation

### Architecture
Same 5-step flow as v2:
1. `get_namespace()` detects from CWD's git → "sql-first"
2. `config.namespace_dir` → `~/.imem/namespaces/sql-first/`
3. SQLite → `~/.imem/namespaces/sql-first/projects/{hash}/metadata.db`
4. Registry → `~/.imem/namespaces/sql-first/registry.json`
5. Collections → `sql-first_imem_{hash}_context`

### Code Signatures

**Namespace Detection** (`config.py:35-74`)
```python
def get_namespace() -> str:
    """Priority: env → git branch → worktree folder → default"""
    if ns := os.getenv('IMEM_NAMESPACE'):
        return sanitize_namespace(ns)
    # git branch --show-current
    # worktree folder fallback
    return 'main'
```

**SQLite Path** (`storage/sqlite.py:34-42`)
```python
project_hash = hashlib.md5(str(project_root.resolve()).encode()).hexdigest()[:8]
project_dir = config.namespace_dir / 'projects' / project_hash
self.db_path = project_dir / 'metadata.db'
```

**Collection Naming** (`registry.py:51-55`)
```python
collections = {
    "context": f"{self.namespace}_imem_{hash_suffix}_context",
    "conversation": f"{self.namespace}_imem_{hash_suffix}_conversation"
}
```

## Patterns

### Cross-Branch Feature Porting
- **Pattern**: Apply same feature to multiple branches with different architectures
- **When**: Shared infrastructure needed across divergent codebases
- **Approach**: Identify common touchpoints (config, storage, registry) vs architecture-specific code
- **Lesson**: Namespace changes apply at storage layer - protocol wrappers inherit automatically

## Audit

### Modified
- `src/imem/config.py` - Added `get_namespace()`, `sanitize_namespace()`, namespace paths, `__post_init__`
- `src/imem/storage/sqlite.py` - Changed db_path to namespace-based central storage
- `src/imem/registry.py` - Uses `config.registry_file`, namespace-prefixed collections

### Configuration
- `IMEM_NAMESPACE` - Override auto-detection
- `IMEM_HOME` - Override `~/.imem` base

### Verification
```bash
# From sql-first worktree
cd /home/axp/projects/fleet/hangar/code/aura/worktrees/sql-first/imem
python3 -c "from src.imem.config import config; print(config.namespace)"
# Output: sql-first

ls ~/.imem/namespaces/
# master/  sql-first/  test-override/
```

### Storage Structure Created
```
~/.imem/namespaces/
├── master/       ← v2 (main branch)
├── sql-first/    ← v3 (this branch)
└── test-override/
```
