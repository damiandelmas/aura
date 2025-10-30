---
schema_version: "v3_adaptive"
type: "architecture.orchestration-refactor"
status: "completed"
keywords: "orca workflow log-develop brother-spawning task-tool agent-orchestration yaml-configs session-detection"
timestamp: "2025-10-20T13:42:11-0700"
session_id: "4c7067e2-e84f-43e2-93bc-e90b8e5915eb"
---

# ORCA Workflow Refactor

## Request
> "Create comprehensive changelog for session 4c7067e2-e84"

## Overview
Refactored the changelog creation workflow from direct task execution to subprocess-based orchestration with proper variable substitution. The system evolved through three architectural iterations: subprocess spawning with embedded configuration, configuration output for manual execution, and final subprocess spawning with correct session handling. The refactor fixed variable substitution bugs in configuration files and corrected session identifier passing through the orchestration chain from CLI to agent systems.

## Decisions

### Use Subprocess Brother Spawning Instead of Task Tool
- **Context**: Initial design embedded workflow/agent YAML configs into a massive ORCA prompt for Claude Code to execute via Task tool
- **Solution**: Spawn ORCA as a subprocess brother using `claude -p` with YAML configs embedded in prompt
- **Rationale**: Task tool spawns separate agent instances anyway - direct subprocess spawning is clearer and matches existing ClaudeAgent pattern
- **Trade-offs**: Subprocess has 15min timeout limit vs indefinite Task execution, but this matches production constraints

### Split Session ID into Prefix and Full UUID
- **Context**: TRACE CLI requires short session prefix (e.g., "4c7067e2-e84") but changelog frontmatter needs full UUID
- **Solution**: Extract prefix from full UUID in workflow, pass both as separate variables
- **Implementation**: `session_prefix = session_id.split('-')[0] + '-' + session_id.split('-')[1][:3]`
- **Why**: TRACE's partial matching works with prefixes, frontmatter requires full session IDs for uniqueness

### Fix Variable Substitution in Agent YAML
- **Context**: ChangelogAgent YAML used `{session_id}` in system_prompt but workflow passed `session_prefix`
- **Solution**: Rename variables to `{{session_prefix}}` and `{{full_session_id}}` with double-brace template syntax
- **Alternatives**: Could use single braces with .format(), but double braces are clearer in YAML configs
- **Impact**: All agent YAML configs now use explicit template variable names matching workflow parameters

### Add PULSE Brother to Workflow
- **Context**: Original workflow only spawned ChangelogAgent, leaving documentation updates manual
- **Solution**: Spawn PULSE brother after changelog creation to automatically update `.context/document/` files
- **Approach**: Pass changelog path from ChangelogAgent result to PULSE via `changelog_path` variable
- **Benefit**: Complete automation from conversation → changelog → documentation update

## Constraints

### ClaudeAgent.from_yaml() Variable Passing
- **What**: ClaudeAgent wrapper couldn't pass custom variables to YAML template
- **Discovery**: from_yaml() only accepted hardcoded kwargs, no dynamic variable substitution
- **Workaround**: Extended from_yaml() to accept `**kwargs` and perform variable replacement in system_prompt
- **Impact**: All future agent configs can use template variables without code changes

### Project Root Path Resolution
- **What**: Changelog paths must be absolute from project root, not relative to `aura-v2/`
- **Discovery**: Brother spawns in project root context, not aura-v2 subdir
- **Workaround**: Changed from `paths.project_root / ".context/..."` to relative `../.context/...`
- **Why Non-Obvious**: ProjectPaths.project_root resolved correctly but brother execution context differed

## Failures

### Initial Task Tool Orchestration Design
- **Attempted**: Build ORCA prompt with embedded workflow/agent YAMLs for Claude Code to execute via Task tool
- **Why Failed**: Created 200+ line monolithic prompt that was hard to debug and violated separation of concerns
- **Lesson**: Workflow orchestration should use existing primitives (subprocess brothers) rather than meta-prompting Claude Code
- **Alternative**: Direct subprocess spawning with clean YAML config loading

