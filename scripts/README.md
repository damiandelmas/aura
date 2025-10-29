# AURA Markdown Compiler

**Philosophy:** Markdown is code. Documentation is source of truth.

## Problem: Documentation Drift

Traditional approach:
```
docs/trace.md        →  manual copy  →  ~/.claude/commands/
    ↓                                         ↓
update docs                              update commands
    ↓                                         ↓
DIVERGENCE (information leak)
```

## Solution: Markdown as Source Code

```
.context/document/runbooks/trace.md (GROUND TRUTH)
    ↓
make slash-commands (BUILD STEP)
    ↓
~/.claude/commands/aura/trace/*.md (ARTIFACTS)
```

## Usage

**Regenerate slash commands:**
```bash
cd /home/axp/projects/fleet/hangar/code/aura/main
make slash-commands
```

**Clean generated files:**
```bash
make clean-slash
```

**When to rebuild:**
- After editing trace.md
- Before committing doc changes
- When slash commands feel out of sync

## Architecture

**md_to_slash.py:**
- Extracts "Common Workflows" section from trace.md
- Parses bold titles + bash code blocks
- Generates slash command files with frontmatter

**Generated commands:**
- `/trace-discover-view` - Find and view sessions
- `/trace-export-for-documentation` - Export chronicle
- `/trace-track-code-evolution` - Review code changes

## Benefits

✅ **Single source of truth** - Edit trace.md only
✅ **Zero drift** - Commands always match docs
✅ **Version controlled** - Doc changes = behavior changes
✅ **Repeatable** - Any Claude instance can rebuild

## Extension

To extract from other runbooks:

1. Add new extractor class to `md_to_slash.py`
2. Add target to `Makefile`
3. Run build step

Pattern is reusable for any markdown → code generation workflow.
