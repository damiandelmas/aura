---
type: "architectural"
timestamp: "2025-10-10T17:57:00-0700"
---

# ORCA Architecture Alignment - Slash Commands + CLI + Brother Spawning

## Question
> "also i would probably type slash command to start it /log:design, then it would give u a command to run the orca design script. it would trigger async and we would continue our covnersation. u get it?"

## Context

AURA system has 3 control layers:
1. **Slash commands** - User convenience (`/log:design`, `/log:develop`)
2. **ORCA CLI** - Explicit brother spawning (`orca design --session abc123`)
3. **Brothers** - Peer intelligence via `claude -p --resume`

Needed clarity on:
- Why ORCA needs a CLI
- How slash commands relate to ORCA CLI
- Async flow pattern (non-blocking)
- When to use which control point

## Key Insights

### 1. The Three Control Points

**Slash Commands** (`/log:design`, `/log:develop`):
- ✅ User convenience (type `/log:develop` in conversation)
- ✅ Auto-extracts session_id from context
- ✅ Synchronous option (I do the work, blocking)
- ✅ Async option (I spawn ORCA brother, non-blocking)

**ORCA CLI** (`orca design`, `orca develop`):
- ✅ Explicit control (manual brother spawning)
- ✅ Requires session_id parameter
- ✅ Always async (background execution)
- ✅ Testing/debugging (spawn without slash)
- ✅ Brother-to-brother calls (ORCA spawns sub-brothers)

**Brothers** (`claude -p`):
- ✅ Full Claude Code intelligence
- ✅ Conversation context via `--resume`
- ✅ Can use all tools (Bash, Read, Write, trace, imem)
- ✅ Returns structured JSON

### 2. The Async Flow Pattern

From INTEGRATION_PATTERNS_REVISED.md (lines 134-176):

```
User: /log:develop "auth decision"
    ↓
Slash command expands
    ↓
I extract bookmark: abc123def456
    ↓
I spawn ORCA CLI (async):
  subprocess.Popen(["orca", "develop", "--session", "abc123"])
    ↓
I return IMMEDIATELY:
  "✅ ChangelogAgent spawned (running in background)
   📋 Session: abc123def456

   Or run manually:
     orca develop --session abc123def456"
    ↓
[ChangelogAgent brother runs in background]
    ↓
[User and I continue conversation unblocked]
    ↓
[~30s later] Brother completes
    ↓
I notify user:
  "📝 Changelog created: 251010-1830_auth-decision.md
   💰 Cost: $0.0034"
```

**Key insight**: User types `/log:develop`, gets:
1. Immediate response (brother spawned)
2. Manual command (for debugging: `orca develop --session abc123`)
3. Unblocked conversation (can continue working)
4. Completion notification (when done)

### 3. Why ORCA Needs a CLI

**Use Case 1: Manual Brother Spawning**
```bash
# Testing: Spawn DesignAgent manually
orca design --session abc123def456

# Debugging: Re-run PULSE on specific changelog
orca pulse --changelog .context/develop/changes/251010-1830_auth.md

# Recovery: Re-run PRUNE after failure
orca prune --session abc123def456
```

**Use Case 2: Brother-to-Brother Orchestration**

CoordinatorAgent (itself a brother) spawns sub-brothers:
```python
# CoordinatorAgent uses Bash tool to spawn ORCA CLI
subprocess.run(["orca", "pulse", "--changelog", changelog_path])
subprocess.run(["orca", "prune", "--session", bookmark])
```

**Use Case 3: Workflow Management**
```bash
# Check running workflows
orca status

# View logs for specific workflow
orca logs <workflow-id>

# Cancel stuck workflow
orca cancel <workflow-id>
```

**Use Case 4: Called by Slash Commands**

Slash command spawns ORCA CLI in background:
```markdown
# ~/.claude/commands/log-develop.md

Extract bookmark from context
Spawn async: orca develop --session {bookmark}
Return immediately with status
```

### 4. ORCA vs pulse Distinction

**ORCA** = Agent orchestration system
- Spawns brothers via `claude -p`
- Coordinates workflows (Swarms)
- **Needs CLI** for manual triggers

**pulse** = Library used by PULSE brother
- Document maintenance logic
- Read/update `.context/document/` files
- **No CLI** (PULSE brother uses Read/Write/Edit + pulse library)

