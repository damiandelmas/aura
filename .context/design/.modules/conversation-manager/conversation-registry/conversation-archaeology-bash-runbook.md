# Conversation Archaeology: Pure Bash Runbook

**Purpose**: Retrieve and analyze Claude Code conversations using only bash/jq (when trace CLI fails or is insufficient)

**Audience**: Future Claude Code instances, developers debugging conversation history

**Philosophy**: Direct access to JSONL files is more reliable than abstraction layers

---

## Quick Reference

```bash
# Find your conversation
find ~/.claude/projects/ -name "*.jsonl" -exec grep -l "keyword" {} \;

# Extract user messages
cat session.jsonl | jq -r 'select(.type == "user") | .message.content | if type == "array" then .[0].text else . end' 2>/dev/null

# List files modified
cat session.jsonl | jq -r 'select(.message.content[]?.type == "tool_use") | .message.content[] | select(.name == "Write" or .name == "Edit") | .input.file_path' | sort -u

# Count tool usage
cat session.jsonl | jq -r 'select(.message.content[]?.type == "tool_use") | .message.content[].name' | sort | uniq -c | sort -rn
```

---

## Understanding Claude Code's Conversation Storage

### File Location
All conversations stored as JSONL (JSON Lines) files:
```
~/.claude/projects/
├── -home-axp-projects-shared-RUNWAY/
│   ├── 015b20a1-e5ae-4499-a301-5547d814926f.jsonl
│   └── 9ca1bf1f-6778-4329-868f-71cb9207b686.jsonl
├── -home-axp-projects-shared/
│   └── 9ca1bf1f-6778-4329-868f-71cb9207b686.jsonl
└── -home-user-other-project/
    └── ...
```

**Pattern**: Directory name is working directory path with:
- Leading `/` removed
- All `/` replaced with `-`
- Prefixed with `-`

**Example**:
- Working dir: `/home/axp/projects/shared/RUNWAY`
- Encoded: `-home-axp-projects-shared-RUNWAY`

### JSONL Format
Each line is a complete JSON object representing one event:
- User message
- Assistant response
- Tool invocation
- File snapshot
- System event

**Not CSV, not multi-line JSON** - each line is independent.

---

## JSONL Structure Reference

### Common Message Types

#### 1. User Message
```json
{
  "type": "user",
  "sessionId": "9ca1bf1f-6778-4329-868f-71cb9207b686",
  "cwd": "/home/axp/projects/shared",
  "timestamp": "2025-10-20T15:22:29.723Z",
  "message": {
    "role": "user",
    "content": [
      {"type": "text", "text": "Warmup"}
    ]
  }
}
```

**Or with tool results**:
```json
{
  "type": "user",
  "message": {
    "role": "user",
    "content": [
      {
        "type": "tool_result",
        "tool_use_id": "toolu_01ABC...",
        "content": "output from previous tool"
      }
    ]
  }
}
```

#### 2. Assistant Message
```json
{
  "type": "assistant",
  "sessionId": "...",
  "timestamp": "...",
  "message": {
    "role": "assistant",
    "content": [
      {"type": "text", "text": "I'm ready to help..."}
    ],
    "usage": {
      "input_tokens": 1340,
      "output_tokens": 178
    }
  }
}
```

**With tool use**:
```json
{
  "type": "assistant",
  "message": {
    "content": [
      {"type": "text", "text": "Let me search for that..."},
      {
        "type": "tool_use",
        "id": "toolu_01ABC...",
        "name": "WebSearch",
        "input": {"query": "Claude Code skills"}
      }
    ]
  }
}
```

#### 3. File Snapshot
```json
{
  "type": "file-history-snapshot",
  "messageId": "...",
  "snapshot": {
    "trackedFileBackups": {...},
    "timestamp": "..."
  }
}
```

#### 4. Sidechain Message (Spawned Agent)
```json
{
  "type": "message",
  "isSidechain": true,
  "sessionId": "parent-session-id",
  "message": {
    "role": "assistant",
    "content": [...]
  }
}
```

---

## Essential Bash Patterns

### 1. Find Conversations by Keyword

**Problem**: Find all conversations that mention "architecture"

```bash
# Search all projects
find ~/.claude/projects/ -name "*.jsonl" -exec grep -l "architecture" {} \;

# Just current project
PROJECT=$(pwd | sed 's|/|-|g' | sed 's|^-||')
grep -l "architecture" ~/.claude/projects/-${PROJECT}/*.jsonl

# With context (show matching line)
find ~/.claude/projects/ -name "*.jsonl" -exec grep -H "architecture" {} \; | head -10
```

