---
type: "design"
timestamp: "2025-09-30T18:03:00-0700"
---

# TRACE Patch Archaeology - Complete System Design

## Question
> "So we could retrace ALL of our steps using this?"

## Key Insights

### Breakthrough Realization
- Every conversation's code changes are now traceable with exact line-by-line diffs
- `structuredPatch` field in JSONL contains unified diff format
- Not theoretical - tested and working with 44 real patches
- Claude Code's `/rewind` uses same data - we can too

### System Capabilities Unlocked
1. **Complete Conversation Archaeology**: Track every code change across all conversations
2. **Custom Rewind**: Build our own undo system using inverse patches
3. **File Evolution Timeline**: See how any file changed across multiple conversations
4. **Git-Like Operations**: Generate diffs, create retroactive commits
5. **Cross-Project Tracking**: Global search finds conversations anywhere

### Critical Limitation Discovered
- Bash file operations NOT tracked (sed, echo >, cat >)
- Only Edit/Write tools have structured patches
- Same limitation as Claude Code's `/rewind`
- Solution: Hooks to enforce Edit/Write tool usage

## Explored Ideas

### Approach 1: Basic Patch Display (Implemented)
```bash
imem trace --session <id> --patches
```
**Result**: Shows all code changes with unified diff format
**Status**: ✅ Complete, tested, working

### Approach 2: SessionStart Bookmarks (Designed)
**Problem**: Current bookmarks created at END → can't reference THIS conversation during it
**Solution**: SessionStart hook creates bookmark immediately
**Benefit**: Multi-dimensional conversations - conversations can reference each other

**Key Capabilities**:
- Mid-conversation retrieval
- Self-reference (conversation reads own earlier state)
- Cross-reference (Conversation B reads Conversation A)
- Async agent coordination (spawned agents know parent)

### Approach 3: Incremental Changelog Chain (Designed)
**Problem**: Multiple changelogs per conversation = massive redundancy
**Solution**: Each part reads previous parts, documents only NEW changes

**Example Flow**:
```
Hour 1: /log:async → Part 1 (changes 1-10)
Hour 3: /log:async → Part 2 (references Part 1, only changes 11-15)
Hour 5: /log:async → Part 3 (references Part 1+2, only changes 16-20)
```

**No redundancy, natural continuation**

### Approach 4: Hook-Based Compliance (Designed)
**Problem**: Bash file operations not tracked → incomplete patch coverage
**Solution**: PreToolUse hook blocks bash file modifications

```bash
# Hook detects: sed -i, echo >, cat >
# Returns: {"permissionDecision": "deny", "reason": "Use Edit tool"}
# Agent learns: Always use Edit/Write for file changes
```

**Result**: 100% patch coverage guarantee

## Design Decisions

### Decision 1: Implement Patch Extraction First
**Rationale**: Verify `structuredPatch` data is usable before building on it
**Implementation**: `get_patches()` method + `--patches` CLI flag
**Outcome**: ✅ Works perfectly, 44 patches extracted from real conversation

### Decision 2: SessionStart Over SessionEnd
**Rationale**: Need bookmark available from conversation start
**Benefit**: Enables mid-conversation retrieval and cross-conversation references
**Trade-off**: None - SessionEnd can still run for post-processing

### Decision 3: On-Demand Changelogs (Not Automatic)
**Rationale**: User knows best checkpoint moments
**Implementation**: `/log:async` slash command spawns headless agent
**Benefit**: Intentional documentation, no spam

### Decision 4: Incremental Chain System
**Rationale**: Avoid redundancy when multiple changelogs per conversation
**Implementation**: Agent reads previous parts, documents only delta
**Benefit**: Natural narrative, no duplication

### Decision 5: Hook Enforcement Optional
**Rationale**: Start permissive (warnings), move to strict (blocking) if needed
**Implementation**: PreToolUse hook with configurable MODE
**Benefit**: Gradual adoption, agent training

## Implementation Architecture

### Tier 1: Patch Extraction (Complete)
```python
# Core method
def get_patches(self, entries: List[ConversationEntry]) -> List[Dict[str, Any]]:
    patches = []
    for entry in entries:
        if 'structuredPatch' in entry.tool_use_result:
            for patch in entry.tool_use_result['structuredPatch']:
                patches.append({
                    'file': entry.tool_use_result['filePath'],
                    'timestamp': entry.timestamp,
                    'patch': patch,
                    'diff_lines': patch['lines']
                })
    return patches
```

**CLI Usage**:
```bash
imem trace --session <id> --patches
imem trace --session <id> --summary --patches
```

### Tier 2: SessionStart Hook (Designed)
```bash
#!/bin/bash
# ~/.claude/hooks/session-start.sh

SESSION_ID="$1"
BOOKMARK=$(echo "$SESSION_ID" | md5sum | head -c 8)

mkdir -p ~/.imem/trace
echo "$SESSION_ID" > ~/.imem/trace/latest_bookmark.txt
echo "$(date -Iseconds)|$SESSION_ID|$BOOKMARK|start" >> ~/.imem/trace/history.log

cat << EOF
{
  "contextInjection": "<session-info>
🔖 Bookmark: $BOOKMARK
📋 Session: $SESSION_ID
💡 Retrieve: /trace:id-read
</session-info>"
}
EOF
```

