---
schema_version: "v3_adaptive"
type: "bug-fix.package-installation"
status: "completed"
keywords: "package-structure setup-py python-packaging import-paths installation"
timestamp: "2025-10-10T20:53:00-0700"
session_id: "c89a3d5f-7c8e-42d1-b9e5-c12d847f90d2"
---

# Aura V2 CLI Installation Fix

## Request
> Audit the recent AURA v2 migration and complete the installation process

## Overview
Completed a package migration by diagnosing a configuration mismatch between packaging metadata and actual code location. Restructured the codebase to follow standard packaging conventions and corrected internal module references. All three command-line interfaces now verify as working with the package properly installed and ready for production.

## Decisions

### Restructure vs. Reconfigure Setup
- **Context**: setup.py expected src/aura/cli/ but actual structure was src/cli/
- **Solution**: Moved all modules into src/aura/ subdirectory and updated setup.py to use standard find_packages()
- **Alternatives**: Updated setup.py to match flat structure (rejected - non-standard Python packaging)
- **Rationale**: Following Python packaging conventions ensures compatibility with tools, documentation, and team expectations
- **Outcome**: Standard-compliant package structure; all CLIs working; installable in production

### Import Path Correction Approach
- **Context**: Moving modules from src/ to src/aura/ broke relative imports
- **Solution**: Updated relative import paths to add one level (from ..core to ...core)
- **Alternatives**: Switch to absolute imports (rejected - reduces modularity)
- **Rationale**: Relative imports better document internal package hierarchy; easier to refactor later
- **Impact**: Required updating imports in modular_ingest.py and other service modules

## Failures

### Initial Package Structure Mismatch
- **Attempted**: Left flat structure (src/cli/, src/services/) with updated setup.py configuration
- **Why Failed**: setup.py mapping was non-standard; pip install would fail on many systems
- **Lesson**: Always follow Python packaging conventions for src layout; flatten only if absolutely necessary
- **Alternative**: Recognized need for standard hierarchy; restructured to src/aura/

## Implementation

### Architecture
Package structure transformation with import path correction:
1. Analyzed original setup.py expectations vs actual file structure
2. Identified mismatch: setup.py expected src/aura/ but files were at src/
3. Created src/aura/ subdirectory structure
4. Moved all modules from src/{cli,services,core,pulse,orca,utils} to src/aura/{cli,services,core,pulse,orca,utils}
5. Updated setup.py to use standard find_packages(where='src') with default package_dir
6. Corrected relative import paths in affected modules (services layer)
7. Cleaned build artifacts (egg-info, __pycache__)
8. Performed pip uninstall, then reinstall with pip install -e .
9. Verified all three CLI entry points work (imem, trace, orca)

### Code Signatures

**Package Discovery Configuration**
```python
# Standard layout: auto-discover packages in src/
packages=find_packages(where='src')
package_dir={'': 'src'}

# Entry points map commands to functions
entry_points={
    'console_scripts': [
        'imem=aura.cli.imem:main',
        'trace=aura.cli.trace:main',
        'orca=aura.cli.orca:main',
    ]
}
```

**Relative Import Pattern for Nested Packages**
```python
# Import depth increases with directory nesting
# One .. per level up, then the module name
from ...core.module import Component
```

## Patterns

### Import Path Adjustment for Hierarchy Changes
- **Pattern**: When moving modules deeper in package hierarchy, systematically update relative imports
- **When**: Restructuring package directories; reorganizing module hierarchy
- **Approach**: Add one level per directory moved down; from ..module becomes ...module for each level deeper
- **Benefit**: Maintains modularity; prevents circular imports; documents package structure changes
- **Replication**: Search for existing relative imports in moved modules; test imports after each change

### Standard Python Packaging Conventions
- **Pattern**: Use find_packages(where='src') with package_dir={'': 'src'} for standard src layout
- **When**: Following Python packaging best practices; ensuring tool compatibility
- **Approach**: Place packages under src/; let setuptools discover automatically
- **Benefit**: Compatible with most Python tools; matches community expectations; easier onboarding

## Audit

### Created
- `src/aura/` - New parent directory for all modules (previously src/ had direct modules)

### Modified
- `src/aura/cli/` - Moved from src/cli/
- `src/aura/services/` - Moved from src/services/
- `src/aura/services/imem/modular_ingest.py` - Updated relative import paths
- `src/aura/core/` - Moved from src/core/
- `src/aura/pulse/` - Moved from src/pulse/
- `src/aura/orca/` - Moved from src/orca/
- `src/aura/utils/` - Moved from src/utils/
- `setup.py` - Updated to use find_packages() and standard package_dir configuration

### Configuration
- **Package Discovery**: `find_packages(where='src')` automatically discovers all packages
- **Package Mapping**: `package_dir={'': 'src'}` maps root packages to src directory
- **Entry Points**: Three console scripts properly reference CLI functions
- **Dependencies**: Unchanged from previous session (5 dependencies)

### Deployment
- **Installation**: `pip install -e .` completed successfully
- **CLI Verification**:
  - `imem --help` returns vector search CLI documentation
  - `trace --help` returns conversation archaeology CLI documentation
  - `orca --help` returns agent orchestration CLI documentation
- **Status**: All CLIs working correctly; package properly installed
- **Environment**: Virtual environment clean; no stale imports or missing modules

