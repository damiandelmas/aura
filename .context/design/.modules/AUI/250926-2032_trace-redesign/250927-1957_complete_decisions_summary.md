# imem Async Agent Architecture - Complete Decisions Summary

## Document Purpose
This document captures ALL decisions made through 9 rounds of alignment questions. This is the definitive reference for implementation.

---

## Core Architecture Decisions

### Foundation (Questions 1-3)

**1. Core Purpose & Scope**
- **Decision**: Memory-focused intelligent agents (Option A)
- **Future**: Architect for potential expansion to planning/design agents (Option B consideration)
- **Rationale**: Start focused, build solid foundation for future growth

**2. Intelligence Distribution Model**
- **Decision**: Intelligent workers - each agent maintains Claude SDK session (Option B)
- **Future**: Potentially hybrid orchestrator/worker pattern (Option C)
- **Rationale**: Full conversational intelligence with context continuity

**3. Integration Pattern**
- **Decision**: Tightly coupled with TRACE/pulse/core (Option A)
- **Event-driven triggers**: changelog.complete → pulse.complete → prune.complete
- **Rationale**: Seamless automatic pipeline, minimal user intervention

---

## Workflow Pipeline (Established)

```
DEVELOPMENT SESSION
    ↓
User: "imem async spawn changelog --context trace:last"
    ↓
[ChangelogAgent spawns with full conversation context]
    ↓ (works asynchronously in background)
    ↓
[Agent autonomously decides: small/medium/large changelog]
    ↓
[Creates CHU-format changelog in .memory/.changes/YYMMDD-HHMM_topic/]
    ↓
[Automatically triggers PULSE]
    ↓
[PULSE reads changelog → updates SNAPSHOT documents]
    ↓
[Automatically triggers PRUNE]
    ↓
[PRUNE updates metadata on previous changelogs]
    ↓
COMPLETE (no automatic re-indexing)
```

---

## Implementation Details (Questions 4-9)

### 4. Changelog Scope Assessment
- **Decision**: Agent uses own judgment (no hardcoded rules)
- **Rationale**: Trust Claude's intelligence to assess context and decide appropriate scope
- **Implementation**: Agent receives full context, autonomously determines small/medium/large

### 5. Pulse Evolution Strategy
- **Decision**: Keep simple, AI-powered from day 1
- **Never use**: Keyword detection or rule-based triggers
- **Future**: Let pulse agent decide if it needs to spawn sub-agents (AssessmentAgent pattern)
- **Phase 1**: Current pulse.py stays as-is, integrated into async system

### 6. Recovery Strategy
- **Decision**: Session-based recovery using Claude SDK session IDs (Option C)
- **Implementation**: Store session IDs in `~/.imem/async/sessions.json`
- **Behavior**: Agent crashes → resume exact conversation from session ID
- **Rationale**: Most sophisticated, most reliable approach

### 7. Agent Context Delivery
- **Decision**: Full context delivery (Option A)
- **Implementation**: Pass entire TRACE conversation to agent at spawn time
- **Rationale**: Let AI intelligence extract what matters, avoid premature curation
- **Note**: Context limits addressed via smart chunking (see Question 23)

### 8. Pipeline Failure Recovery
- **Decision**: Agent self-diagnosis (Option C)
- **Behavior**: Failed agent analyzes its own failure, decides if retry makes sense
- **Rationale**: Trust intelligent agents over complex retry mechanisms
- **Anti-pattern**: No exponential backoff or over-engineered failure handling

### 9. Concurrent Agent Scenarios
- **Decision**: Agent coordination (Option C)
- **Use Case**: Two parallel development streams in same codebase
- **Example**: Feature A work + Feature B prototyping simultaneously
- **Implementation**: Agents coordinate via file locks OR sequential queuing (see Question 10)
- **Rationale**: User isn't stupid - won't spawn duplicates accidentally

---

## Operational Behavior (Questions 10-15)

### 10. Agent Coordination Mechanism
- **Decision**: Sequential queue for PULSE operations (Option B)
- **Behavior**:
  - Changelog agents work in parallel creating changelogs
  - PULSE operations queue sequentially to avoid SNAPSHOT conflicts
  - No complex lock management needed
- **Rationale**: Clean, simple, prevents file conflicts

### 11. Agent Self-Diagnosis Implementation
- **Decision**: Conversational diagnosis (Option C)
- **Capability**: Agent maintains full context throughout execution
- **On Failure**: Can reason about "what I was trying to do when I failed"
- **Access**: Error logs + original changelog + SNAPSHOT state + git diff + conversation context

