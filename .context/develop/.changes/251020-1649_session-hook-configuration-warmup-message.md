---
schema_version: "v3_adaptive"
type: "bug-fix.session-hook-configuration"
status: "completed"
keywords: "session-start-hook warmup-message hook-configuration user-level-hooks sessionid-injection"
timestamp: "2025-10-20T16:49:00-0700"
session_id: "d560e433-2ff1-438a-bd38-1e2d589ffcea"
---

# SessionStart Hook Configuration & Warmup Message Investigation

## Request
> "Debug why conversations show 'Warmup' as first message when I'm not sending it"

## Overview
Debugged initialization behavior and discovered two distinct issues. The system sends an automatic cache optimization message at startup as intended. Separately, hook scripts existed but were not activated in settings, preventing automatic context injection. Resolved both by documenting the intended cache priming behavior and enabling hook configuration. This unblocked automatic session registration workflows.

## Decisions

### Cache Priming is Intentional Optimization
- **Context**: Initial message appears before user interaction, causing concern about unexpected behavior
- **Discovery**: System automatically primes resource caches at startup to optimize response times
- **Decision**: Keep cache priming behavior as-is
- **Rationale**: Reduces latency for first user interaction by preloading system prompts and metadata

### User-Level Hook Over Project-Level Hooks
- **Context**: SessionStart hooks duplicated across multiple projects (RUNWAY, imem-suite)
- **Decision**: Migrate to single user-level hook at `~/.claude/hooks/session-start.sh`
- **Rationale**: DRY principle, zero per-project configuration, easier maintenance
- **Implementation**: Removed project-level hooks and settings, consolidated to `~/.claude/`

### Hook Must Be Configured in settings.json
- **Context**: Hook script existed but wasn't running (SESSION_ID not being injected)
- **Discovery**: `~/.claude/settings.json` had `"hooks": null` - no hook configuration!
- **Decision**: Add `"hooks"` section to `~/.claude/settings.json` to actually call the script
- **Rationale**: Claude Code needs explicit configuration to know which hooks to run

## Implementation

### Architecture
1. Debugged "Warmup" message source and identified Claude Code internal cache optimization
2. Traced SessionStart hook execution path and discovered hook existed but wasn't configured
3. Inspected `~/.claude/settings.json` and found missing `"hooks"` configuration section
4. Added hook configuration to settings.json to enable hook execution on session start
5. Verified SESSION_ID injection into conversation context via updated hook configuration

### Code Signatures

**Hook Project Detection Pattern** (`~/.claude/hooks/session-start.sh`)
```bash
# Skip if spawned as brother instance
[[ -n "${CLAUDE_IS_BROTHER:-}" ]] && exit 0

# Walk up to find project root
while [[ "$PROJECT_ROOT" != "/" ]]; do
    [[ -d "$PROJECT_ROOT/.git" ]] && break
    PROJECT_ROOT=$(dirname "$PROJECT_ROOT")
done

# Check for AURA, register session if available
[[ -d "$PROJECT_ROOT/aura-v2/src/orchestrator" ]] && python -c "from orchestrator.registry import add_session; add_session('$SESSION_ID')"
```

**Hook Activation** (`~/.claude/settings.json`)
```json
{
  "hooks": {
    "SessionStart": [{
      "matcher": "*",
      "hooks": [{"type": "command", "command": "/home/axp/.claude/hooks/session-start.sh"}]
    }]
  }
}
```

## Patterns

### User-Level Hook with Project Detection
- **Pattern**: Single user-level hook that detects project capabilities and adapts behavior
- **When**: Hook needs to work across multiple projects with different configurations
- **Approach**: Check for `aura-v2/` or `aura/` directories, gracefully skip if not found
- **Benefit**: Zero per-project configuration, works automatically for all AURA projects

### Graceful Module Import Failure
- **Pattern**: Wrap imports in try/except with silent pass for missing modules
- **When**: Hook runs in environments where dependencies may not be available
- **Approach**: `try: import module; except ImportError: pass`
- **Benefit**: Hook doesn't block session start if AURA not installed

### SESSION_ID Injection via hookSpecificOutput
- **Pattern**: Hook outputs JSON with `additionalContext` containing SESSION_ID text
- **When**: Claude agent needs session metadata that's not available in environment
- **Approach**: Hook injects text that becomes part of conversation context Claude can read
- **Benefit**: Slash commands can extract SESSION_ID via grep from conversation history

## Audit

### Created
- None (all files already existed)

### Modified
- `~/.claude/hooks/session-start.sh` - Added graceful error handling, PYTHONPATH export, project detection
- `~/.claude/settings.json` - Added `"hooks"` configuration to actually call SessionStart hook
- Removed `/home/axp/projects/shared/RUNWAY/.claude/hooks/session-start.sh` (migrated to user-level)
- Removed `/home/axp/projects/shared/RUNWAY/.claude/settings.json` (migrated to user-level)
- Removed `/home/axp/projects/aura-retrieval-qdrant/aura/projects/imem-suite/main/.claude/hooks/session-start.sh`
- Removed `/home/axp/projects/aura-retrieval-qdrant/aura/projects/imem-suite/main/.claude/settings.json`

### Configuration
Hook behavior:
- Runs on every Claude Code session start
- Detects AURA projects automatically (checks for `aura-v2/` or `aura/`)
- Skips non-AURA projects silently
- Respects `CLAUDE_IS_BROTHER` environment variable (doesn't register brother spawns)
- Injects SESSION_ID into conversation context for slash command extraction

Testing:
```bash
# Start new Claude Code session
claude

# Session ID should appear at start:
# SESSION_ID: 7e938201-ac2a-483d-a7ee-77e64849e2f6
#
# Use /log:develop to create changelog for this conversation.

# Also visible in status line at bottom
```

Session ID extraction:
```bash
# Slash commands can now extract session ID from conversation context
grep -oP 'SESSION_ID:\s*\K[0-9a-f-]{36}' <<< "conversation text"
```