**PRUNE** = Pure brother logic
- Updates metadata chains
- **No CLI, no library** (just uses Read/Edit)

**Correct flow**:
```
orca develop --session abc123
    ↓
Spawns ChangelogAgent brother
    ↓
ChangelogAgent uses: trace --session abc123 --patches
    ↓
Spawns PULSE brother
    ↓
PULSE brother uses: Read/Write/Edit + pulse library
    ↓
Spawns PRUNE brother
    ↓
PRUNE brother uses: Read/Edit (no library)
```

### 5. Component Roles (Crystallized)

**Tools** (used by brothers):
- `trace` - CLI for conversation archaeology
- `imem` - CLI for vector search
- `pulse` - Library for document maintenance (no CLI)

**Orchestrator** (spawns brothers):
- `orca` - CLI for agent orchestration
- Spawns: DesignAgent, ChangelogAgent, PULSE, PRUNE
- Uses: Swarms (SequentialWorkflow, ConcurrentWorkflow)

**Brothers** (peer intelligence):
- ChangelogAgent - Uses trace CLI, writes `.develop/.changes/`
- PULSE - Uses pulse library + Read/Write, updates `.document/`
- PRUNE - Uses Read/Edit, updates metadata

## Explored Ideas

### ORCA CLI Subcommands

**Option A: Workflow-focused**
```bash
orca workflow run log-develop --session abc123
orca workflow status
orca workflow logs <id>
```
❌ Too verbose

**Option B: Agent-focused** (CHOSEN)
```bash
orca design --session abc123       # Spawn DesignAgent
orca develop --session abc123      # Spawn ChangelogAgent
orca pulse --changelog <file>      # Spawn PULSE
orca prune --session abc123        # Spawn PRUNE
orca status                        # Show running
orca logs <id>                     # View logs
```
✅ Concise, maps to brother names

### Slash Command Behavior

**Option A: Synchronous Only**
```
/log:develop → I analyze + write changelog (blocks)
```
❌ Blocks conversation, no async option

**Option B: Async Only**
```
/log:develop → Spawns ORCA, returns immediately
```
❌ Can't see result in conversation

**Option C: Hybrid** (CHOSEN)
```
/log:develop → Spawns ORCA (async)
            → Gives manual command
            → Polls for completion
            → Notifies when done
```
✅ Best of both: async + visibility + manual control

## Outcomes

### ORCA CLI Specification

```bash
# Design changelog (exploration)
orca design --session <bookmark>
  Spawns: DesignAgent brother
  Output: .context/design/changes/YYMMDD-HHMM_topic.md
  Uses: Full conversation context (--resume)

# Development changelog (validated)
orca develop --session <bookmark>
  Spawns: ChangelogAgent brother
  Output: .context/develop/changes/YYMMDD-HHMM_topic.md
  Uses: trace --session, conversation context
  Triggers: PULSE → PRUNE → imem update (sequential)

# Manual PULSE trigger
orca pulse --changelog <file>
  Spawns: PULSE brother
  Output: Updated .context/document/ files
  Uses: pulse library + Read/Write/Edit

# Manual PRUNE trigger
orca prune --session <bookmark>
  Spawns: PRUNE brother
  Output: Updated metadata chains
  Uses: Read/Edit

# Workflow management
orca status
  Shows: Running workflows, progress, cost
  Returns: JSON with workflow states

orca logs <workflow-id>
  Shows: Full logs for specific workflow
  Returns: JSONL with brother outputs
```

### Slash Command Behavior (Revised)

**`/log:design <topic>`**:
```
I extract bookmark from context
I spawn: orca design --session {bookmark}
I return:
  "✅ DesignAgent spawned (background)
   📋 Session: abc123def456
   📝 Topic: {topic}

   Or run manually:
     orca design --session abc123def456"

[Brother runs in background]
[User continues conversation]
[~15s later] I notify: "📄 Design log created"
```

**`/log:develop <topic>`**:
```
I extract bookmark from context
I spawn: orca develop --session {bookmark}
I return:
  "✅ ChangelogAgent spawned (background)
   📋 Session: abc123def456

   Or run manually:
     orca develop --session abc123def456"

[ChangelogAgent → PULSE → PRUNE run sequentially]
[User continues conversation]
[~45s later] I notify:
  "📝 Changelog created: 251010-1830_topic.md
   📚 Updated: ARCHITECTURE.md, USER_GUIDE.md
   🔗 Metadata: Updated chains
   💰 Total cost: $0.0089"
```

