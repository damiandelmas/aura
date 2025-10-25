# Implementation Checklist - What Needs to Be Built

## Overview
This document lists every component, file, and integration point needed to build the async agent system.

---

## Phase 0: Prerequisites & Dependencies

### External Dependencies to Install
```bash
# Claude Code SDK (if not already installed)
pip install claude-code-sdk

# Verify existing dependencies
pip list | grep -E "qdrant-client|sentence-transformers|click|pyyaml"
```

### Verify Existing Components Work
- [ ] TRACE system functional (`imem trace --list`)
- [ ] Pulse system functional (existing `pulse.py`)
- [ ] Registry system functional (`~/.imem/registry.json`)
- [ ] Service management functional (`imem service status`)

---

## Phase 1: Core Infrastructure

### 1.1 Directory Structure
Create new directories in `imem/src/`:

```bash
mkdir -p imem/src/async_agents
mkdir -p imem/src/async_agents/agents
mkdir -p imem/src/async_agents/state
mkdir -p ~/.imem/async
mkdir -p ~/.imem/async/archive
```

### 1.2 Base Agent Framework

**File: `imem/src/async_agents/base_agent.py`**
- [ ] BaseAsyncAgent class
  - [ ] Claude SDK client initialization
  - [ ] Session ID management
  - [ ] Status tracking (idle/initializing/running/completed/failed)
  - [ ] Abstract execute() method
  - [ ] Streaming progress updates
  - [ ] Session persistence hooks
  - [ ] Error handling and self-diagnosis

**Key Methods**:
```python
class BaseAsyncAgent:
    def __init__(self, agent_id: str)
    async def spawn(self, context: dict) -> AsyncGenerator
    async def execute_with_context(self, context: dict) -> AsyncGenerator
    async def save_session(self) -> None
    async def load_session(self, agent_id: str) -> dict
    async def recover_from_crash(self, agent_id: str) -> None
    def update_status(self, status: str, message: str = None)
    async def self_diagnose(self, error: Exception) -> dict
```

### 1.3 Agent Manager

**File: `imem/src/async_agents/manager.py`**
- [ ] AsyncAgentManager class
  - [ ] Agent lifecycle management (spawn/monitor/kill)
  - [ ] Event-driven trigger system
  - [ ] FIFO queue for PULSE operations
  - [ ] Agent status tracking
  - [ ] Concurrent agent coordination
  - [ ] Session recovery orchestration

**Key Methods**:
```python
class AsyncAgentManager:
    def __init__(self)
    async def spawn_agent(self, agent_class, context: dict) -> str
    async def get_status(self, agent_id: str = None) -> dict
    async def cancel_agent(self, agent_id: str) -> bool
    async def recover_agent(self, agent_id: str) -> bool
    async def on_agent_complete(self, agent_type: str, result: dict)
    def get_all_active_agents(self) -> List[dict]
    def get_completed_agents(self, limit: int = 5) -> List[dict]
```

**Event Handlers**:
```python
self.event_handlers = {
    "changelog.complete": self.trigger_pulse,
    "pulse.complete": self.trigger_prune,
    "prune.complete": self.mark_pipeline_complete
}
```

### 1.4 State Management

**File: `imem/src/async_agents/state/session_store.py`**
- [ ] SessionStore class
  - [ ] Save session metadata to `~/.imem/async/sessions.json`
  - [ ] Load session for recovery
  - [ ] Archive old sessions (30-day policy)
  - [ ] Delete archived sessions (90-day policy)
  - [ ] Session ID to agent ID mapping

**Data Format**:
```json
{
  "agent_id": "changelog_20250922_1630",
  "session_id": "sess_abc123xyz",
  "status": "running",
  "started_at": "2025-09-22T16:30:00Z",
  "checkpoint": "analyzing_context",
  "context": {
    "trace_context": "...",
    "conversation_id": "conv_xyz"
  }
}
```

**File: `imem/src/async_agents/state/agent_status.py`**
- [ ] AgentStatus class
  - [ ] Track agent state (idle/running/completed/failed)
  - [ ] Progress tracking (percentage or milestone)
  - [ ] Queue position tracking
  - [ ] Completion results
  - [ ] Error tracking

### 1.5 PULSE Queue Implementation

**File: `imem/src/async_agents/pulse_queue.py`**
- [ ] PulseQueue class
  - [ ] FIFO queue using asyncio.Queue
  - [ ] Sequential processing (one PULSE at a time)
  - [ ] Queue status tracking
  - [ ] Automatic dequeuing when PULSE completes

