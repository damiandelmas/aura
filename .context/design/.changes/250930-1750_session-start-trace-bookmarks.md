---
type: "design"
timestamp: "2025-09-30T17:50:00-0700"
---

# SessionStart TRACE Bookmarks for Multi-Dimensional Conversations

## Question
> "trace should be happening at beginning of conversation so that we stamp a unique hash to each conversation that can be retrieved at any time by any other conversation. // gives us a RETRIEVAL point for using TRACE READ at any point in the conversation. and makes conversations multi-dimensional — i could have conversations interacting with other conversations."

## Key Insights

### Current Limitation
- Bookmarks created at END of conversation (SessionEnd)
- Can't reference THIS conversation DURING it
- No mid-conversation retrieval
- Agents can't self-reference or cross-reference
- Linear conversation model only

### Breakthrough: SessionStart Bookmarking
- Create unique hash IMMEDIATELY when conversation starts
- Bookmark available from message 1
- Enables:
  - **Self-reference**: Conversation reads its own earlier state
  - **Cross-reference**: Conversation B reads Conversation A's context
  - **Async agents**: Spawned agents know parent conversation bookmark
  - **Multi-dimensional**: Conversations can interact with other conversations

## Explored Ideas

### Approach 1: SessionEnd Hook (Current)
```
Conversation starts → Work happens → Conversation ends → Create bookmark
```
**Problem:** Bookmark not available during conversation

### Approach 2: SessionStart Hook (Proposed)
```
Conversation starts → Create bookmark immediately → Bookmark available entire time
```
**Benefit:** Bookmark usable from first message

### Approach 3: Hybrid (Both Hooks)
```
SessionStart: Create bookmark
SessionEnd: Index into imem, generate analytics
```
**Best of both worlds**

## Design Decisions

### Decision 1: Use SessionStart Hook
**What:** Create bookmark hash at conversation start
**Why:** Enables mid-conversation retrieval and cross-conversation references
**How:**
```bash
# SessionStart hook
SESSION_ID="$1"  # Provided by Claude Code
BOOKMARK=$(echo "$SESSION_ID" | md5sum | head -c 8)

# Save immediately
echo "$SESSION_ID" > ~/.imem/trace/latest_bookmark.txt
echo "$(date -Iseconds)|$SESSION_ID|$BOOKMARK|session_start" >> ~/.imem/trace/history.log

# Display to agent
echo "🔖 This conversation bookmark: $BOOKMARK"
```

### Decision 2: Inject Bookmark into Context
**What:** Make bookmark visible to agent from start
**Why:** Agent knows its own identity, can reference self
**How:**
```json
{
  "contextInjection": "<session-info>
🔖 This conversation bookmark: abc123
📋 Session ID: 0a7d438e-63f6-4a68-aecc-cb595b1b9101
💡 Other agents can reference this conversation via bookmark
</session-info>"
}
```

### Decision 3: Multi-Dimensional Interaction Protocol
**What:** Standard way for conversations to reference each other
**Why:** Enable async agents, parallel work, conversation inheritance
**How:**
```bash
# Conversation A spawns async agent B
# A's bookmark: abc123
# B's bookmark: def456

# B can read A:
imem trace --bookmark abc123 --conversation
imem trace --session <A's-session-id> --patches

# B can reference A in output:
"Building on conversation abc123, I've extended the implementation..."
```

## Implementation Architecture

### Hook: SessionStart
```bash
#!/bin/bash
# ~/.claude/hooks/session-start.sh

SESSION_ID="$1"
PROJECT_ROOT="$2"
BOOKMARK=$(echo "$SESSION_ID" | md5sum | head -c 8)

# Create bookmark directory
mkdir -p ~/.imem/trace

# Save bookmark
echo "$SESSION_ID" > ~/.imem/trace/latest_bookmark.txt

# Log to history
echo "$(date -Iseconds)|$SESSION_ID|$BOOKMARK|$PROJECT_ROOT|start" >> ~/.imem/trace/history.log

# Return context injection
cat << EOF
{
  "contextInjection": "<session-info>
🔖 Bookmark: $BOOKMARK
📋 Session: $SESSION_ID
💡 Retrieve anytime: /trace:id-read
</session-info>"
}
EOF
```

### Slash Command: /trace:current
```markdown
Show THIS conversation's bookmark and context.

Output:
🔖 Bookmark: abc123
📋 Session ID: 0a7d438e-63f6-4a68-aecc-cb595b1b9101
⏰ Started: 2025-09-30 14:30:00
📝 Current message count: 42
```

### Use Case: Async Changelog Agent
```
Main Conversation (bookmark: abc123):
  USER: Implement feature X
  AGENT: [builds feature]
  AGENT: Spawning changelog agent...

  # Spawns headless Claude
  claude -p "Generate changelog for conversation abc123

  Use: imem trace --bookmark abc123 --conversation
  Output: .memory/.changes/...

  Note: Your bookmark is def456" --headless --async

Async Agent (bookmark: def456):
  SYSTEM: 🔖 Bookmark: def456
  AGENT: Reading parent conversation abc123...
  AGENT: [uses TRACE to read abc123]
  AGENT: Creating changelog...
  AGENT: Reference: Built from conversation abc123
```

## Outcomes

### Capabilities Unlocked

1. **Mid-Conversation Self-Reference**
   - Agent can review its own earlier messages
   - "Let me check what I said 10 messages ago..."

2. **Cross-Conversation Context**
   - Agent B can read full context from Agent A
   - "Building on the work from session abc123..."

3. **Async Agent Coordination**
   - Main conversation spawns workers
   - Workers know parent conversation
   - Can read parent's full context

4. **Conversation Inheritance**
   - Child conversations reference parent
   - Full lineage tracking
   - "This changelog documents conversation abc123"

5. **Parallel Workflows**
   - Multiple agents working simultaneously
   - Each has unique bookmark
   - All can reference each other

### Breaking Changes
- None - SessionStart is additive
- SessionEnd hooks still work
- Backward compatible

### Testing Strategy
1. Implement SessionStart hook
2. Verify bookmark created immediately
3. Test `/trace:id-read` mid-conversation
4. Spawn async agent, verify parent context accessible
5. Create incremental changelogs

## References

- TRACE conversation retrieval: `imem/src/trace/conversation_retrieval.py`
- Conversation finder: `imem/src/trace/conversation_finder.py`
- Patch extraction: `imem trace --session <id> --patches`
- Claude Code hooks: https://docs.claude.com/en/docs/claude-code/hooks
- Hook types: SessionStart, SessionEnd, PreToolUse, PostToolUse

## Next Steps

1. Implement SessionStart hook
2. Create `/trace:current` slash command
3. Update `/trace:id-log` to work with SessionStart bookmarks
4. Implement incremental changelog system (separate design doc)
5. Test multi-dimensional conversation flows