### 12. TRACE Session Binding
- **Decision**: One-time context snapshot (Option A)
- **Behavior**: Pass full conversation at spawn time, agent works with that frozen context
- **Rationale**: Avoids context limit issues from live querying
- **Note**: Questions 12A and 12B were functionally equivalent

### 13. Sequential PULSE Queue Behavior
- **Decision**: Strict FIFO (Option A)
- **Behavior**: First to complete runs first, second waits until first PULSE fully done
- **Rationale**: Simple, predictable, avoids race conditions

### 14. Agent State Visibility
- **Decision**: Dashboard + on-demand detail (Option C + Enhanced)
- **Commands**:
  ```bash
  imem async status                              # Dashboard of ALL agents
  imem async status changelog_20250922_1630      # High-level status
  imem async status changelog_20250922_1630 --verbose  # Full logs
  ```
- **Rationale**: Simple overview by default, granular detail when needed

### 15. Pipeline Abort/Cleanup
- **Decision**: Simple kill (Option A, pragmatic)
- **Behavior**: `imem async cancel <agent_id>` terminates immediately
- **Rationale**: Edge case that won't happen 99% of the time, keep simple

---

## Data Architecture (Questions 16-18)

### 16. Agent Output Organization
- **Decision**: Agent auto-names from conversation analysis (like `/log` slash command)
- **Format**: `.memory/.changes/YYMMDD-HHMM_topic/changelog.md`
- **Example**: `.memory/.changes/250922-1630_async-agent-architecture/changelog.md`
- **Implementation**: Agent analyzes conversation and creates meaningful folder names

### 17. Pipeline State Storage
- **Decision**: Global registry storage (Option C)
- **Location**: `~/.imem/async/` (consistent with `~/.imem/registry.json`)
- **Structure**:
  ```
  ~/.imem/async/
  ├── sessions.json       # Session IDs for recovery
  ├── agents.json         # Active agent metadata
  └── archive/            # Completed agent data
  ```
- **Rationale**: Consistent with existing imem architecture

### 18. Agent Session Artifacts
- **Decision**: Archive strategy (Option B)
- **Behavior**:
  - Keep session logs and context for analysis
  - Move to `.async/archive/` after 30 days
  - Delete after 90 days
- **Rationale**: Balance debugging needs with disk space

---

## Output Format & Intelligence (Questions 19-21)

### 19. CHU Metadata Generation
- **Decision**: Match existing CHU format exactly (Option A)
- **Schema**:
  ```yaml
  schema_version: "v2_7f3a9b4e"
  type: completed/planning/architectural/revert/analysis
  status: implemented/reverted/partial/draft
  scope: ui/backend/data/architecture/bug-fix/feature/refactor
  chu_keywords: 6-9 dense technical terms
  timestamp: PST format
  ```
- **Rationale**: Consistency with existing `/log` slash command output

### 20. Conversation Analysis Depth
- **Decision**: Full depth always (Option A)
- **Phase 1**: Match comprehensive CHU template exactly
- **Phase 2**: Enable adaptive depth (agent decides summary vs detailed)
- **Sections**:
  - Original Request
  - Implementation Overview
  - Key Decisions
  - Technical Implementation
  - File Operations Audit Trail
  - Knowledge Capture

### 21. Agent Naming & Topic Extraction
- **Decision**: Agent extracts topic autonomously (Option A)
- **Behavior**: Agent analyzes conversation, generates topic string
- **Format**: `parallel-agents-implementation`, `auth-system-refactor`
- **No user override**: Trust agent's topic extraction ability

---

## Pipeline Orchestration (Questions 22-24)

### 22. Pipeline Completion Notification
- **Decision**: Silent completion (Option A)
- **Behavior**: User checks `imem async status` when they want updates
- **Rationale**: Clean, unobtrusive, no terminal spam

### 23. Agent Conversation Context Limits
- **Decision**: Smart chunking (Option C)
- **Behavior**: For massive conversations (>200k tokens):
  - Agent processes conversation in chunks
  - Synthesizes final changelog from chunk summaries
  - No manual intervention required
- **Rationale**: Handles real-world large sessions gracefully

### 24. Re-indexing After Pipeline
- **Decision**: Manual trigger (Option C)
- **Behavior**: Prune updates metadata only, no automatic re-indexing
- **Command**: User runs `imem update` when desired
- **Rationale**:
  - Embeddings are semantic, can tolerate metadata/content discrepancy
  - Prune only touches metadata, not content
  - Avoid unnecessary re-indexing overhead

---

## Agent Types - Phase 1

### ChangelogAgent (Intelligent Decision Maker)

**Purpose**: Create CHU-format changelogs from development sessions