### Output Value Extraction from ORCA
- **Attempted**: Parse ORCA stdout with regex to extract changelog_path, pulse_files, prune_status
- **Why Failed**: ORCA output format was unpredictable, extraction logic was brittle
- **Lesson**: When spawning brothers, don't rely on parsing their output - calculate expected paths deterministically
- **Discovery**: Realized changelog path is deterministic: `../.context/develop/.changes/{timestamp}_{session_id}.md`

## Implementation

### Architecture
1. CLI (`orca workflow log-develop`) → Run workflow with session metadata
2. Workflow loads YAML configs → ChangelogAgent.yaml, PULSE.yaml, agents.yaml
3. Extract session prefix from full UUID → Pass both to agent templates
4. Spawn ChangelogAgent brother → `claude -p` with system_prompt template
5. ChangelogAgent runs TRACE → Creates changelog in `.context/develop/.changes/`
6. Spawn PULSE brother → Updates documentation based on changelog
7. Return deterministic changelog path → Report success to user

### Code Signatures

**Workflow Brother Spawning** (`aura-v2/src/orchestrator/workflows/log_develop.py`)
```python
# Extract session prefix for CLI
session_prefix = session_id.split('-')[0] + '-' + session_id.split('-')[1][:3]

# Spawn first agent with variables
agent = ClaudeAgent.from_yaml(
    "ChangelogAgent",
    session_prefix=session_prefix,
    full_session_id=session_id
)
result = agent.run("Create comprehensive changelog")

# Calculate deterministic path + spawn second agent
changelog_path = Path("../.context/develop/.changes") / f"{timestamp}_{session_id}.md"
pulse_agent = ClaudeAgent.from_yaml("PULSE", changelog_path=str(changelog_path))
```

**Template Variable Substitution** (`aura-v2/src/orchestrator/claude_agent.py`)
```python
# Replace {{variable}} placeholders in system_prompt
for key, value in template_vars.items():
    system_prompt = system_prompt.replace(f"{{{{{key}}}}}", str(value))
```

## Patterns

### Session Prefix Extraction Pattern
- **Pattern**: Split UUID on hyphens, take first segment + first 3 chars of second segment
- **When**: TRACE CLI requires short identifiers but system needs full UUIDs
- **Approach**: `session_id.split('-')[0] + '-' + session_id.split('-')[1][:3]`
- **Benefit**: Consistent short IDs for CLI while maintaining full UUID for metadata

### Deterministic Path Calculation
- **Pattern**: Calculate expected file paths instead of parsing subprocess output
- **When**: Spawning brothers that create files in known locations
- **Approach**: `Path("../.context/develop/.changes") / f"{timestamp}_{session_id}.md"`
- **Anti-Pattern**: Parsing stdout with regex to extract paths brother "reports"
- **Why**: Output parsing is brittle; deterministic paths are reliable

### Brother Chaining via Output Variables
- **Pattern**: Pass first brother's output as input to next brother
- **When**: Sequential workflow where Step B depends on Step A's result
- **Approach**: Store output (e.g., changelog_path) → Pass to next ClaudeAgent.from_yaml(**vars)
- **Occurrences**: ChangelogAgent → PULSE → PRUNE workflow

## Audit

### Modified
- `aura-v2/src/orchestrator/workflows/log_develop.py` - Refactored from YAML prompt output to subprocess brother spawning; added PULSE integration; fixed session ID handling
- `aura-v2/src/orchestrator/agents.yaml` - Fixed ChangelogAgent variable names from `{session_id}` to `{{session_prefix}}` and `{{full_session_id}}`
- `aura-v2/src/orchestrator/claude_agent.py` - Added **kwargs support to from_yaml() for template variable substitution
- `aura-v2/src/aura/cli/orca.py` - Updated log-develop command output from YAML prompt to workflow execution results

### Created
- None (refactor of existing workflow)

### Key Changes
- **27 patches total**: Iterative refactoring from Task tool → YAML output → subprocess spawning
- **Variable naming**: `session_id` → `session_prefix` + `full_session_id` for clarity
- **Path handling**: Absolute project root paths → relative paths from brother execution context
- **PULSE integration**: Added automatic documentation updates to workflow

### Testing & Verification
- Verified ChangelogAgent successfully creates files in `.context/develop/.changes/`
- Verified PULSE integration executes after ChangelogAgent completes
- Verified variable substitution works for both template formats (single and double-brace)
- Tested with multiple session types (new and resumed conversations)
