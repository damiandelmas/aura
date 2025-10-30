---
schema_version: "v3_adaptive"
type: "architecture.session-id-parameter-refactor"
status: "completed"
keywords: "session-id architecture brother-agent parameter-separation trace-cli resume"
timestamp: "2025-10-18T15:38:28-0700"
session_id: "3f7d3dd5-d570-4e20-81d7-a5008e501619"
---

# Fixed Brother Agent Session ID Architecture

## Request
> "Fix architectural flaw in ChangelogAgent session ID handling to prevent brothers from resuming into conversations instead of observing externally"

## Overview
Fixed an architectural flaw where observer agents were resuming existing conversations instead of analyzing them externally. The solution separates session identifiers into two formats: a short form for external CLI queries and a complete form for internal metadata tracking. This eliminates circular references where analysis agents inadvertently become part of what they analyze, enabling clean external observation.

## Decisions

### Parameter Format Separation
- **Context**: Brother agents need to observe conversations without becoming part of them, but the system was passing full UUIDs which triggered `--resume` behavior
- **Solution**: Split session ID into two formats—session_prefix (12 chars) for TRACE CLI partial matching, full_session_id (full UUID) for YAML metadata only
- **Rationale**: TRACE CLI uses fuzzy matching and doesn't need full UUID; YAML metadata requires full UUID for global uniqueness without triggering resume behavior
- **Implications**: Establishes pattern for all future observation-type agents; prevents circular references where agents analyze conversations they've been merged into

### Remove session_id Parameter from Agent Constructor
- **Context**: ClaudeAgent automatically adds `--resume <session_id>` when session_id parameter is provided, causing brothers to merge into conversations
- **Solution**: Remove `session_id=session_id` from ClaudeAgent.from_yaml() call, letting brother spawn fresh and use TRACE CLI for read-only observation
- **Alternatives**: Modify ClaudeAgent wrapper (breaks other callers), pass special flag to disable resume (adds complexity)
- **Trade-offs**: Requires understanding two different patterns (external observation vs resume-into); more parameters to track in workflow

### Session ID Propagation Strategy
- **Context**: Two fundamentally different approaches exist: external observation (separate conversation analyzing source) vs resume-into (continuing existing conversation)
- **Solution**: Use external observation pattern where brother runs fresh conversation and uses TRACE CLI to read JSONL files
- **Alternatives**: Resume-into (merges agent into conversation); flag-based control (adds complexity)
- **Rationale**: Prevents circular references, allows analysis of completed or ongoing conversations, maintains separation between analysis and analyzed conversation

## Implementation

### Architecture
The parameter flow establishes a clean separation:
1. User invokes `/log:develop` slash command
2. SessionStart hook provides full UUID
3. Workflow extracts session prefix (first 12 chars)
4. Brother spawns fresh with session_prefix (for TRACE CLI) and full_session_id (for YAML)
5. Brother runs `trace --session <prefix> --patches` to observe conversation
6. Changelog created with full UUID in filename

### Code Signatures

**Parameter Separation Pattern** (Orchestrator layer)
```python
# Extract session prefix (short form) for external queries
session_prefix = extract_id_prefix(session_id)

# Pass both formats independently - no session_id to constructor
agent.spawn(
    session_prefix=session_prefix,      # For external observation
    full_session_id=session_id,         # For metadata only
    # Note: session_id NOT passed - prevents auto-resume behavior
)
```

**Metadata Template Pattern** (Agent configuration)
```yaml
# Store full UUID separately from execution parameters
session_id: {full_session_id}
observation_mode: external  # Signals read-only vs. resume behavior
```

## Patterns

### External Observation for Agent Analysis
- **Pattern**: Spawn agents fresh (don't resume) and use CLI tools to access source conversation data
- **When**: Building agents that analyze or document existing conversations
- **Approach**: Pass observation parameters (session_prefix for CLI) separately from execution parameters; never pass session_id to agent constructor
- **Benefit**: Enables clean analysis without creating circular dependencies; agents can analyze completed or ongoing conversations independently
- **Anti-Pattern**: Resuming agent into source conversation; passing agent constructor the conversation it should analyze

## Audit

### Modified
- `aura-v2/src/orchestrator/workflows/log_develop.py` - Added session prefix extraction; removed session_id parameter from ClaudeAgent.from_yaml(); updated step numbering to reflect new prefix extraction step
- `aura-v2/src/orchestrator/agents.yaml` - Updated ChangelogAgent system prompt to use session_prefix for TRACE CLI command and full_session_id for YAML metadata and filename

### Impact
**Before**: ChangelogAgent would try to `--resume` into conversation, creating loop where it becomes part of conversation it analyzes.

**After**: ChangelogAgent spawns fresh and uses `trace --session <prefix> --patches` to observe conversation externally, producing clean changelogs without circular references.

### Validation
This change enables `/log:develop` slash command to correctly spawn ChangelogAgent brothers that run independently (not merged into source), use TRACE CLI for conversation archaeology, generate changelogs with full UUID in filename, and maintain clean separation between analysis and analyzed conversation.

### Future Implications
Establishes correct pattern for all observation-type brothers: never pass `session_id` to `ClaudeAgent.from_yaml()`, pass `session_prefix` for TRACE CLI, pass `full_session_id` for metadata only, let brothers spawn fresh and observe via TRACE. Any future agents analyzing conversations should follow this pattern.