**Intelligence**: Full Claude SDK session analyzing conversation context

**Inputs**:
- Full TRACE conversation (one-time snapshot)
- Optional: `--context trace:last` or `--context trace:session_xyz`

**Decision Process**:
- Analyzes conversation context autonomously
- Decides small/medium/large changelog scope
- Generates folder name (e.g., `250922-1630_topic`)
- Creates comprehensive CHU documentation

**Output**: `.memory/.changes/YYMMDD-HHMM_topic/changelog.md`

**Triggers**:
- Manual: `imem async spawn changelog --context trace:last`
- Future: Automatic after significant TRACE sessions

---

### PulseAgent (Document Synthesizer)

**Purpose**: Read changelogs and update SNAPSHOT documentation

**Intelligence**: Claude SDK session understanding documentation structure

**Current Behavior** (from existing pulse.py):
- Reads changelog from `.changes/`
- Updates relevant files in `.snapshot/`
- Maintains documentation coherence

**Future Enhancement**:
- Agent decides if architectural decisions need separate decision document
- Spawns sub-agents (DecisionDocAgent, ArchitectureUpdateAgent)
- For now: Keep existing pulse.py logic, integrate into async system

**Triggers**: Automatically after ChangelogAgent completes

---

### PruneAgent (Metadata Manager)

**Purpose**: Update metadata on previous changelogs based on new changes

**Intelligence**: Understands changelog relationships and obsolescence

**Behavior**:
- Reviews all previous changelogs in `.memory/.changes/`
- Updates metadata on obsoleted changelogs
- Marks superseded content
- Updates cross-references
- **Does NOT** trigger re-indexing (user does manually)

**Triggers**: Automatically after PulseAgent completes

---

## Technical Implementation

### Component Structure

```
imem/src/
├── async_agents/
│   ├── manager.py              # AsyncAgentManager - lifecycle control
│   ├── base_agent.py           # BaseAsyncAgent - Claude SDK integration
│   ├── agents/
│   │   ├── changelog_agent.py  # Intelligent changelog creation
│   │   ├── pulse_agent.py      # Document synthesis
│   │   └── prune_agent.py      # Metadata management
│   └── state/
│       ├── session_store.py    # Session ID persistence
│       └── agent_status.py     # Status tracking
```

### Session Persistence Format

```json
// ~/.imem/async/sessions.json
{
  "agent_id": "changelog_20250922_1630",
  "session_id": "sess_abc123xyz",
  "status": "running",
  "started_at": "2025-09-22T16:30:00Z",
  "checkpoint": "analyzing_context",
  "context": {
    "trace_last_n": 7,
    "conversation_id": "conv_xyz"
  }
}
```

### Event-Driven Triggers

```python
class AsyncAgentManager:
    def __init__(self):
        self.event_handlers = {
            "changelog.complete": self.trigger_pulse,
            "pulse.complete": self.trigger_prune,
            "prune.complete": self.mark_pipeline_complete
        }

    async def on_agent_complete(self, agent_type, result):
        event_name = f"{agent_type}.complete"
        if event_name in self.event_handlers:
            await self.event_handlers[event_name](result)
```

### PULSE Sequential Queue

```python
class PulseQueue:
    def __init__(self):
        self.queue = asyncio.Queue()
        self.current_pulse = None

    async def enqueue(self, pulse_agent):
        """Add pulse operation to FIFO queue"""
        await self.queue.put(pulse_agent)

    async def process_queue(self):
        """Process pulse operations sequentially"""
        while True:
            pulse_agent = await self.queue.get()
            self.current_pulse = pulse_agent
            await pulse_agent.execute()
            self.current_pulse = None
            self.queue.task_done()
```

---

## CLI Interface

### Commands Defined

```bash
# Spawn changelog agent
imem async spawn changelog --context trace:last
imem async spawn changelog --context trace:session_xyz

# Status monitoring
imem async status                              # Dashboard of all agents
imem async status changelog_20250922_1630      # Specific agent high-level
imem async status changelog_20250922_1630 --verbose  # Full logs

# Agent control
imem async cancel changelog_20250922_1630      # Kill agent immediately

# Recovery
imem async recover changelog_20250922_1630     # Resume from session ID
```

### Dashboard Output Format

