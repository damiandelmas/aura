---
schema_version: "v3_adaptive"
type: "bug-fix.session-id-detection"
status: "completed"
keywords: "session-id hooks sessionstart userpromptsubmit registry resume wrapper-session uuid-unification"
timestamp: "2025-10-20T13:15:00-0700"
session_id: "bc697a29-8dd9-43f9-be7b-0e658ba2e656"
---

# Session ID Detection Fix

## Request
> "bc697a29-8dd9-43f9-be7b-0e658ba2e656 <<< is this in your memory at all before my most recent message? what is the sessionstart hook showing u?"

## Overview
Fixed critical session ID detection bug where the system receives incorrect session identifier on conversation resume. The system creates temporary wrapper sessions during resume operations, but initialization hooks were injecting wrapper identifiers instead of the actual conversation UUID. This caused workflows to fail because they couldn't locate the conversation. Solution: Modified initialization to only run on new sessions, added resume-specific hooks that extract the session ID from conversation metadata, and unified all identifier formats to a single standard.

## Decisions

### SessionStart Matcher: startup-only
- **Context**: SessionStart hook was firing on both new sessions and resumes, receiving wrapper session IDs on resume
- **Solution**: Changed matcher from `*` to `startup` - only fires for new conversations
- **Rationale**: Resume behavior is fundamentally different (wrapper session created), needs separate handling

### UserPromptSubmit Hook for Resume Detection
- **Context**: Need correct session ID on resume, but SessionStart fires too early (before resume completes)
- **Solution**: Created UserPromptSubmit hook that extracts session ID from `transcript_path` field
- **Alternatives**: Could use find_recent() or mtime-based detection - rejected (unreliable for parallel conversations)
- **Approach**: `basename(transcript_path, .jsonl)` gives actual conversation UUID, not wrapper
- **Benefit**: Works for both single and parallel conversations, no race conditions

### Unified to Full UUID Format
- **Context**: System had three UUID formats: `session_prefix` (12 chars), `full_session_id` (36 chars), `bookmark` (8 chars)
- **Solution**: Removed all except full 36-char UUID format
- **Rationale**: TRACE's `find_by_session_id()` handles partial/full UUIDs natively via fuzzy matching
- **Impact**: Removed session_prefix extraction logic from workflows, simplified agent configs

### Registry context_injected Tracking
- **Context**: UserPromptSubmit fires on every message, would create duplicate injections
- **Solution**: Added `context_injected: bool` field to registry, check before injecting
- **Approach**: First message registers session and marks injected, subsequent messages skip
- **Benefit**: One injection per session, clean context

### Distinct Injection Labels
- **Context**: Multiple session IDs in context (SessionStart + UserPromptSubmit) caused extraction ambiguity
- **Solution**: SessionStart uses `[START_SESSION_ID: ...]`, UserPromptSubmit uses `[CURRENT_SESSION_ID: ...]`
- **Extraction priority**: Slash commands look for `CURRENT_SESSION_ID` first, fallback to `START_SESSION_ID`
- **Why**: Makes it explicit which is authoritative (CURRENT from transcript vs START from hook timing)

## Implementation

### Architecture
1. New conversation starts → SessionStart fires (matcher: startup)
2. Hook injects `[START_SESSION_ID: abc...]` + registers in registry
3. User sends first message → UserPromptSubmit checks registry `context_injected`
4. Already injected from SessionStart → Skip (no duplicate)

**Resume flow:**
1. User resumes conversation → SessionStart does NOT fire (matcher is startup only)
2. User sends first message → UserPromptSubmit fires
3. Hook extracts session from `transcript_path`: `basename($TRANSCRIPT_PATH, .jsonl)`
4. Registry check: `is_context_injected(session_id)` → false
5. Register session + mark injected → Inject `[CURRENT_SESSION_ID: bc697a29...]`
6. Subsequent messages → Registry returns true, skip injection

### Code Signatures

