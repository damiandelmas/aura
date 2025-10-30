---
type: "design"
timestamp: "2025-10-09 16:41 PST"
---

# Coordinator Agent Architecture: "Brother" Pattern for Intelligent Orchestration

## Question
> How should we orchestrate PULSE/PRUNE agents? Should we use file watchers (dumb automation) or intelligent coordination? What's the most elegant approach?

## Key Insights

### 1. Intelligence Over Automation
- **Dumb automation** (file watchers): Blind triggering, no context, no adaptation
- **Intelligent orchestration**: Context-aware, adaptive, error-recovery capable
- Eliminate file watcher daemon entirely - use slash commands + agent coordination

### 2. "Brother" Pattern - Peer Intelligence
- CoordinatorAgent = Peer to Claude Code agent, not subordinate
- Inherits FULL conversation context via TRACE (no summarization loss)
- Same reasoning capability, same architectural understanding
- Runs asynchronously (doesn't block user)

### 3. Context Inheritance is Critical
- CoordinatorAgent receives complete conversation memory
- Understands architectural decisions made during development
- Can make intelligent routing decisions (not rule-based)
- Agent "spawns a brother of itself" with same intelligence

### 4. Swarms as Infrastructure, Not Intelligence
- Extract: TaskQueue, priority handling, retry logic, MCP management
- Keep: Memory hierarchy, validation gates, context inheritance, intelligent routing
- Swarms provides plumbing, our system provides intelligence

## Explored Ideas

### Initial Design (Rejected)
```
File created → Watchdog detects → PULSE triggers → Hope it works
```
**Problems:**
- Extra daemon to manage
- No context awareness
- Can't adapt to change scope
- No error recovery

### Intelligent Orchestration (Adopted)
```
/log:develop → Spawn CoordinatorAgent (with context) →
  Assess impact → Generate guidance → Spawn sub-agents → Monitor
```
**Benefits:**
- No background daemon
- Context-aware triggering
- Adaptive workflows
- Intelligent guidance generation
- Error recovery capability

### Architecture Layers

**Layer 1: User Validation Gate (Synchronous)**
- Slash command entry point
- Human approval checkpoint
- Spawns CoordinatorAgent with conversation context

**Layer 2: Context Inheritance (Read-only)**
- TRACE provides full conversation memory
- No summarization - complete context transfer
- Agent understands architecture decisions

**Layer 3: Meta-Intelligence (Asynchronous)**
- CoordinatorAgent assesses changelog impact
- Generates specific guidance for each sub-agent
- Makes intelligent routing decisions
- Monitors execution

**Layer 4: Task Execution (Swarms TaskQueue)**
- Priority queue: ChangelogAgent (high) → PULSE (medium) → PRUNE (low)
- Retry logic and error handling
- MCP management endpoints

**Layer 5: Results (Async callback)**
- CoordinatorAgent reports results
- Claude Code displays to user

## Outcomes

### Final Architecture Shape

```
USER: /log:develop (in conversation)
    ↓
Claude Code spawns CoordinatorAgent
    ↓
CoordinatorAgent inherits conversation memory (via TRACE)
    ↓
CoordinatorAgent decides:
  - What guidance to give ChangelogAgent
  - What guidance to give PULSE (context-specific)
  - What guidance to give PRUNE
  - How to route updates
    ↓
CoordinatorAgent spawns sub-agents (Swarms TaskQueue)
    ↓
Results flow back to Claude Code
    ↓
Report to user
```

### Key Design Decisions

1. **No file watcher daemon** - Intelligent coordination only
2. **Full context inheritance** - TRACE provides complete conversation
3. **Peer intelligence pattern** - CoordinatorAgent = brother, not servant
4. **Swarms for infrastructure** - TaskQueue, retry, MCP management
5. **Intelligence-based routing** - Agent decides, not rules

### Code Shape Principles

1. **Validation Gate (Synchronous)**
   - `/log:develop` → Validate → Spawn coordinator

2. **Context Inheritance (Read-only)**
   - `TRACE.get_conversation(session_id)` → Full context

3. **Meta-Intelligence (Asynchronous)**
   ```python
   class CoordinatorAgent:
       def __init__(self, session_id):
           self.conversation = TRACE.get_conversation(session_id)

       def assess_impact_with_context(self, changelog):
           # Uses full conversation context, not rules
           # Understands architecture decisions
           # Generates intelligent guidance
   ```

4. **Task Execution (Swarms)**
   ```python
   queue.add_task(task, priority=high|medium|low, max_retries=3)
   ```

### What We Extract from Swarms
- TaskQueue class (priority queue + retry)
- MCP management tools (pause/resume/stats)
- Worker pool pattern
- Thread-based execution

### What We Keep from Our System
- Three-tier memory (.design/.develop/.document/)
- Validation gates (slash commands)
- Bookmark-based session tracking
- Intelligence chain (reader → transformer → indexer)
- Temporal blockchain (part N references N-1)
- Agent-decides-routing (not rule-based)

## References

### Architecture Comparisons
- **imem-suite system**: Three-tier memory, intelligence chain, truth cascade
- **Swarms AOP**: Task queue, priority handling, MCP management
- **Integration**: Swarms provides infrastructure, imem provides intelligence

### Key Patterns
- **"Brother" pattern**: Spawn peer intelligence with full context
- **Context inheritance**: TRACE → Full conversation → CoordinatorAgent
- **Intelligence over rules**: Agent decides based on context, not thresholds
- **Async orchestration**: User unblocked, coordination happens in background

### Practical Implementation
- Eliminate watchdog dependency
- Simpler architecture (4 CLIs + 3 services + agents, no daemon)
- More agile (change guidance prompts easily)
- Better error recovery (intelligent retry)
- Skip processing for trivial changes
- Spawn assessment crews for major changes

### Benefits Summary

**Simpler:**
- ❌ No watchdog daemon
- ❌ No background processes
- ❌ No process management
- ✅ Just slash commands + agents

**Smarter:**
- ✅ Context-aware triggering
- ✅ Intelligent guidance generation
- ✅ Adaptive workflows
- ✅ Error recovery

**More Agile:**
- ✅ Change guidance prompts easily
- ✅ Skip PULSE for trivial changes
- ✅ Spawn assessment crews for major changes
- ✅ Iterate based on results
