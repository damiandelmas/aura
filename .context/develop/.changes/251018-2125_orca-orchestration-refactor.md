---
schema_version: "v3_adaptive"
type: "refactor.orchestration-architecture"
status: "completed"
keywords: "orca workflow brother-spawning subprocess task-tool log-develop orchestration yaml-configs"
timestamp: "2025-10-18T21:25:32-0700"
session_id: "4c7067e2-e84f-43e2-93bc-e90b8e5915eb"
---

# ORCA Orchestration Refactor: Subprocess Brother Spawning

## Request
> "The current implementation returns an ORCA prompt expecting Claude Code to execute it, but that creates an infinite loop. We need to spawn the ORCA brother as a separate subprocess that runs the workflow."

## Overview
Fixed a circular execution problem in the workflow orchestration system by switching from prompt-return to subprocess spawning. The original approach created a paradox where an agent tried to spawn itself within its own execution context. The new architecture spawns multi-agent workflows as independent processes with embedded configurations, enabling clean separation between orchestration and execution phases.

## Decisions

### Use Subprocess Spawning Instead of Prompt Return
- **Context**: Original implementation returned ORCA prompt as a string, expecting Claude Code to execute it using Task tool, creating circular execution
- **Solution**: Changed `run_log_develop_workflow()` to spawn ORCA as subprocess using `subprocess.run(["claude", "-p", orca_prompt])`
- **Rationale**: Brother agents must run as independent processes with separate contexts, not execute within the calling conversation
- **Trade-offs**: Added subprocess dependency and error handling complexity, but eliminated execution paradox

### Embed Configuration Structures in Orchestration Prompt
- **Context**: Independent workflow processes can't access configuration files in their execution context
- **Solution**: Load configuration data and embed it directly in the orchestration prompt during handoff
- **Rationale**: Eliminates filesystem dependencies for spawned processes, ensuring complete context transfer

### Remove ORCA Output Parsing
- **Context**: First iteration attempted to parse structured output from ORCA brother
- **Solution**: Simplified to just return success/failure and changelog path
- **Rationale**: ORCA brother's detailed output goes to its own conversation; parent workflow only needs completion status

## Implementation

### Architecture
1. Python workflow function → Validates session exists via TRACE
2. Workflow function → Loads 4 YAML configuration files (agents + tasks)
3. Workflow function → Constructs comprehensive ORCA prompt with embedded configs
4. Workflow function → Spawns ORCA brother: `subprocess.run(["claude", "-p", prompt])`
5. ORCA brother → Executes workflow using Task tool for agents, Bash tool for tasks
6. Parent workflow → Returns changelog path and success status

### Code Signatures

**Configuration Embedding Pattern**
```python
# Serialize structured data and embed in handoff prompt
prompt = f"""CONTEXT:
{serialized_config_1}
{serialized_config_2}
{serialized_config_3}
"""
```

**Subprocess Invocation**
```python
# Spawn independent process with captured output
result = subprocess.run(
    ["process-name", "-p", prompt],
    capture_output=True,
    timeout=timeout_seconds
)
```

## Patterns

### Embedded Configuration Pattern
- **Pattern**: Serialize structured configuration and embed directly in handoff messages to isolated processes
- **When**: Child processes require access to configuration but run in separate execution contexts
- **Approach**: Read configuration in parent process, serialize to portable format, inject into handoff message/prompt
- **Benefit**: Child processes receive complete context without filesystem dependencies
- **Anti-Pattern**: Don't assume isolated processes can read configuration files from parent directories

### Independent Process Spawning
- **Pattern**: Spawn multi-agent workflows as separate processes with complete context
- **When**: Workflows require independent execution contexts to prevent circular dependencies
- **Approach**: Construct comprehensive handoff message with all context, spawn process, capture completion status
- **Benefit**: True isolation between orchestration and execution layers
- **Why**: Prevents execution paradoxes where a process tries to spawn itself within its own context

## Audit

### Modified
- `src/orchestrator/workflows/log_develop.py` - Refactored from prompt-return to subprocess-spawn architecture, added YAML configuration loading and embedding, removed output parsing helper function
- `src/aura/cli/orca.py` - Updated to handle subprocess execution results instead of prompt strings

### Evolution
**First iteration:** Returned ORCA prompt expecting Claude Code to execute it
**Second iteration:** Added subprocess spawning with complex output parsing
**Final iteration:** Simplified to subprocess spawn with basic success/path return

### Dependencies
- `subprocess` module for brother spawning
- `yaml` module for configuration serialization
- Requires `claude` CLI to be available in PATH
- Requires YAML files: `workflows/log-develop.yaml`, `agents/{ChangelogAgent,PULSE,PRUNE}.yaml`, `tasks/imem-update.yaml`