**Output**:
```
/home/axp/.claude/projects/-home-axp-projects-shared/9ca1bf1f-6778.jsonl
/home/axp/.claude/projects/-home-axp-projects-shared-RUNWAY/015b20a1-e5ae.jsonl
```

### 2. List Recent Conversations

**Problem**: What conversations happened recently in this project?

```bash
PROJECT=$(pwd | sed 's|/|-|g' | sed 's|^-||')
ls -lth ~/.claude/projects/-${PROJECT}/*.jsonl | head -10
```

**Better output with dates**:
```bash
find ~/.claude/projects/-${PROJECT}/ -name "*.jsonl" -printf "%T@ %p\n" | sort -rn | head -10 | awk '{print strftime("%Y-%m-%d %H:%M", $1), $2}'
```

### 3. Extract Conversation Summary

**Problem**: Get session metadata, duration, message count

```bash
SESSION="9ca1bf1f-6778-4329-868f-71cb9207b686"
JSONL=$(find ~/.claude/projects/ -name "${SESSION}.jsonl")

echo "=== SESSION METADATA ==="
head -10 "$JSONL" | jq -r 'select(.sessionId) | {session: .sessionId, cwd: .cwd, start: .timestamp}' | head -1

echo -e "\n=== MESSAGE COUNT ==="
grep -c '"type":"user"\|"type":"assistant"' "$JSONL"

echo -e "\n=== DURATION ==="
FIRST=$(head -1 "$JSONL" | jq -r '.timestamp')
LAST=$(tail -1 "$JSONL" | jq -r '.timestamp')
echo "Start: $FIRST"
echo "End: $LAST"
```

### 4. Extract User Messages

**Problem**: What did the user ask for?

```bash
cat "$JSONL" | jq -r 'select(.type == "user") | .message.content | if type == "array" then .[0].text else . end' 2>/dev/null
```

**With line numbers**:
```bash
cat "$JSONL" | jq -r 'select(.type == "user") | .message.content | if type == "array" then .[0].text else . end' 2>/dev/null | nl
```

**Filter nulls and noise**:
```bash
cat "$JSONL" | jq -r 'select(.type == "user") | .message.content | if type == "array" then .[0].text else . end' 2>/dev/null | grep -v "^null$" | grep -v "^$"
```

### 5. Extract Assistant Responses

**Problem**: What did Claude say?

```bash
cat "$JSONL" | jq -r 'select(.type == "assistant") | .message.content[] | select(.type == "text") | .text' 2>/dev/null
```

**First response only**:
```bash
cat "$JSONL" | jq -r 'select(.type == "assistant") | .message.content[] | select(.type == "text") | .text' 2>/dev/null | head -1
```

### 6. List All Files Modified

**Problem**: What files were created or edited?

```bash
# Method 1: Via tool_use in messages
cat "$JSONL" | jq -r '
  select(.message.content[]?.type == "tool_use") |
  .message.content[] |
  select(.type == "tool_use") |
  select(.name == "Write" or .name == "Edit") |
  .input.file_path // .input.path
' | sort -u

# Method 2: Via input object (alternative structure)
cat "$JSONL" | jq -r 'select(.input?.file_path) | .input.file_path' | sort -u

# Method 3: Combined (most reliable)
cat "$JSONL" | jq -r '
  (select(.message.content[]?.type == "tool_use") | .message.content[] | select(.type == "tool_use") | select(.name == "Write" or .name == "Edit") | .input.file_path),
  (select(.input?.file_path) | .input.file_path)
' 2>/dev/null | sort -u
```

### 7. Count Tool Usage

**Problem**: What tools were used and how often?

```bash
cat "$JSONL" | jq -r '
  select(.message.content[]?.type == "tool_use") |
  .message.content[] |
  select(.type == "tool_use") |
  .name
' | sort | uniq -c | sort -rn
```

**Example output**:
```
      5 mcp__sequential-thinking__sequentialthinking
      3 WebSearch
      3 WebFetch
      2 Write
      1 Read
```

### 8. Find Specific Tool Invocations

**Problem**: Show all WebSearch queries

```bash
cat "$JSONL" | jq -r '
  select(.message.content[]?.type == "tool_use") |
  .message.content[] |
  select(.type == "tool_use" and .name == "WebSearch") |
  .input.query
'
```

**Problem**: Show all Write operations

