---
schema_version: "v3_adaptive"
type: "implementation.packaging-and-deployment"
status: "completed"
keywords: "packaging deployment pipx global-install force-flag swarms-dependency git-optional"
timestamp: "2025-10-18T20:16:08-0700"
session_id: "1f8cfd36-e1b6-4eae-9518-277cb0f07a0c"
---

# AURA Packaging Improvements: Global Installation & Git-Optional Setup

## Request
> "Create comprehensive changelog for packaging improvements: 1) Add --force flag to skip git requirement, 2) Enable global installation with pipx, 3) Add swarms dependency to setup.py for agent orchestration"

## Overview
Made the system deployable in environments that don't require version control by adding an optional bypass flag for repository checks. Enabled global installation as a standalone tool while maintaining support for agent orchestration features. Unified the initialization interface into a single command while preserving specialized operational subcommands.

## Decisions

### Make Git Repository Optional
- **Context**: Users wanted to use AURA in directories without git initialization
- **Solution**: Added `--force` flag to `aura init` that uses current directory as project root when no `.git/` found
- **Alternatives**: Could require git always, but limits use cases for scratch projects or non-git workflows
- **Rationale**: Supports non-git workflows while maintaining safe defaults with helpful error messages
- **Implications**: Non-git users can initialize AURA anywhere, but git-aware workflows maintain better traceability

### Add Swarms as Explicit Dependency
- **Context**: ClaudeAgent wrapper uses Swarms SDK for agent coordination but dependency was missing
- **Solution**: Added `"swarms>=5.0.0"` to `install_requires` in `setup.py`
- **Rationale**: Ensures all agent orchestration features work out of the box after `pip install -e .`

### Create Unified `aura` CLI Entry Point
- **Context**: System had 3 separate CLIs (`imem`, `trace`, `orca`) but no unified initialization command
- **Solution**: Added `aura=aura.cli.aura:init` entry point in `setup.py`
- **Rationale**: Single command for project setup (`aura`), specialized commands for operations (`imem`, `trace`, `orca`)
- **Implications**: Users can initialize projects without knowing about subcommands; discovery-friendly

## Constraints

### Global Tool Import Isolation
- **What**: When tools are globally installed, relative path imports break because they assume source directory context
- **Discovery**: SessionStart hook failed when running from different working directories after global installation
- **Workaround**: Rely on proper package namespace imports instead of manual path manipulation
- **Impact**: Tools must be properly installed as packages; ensures consistent behavior across execution contexts

## Implementation

### Architecture
1. User runs `aura` or `aura --force` in project directory
2. System attempts to find `.git/` walking up directory tree
3. If no git found and `--force` provided → use `Path.cwd()` as project root
4. If no git found and no `--force` → error with helpful message
5. Continue with `.context/` directory creation and hook installation

### Code Signatures

**Git-Optional Check** (CLI initialization)
```python
if not project_root:
    if force:
        project_root = Path.cwd()  # Skip requirement when flag provided
    else:
        sys.exit(1)  # Fail with message, suggest --force flag
```

**Dependency Declaration** (package configuration)
```
install_requires=[
    "swarms>=5.0.0",  # For agent orchestration features
]
```

**CLI Entry Points** (package configuration)
```
console_scripts=[
    "aura" → initialization workflow
    "imem" → vector search operations
    "trace" → session archaeology
    "orca" → agent orchestration
]
```

**Import Pattern** (installed tool)
```python
# Use package namespace imports, not relative paths
from orchestrator.registry import add_session
```

## Patterns

### Force Flag Multi-Purpose Pattern
- **Pattern**: Single `--force` flag serves dual purpose (overwrite + skip requirement)
- **When**: CLI commands have both optional checks (git requirement) and safeguards (overwrite protection)
- **Approach**: Document both behaviors in help text: "Overwrite existing configuration OR skip git requirement"
- **Benefit**: Simpler UX than `--force` + `--no-git` flags, preserves "force through obstacles" semantics
- **Anti-Pattern**: Don't create separate flags (`--no-git`, `--skip-git`) - reduces discoverability

### Clean Package Imports for Installed Tools
- **Pattern**: When tool is installed globally, import from package namespace not relative paths
- **When**: Scripts/hooks run in different execution context than package source directory
- **Approach**: Install AURA globally with `pipx install -e aura-v2/`, hooks use `from orchestrator.registry`
- **Why**: Removes fragile `sys.path.insert(0, ...)` dependencies and assumes directory structure
- **Benefit**: Tool works consistently regardless of installation location or parent directory structure

## Audit

### Modified
- `aura-v2/setup.py` - Added swarms dependency, added `aura` CLI entry point, noted template packaging
- `aura-v2/src/aura/cli/aura.py` - Added `--force` flag for git-optional initialization
- `.claude/hooks/session-start.sh` - Removed manual `sys.path` manipulation (relies on installed package)
- `CLAUDE.md` - Updated documentation examples showing `aura --force` usage

### Configuration
- **Installation**: `pipx install -e aura-v2/` for global access to `aura`, `imem`, `trace`, `orca` commands
- **Usage**: `aura` (requires git) or `aura --force` (works anywhere)
- **Dependencies**: Automatic installation of `swarms>=5.0.0` for brother spawning support
