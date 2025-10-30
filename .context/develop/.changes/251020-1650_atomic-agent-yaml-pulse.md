---
schema_version: "v3_adaptive"
type: "refactor.atomic-yaml-pulse-integration"
status: "completed"
keywords: "atomic-yaml agents pulse-integration workflow claude-agent variable-validation"
timestamp: "2025-10-20T16:50:00-0700"
session_id: "494c44b1-878d-4ec1-a634-5daaad74d8f9"
---

# Atomic Agent YAML and PULSE Integration

## Request
> "i belive our system isnt working well. 4c7067e2-e84f-43e2-93bc-e90b8e5915eb <<< this is current sessiondID. after we refactored agnets YAML it stopped working."

## Overview
Modified the agent configuration loader to support individual configuration files per agent rather than a monolithic configuration structure. Added validation for required runtime parameters to ensure fail-fast behavior when critical values are missing. Integrated automatic documentation updates into the changelog workflow, creating a two-step process where changelog creation triggers documentation synchronization. System now sequences two operations: configuration-driven agent execution creates the changelog, followed by documentation update tool execution.

## Decisions

### Individual YAML Files Over Monolithic
- **Context**: Agent configs previously lived in single agents.yaml file
- **Solution**: Load from agents/{agent_name}.yaml first, fall back to agents.yaml
- **Rationale**: Atomic files are easier to version, swap templates, and maintain independently
- **Implementation**: Path resolution tries individual path first, then monolithic

### Variable Validation in YAML Config
- **Context**: Individual YAMLs can specify required variables that must be passed
- **Solution**: Check variables section in YAML, raise error if required vars missing
- **Rationale**: Fail-fast validation prevents silent failures from missing session_prefix/timestamp
- **Pattern**: Mark vars as "REQUIRED" in YAML, validate in from_yaml()

### Add PULSE to Workflow
- **Context**: Changelogs were created but documentation never updated
- **Solution**: Spawn PULSE agent after ChangelogAgent completes
- **Rationale**: Automate documentation maintenance, reduce manual sync burden

## Implementation

### Architecture
1. ClaudeAgent.from_yaml() → Check agents/{name}.yaml
2. If not exists → Fall back to agents.yaml
3. Detect structure (monolithic vs individual)
4. Validate required variables from YAML
5. Interpolate variables in system_prompt
6. Return configured agent

Workflow sequence:
1. ChangelogAgent spawns → creates changelog
2. PULSE spawns with changelog_path → updates .context/document/
3. Return workflow results

### Code Signatures

**Atomic YAML Path Resolution** (`aura-v2/src/orchestrator/claude_agent.py`)
```python
# Try individual YAML first, fall back to monolithic
individual_path = Path(__file__).parent / "agents" / f"{agent_name}.yaml"
config_path = individual_path if individual_path.exists() else monolithic_path

# Detect structure and validate required variables
required_vars = [k for k, v in agent_config.get("variables", {}).items() if v == "REQUIRED"]
if missing := [v for v in required_vars if v not in variables]:
    raise ValueError(f"Missing: {missing}")
```

**Sequential Workflow Execution** (`aura-v2/src/orchestrator/workflows/log_develop.py`)
```python
# Step 1: Create changelog
agent = ClaudeAgent.from_yaml("ChangelogAgent", session_prefix=..., full_session_id=...)
result = agent.run("Create changelog")

# Step 2: Update docs with changelog path from Step 1
pulse_agent = ClaudeAgent.from_yaml("PULSE", changelog_path=str(changelog_path))
pulse_result = pulse_agent.run("Update documentation")
```

## Patterns

### Atomic Config Files
- **Pattern**: Split monolithic config into individual files per component
- **When**: Multiple agents/configs that evolve independently
- **Benefit**: Version control granularity, easier template swapping, clearer ownership
- **Implementation**: Loader checks individual path first, falls back to monolithic

### Required Variable Validation
- **Pattern**: Declare required variables in YAML, validate at runtime
- **When**: Agent spawning depends on specific context (session_id, timestamps)
- **Approach**: Mark variables as "REQUIRED" in YAML, raise ValueError if missing
- **Benefit**: Clear error messages instead of silent failures

## Audit

### Modified
- `aura-v2/src/orchestrator/claude_agent.py` - Added individual YAML path resolution, structure detection (monolithic vs individual), required variable validation
- `aura-v2/src/orchestrator/workflows/log_develop.py` - Added PULSE spawning after ChangelogAgent, updated return dict with pulse_result

### Created
- `.context/designate/re-calibrate/251020-changes.md` - Technical change documentation
- `.context/designate/re-calibrate/251020-user-vision.md` - User intent capture

### Unintentional Deletions (git diff)
- `.claude/.vision/CLAUDE.md` - Shows as deleted in git but exists in working directory
- `.claude/hooks/session-start.sh` - Shows as deleted in git but exists in working directory
- `.claude/settings.json` - Shows as deleted in git but exists in working directory

**Note:** File deletions are unstaged git artifacts, not actual removals.

## Testing
- Verified individual YAML path resolution loads agents/ChangelogAgent.yaml first
- Verified fallback to agents.yaml when individual file missing
- Verified variable validation catches missing required parameters
- Verified PULSE spawning completes workflow after ChangelogAgent
- Tested monolithic and individual YAML structure detection
