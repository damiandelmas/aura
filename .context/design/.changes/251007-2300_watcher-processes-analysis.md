---
schema_version: "v2_7f3a9b4e"
type: "analysis"
status: "documented"
scope: "architecture/assessment"
chu_keywords: "watcher-processes, agent-manager, pulse-integration, command-consolidation, architectural-analysis"
timestamp: "2025-10-07T23:00:00-0700"
---

# Watcher & Processes Analysis: Integration with Pulse

## Context
User feedback: "watcher and processes are part of pulse I believe? to watch over agents we've spawned"

Analyzing current implementation to understand relationship with pulse system and agent management.

## Current Implementation Analysis

### Watcher System (`watcher.py` - 173 lines)

**Purpose**: File watcher for automatic changelog syncing

**Commands**:
```bash
imem watcher start [--daemon]  # Start watching .memory/.changes/
imem watcher stop              # Stop daemon
imem watcher status            # Show daemon status
imem watcher test              # Create test file to verify
```

**What it does**:
1. Watches `.memory/.changes/` directory for new/modified markdown files
2. When change detected → triggers sync (likely calls pulse)
3. Runs as daemon or foreground process
4. Uses `WatcherDaemon` and `ChangelogWatcher` from core

**Key Code**:
```python
from ...core.daemon import WatcherDaemon
from ...core.watcher import ChangelogWatcher

# Start watching
watcher = ChangelogWatcher(project_root)
watcher.start()
```

**User's Assessment**: "doesn't work well"

### Processes System (`processes.py` - 190 lines)

**Purpose**: Manage Claude agent processes

**Commands**:
```bash
imem processes status [--all]        # Show process manager status
imem processes kill [task_id]        # Kill specific or all tasks
imem processes shutdown              # Shutdown process manager
imem processes test                  # Submit test Claude task
imem processes emergency-stop        # Kill ALL imem/claude processes
```

**What it does**:
1. Manages async Claude agent spawning
2. Tracks process states, statistics (spawned/completed/failed)
3. Limits: max_concurrent, max_total
4. Provides emergency kill switch

**Key Code**:
```python
from ...core.process_manager import get_process_manager, shutdown_process_manager

manager = get_process_manager(project_root)
manager.submit_claude_task(
    task_id=task_id,
    system_prompt=test_prompt,
    working_dir=docs_dir,
    timeout=60,
    callback=lambda tid, info: click.echo(...)
)
```

**User's Assessment**: "doesn't work well"

## Relationship to Pulse

### Current Architecture:
```
Watcher watches .memory/.changes/
    ↓
Detects new changelog file
    ↓
Triggers sync (pulse?)
    ↓
Pulse processes changelog
    ↓
Updates institutional memory
```

### Agent Spawning Flow (Hypothesized):
```
User: /log:async
    ↓
Processes spawns async Claude agent
    ↓
Agent uses TRACE to read conversation
    ↓
Agent generates changelog
    ↓
Agent writes to .memory/.changes/
    ↓
Watcher detects new file
    ↓
Pulse processes it automatically
```

## Why They Don't Work Well (Analysis)

### Watcher Issues (Suspected):
1. **File watching race conditions** - File written while being watched?
2. **Daemon management fragile** - PID files, process cleanup
3. **Unclear trigger mechanism** - What exactly happens on file change?
4. **Integration unclear** - Does it call pulse? How?

### Processes Issues (Suspected):
1. **Process lifecycle unclear** - Where do agents run? How do they report back?
2. **No output capture** - How do you see what agent produced?
3. **Error handling weak** - What if agent fails? Hangs?
4. **Session tracking missing** - Can't link agent to parent conversation
5. **Emergency stop too aggressive** - Kills ALL claude processes system-wide

### Architectural Problems:
1. **Separation of concerns violated** - Watcher watches, but who syncs?
2. **Process manager disconnected** - Not integrated with SessionStart hooks
3. **No agent lineage** - Can't track parent → child conversation relationships
4. **Manual spawning** - Should be automatic via hooks

## Integration with Pulse (Proposed)

### Consolidated Architecture:
```
imem pulse <file>           # Process specific changelog (existing)
imem pulse --history        # Show pulse session history (consolidated)
imem pulse --clear-cache    # Clear pulse cache (consolidated)
imem pulse --watch          # Watch for changes + auto-pulse
imem pulse --agents         # Spawn async agents for pulsing
```

### What `pulse --watch` Should Do:
```python
@click.option('--watch', is_flag=True)
@click.option('--agents', is_flag=True, help='Use async agents instead of direct pulse')
def pulse(changelog_file, watch, agents, ...):
    if watch:
        # Start file watcher
        watcher = FileWatcher(project_root / ".memory" / ".changes")

        def on_file_change(filepath):
            if agents:
                # Spawn async agent to pulse this file
                spawn_pulse_agent(filepath)
            else:
                # Direct pulse processing
                pulse_file(filepath)

        watcher.on_change(on_file_change)
        watcher.start()
```

### What Agent Manager Should Do:
1. **Integrated with SessionStart hooks** - Know parent conversation bookmark
2. **Proper lifecycle management** - Spawn, monitor, collect output
3. **Error handling** - Retry, timeout, failure reporting
4. **Output capture** - Save agent's changelog to .memory/.changes/
5. **Lineage tracking** - Record parent → child relationship

## Recommendations

