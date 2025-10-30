---
type: "design"
timestamp: "2025-10-11T14:17:00-07:00"
status: "decided"
---

# Phase 4: Session Management Architecture - Current vs Other Conversations

## Question
> "How should ORCA and TRACE handle session detection? Should users need to provide bookmarks when they're already inside a conversation?"

## Key Insights

### 1. Bookmark is an Implementation Detail, Not a User Concept
- **Inside conversation**: Bookmark should be invisible (auto-detected from context)
- **Outside conversation**: Bookmark is explicit (for working with OTHER conversations)
- **User mental model**: "this conversation" vs "that conversation", NOT "bookmark abc123"

### 2. Two Distinct Usage Modes

**Mode 1: Inside Conversation (90% of cases)**
```bash
/log:develop              # Auto-extracts bookmark from context
trace --current           # Shows THIS conversation
orca spawn ChangelogAgent # Works on THIS conversation
```

**Mode 2: Outside Conversation (10% of cases)**
```bash
# From terminal, documenting OTHER conversations:
orca spawn ChangelogAgent --bookmark abc123
trace --session abc123

# Or work with most recent:
orca spawn ChangelogAgent --recent
trace --recent
```

### 3. Context Injection Makes This Possible
- SessionStart hook already injects: `🔖 Session: uuid` + `📎 Bookmark: abc123`
- Slash commands can extract directly from conversation context
- No file reading or manual lookup needed

### 4. TRACE Should Have Current Awareness
```bash
# TRACE modes:
trace --current           # THIS conversation (auto-detect)
trace --session abc123    # THAT conversation (explicit bookmark)
trace --session 1         # THAT conversation (by index)
trace --list              # All conversations
```

## Explored Ideas

### A. Always Require Bookmark (Rejected)
```bash
# Every command needs bookmark:
orca spawn ChangelogAgent --bookmark abc123
trace --session abc123
```
**Why rejected**: Too much friction when you're already IN the conversation. User has to manually extract bookmark from context.

### B. Implicit Current Detection (Chosen)
```bash
# Inside conversation:
orca spawn ChangelogAgent    # Auto-detects from context
trace --current              # Auto-detects from context

# Outside conversation:
orca spawn --bookmark abc123  # Explicit
trace --session abc123        # Explicit
```
**Why chosen**: Zero friction for 90% case (working on current conversation), explicit only when needed.

### C. Environment Variable Detection
```bash
# Set by slash command or hook:
export ORCA_CURRENT_SESSION="93e11440-14d1-4343-99b3-d5437fdb4c6a"
export ORCA_CURRENT_BOOKMARK="93e11440-14d"

# CLI commands check environment first:
orca spawn ChangelogAgent  # Uses env vars if present
```
**Status**: Optional enhancement - slash command can set env vars for CLI to read.

## Design Decisions

### 1. Slash Command Auto-Extraction
```markdown
# ~/.claude/commands/log-develop.md

Extract bookmark from conversation context:
- Look for: "📎 Bookmark: <bookmark>"
- Parse the 12-char bookmark
- Pass to: orca workflow log-develop --bookmark {extracted}

NO manual bookmark lookup required!
```

### 2. ORCA CLI --current Flag
```python
# aura-v2/src/cli/orca.py

@click.command()
@click.option('--bookmark', default=None)
@click.option('--current', is_flag=True, help='Use current conversation')
def spawn(bookmark, current):
    if current or (not bookmark and is_slash_command_context()):
        # Auto-detect from:
        # 1. Environment variable (set by slash command)
        # 2. Registry (most recent)
        bookmark = detect_current_session()

    if not bookmark:
        click.echo("❌ Not in conversation. Use --bookmark or --current")
        return

    # Resolve and spawn...
```

### 3. TRACE CLI --current Flag
```python
# Enhanced trace CLI

@click.command()
@click.option('--current', is_flag=True)
@click.option('--session', default=None)
def trace(current, session):
    if current:
        # Detect current session from:
        # 1. Environment variable
        # 2. Registry (most recent)
        # 3. JSONL files (most recently modified)
        session_id = detect_current_session()
    elif session:
        session_id = resolve_bookmark(session)
    else:
        list_conversations()
        return

    show_conversation(session_id)
```