### Implementation Strategy

**Phase 1: ORCA CLI Stub**
```python
# aura/cli/orca.py
import click

@click.group()
def orca():
    """ORCA - Agent orchestration for AURA"""
    pass

@orca.command()
@click.option('--session', required=True)
def design(session):
    """Spawn DesignAgent brother"""
    # TODO: Spawn via claude -p
    click.echo(f"✅ DesignAgent spawned for session {session}")

@orca.command()
@click.option('--session', required=True)
def develop(session):
    """Spawn ChangelogAgent brother"""
    # TODO: Spawn via claude -p
    click.echo(f"✅ ChangelogAgent spawned for session {session}")

if __name__ == '__main__':
    orca()
```

**Phase 2: Brother Spawning**
```python
def spawn_brother(agent_name, session_id, task):
    """Spawn brother via claude -p"""
    cmd = [
        "claude", "-p",
        "--resume", session_id,
        "--output-format", "json",
        "--append-system-prompt", f"You are {agent_name}",
        task
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    return json.loads(result.stdout)
```

**Phase 3: Swarms Integration**
```python
from swarms import SequentialWorkflow
from aura.orca.claude_agent import ClaudeAgent

workflow = SequentialWorkflow(agents=[
    ClaudeAgent("ChangelogAgent", session_id=bookmark),
    ClaudeAgent("PULSE"),
    ClaudeAgent("PRUNE")
])
```

## Knowledge Capture

### Pattern: Three-Layer Control

**Layer 1: Slash Commands** (user convenience)
- Auto-extracts context
- Spawns layer 2 (ORCA CLI)
- Returns immediately with manual command

**Layer 2: ORCA CLI** (explicit control)
- Requires parameters
- Spawns layer 3 (brothers)
- Background execution

**Layer 3: Brothers** (peer intelligence)
- Full tool access
- Conversation context
- Structured results

**Example flow**:
```
/log:develop (Layer 1: Slash)
    ↓
orca develop --session abc123 (Layer 2: ORCA CLI)
    ↓
claude -p --resume abc123 "Create changelog" (Layer 3: Brother)
```

### Pattern: Async + Visibility

**Problem**: How to run async without losing visibility?

**Solution**:
1. Spawn async (background process)
2. Give manual command (for debugging)
3. Poll completion (check status)
4. Notify when done (show results)

**User experience**:
- Types `/log:develop`
- Gets immediate response (not blocked)
- Continues conversation
- Gets notification when complete
- Can re-run manually if needed

### Pattern: CLI Naming for Orchestration

**ORCA subcommands** = **Brother names**:
- `orca design` → DesignAgent
- `orca develop` → ChangelogAgent
- `orca pulse` → PULSE
- `orca prune` → PRUNE

**Benefits**:
- Self-documenting (command reveals brother)
- Predictable (one command per brother)
- Debuggable (test brothers independently)

## References

- `INTEGRATION_PATTERNS_REVISED.md` - Async flow (lines 134-176)
- `E_01_SYSTEM_ARCHITECTURE.md` - ORCA structure (lines 180-189)
- `E_02_AGENT_PROTOCOLS.md` - Brother protocols (lines 267-317)

## Success Metrics

- ✅ **3-layer control** clearly defined (slash, ORCA CLI, brothers)
- ✅ **Async flow** pattern documented (non-blocking)
- ✅ **Manual commands** provided (debugging)
- ✅ **ORCA CLI spec** complete (subcommands defined)

## Duration
~20 minutes (architecture alignment, flow documentation)

## Impact

**For users**:
- Slash commands = convenience (quick async spawn)
- Manual commands = control (debugging, re-running)
- Unblocked conversations = productivity (continue working)

**For system**:
- Clear orchestration boundary (ORCA)
- Testable brothers (spawn via CLI)
- Observable workflows (status, logs)

**For brothers**:
- ORCA coordinates (Swarms)
- Brothers execute (full intelligence)
- Clean separation (orchestration vs execution)

## Next Steps

1. ✅ ORCA architecture aligned (this document)
2. ⏳ Create ORCA CLI stub (`aura/cli/orca.py`)
3. ⏳ Update slash commands to spawn ORCA
4. ⏳ Implement brother spawning (`spawn_brother()`)
5. ⏳ Add Swarms workflows (`log_develop.py`)