**Key Methods**:
```python
class PulseQueue:
    def __init__(self)
    async def enqueue(self, pulse_agent: PulseAgent) -> int
    async def process_queue(self) -> None
    def get_queue_status(self) -> List[dict]
    def get_current_pulse(self) -> Optional[PulseAgent]
```

---

## Phase 2: Agent Implementations

### 2.1 ChangelogAgent

**File: `imem/src/async_agents/agents/changelog_agent.py`**
- [ ] ChangelogAgent(BaseAsyncAgent)
  - [ ] TRACE context integration
  - [ ] Full conversation loading
  - [ ] Smart chunking for large contexts (>200k tokens)
  - [ ] Autonomous scope decision (small/medium/large)
  - [ ] Topic extraction from conversation
  - [ ] Folder naming (`YYMMDD-HHMM_topic`)
  - [ ] CHU metadata generation
  - [ ] Complete CHU template output
  - [ ] File writing to `.memory/.changes/`
  - [ ] Trigger PULSE on completion

**Prompt Template**:
- [ ] Create prompt that mirrors `/log` command behavior
- [ ] Include CHU schema version and metadata fields
- [ ] File operations audit trail instructions
- [ ] Knowledge capture guidance

**Output Validation**:
- [ ] Verify CHU format compliance
- [ ] Check all required sections present
- [ ] Validate metadata schema
- [ ] Ensure timestamp format correct (PST)

### 2.2 PulseAgent

**File: `imem/src/async_agents/agents/pulse_agent.py`**
- [ ] PulseAgent(BaseAsyncAgent)
  - [ ] Integration with existing `pulse.py`
  - [ ] Read changelog from `.memory/.changes/`
  - [ ] Identify relevant SNAPSHOT files to update
  - [ ] Update SNAPSHOT documentation
  - [ ] Maintain documentation coherence
  - [ ] Handle partial update failures
  - [ ] Trigger PRUNE on completion

**Integration Strategy**:
- [ ] Wrap existing pulse.py functionality
- [ ] Add async/await support
- [ ] Add streaming progress updates
- [ ] Add conversational diagnosis on failure

### 2.3 PruneAgent

**File: `imem/src/async_agents/agents/prune_agent.py`**
- [ ] PruneAgent(BaseAsyncAgent)
  - [ ] Read new changelog content
  - [ ] Scan all previous changelogs in `.memory/.changes/`
  - [ ] Identify metadata that needs updating
  - [ ] Update YAML frontmatter
  - [ ] Mark superseded content
  - [ ] Update cross-references
  - [ ] Log all metadata changes
  - [ ] Mark pipeline complete (no re-index trigger)

**Metadata Updates**:
- [ ] Add `superseded_by` field
- [ ] Add `related_changelogs` field
- [ ] Update `status` if appropriate
- [ ] Preserve all existing metadata

---

## Phase 3: CLI Integration

### 3.1 New CLI Commands

**File: `imem/src/cli/modules/async_commands.py`**

**Command: `imem async spawn changelog`**
- [ ] Parse `--context` flag (trace:last, trace:session_xyz)
- [ ] Load TRACE conversation data
- [ ] Spawn ChangelogAgent via AsyncAgentManager
- [ ] Print agent ID and session ID
- [ ] Return immediately (fire-and-forget)

**Command: `imem async status`**
- [ ] Display dashboard of all agents (active/queued/completed)
- [ ] Show agent ID, type, status, progress
- [ ] Show queue positions for PULSE queue
- [ ] Show last 5 completed agents

**Command: `imem async status <agent_id>`**
- [ ] Display detailed status for specific agent
- [ ] High-level by default
- [ ] Add `--verbose` flag for full logs

**Command: `imem async cancel <agent_id>`**
- [ ] Terminate agent process
- [ ] Cleanup session data
- [ ] Mark as cancelled

**Command: `imem async recover <agent_id>`**
- [ ] Load session from sessions.json
- [ ] Resume Claude SDK session
- [ ] Continue from last checkpoint

### 3.2 CLI Output Formatting

**File: `imem/src/cli/modules/async_output.py`**
- [ ] Dashboard table renderer (using rich or tabulate)
- [ ] Progress indicators
- [ ] Status symbols (✓ ✗ ⟳ ...)
- [ ] Time formatting (relative: "2 minutes ago")
- [ ] Queue visualization

---

## Phase 4: TRACE Integration

### 4.1 TRACE Context Retrieval

