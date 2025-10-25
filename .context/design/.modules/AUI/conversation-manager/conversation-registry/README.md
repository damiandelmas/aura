# Conversation Registry & Archaeology Module

**Purpose**: Enable future Claude Code instances to retrieve and learn from past conversations

**Status**: Active - Documentation and methodology established

---

## Overview

This module documents how to perform **conversation archaeology** - the practice of retrieving and analyzing past Claude Code sessions to maintain context across conversations.

### The Problem

Claude Code instances have no memory between sessions. Each new conversation starts from zero, requiring:
- Manual re-explanation of context
- Duplicate research
- Lost decisions and rationale
- Wasted tokens and time

### The Solution

Three-tier approach to conversation retrieval:

1. **trace CLI** - Clean UX for common queries (when it works)
2. **Pure bash/jq** - Reliable fallback for all scenarios
3. **Documentation** - Knowledge transfer between Claude instances

---

## Documents in This Module

### 1. `conversation-archaeology-methodology.md`
**Original methodology document** from advisory-board project

**Key learnings**:
- How to manually parse JSONL conversation files
- trace CLI design and intended usage
- IMEM integration vision for semantic search
- Agent task detection patterns

**Use when**: Understanding the historical context and evolution of this approach

### 2. `trace-vs-bash-analysis.md`
**Comparative analysis** of trace CLI vs pure bash

**Key insights**:
- trace provides better UX but can fail
- Bash always works but requires more knowledge
- Hybrid approach recommended: trace first, bash fallback
- Real-world example: finding vision module conversation

**Use when**: Deciding which approach to use for a specific task

### 3. `conversation-archaeology-bash-runbook.md`
**Practical guide** to bash-based conversation retrieval

**Contents**:
- JSONL structure reference
- Essential jq patterns for all common queries
- Recipes for specific tasks
- Debugging tips
- Quick reference card

**Use when**: trace fails or custom queries needed

---

## Quick Start

### For Future Claude Instances

**Scenario**: User mentions "we discussed this before" or "continue from last time"

**Action**:

```bash
# Step 1: Try trace first (clean UX)
trace --marker "keyword" --recent 10
trace --session <found-id> --conversation

# Step 2: If trace fails, use bash (reliable)
find ~/.claude/projects/ -name "*.jsonl" -exec grep -l "keyword" {} \;
cat <found-file> | jq -r 'select(.type == "user") | .message.content[0].text' 2>/dev/null

# Step 3: Provide context to user
# Summarize what was discussed, decided, or created
```

### Common Use Cases

#### 1. "What did we decide about X?"
```bash
# Find conversation
trace --marker "X" --recent 10

# Extract relevant messages
trace --session <id> --conversation | grep -A5 -B5 "decision"
```

#### 2. "Which conversation created this file?"
```bash
# Bash approach (most reliable)
find ~/.claude/projects/ -name "*.jsonl" -exec grep -l "filename.md" {} \;

# Verify it was created (not just mentioned)
cat <found-jsonl> | jq 'select(.message.content[]?.name == "Write")' | grep "filename.md"
```

#### 3. "Continue where we left off"
```bash
# Find most recent session
trace --recent 1

# Get summary
trace --session <id> --summary

# Review last messages
trace --session <id> --conversation | tail -50
```

#### 4. "What research was done on Y?"
```bash
# Find session
trace --marker "research" --marker "Y"

# Check tools used (web searches, etc)
trace --session <id> --tools

# Extract web search queries
cat <jsonl> | jq -r 'select(.message.content[]?.name == "WebSearch") | .message.content[].input.query'
```

---

## File Discovery Timeline (Meta Example)

**Question**: Which conversation created `architecture.md` and `dataflow.md`?

**Journey** (demonstrates the methodology):

1. **Started with trace**:
   ```bash
   trace --marker "architecture" --recent 10
   ```
   → Found conversations but not the right one

2. **Checked trace files**:
   ```bash
   trace --session <id> --files
   ```
   → Showed wrong project (IMEM not RUNWAY)

3. **Fell back to bash**:
   ```bash
   find ~/.claude/projects/ -name "*.jsonl" -exec grep -l "architecture.md" {} \;
   ```
   → Found 3 candidates across different projects

4. **Checked file timestamps**:
   ```bash
   ls -la /path/to/architecture.md  # Created 08:47
   stat ~/.claude/projects/*/9ca1bf1f*.jsonl  # Modified 09:01
   ```
   → Confirmed timing matched