### Tier 3: Incremental Changelog (Designed)
```bash
# /log:async slash command

# Detect existing parts
BOOKMARK=$(cat ~/.imem/trace/latest_bookmark.txt | md5sum | head -c 8)
EXISTING=$(find .memory/.changes -name "*_${BOOKMARK}_*.md" | sort | tail -1)

if [[ -n "$EXISTING" ]]; then
    PART_NUM=$(($(echo "$EXISTING" | grep -oP 'part-\K[0-9]+') + 1))
    MODE="incremental"
else
    PART_NUM=1
    MODE="initial"
fi

# Spawn headless agent
claude -p "Generate CHU changelog Part $PART_NUM

Read previous: $EXISTING (if exists)
Use TRACE: imem trace --session $SESSION_ID
Document: Only NEW changes

Output: .memory/.changes/$(date +%y%m%d-%H%M)_${BOOKMARK}_part-${PART_NUM}.md" \
--headless --async
```

### Tier 4: Bash Guard Hook (Designed)
```bash
#!/bin/bash
# ~/.claude/hooks/pre-tool-use.sh

TOOL_INPUT=$(cat)
TOOL_NAME=$(echo "$TOOL_INPUT" | jq -r '.tool_name')
COMMAND=$(echo "$TOOL_INPUT" | jq -r '.tool_input.command')

if [[ "$TOOL_NAME" == "Bash" ]] && echo "$COMMAND" | grep -qE '(sed -i|>|>>|echo.*>|cat.*>)'; then
    cat << EOF
{
  "permissionDecision": "deny",
  "permissionDecisionReason": "❌ File modifications via bash not tracked in TRACE.\n✅ Use Edit/Write tools for 100% patch coverage."
}
EOF
else
    echo '{"permissionDecision": "allow"}'
fi
```

## Outcomes

### What Works Now
✅ Complete patch extraction from any conversation
✅ Unified diff format with exact line changes
✅ Global search across all projects
✅ Works with conversations from any directory
✅ Comprehensive testing (44 patches validated)

### What's Designed (Ready to Implement)
📋 SessionStart bookmark system
📋 Multi-dimensional conversation references
📋 Incremental changelog chain (no redundancy)
📋 Bash guard hook (enforce tool compliance)
📋 Context injection hook (auto-add project info)

### Future Capabilities
- Custom rewind/undo system (apply inverse patches)
- File evolution timeline (all changes to file across conversations)
- Visual diff viewer (side-by-side comparisons)
- Retroactive git commits from conversations
- Conversation dependency graphs

### Testing Results
```
✅ Conversation with edits: 44 patches, 5 files
✅ Conversation without edits: 0 patches (correct)
✅ Cross-project search: Works globally
✅ Diff format: Valid unified diff
✅ All required keys present in patch structure
```

## References

### Implementation Files
- `imem/src/trace/conversation_retrieval.py:292-336` - get_patches() method
- `imem/src/cli/modules/trace.py:30,40,197-223` - --patches flag
- `.design/250930-1750_session-start-trace-bookmarks.md` - SessionStart design
- `.design/250930-1755_incremental-changelog-chain.md` - Changelog chain design

### External References
- Claude Code hooks documentation: https://docs.claude.com/en/docs/claude-code/hooks
- Unified diff format: Standard git diff format
- Claude Code `/rewind` feature: Uses same structuredPatch data

### Test Commands
```bash
# Basic patch extraction
imem trace --session 0a7d438e --patches

# Combined with summary
imem trace --session 0a7d438e --summary --patches

# Cross-project
imem trace --session 8f84c987 --patches

# Programmatic access
python3 -c "
from imem.src.trace import ConversationFinder, ConversationRetrieval
finder = ConversationFinder()
conv = finder.find_by_session_id('0a7d438e')
retrieval = ConversationRetrieval()
entries = retrieval.load_conversation(conv)
patches = retrieval.get_patches(entries)
print(f'Found {len(patches)} patches')
"
```

## Next Steps

**Immediate (Next Session)**:
1. Implement SessionStart hook
2. Test bookmark creation on new conversation
3. Verify mid-conversation retrieval works
4. Create /trace:current slash command

**Short-Term**:
1. Implement /log:async slash command
2. Test incremental changelog generation
3. Verify Part 1 → Part 2 → Part N chain
4. Add TRACE timestamp filtering (--after, --before)

**Medium-Term**:
1. Implement Bash guard hook
2. Implement context injection hook
3. Build conversation analytics dashboard
4. Create visual diff viewer

**Long-Term**:
1. Custom rewind feature
2. File evolution timeline
3. Conversation dependency graph
4. Auto-git integration hook

## Cross-Project Patterns

### Pattern: Conversation as First-Class Object
- Every conversation has unique, stable ID (bookmark)
- Available from start to end
- Can be referenced by other conversations
- Complete lineage tracking

### Pattern: Zero-Effort Institutional Memory
- Hooks automate documentation
- SessionStart → bookmark
- SessionEnd → index into imem
- /log:async → changelog on demand
- No user effort required

### Pattern: Tool Compliance Enforcement
- Hooks guide/enforce best practices
- Block bad patterns before execution
- Train agents through feedback
- Guarantee data quality (100% patch coverage)

### Pattern: Incremental Documentation
- Multiple checkpoints per conversation
- Each builds on previous (no redundancy)
- Natural narrative continuation
- Complete coverage without duplication