**File: `imem/src/async_agents/trace_integration.py`**
- [ ] TraceContextRetriever class
  - [ ] Load conversation by session ID
  - [ ] Load last N conversations
  - [ ] Format conversation for agent context
  - [ ] Handle large conversations (chunking)
  - [ ] Extract metadata (files changed, tools used, etc.)

**Key Methods**:
```python
class TraceContextRetriever:
    def get_last_conversation(self) -> dict
    def get_conversation_by_session(self, session_id: str) -> dict
    def get_last_n_conversations(self, n: int) -> List[dict]
    def chunk_large_conversation(self, conversation: dict) -> List[dict]
    def extract_metadata(self, conversation: dict) -> dict
```

### 4.2 Context Formatting

- [ ] Convert TRACE JSON to readable format
- [ ] Include message threads
- [ ] Include tool usage logs
- [ ] Include file operations
- [ ] Format for Claude SDK consumption

---

## Phase 5: Error Handling & Recovery

### 5.1 Self-Diagnosis Implementation

**File: `imem/src/async_agents/diagnosis.py`**
- [ ] DiagnosisEngine class
  - [ ] Error classification
  - [ ] Context-aware error analysis
  - [ ] Retry decision logic
  - [ ] Failure reporting

**Decision Tree**:
```python
def should_retry(error: Exception, context: dict) -> bool:
    # Transient errors: retry
    if isinstance(error, NetworkError):
        return True

    # File not found: don't retry
    if isinstance(error, FileNotFoundError):
        return False

    # Claude API rate limit: retry with backoff
    if isinstance(error, RateLimitError):
        return True

    # Unknown errors: agent decides
    return agent_decides_via_prompt(error, context)
```

### 5.2 Session Recovery

- [ ] Detect crashed agents on startup
- [ ] Offer recovery via CLI
- [ ] Auto-recovery option (with confirmation)
- [ ] Checkpoint-based state restoration

---

## Phase 6: Testing Infrastructure

### 6.1 Unit Tests

**Directory: `imem/tests/async_agents/`**

- [ ] `test_base_agent.py`
  - [ ] Test session creation
  - [ ] Test status tracking
  - [ ] Test session persistence
  - [ ] Test recovery

- [ ] `test_manager.py`
  - [ ] Test agent spawning
  - [ ] Test event triggers
  - [ ] Test queue management
  - [ ] Test concurrent agents

- [ ] `test_changelog_agent.py`
  - [ ] Test TRACE context loading
  - [ ] Test CHU format output
  - [ ] Test topic extraction
  - [ ] Test large conversation chunking

- [ ] `test_pulse_agent.py`
  - [ ] Test changelog reading
  - [ ] Test SNAPSHOT updates
  - [ ] Test failure handling

- [ ] `test_prune_agent.py`
  - [ ] Test metadata updates
  - [ ] Test changelog scanning
  - [ ] Test cross-reference updates

### 6.2 Integration Tests

- [ ] `test_full_pipeline.py`
  - [ ] Test changelog → pulse → prune pipeline
  - [ ] Test event-driven triggers
  - [ ] Test FIFO queue
  - [ ] Test concurrent pipelines

### 6.3 Mock Objects

- [ ] Mock Claude SDK client
- [ ] Mock TRACE data
- [ ] Mock file system operations
- [ ] Mock session persistence

---

## Phase 7: Documentation

### 7.1 User Documentation

**File: `.imem/.snapshot/ASYNC_AGENTS.md`**
- [ ] Overview of async agent system
- [ ] User guide for spawning agents
- [ ] CLI command reference
- [ ] Status monitoring guide
- [ ] Troubleshooting common issues

### 7.2 Developer Documentation

**File: `.imem/.snapshot/ASYNC_AGENT_DEVELOPMENT.md`**
- [ ] Architecture overview
- [ ] How to create new agent types
- [ ] Event system documentation
- [ ] Session management guide
- [ ] Testing guidelines

### 7.3 Code Documentation

- [ ] Docstrings for all classes
- [ ] Docstrings for all public methods
- [ ] Type hints throughout
- [ ] Example usage in docstrings

---

## Phase 8: Configuration & Tuning

### 8.1 Configuration File

**File: `~/.imem/async_config.yaml`**
```yaml
# Agent resource limits
max_concurrent_agents: 3
max_session_memory_mb: 10

# Archive policies
archive_after_days: 30
delete_after_days: 90

# Retry policies
max_retries: 1
retry_delay_seconds: 30

# Queue settings
pulse_queue_timeout_minutes: 30

# Context limits
max_context_tokens: 200000
chunk_size_tokens: 50000
```