5. **Verified with grep**:
   ```bash
   grep -o '"file_path":"[^"]*architecture\.md"' <jsonl>
   ```
   → Confirmed Write operation in that session

**Answer**: Session `9ca1bf1f-6778-4329-868f-71cb9207b686`

**Lesson**: trace + bash hybrid approach is most effective

---

## Architecture Notes

### Storage Location
```
~/.claude/projects/
└── -<encoded-working-directory>/
    └── <session-uuid>.jsonl
```

**Encoding**: Working directory path with `/` → `-` and leading `-`
- `/home/user/project` → `-home-user-project`

### JSONL Structure
Each line is independent JSON object:
```json
{"type": "user", "message": {...}, "sessionId": "...", "timestamp": "..."}
{"type": "assistant", "message": {...}, ...}
{"type": "file-history-snapshot", ...}
```

**Not** multi-line JSON - each line parseable independently.

### Message Content Types
```json
{
  "message": {
    "content": [
      {"type": "text", "text": "..."},           // User/assistant text
      {"type": "tool_use", "name": "...", ...},  // Tool invocation
      {"type": "tool_result", "content": "..."}  // Tool output
    ]
  }
}
```

---

## Tool Comparison Matrix

| Feature | trace CLI | Bash/jq | Notes |
|---------|-----------|---------|-------|
| **Setup** | Works if installed | Always available | Bash requires no deps |
| **UX** | Clean, formatted | Raw, requires piping | trace filters noise |
| **Reliability** | Can fail (imports) | 100% reliable | Bash is escape hatch |
| **Flexibility** | Fixed queries | Unlimited custom | Bash for novel queries |
| **Speed** | Fast | Can be slow on large files | trace pre-filters |
| **Learning curve** | Low (intuitive commands) | Medium (need jq knowledge) | Runbook helps with bash |

**Recommendation**:
1. Try trace first (90% of cases)
2. Use bash when trace fails or for custom queries
3. Document approach in this module for future instances

---

## Best Practices

### For Claude Instances

1. **Always check for prior conversations** when user mentions past context
2. **Use trace first** for standard queries (summary, files, conversation)
3. **Fall back to bash** when trace fails or gives insufficient results
4. **Search globally** not just current project: `find ~/.claude/projects/`
5. **Verify file operations** distinguish between "mentioned" vs "created"
6. **Provide summaries** to user after retrieving context

### For Users

1. **Mention session IDs** if you know them (from `trace --recent`)
2. **Use keywords** that appear in conversation ("we discussed BASE/PORT")
3. **Reference files** that were created ("the architecture.md file")
4. **Be patient** - archaeology takes 2-3 queries to narrow down

---

## Future Enhancements

### Short-term
- [ ] Fix trace import errors (make standalone or fix Python path)
- [ ] Add trace `--json` output mode for scriptability
- [ ] Create trace debugging guide
- [ ] Test bash runbook on more conversations

### Long-term
- [ ] IMEM integration for semantic search across all conversations
- [ ] Automatic conversation ingestion pipeline
- [ ] Agent research compilation (detect multi-agent patterns)
- [ ] Cross-conversation knowledge transfer

### Vision (from methodology doc)
```
Claude Session A → Research → Auto-ingested to IMEM
                                    ↓
Claude Session B → imem query "topic" → Semantic results
                                    ↓
                              Continues with full context
```

---

## Meta Notes

### Dogfooding

This module was created using the techniques it documents:
1. Found methodology doc via bash: `find ~/.claude/projects/ -name "*archaeology*"`
2. Used trace to review recent sessions: `trace --recent 5`
3. Used bash to find vision file conversation: `grep -l "architecture.md" ~/.claude/projects/*/*.jsonl`
4. Created this documentation to codify the learnings

### Irony

The fact that I needed to use bash to analyze trace demonstrates the necessity of this dual-approach documentation.

### Living Document

This module should evolve as:
- New patterns discovered
- trace CLI improved
- IMEM integration developed
- More conversations analyzed

---

## See Also

- `TRACE.md` in project root - trace CLI documentation
- `.claude/hooks/` - Session start hooks (for auto-registration)
- `.context/conversations/registry.json` - Session bookmarks (if using ORCA)

---

## Contributors

- Claude Sonnet 4.5 (2025-10-20) - Initial documentation
- Future Claude instances - Please update as you discover new patterns!