### 4. Detection Priority
```python
def detect_current_session():
    """Auto-detect current session bookmark"""

    # Priority 1: Environment variable (set by slash command)
    if env_bookmark := os.getenv('ORCA_CURRENT_BOOKMARK'):
        return env_bookmark

    # Priority 2: Registry (most recent conversation)
    registry = Registry()
    if recent := registry.get_most_recent():
        return recent['bookmark']

    # Priority 3: JSONL files (most recently modified)
    conversations = find_conversations()
    if conversations:
        return conversations[0]['bookmark']

    return None
```

## Outcomes

### Updated Phase 4 Components

1. **SessionStart Hook** (.claude/hooks/session-start.sh)
   - Captures session_id
   - Generates 12-char bookmark
   - Updates registry
   - Injects context markers (🔖/📎)
   - Sets environment variables (optional)

2. **Registry System** (aura-v2/src/orchestrator/registry.py)
   - add_session(session_id, bookmark)
   - get_session_id(bookmark) → full UUID
   - get_most_recent() → latest conversation
   - list_all() → all conversations

3. **ORCA CLI** (aura-v2/src/cli/orca.py)
   - `orca spawn <Agent>` → Auto-detects current
   - `orca spawn <Agent> --bookmark abc123` → Explicit
   - `orca spawn <Agent> --current` → Force current detection
   - `orca workflow log-develop` → Auto-detects current

4. **TRACE CLI Enhancement** (existing trace CLI)
   - `trace --current` → Show THIS conversation
   - `trace --current --patches` → THIS conversation's diffs
   - Keep existing: `trace --session abc123`

5. **Slash Command** (~/.claude/commands/log-develop.md)
   - Extracts bookmark from context (📎 marker)
   - Sets environment variable (optional)
   - Calls: `orca workflow log-develop --bookmark {extracted}`

### User Experience Flow

**Inside Conversation** (Zero manual steps):
```
User types: /log:develop
  ↓
Slash command extracts: "📎 Bookmark: 93e11440-14d"
  ↓
Calls: orca workflow log-develop --bookmark 93e11440-14d
  ↓
ORCA resolves bookmark → UUID from registry
  ↓
Spawns ChangelogAgent with --resume {UUID}
  ↓
Brother analyzes THIS conversation
  ↓
Changelog created automatically
```

**From Terminal** (One explicit step):
```
User runs: orca spawn ChangelogAgent --bookmark abc123
  ↓
ORCA resolves bookmark → UUID from registry
  ↓
Spawns ChangelogAgent with --resume {UUID}
  ↓
Brother analyzes THAT conversation
```

## Trade-offs

### Accepted
- **Environment variables**: Optional but useful for CLI detection
- **Registry dependency**: ORCA must read registry for bookmark → UUID resolution
- **Two code paths**: "current" detection vs explicit bookmark (worth the UX improvement)

### Rejected
- **Always require bookmark**: Too much friction for primary use case
- **Magic session detection in every CLI**: Keep detection logic in ORCA only
- **No explicit mode**: Still need --bookmark for working on OTHER conversations

## Implementation Priority

### Phase 4A (Core - 40 min):
1. ✅ SessionStart hook (10 min)
2. ✅ Registry system (20 min)
3. ✅ ORCA CLI with auto-detection (10 min)

### Phase 4B (Integration - 30 min):
4. ✅ Slash command with extraction (10 min)
5. ✅ TRACE --current flag (10 min)
6. ✅ End-to-end testing (10 min)

### Phase 4C (Polish - optional):
7. ⏸️ Environment variable integration
8. ⏸️ --recent flag (work with most recent)
9. ⏸️ Better error messages

## References

- E_01_SYSTEM_ARCHITECTURE.md: ORCA + TRACE CLI signatures
- E_02_AGENT_PROTOCOLS.md: SessionStart hook specification
- E_03_DESIGN_RATIONALE.md: Bookmark design (12-char, collision risk)
- Phase 3 completion: ClaudeAgent + YAML + Workflows ($1.20 test SUCCESS)

## Key Architectural Principle

**"Bookmark is a bridge for cross-conversation work, not a required input when you're already in the conversation."**

Users think in terms of:
- ✅ "This conversation" (current, auto-detected)
- ✅ "That conversation" (other, explicit bookmark)

NOT:
- ❌ "Let me find my bookmark first"
- ❌ "What's my session ID?"

The system handles the translation automatically.