```bash
cat "$JSONL" | jq '
  select(.message.content[]?.type == "tool_use") |
  .message.content[] |
  select(.type == "tool_use" and .name == "Write") |
  {file: .input.file_path, preview: .input.content[:100]}
'
```

### 9. Extract Token Usage

**Problem**: How many tokens were used?

```bash
cat "$JSONL" | jq -r '
  select(.message.usage) |
  .message.usage |
  "Input: \(.input_tokens), Output: \(.output_tokens)"
' | awk '{in+=$2; out+=$4} END {print "Total Input:", in, "Total Output:", out}'
```

### 10. Find Conversations by File Created

**Problem**: Which conversation created `architecture.md`?

```bash
FILE="architecture.md"

# Search and show session ID + timestamp
find ~/.claude/projects/ -name "*.jsonl" -exec grep -l "$FILE" {} \; | while read jsonl; do
  SESSION=$(basename "$jsonl" .jsonl)
  TIMESTAMP=$(stat -c "%y" "$jsonl" | cut -d' ' -f1,2)
  echo "$TIMESTAMP | $SESSION | $jsonl"
done | sort
```

**Verify it was actually created (not just mentioned)**:

```bash
cat "$JSONL" | jq -r '
  select(.message.content[]?.type == "tool_use") |
  .message.content[] |
  select(.type == "tool_use" and .name == "Write") |
  select(.input.file_path | contains("architecture.md")) |
  "Created: \(.input.file_path)"
'
```

### 11. Extract Conversation as Markdown

**Problem**: Export conversation for reading or agent consumption

```bash
cat "$JSONL" | jq -r '
  select(.type == "user" or .type == "assistant") |
  if .type == "user" then
    "\n## USER\n\n" + (.message.content | if type == "array" then (.[0].text // "") else . end)
  else
    "\n## ASSISTANT\n\n" + (.message.content[] | select(.type == "text") | .text)
  end
' 2>/dev/null | grep -v "^$" > conversation.md
```

### 12. Find Multi-Agent Sessions

**Problem**: Did this conversation spawn sub-agents?

```bash
# Count Task tool usage
cat "$JSONL" | jq 'select(.message.content[]?.name == "Task")' | wc -l

# Show agent descriptions
cat "$JSONL" | jq -r '
  select(.message.content[]?.type == "tool_use") |
  .message.content[] |
  select(.type == "tool_use" and .name == "Task") |
  "Agent: \(.input.description)"
'
```

---

## Advanced Patterns

### Cross-Project Keyword Search with Context

```bash
KEYWORD="vision"

find ~/.claude/projects/ -name "*.jsonl" -exec sh -c '
  grep -l "$1" "$2" && echo "=== $2 ===" &&
  grep "$1" "$2" | head -2 | jq -r .message.content[0].text 2>/dev/null
' _ "$KEYWORD" {} \;
```

### Find Expensive Conversations (>10k tokens)

```bash
for jsonl in ~/.claude/projects/*/*.jsonl; do
  TOKENS=$(cat "$jsonl" | jq -r 'select(.message.usage) | .message.usage.output_tokens' | awk '{sum+=$1} END {print sum}')
  if [ "$TOKENS" -gt 10000 ]; then
    echo "$TOKENS tokens | $(basename $jsonl .jsonl)"
  fi
done | sort -rn
```

### Extract All WebSearch Results

```bash
cat "$JSONL" | jq -r '
  select(.type == "user") |
  .message.content[] |
  select(.type == "tool_result") |
  select(.content | contains("WebSearch")) |
  .content
' | head -1000
```

### Timeline of Conversation

```bash
cat "$JSONL" | jq -r '
  select(.type == "user" or .type == "assistant") |
  .timestamp + " | " + .type + " | " +
  (if .type == "user" then
    (.message.content | if type == "array" then (.[0].text[:50] // "") else ""end)
   else
    (.message.content[0].text[:50] // "")
   end)
' | column -t -s '|'
```

---

## Debugging Tips

### 1. Unknown JSONL Structure?

```bash
# Sample first 5 lines, pretty print
head -5 "$JSONL" | jq '.' | less
```

### 2. Finding Specific Fields

```bash
# List all top-level keys
cat "$JSONL" | jq -r 'keys[]' | sort -u

# List message content types
cat "$JSONL" | jq -r '.message.content[]?.type' | sort -u
```

### 3. Dealing with jq Errors

**Error**: `Cannot index string with number`
**Cause**: Trying to iterate over a string instead of array