- [ ] Configuration loader
- [ ] Validation
- [ ] Default values
- [ ] User overrides

---

## Phase 9: Performance Monitoring

### 9.1 Metrics Collection

**File: `imem/src/async_agents/metrics.py`**
- [ ] Agent spawn time tracking
- [ ] Pipeline completion time tracking
- [ ] Success/failure rates
- [ ] Token usage tracking
- [ ] Session size tracking

### 9.2 Metrics Reporting

- [ ] `imem async metrics` command
- [ ] Show aggregate statistics
- [ ] Show per-agent-type breakdown
- [ ] Cost estimation (token usage)

---

## Implementation Priority Order

### Week 1: Foundation (Must Have)
1. ✅ Directory structure
2. ✅ BaseAsyncAgent with Claude SDK
3. ✅ AsyncAgentManager basic lifecycle
4. ✅ SessionStore for persistence
5. ✅ AgentStatus tracking
6. ✅ Basic CLI commands (spawn, status)

### Week 2: ChangelogAgent (Must Have)
7. ✅ TraceContextRetriever
8. ✅ ChangelogAgent implementation
9. ✅ CHU format generation
10. ✅ Smart chunking for large contexts
11. ✅ Output to `.memory/.changes/`
12. ✅ Basic error handling

### Week 3: Pipeline (Must Have)
13. ✅ PulseAgent wrapper around pulse.py
14. ✅ PruneAgent implementation
15. ✅ Event-driven triggers
16. ✅ PulseQueue (FIFO)
17. ✅ Pipeline completion tracking
18. ✅ Basic testing

### Week 4: Polish (Nice to Have)
19. ⚠️ Session recovery mechanism
20. ⚠️ Self-diagnosis implementation
21. ⚠️ Dashboard formatting (rich tables)
22. ⚠️ Verbose logging mode
23. ⚠️ Documentation
24. ⚠️ Metrics collection

### Future Enhancements (Can Wait)
25. 🔮 Cross-agent learning
26. 🔮 Pipeline modification mid-flight
27. 🔮 Automatic triggering from TRACE
28. 🔮 Pulse assessment crew
29. 🔮 Advanced retry policies
30. 🔮 Cost optimization

---

## Dependencies Map

### What Each Component Depends On

```
BaseAsyncAgent
  ├─ Requires: claude-code-sdk, asyncio
  └─ Used by: All agent implementations

AsyncAgentManager
  ├─ Requires: BaseAsyncAgent, SessionStore, PulseQueue
  └─ Used by: CLI commands

SessionStore
  ├─ Requires: json, pathlib
  └─ Used by: BaseAsyncAgent, AsyncAgentManager

ChangelogAgent
  ├─ Requires: BaseAsyncAgent, TraceContextRetriever
  └─ Triggers: PulseAgent

PulseAgent
  ├─ Requires: BaseAsyncAgent, existing pulse.py
  └─ Triggers: PruneAgent

PruneAgent
  ├─ Requires: BaseAsyncAgent, yaml parser
  └─ Marks: Pipeline complete

CLI Commands
  ├─ Requires: AsyncAgentManager, TraceContextRetriever
  └─ Used by: User

TraceContextRetriever
  ├─ Requires: existing TRACE system
  └─ Used by: ChangelogAgent, CLI commands
```

---

## External Dependencies Required

```bash
# Python packages
pip install claude-code-sdk
pip install asyncio
pip install aiofiles  # For async file operations
pip install rich      # For CLI formatting (optional)

# Already installed (verify)
pip install qdrant-client
pip install sentence-transformers
pip install click
pip install pyyaml
```

---

## File Creation Checklist

### New Files to Create (16 files)

#### Core Infrastructure (5 files)
- [ ] `imem/src/async_agents/__init__.py`
- [ ] `imem/src/async_agents/base_agent.py`
- [ ] `imem/src/async_agents/manager.py`
- [ ] `imem/src/async_agents/pulse_queue.py`
- [ ] `imem/src/async_agents/diagnosis.py`

#### State Management (3 files)
- [ ] `imem/src/async_agents/state/__init__.py`
- [ ] `imem/src/async_agents/state/session_store.py`
- [ ] `imem/src/async_agents/state/agent_status.py`

#### Agent Implementations (4 files)
- [ ] `imem/src/async_agents/agents/__init__.py`
- [ ] `imem/src/async_agents/agents/changelog_agent.py`
- [ ] `imem/src/async_agents/agents/pulse_agent.py`
- [ ] `imem/src/async_agents/agents/prune_agent.py`

