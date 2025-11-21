---
schema_version: "v3_adaptive"
type: "refactor.indexing-flexibility"
status: "completed"
keywords: "path-based indexing phase-detection cli arbitrary-paths metadata-first"
timestamp: "2025-11-19T15:15:00-0700"
session_id: "28de8ddb-d72f-4247-ac0e-65126d040c26"
---

# Path-Based Indexing Support

## Request
> "perhaps we just let it be imem index 'file/path'?"

## Overview
Removed hardcoded `.context/` directory requirement from v3 indexing pipeline. Now supports indexing markdown files from arbitrary paths while maintaining backward compatibility. Phase detection switched from path-parts parsing to string pattern matching for flexibility.

## Decisions

### String-Based Phase Detection
- **Context**: v3's `_detect_phase()` required `.context` literal in path parts, breaking on arbitrary paths
- **Solution**: Changed to substring matching (`/develop/` anywhere in path) matching v2's approach
- **Rationale**: Eliminates directory structure assumptions while preserving phase detection accuracy

### Optional Path Argument
- **Context**: CLI hardcoded `project_root / '.context'` as index target
- **Solution**: Added optional `path` argument with `.context/` as fallback default
- **Benefit**: Users can index any directory while maintaining backward compatibility

## Implementation

### Code Signatures

**Phase Detection** (`imem/src/imem/parse/markdown.py:73`)
```python
def _detect_phase(self, file_path: Path) -> str:
    """Extract phase from any path containing phase directory name"""
    path_str = str(file_path)

    if '/design/' in path_str:
        return 'design'
    elif '/develop/' in path_str:
        return 'develop'
    # ... document, designate
    else:
        return 'unknown'
```

**CLI Command** (`imem/src/imem/cli.py:1546`)
```python
@imem.command('index-metadata')
@click.argument('path', type=click.Path(exists=True), required=False)
def index_metadata(path, force, limit):
    # Defaults to .context/ if no path provided
    if path:
        target_dir = Path(path)
    else:
        target_dir = project_root / '.context'
```

## Audit

### Modified
- `imem/src/imem/parse/markdown.py` - Replaced `.context` path-parts detection with string matching
- `imem/src/imem/cli.py` - Added optional path argument to index-metadata command

### Testing
- ✅ Backward compatible with `.context/` structure
- ✅ Indexes arbitrary paths: `imem index-metadata /any/path/develop/`
- ✅ Phase auto-detected from directory names in path
- ✅ Queries work correctly with detected phases