**Fix**: Add type check
```bash
# Bad
.message.content[0].text

# Good
.message.content | if type == "array" then .[0].text else . end
```

### 4. Filtering Nulls

```bash
# Add to end of pipeline
... | grep -v "^null$"

# Or in jq
... | select(. != null)
```

---

## Common Task Recipes

### Recipe 1: "What did we decide about X?"

```bash
KEYWORD="architecture"
SESSION="9ca1bf1f-6778"
JSONL=$(find ~/.claude/projects/ -name "${SESSION}*.jsonl")

# Find messages containing keyword
cat "$JSONL" | jq -r '
  select(.type == "user" or .type == "assistant") |
  select(.message.content | tostring | contains("'"$KEYWORD"'")) |
  if .type == "user" then "\n## USER\n" else "\n## ASSISTANT\n" end +
  (.message.content | if type == "array" then (.[0].text // .[0].type) else . end)
' 2>/dev/null
```

### Recipe 2: "Show me all code changes"

```bash
cat "$JSONL" | jq -r '
  select(.message.content[]?.type == "tool_use") |
  .message.content[] |
  select(.type == "tool_use" and .name == "Edit") |
  "File: \(.input.file_path)\nOld: \(.input.old_string[:100])\nNew: \(.input.new_string[:100])\n---"
'
```

### Recipe 3: "Export for another agent"

```bash
# Create clean markdown for piping to claude -p
cat "$JSONL" | jq -r '
  select(.type == "user" or .type == "assistant") |
  if .type == "user" then
    "**User**: " + (.message.content | if type == "array" then (.[0].text // "") else . end)
  else
    "**Claude**: " + ((.message.content[] | select(.type == "text") | .text) // "")
  end
' 2>/dev/null | grep -v "^**.*: $" > export.md

# Use it
cat export.md | claude -p "Summarize the key decisions"
```

---

## Comparison: trace vs Bash

| Task | trace | Bash |
|------|-------|------|
| Get conversation | `trace --session ID --conversation` | 15-line jq pipeline |
| List files | `trace --session ID --files` | 5-line jq pipeline |
| Tools used | `trace --session ID --tools` | 3-line jq pipeline |
| Find by keyword | `trace --marker "X"` | `find ... -exec grep ...` |
| Cross-project | Auto | Manual path encoding |
| **Reliability** | Fails on import errors | **Always works** |
| **Flexibility** | Fixed queries | **Unlimited** |
| **Speed** | Fast (filtered) | Raw (can be slow on large files) |

**Recommendation**: Use trace when it works, bash when it doesn't or when you need custom queries.

---

## Troubleshooting

### "Session not found"

**Problem**: trace can't find session in current project

**Solution**: Search globally
```bash
find ~/.claude/projects/ -name "*session-prefix*.jsonl"
```

### "Cannot parse JSON"

**Problem**: jq fails on certain lines

**Solution**: Add error suppression
```bash
... 2>/dev/null
```

Or debug which line fails:
```bash
cat "$JSONL" | while read line; do
  echo "$line" | jq '.' >/dev/null 2>&1 || echo "Bad line: $line"
done
```

### "Too much output"

**Problem**: jq dumps huge JSON

**Solution**: Pipe through less or head
```bash
cat "$JSONL" | jq '.' | less
cat "$JSONL" | jq -r '.message.content[0].text' | head -20
```

---

## Quick Reference Card

```bash
# Project encoding
PROJECT=$(pwd | sed 's|/|-|g' | sed 's|^-||')

# Find session file
JSONL=$(find ~/.claude/projects/ -name "${SESSION}*.jsonl")

# User messages
cat "$JSONL" | jq -r 'select(.type == "user") | .message.content | if type == "array" then .[0].text else . end' 2>/dev/null

# Files modified
cat "$JSONL" | jq -r 'select(.message.content[]?.type == "tool_use") | .message.content[] | select(.name == "Write" or .name == "Edit") | .input.file_path' | sort -u

# Tools used
cat "$JSONL" | jq -r 'select(.message.content[]?.type == "tool_use") | .message.content[].name' | sort | uniq -c | sort -rn

# Find by file
find ~/.claude/projects/ -name "*.jsonl" -exec grep -l "file.md" {} \;

# Session metadata
head -10 "$JSONL" | jq -r 'select(.sessionId) | {session, cwd, timestamp}' | head -1
```

---

## See Also

- `trace-vs-bash-analysis.md` - Comparative analysis of approaches
- `conversation-archaeology-methodology.md` - Original methodology document
- TRACE CLI documentation (when working)