### 1. Consolidate into Pulse ✅
```bash
# OLD (4 separate commands)
imem pulse <file>
imem pulse-history
imem clear-pulse-cache
imem watcher start

# NEW (1 command with flags)
imem pulse <file>           # Default: process file
imem pulse --history        # Consolidated
imem pulse --clear-cache    # Consolidated
imem pulse --watch          # Consolidated, improved
```

### 2. Delete Watcher & Processes ✅
- Remove `watcher.py` (173 lines)
- Remove `processes.py` (190 lines)
- Clean up core dependencies (WatcherDaemon, ChangelogWatcher, ProcessManager)

### 3. Find External Agent Manager 🔍
User suggestion: "find someone else's agent manager and take from them"

**Options to research**:
- **Claude Desktop** - Does it have agent spawning?
- **LangChain Agents** - Process orchestration patterns
- **AutoGen** - Multi-agent conversation framework
- **CrewAI** - Agent coordination system
- **Aider** - Git-aware agent management

**What to look for**:
- Async process spawning patterns
- Output capture mechanisms
- Error handling strategies
- Parent-child agent relationships
- Session/conversation tracking

### 4. Defer to Phase 2
Agent manager needs:
- SessionStart hooks (Tier 2)
- Bookmark system working
- Clear parent-child conversation model

**Don't build yet** - Research and design in Phase 2

## Update/Dedupe Alignment

### `imem update`
**What it does**:
```python
def update():
    """Re-index current project (incremental)"""
    ctx.invoke(init, force=False)
```

**Analysis**: Just calls `init` without force flag
- ✅ Simple, clear purpose
- ✅ Incremental re-indexing
- ❌ Could be `imem init --update` or `imem search --reindex`?

**Recommendation**: Keep separate for now - common operation, clear name

### `imem dedupe`
**What it does**:
- Finds documents with identical MD5 hash (same content, different paths)
- Removes older duplicates, keeps most recent version
- Has `--dry-run` mode
- Requires confirmation

**Analysis**:
- ✅ Valuable maintenance operation
- ✅ Safe with dry-run and confirmation
- ❓ Could be `imem update --dedupe`?

**Comparison**:
```bash
# Option A: Separate (current)
imem dedupe --dry-run
imem dedupe

# Option B: As update flag
imem update --dedupe --dry-run
imem update --dedupe

# Option C: As search subcommand
imem search --dedupe
```

**Recommendation**:
- **Keep separate for Phase 1** - Clear, focused, valuable
- **Consider as update flag in Phase 2** - `imem update --dedupe` makes logical sense (updating index by removing dupes)

## Final Command Architecture

### Phase 1 Consolidated (8 commands):
```bash
TRACE (1):
  trace                      # All trace functionality

PULSE (1):
  pulse                      # Process changelog
  pulse --history            # Was: pulse-history
  pulse --clear-cache        # Was: clear-pulse-cache
  pulse --watch              # Was: watcher start

IMEM (6):
  search                     # Vector search
  init                       # Initialize project
  update                     # Re-index
  status                     # Show projects
  dedupe                     # Remove duplicates
  service                    # Manage Qdrant
```

**Deleted**:
- ❌ `watcher` (4 subcommands) → Merged into `pulse --watch`
- ❌ `processes` (5 subcommands) → Defer to Phase 2 agent manager

**Net Change**: 12 → 8 commands (33% reduction)

## Implementation Tasks (Day 2)

### 1. Consolidate Pulse Commands
- [x] Read current pulse.py
- [ ] Add `--history` flag
- [ ] Add `--clear-cache` flag
- [ ] Add `--watch` flag (simple file watcher, no agents yet)
- [ ] Update help text
- [ ] Test all modes

### 2. Delete Watcher
- [ ] Remove `watcher.py`
- [ ] Remove from CLI imports
- [ ] Delete `core/daemon.py`
- [ ] Delete `core/watcher.py`
- [ ] Test pulse --watch works

### 3. Delete Processes
- [ ] Remove `processes.py`
- [ ] Remove from CLI imports
- [ ] Delete `core/process_manager.py`
- [ ] Note: Agent manager deferred to Phase 2

### 4. Documentation
- [ ] Update CLAUDE.md
- [ ] Document pulse consolidation
- [ ] Note agent manager as Phase 2 work

## Phase 2 Agent Manager Design (Future)

### Research Phase:
1. Study AutoGen, CrewAI, LangChain agent patterns
2. Understand Claude Desktop's spawning mechanism
3. Design agent lifecycle: spawn → monitor → capture → link

### Requirements:
- Integrated with SessionStart hooks
- Parent-child bookmark relationships
- Output capture to .memory/.changes/
- Error handling and retry logic
- Graceful shutdown

### Integration Point:
```bash
imem pulse --watch --agents    # Use agent-based pulsing
/log:async                     # Spawns pulse agent via agent manager
```

## Success Metrics

**Phase 1 Completion**:
- ✅ 12 → 8 commands
- ✅ Pulse has subcommands (--history, --clear-cache, --watch)
- ✅ Watcher deleted (173 lines removed)
- ✅ Processes deleted (190 lines removed)
- ✅ Cleaner architecture around trace/pulse/imem pillars

**Phase 2 Goals**:
- Agent manager researched and designed
- Integration with SessionStart hooks
- Multi-dimensional conversations working
- Async changelog generation functional