```
ACTIVE AGENTS:
┌────────────────────────────────┬──────────┬────────────┬──────────┐
│ Agent ID                       │ Type     │ Status     │ Progress │
├────────────────────────────────┼──────────┼────────────┼──────────┤
│ changelog_20250922_1630        │ Changelog│ Running    │ 45%      │
│ Session: sess_abc123xyz        │          │            │          │
│ Started: 2 minutes ago         │          │            │          │
└────────────────────────────────┴──────────┴────────────┴──────────┘

QUEUED AGENTS:
┌────────────────────────────────┬──────────┬────────────┐
│ Agent ID                       │ Type     │ Queue Pos  │
├────────────────────────────────┼──────────┼────────────┤
│ pulse_20250922_1632            │ Pulse    │ #1         │
└────────────────────────────────┴──────────┴────────────┘

COMPLETED AGENTS (last 5):
┌────────────────────────────────┬──────────┬──────────┬──────────┐
│ Agent ID                       │ Type     │ Duration │ Result   │
├────────────────────────────────┼──────────┼──────────┼──────────┤
│ prune_20250922_1500            │ Prune    │ 45s      │ Success  │
│ pulse_20250922_1459            │ Pulse    │ 2m 15s   │ Success  │
└────────────────────────────────┴──────────┴──────────┴──────────┘
```

---

## Key Design Principles

### 1. AI Judgment Over Rules
- Agents use Claude's intelligence to make decisions
- No hardcoded thresholds or keyword detection
- Trust AI to understand nuance and context

### 2. Session-Based Intelligence
- Each agent is a full Claude SDK session
- Maintains conversation context throughout execution
- Session IDs enable exact recovery after crashes

### 3. Tight Integration
- Event-driven triggers between agents
- Automatic pipeline execution (changelog → pulse → prune)
- Seamless integration with TRACE/pulse/core

### 4. Fire-and-Forget UX
- User spawns agent and continues development
- Agents work asynchronously in background
- Optional monitoring via status commands

### 5. Graceful Recovery
- Session persistence enables crash recovery
- Resume exact conversation from session ID
- No lost work, no manual intervention needed

### 6. Simplicity Over Complexity
- No exponential backoff or over-engineered retry logic
- Simple kill for abort (99% won't happen)
- Sequential queue over complex lock management
- Trust Claude SDK robustness

---

## Success Metrics

### Performance Targets
- Agent spawn time: < 2 seconds
- Changelog creation: < 5 minutes for large sessions
- Full pipeline (changelog → pulse → prune): < 10 minutes
- Recovery time: < 10 seconds

### Resource Constraints
- Max 3 concurrent changelog agents (parallel development streams)
- Session state < 10MB per agent
- Clean shutdown with SIGTERM handling
- Archive after 30 days, delete after 90 days

### Quality Metrics
- Agent decisions align with human judgment 90%+
- Zero data loss on crashes (session recovery)
- Pipeline success rate > 95%
- CHU format consistency 100%

---

## Open Questions (Round 9 - Pending)

### 25. Agent Failure Self-Diagnosis Scope
When agent fails and diagnoses itself, what actions can it take?
- Diagnosis only?
- Self-repair attempts?
- Escalation decisions?

### 26. Cross-Agent Learning
Should successful agent patterns help future agents?
- Isolated agents?
- Prompt evolution?
- Shared knowledge pool?

### 27. Pipeline Modification Mid-Flight
Can user modify pipeline after spawn?
- No modifications?
- Interruptible?
- Pre-configured flags?

---

## Implementation Timeline

### Week 1: Foundation
- [ ] BaseAsyncAgent with Claude SDK integration
- [ ] Session persistence (sessions.json)
- [ ] AsyncAgentManager lifecycle
- [ ] Status tracking in ~/.imem/async/

### Week 2: ChangelogAgent
- [ ] Full ChangelogAgent implementation
- [ ] TRACE context integration
- [ ] CHU format output
- [ ] Smart chunking for large contexts

### Week 3: Pipeline Automation
- [ ] Integrate pulse.py as PulseAgent
- [ ] Implement PruneAgent
- [ ] Event-driven triggers
- [ ] Sequential PULSE queue

### Week 4: Polish & Recovery
- [ ] Session-based recovery
- [ ] CLI commands (spawn, status, cancel, recover)
- [ ] Dashboard output
- [ ] Documentation

---

## Conclusion

We have complete alignment on:
- Core architecture (intelligent workers with Claude SDK sessions)
- Workflow pipeline (changelog → pulse → prune)
- Operational behavior (FIFO queue, silent completion, simple kill)
- Data organization (CHU format, auto-naming, global registry)
- Intelligence boundaries (AI judgment, conversational diagnosis, smart chunking)

**Three open questions remain** (Round 9) before final implementation lockdown.

This architecture delivers intelligent, autonomous agents that maintain institutional memory while developers continue working, with full crash recovery and minimal user intervention.

---

**Status**: 24/27 decisions finalized, ready for Round 9 final questions.