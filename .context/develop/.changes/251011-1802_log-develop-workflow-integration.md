---
schema_version: "v3_adaptive"
type: "implementation.workflow-integration"
status: "completed"
keywords: "slash command workflow brother spawning trace session detection cli integration background execution"
timestamp: "2025-10-11T18:02:37-0700"
session_id: "e6ef3740-b495-4c51-a4b0-7260a9054485"
---

# Log Develop Workflow Brother Spawning Integration

## Request
> "Implement functional /log:develop slash command that spawns a background agent to create changelogs automatically when users type the command in conversation, without blocking workflow."

## Overview
Implemented workflow integration to detect active conversations and spawn background agents as external observers. Key discovery: passing conversation state directly to spawned agents causes infinite loops; solution was separating conversation context into observation data (for external queries) and metadata (for documentation). Established the pattern for all future background workflows: agents spawn fresh, observe externally, and execute asynchronously. Non-blocking execution enables immediate return while background work completes.

## Decisions

### Brother Spawning Architecture: Fresh Observation vs Resume
- **Context**: Initial attempts to pass session_id directly to brother constructor caused infinite loop behavior
- **Solution**: Split session context into two separate parameters: session_prefix for external TRACE observation, full_session_id for metadata only (never passed to constructor)
- **Alternatives**: Resume into parent conversation (rejected - causes infinite loops), direct JSONL parsing (rejected - duplicates TRACE), registry-only detection (rejected - lags behind real conversations)
- **Rationale**: TRACE is definitive source of truth for real conversations; brothers are external observers, not participants
- **Implications**: All future brother workflows must follow this pattern; session context management is critical architectural decision

### TRACE-First Session Detection
- **Context**: System needed to determine which conversation is "current" when slash command executes
- **Solution**: Use TRACE CLI with ConversationFinder to discover most recent conversation by file mtime, then auto-register in bookmark registry
- **Trade-offs**: Registry transitions from authoritative source to secondary bookmark index; adds dependency on TRACE system availability
- **Rationale**: When slash command runs, JSONL file is written and mtime updated; find_recent(1) definitively returns current conversation
- **Benefit**: Works with real conversation files, not manual registry entries; scales naturally as new conversations are created

### Path Handling Strategy
- **Context**: Brother agents spawn in aura-v2 root directory but need to write changelogs to main/.context/develop/.changes/
- **Solution**: Use relative path `../.context/develop/.changes/` in system prompt with explicit documentation
- **Constraint**: Cannot assume brother knows project structure; must encode path knowledge in prompt
- **Impact**: Makes prompt documentation critical; path changes require prompt updates

### Multiple Changelogs Per Session Pattern
- **Context**: Long conversations may span multiple distinct phases or milestones worth documenting separately
- **Solution**: Filename uses both timestamp and bookmark: `{timestamp}_{bookmark}.md`, allowing multiple entries per session
- **Benefit**: Enables natural narrative progression; each /log:develop invocation creates separate changelog
- **Precedent**: Aligns with AURA system's per-phase documentation philosophy

## Constraints

### Session ID Format and Matching
- **What**: UUID session IDs must be truncated to 11 characters for TRACE CLI prefix matching (full format: "93e11440-14d1-4343-99b3-d5437fdb4c6a")
- **Discovery**: TRACE accepts partial UUID matching; truncation at first two dash-separated segments provides uniqueness while being human-readable
- **Workaround**: Extract prefix in format "XXXXXXXX-XXX" before passing to TRACE commands
- **Impact**: Requires careful string manipulation; incorrect truncation causes TRACE to fail matching

### TRACE Availability Dependency
- **What**: Slash command and auto-detection depend on TRACE system and ConversationFinder being available
- **Discovery**: System design assumes TRACE conversation indexing is current and accessible
- **Workaround**: Add fallback to registry-based detection if TRACE lookup fails
- **Impact**: Requires TRACE service to be operational for slash command to function

### Background Process Lifecycle
- **What**: Shell background operator `&` provides no guarantees about process completion or error visibility
- **Discovery**: Brother execution takes 2-5 minutes; user must see feedback that process is running
- **Workaround**: Write debug logs to `.context/.debug/` and inform user of estimated time; future use proper job manager
- **Impact**: No real-time error feedback to user; must check debug logs to troubleshoot failures

## Failures

### Initial Infinite Loop Behavior
- **Attempted**: Passed full session_id directly to ClaudeAgent constructor during brother spawning
- **Why Failed**: Brother inherited parent session context and attempted to resume into active conversation, creating message duplication and infinite loop
- **Discovery**: Manual testing of /log:develop command revealed exponential message growth
- **Lesson**: Session context must be carefully partitioned; brothers need external observation context, not internal conversation state
- **Alternative**: Split session parameter into observation-only prefix and metadata-only full_session_id

### Registry-Only Session Detection
- **Attempted**: Relied solely on manually maintained registry to identify current session
- **Why Failed**: Registry entries become stale between invocations; no automatic detection of real-time conversation
- **Discovery**: Found that JSONL files update on slash command execution, providing definitive mtime-based detection
- **Lesson**: Let data structure (file mtime) be source of truth; maintain registry as index, not authority
- **Alternative**: Switched to TRACE-first detection with auto-registration

## Patterns