#### Integrations (2 files)
- [ ] `imem/src/async_agents/trace_integration.py`
- [ ] `imem/src/async_agents/metrics.py`

#### CLI (2 files)
- [ ] `imem/src/cli/modules/async_commands.py`
- [ ] `imem/src/cli/modules/async_output.py`

### Files to Modify (3 files)
- [ ] `imem/src/cli/cli.py` - Add async command group
- [ ] `imem/src/pulse/pulse.py` - Add async wrapper hooks
- [ ] `imem/setup.py` - Add new dependencies

### Configuration Files (1 file)
- [ ] `~/.imem/async_config.yaml` - Default configuration

---

## Testing Files to Create (6 files)

- [ ] `imem/tests/async_agents/test_base_agent.py`
- [ ] `imem/tests/async_agents/test_manager.py`
- [ ] `imem/tests/async_agents/test_changelog_agent.py`
- [ ] `imem/tests/async_agents/test_pulse_agent.py`
- [ ] `imem/tests/async_agents/test_prune_agent.py`
- [ ] `imem/tests/async_agents/test_full_pipeline.py`

---

## Documentation Files to Create (2 files)

- [ ] `.imem/.snapshot/ASYNC_AGENTS.md` - User guide
- [ ] `.imem/.snapshot/ASYNC_AGENT_DEVELOPMENT.md` - Developer guide

---

## Estimated Effort

### Lines of Code Estimates

| Component | Est. LOC | Complexity |
|-----------|----------|------------|
| BaseAsyncAgent | 300 | Medium |
| AsyncAgentManager | 400 | High |
| SessionStore | 150 | Low |
| AgentStatus | 100 | Low |
| PulseQueue | 150 | Medium |
| ChangelogAgent | 400 | High |
| PulseAgent | 200 | Medium |
| PruneAgent | 250 | Medium |
| TraceContextRetriever | 200 | Medium |
| CLI Commands | 300 | Medium |
| CLI Output | 200 | Low |
| Tests | 800 | Medium |
| **TOTAL** | **~3,450 LOC** | |

### Time Estimates (1 developer)

- **Week 1**: Foundation (15-20 hours)
- **Week 2**: ChangelogAgent (15-20 hours)
- **Week 3**: Pipeline (15-20 hours)
- **Week 4**: Polish (10-15 hours)

**Total**: 55-75 hours for MVP with basic testing

---

## Success Criteria Checklist

### Minimum Viable Product (MVP)

- [ ] User can spawn ChangelogAgent with TRACE context
- [ ] Agent creates CHU-format changelog autonomously
- [ ] Pipeline automatically triggers PULSE and PRUNE
- [ ] User can check status of agents
- [ ] User can cancel running agent
- [ ] Sessions persist and can recover after crash
- [ ] Multiple changelog agents can run concurrently
- [ ] PULSE operations queue sequentially
- [ ] All agents handle failures gracefully

### Phase 2 Enhancements

- [ ] Self-diagnosis on failures
- [ ] Rich dashboard with formatted tables
- [ ] Verbose logging mode
- [ ] Comprehensive documentation
- [ ] Metrics collection
- [ ] Archive policy enforcement

---

## Risk Assessment

### High Risk Areas

1. **Claude SDK Integration**
   - Risk: SDK behavior differs from expectations
   - Mitigation: Prototype early, test thoroughly

2. **Large Context Handling**
   - Risk: Chunking breaks conversation coherence
   - Mitigation: Test with real large sessions, iterate on chunking strategy

3. **Session Recovery**
   - Risk: Session IDs don't persist conversation state as expected
   - Mitigation: Fallback to checkpoint-based recovery

4. **Concurrent Agent Coordination**
   - Risk: Race conditions in PULSE queue or file writes
   - Mitigation: Use proper async locks, test concurrent scenarios

### Medium Risk Areas

5. **CHU Format Compliance**
   - Risk: Agent outputs don't match expected format
   - Mitigation: Validation layer, clear prompt templates

6. **TRACE Integration**
   - Risk: TRACE data format changes or incomplete
   - Mitigation: Robust parsing, graceful degradation

---

## Ready for Implementation?

**Total Components to Build**: 27 files (16 new, 3 modified, 6 tests, 2 docs)

**Estimated Effort**: 55-75 hours

**Dependencies**: claude-code-sdk, asyncio, aiofiles, rich (optional)

**Next Steps**:
1. Answer final 3 alignment questions (Q25-Q27)
2. Create development branch
3. Begin Week 1: Foundation implementation

**Are we ready to proceed?**