**SessionStart Hook Configuration** (`~/.claude/settings.json`)
```json
{
  "SessionStart": [{
    "matcher": "startup",
    "hooks": [{"command": "/path/to/session-start.sh"}]
  }]
}
```

**UserPromptSubmit Registry Check** (`~/.claude/hooks/user-prompt-submit.sh`)
```bash
ACTUAL_SESSION_ID=$(basename "$TRANSCRIPT_PATH" .jsonl)
ALREADY_INJECTED=$(python -c "from registry import is_context_injected; print(...)")
if [[ "$ALREADY_INJECTED" != "true" ]]; then
  # Inject [CURRENT_SESSION_ID: ...]
fi
```

**Registry State Tracking** (`aura-v2/src/orchestrator/registry.py`)
```python
def is_context_injected(session_id: str) -> bool:
    session = get_session(session_id)
    return session.get("context_injected", False) if session else False
```

## Patterns

### Transcript Path as Source of Truth
- **Pattern**: Extract session ID via `basename(transcript_path, .jsonl)` instead of using hook's `session_id` field
- **When**: Claude Code provides multiple session-related IDs and you need the actual conversation UUID
- **Approach**: UserPromptSubmit hook receives `transcript_path` field, extract filename without extension
- **Benefit**: Works correctly on resume (transcript_path points to original conversation, not wrapper)

### Hook Timing Separation
- **Pattern**: Different hooks for different timing requirements (SessionStart for immediate, UserPromptSubmit for after-load)
- **When**: Data needed at different points in session lifecycle (new vs resume, before vs after context load)
- **Approach**: SessionStart matcher filtered to specific triggers, UserPromptSubmit uses registry to prevent duplicates
- **Anti-Pattern**: Don't use SessionStart for resume detection - it fires before Claude Code resolves wrapper sessions

### Registry-Based Deduplication
- **Pattern**: Use persistent registry flag to prevent duplicate hook executions
- **When**: Hook fires on every occurrence (UserPromptSubmit on every message) but should only execute once
- **Approach**: Check registry flag before executing, set flag after execution
- **Benefit**: Idempotent hook behavior without complex state management

## Audit

### Created
- `~/.claude/hooks/user-prompt-submit.sh` - Extracts session ID from transcript_path, injects CURRENT_SESSION_ID on first message
- `.context/designate/re-calibrate/251020-session-id-unification.md` - Technical specification of changes
- `.context/designate/re-calibrate/251020-session-id-vision.md` - User vision with exact quotes

### Modified
- `~/.claude/hooks/session-start.sh` - Changed injection from `SESSION_ID:` to `[START_SESSION_ID: ...]`
- `~/.claude/settings.json` - SessionStart matcher: `*` → `startup`, added UserPromptSubmit hook config
- `aura-v2/src/orchestrator/registry.py` - Added `context_injected` field, `mark_context_injected()`, `is_context_injected()`
- `aura-v2/src/orchestrator/workflows/log_develop.py` - Removed session_prefix extraction, unified to session_id parameter
- `aura-v2/src/orchestrator/agents/ChangelogAgent.yaml` - Removed session_prefix/full_session_id variables, unified to session_id
- `aura-v2/src/orchestrator/agents.yaml` - Same cleanup for monolithic config
- `.claude/commands/log/develop.md` - Documented extraction priority: CURRENT_SESSION_ID > START_SESSION_ID

### Configuration
Hook behavior changes:
- SessionStart: Only fires on `startup` matcher (new conversations only)
- UserPromptSubmit: Fires on all user messages, checks registry before injecting
- Both hooks now inject bracketed format: `[LABEL: uuid]` for clear extraction

Session ID format:
- Old: `session_prefix` (12 chars), `full_session_id` (36 chars), `bookmark` (8 chars)
- New: `session_id` (36 chars) everywhere

### Testing
- Verified SessionStart fires only on startup matcher
- Verified UserPromptSubmit extracts correct session from transcript_path
- Verified registry prevents duplicate context injections
- Tested resume workflow end-to-end with workflow execution