### TRACE-First Session Detection Pattern
- **Pattern**: Query conversation file system via mtime ordering (source of truth) before consulting registry (secondary index)
- **When**: Need to identify "current" resource that changes frequently and may not be manually tracked
- **Approach**: Use ConversationFinder with find_recent(1) to get actual file, extract session ID from filename, generate bookmark deterministically
- **Benefit**: Always accurate; auto-registers new sessions; handles rapid conversation creation naturally
- **Occurrences**: Applied to /log:develop slash command; generalizable to all session-detection use cases

### Session Context Partitioning Pattern
- **Pattern**: Split session information into observation context (for external tools) and metadata context (for documentation)
- **When**: Spawning external agents that must observe parent but not participate
- **Approach**: session_prefix for TRACE commands, full_session_id for frontmatter and logging, never pass session ID to agent constructor
- **Why**: Direct session inheritance causes agent to resume into parent; partitioning enables fresh external observation
- **Benefit**: Prevents infinite loops; cleanly separates external observation from internal state

### Background Workflow with Debug Logging Pattern
- **Pattern**: Spawn long-running processes in background with comprehensive debug logs written to `.context/.debug/` for post-execution troubleshooting
- **When**: Users need immediate return to workflow while background process completes asynchronously
- **Approach**: Use shell `&` operator for background execution, write JSON or text logs with timestamp/bookmark/cost/turns, inform user of expected time
- **Benefit**: Non-blocking user experience; traceable execution history for debugging
- **Future**: Replace with proper background job manager (imem service pattern)

## Implementation

### Architecture
The /log:develop workflow integrates brother spawning with CLI commands and slash commands:
1. User types `/log:develop` in conversation
2. Slash command executes orca CLI with --current flag
3. TRACE-first detection finds most recent conversation by mtime
4. Session ID extracted from filename, bookmark generated via MD5 hash
5. Brother spawns via ClaudeAgent.from_yaml("ChangelogAgent", session_prefix=..., full_session_id=...)
6. Brother executes fresh (never resumes into parent conversation)
7. Changelog written to `../.context/develop/.changes/` relative to aura-v2
8. Debug log written to `.context/.debug/` with results and cost
9. User continues working immediately (returns within 1 second)

### Code Signatures

**Session Detection** (`aura/cli/orca.py`)
```python
finder = ConversationFinder()
recent = finder.find_recent(1)  # By file modification time
session_id = recent[0].stem
bookmark = hashlib.md5(session_id.encode()).hexdigest()[:12]
```

**Context Separation** (`orchestrator/workflows/log_develop.py`)
```python
# Partition: prefix for observation, full_id for metadata only
parts = session_id.split('-')
observation_prefix = f"{parts[0]}-{parts[1][:3]}"

agent.spawn(
    observation_context=observation_prefix,  # External queries
    metadata_id=session_id,                   # Documentation only
    bookmark=bookmark
)
```

**Debug Logging** (`orchestrator/workflows/log_develop.py`)
```python
debug_log = Path(".context/.debug") / f"{timestamp}_{bookmark}_response.txt"
debug_log.write_text(f"""Execution Log
Session: {session_id}
Cost: ${result['cost']:.2f}
Turns: {result['turns']}
""")
```

## Audit

### Created
- `.context/.debug/` directory - Debug logs for brother execution tracking
- `aura/cli/orca.py` - New workflow log-develop command structure

### Modified
- `src/aura/cli/orca.py` - Added TRACE-first detection, workflow commands, auto-registration
- `src/orchestrator/workflows/log_develop.py` - Integrated session prefix extraction, debug logging
- `src/orchestrator/agents.yaml` - Updated ChangelogAgent system prompt with session_prefix clarification
- `.claude/commands/log/develop.md` - Slash command updated to use new workflow command
- `src/orchestrator/__init__.py` - Exported registry functions (add_session, find_session)

### Configuration

**agents.yaml update for ChangelogAgent**:
```yaml
ChangelogAgent:
  system_prompt: |
    You are ChangelogAgent - Development changelog creator.

    Your Task:
    1. Use trace CLI with session_prefix (UUID prefix, not bookmark):
       trace --session {session_prefix} --patches

    2. Write to: ../.context/develop/.changes/{timestamp}_{bookmark}.md

    IMPORTANT: {session_prefix} is first 11 chars of session UUID
              {bookmark} is deterministic 12-char MD5 hash
              Multiple changelogs per session are normal
```

**CLI command structure**:
```bash
# User-facing workflow commands
orca workflow log-develop --current          # Auto-detect via TRACE
orca workflow log-develop --bookmark <id>    # Explicit bookmark

# Session management
orca session                   # Show current session
orca list                      # List all registered conversations

# Slash command execution
orca workflow log-develop --current &        # Background execution
```

### Deployment
- TRACE-first detection implementation
- Background execution with `&` operator
- Debug logging to `.context/.debug/`
- Auto-registration in session registry
- Cost tracking: ~$0.65 per brother execution
- Expected duration: 2-5 minutes per changelog generation

### Testing
**Manual test** (successful):
- Brother spawned without errors
- No infinite loops (fresh execution confirmed)
- TRACE detection found correct conversation
- Auto-registration successful
- Debug logs created with proper metadata
- Timestamp: ~3 minutes execution
- Cost: ~$0.65
