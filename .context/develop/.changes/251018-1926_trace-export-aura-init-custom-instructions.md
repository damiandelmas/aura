---
schema_version: "v3_adaptive"
type: "implementation.cli-enhancement"
status: "completed"
keywords: "trace markdown-export aura-init custom-instructions slash-command sessionstart-hook"
timestamp: "2025-10-18T19:26:12-0700"
session_id: "1f8cfd36-e1b6-4eae-9518-277cb0f07a0c"
---

# Trace Markdown Export + /log:develop Argument Support + Unified AURA Init

## Request
> "Add markdown export capability to TRACE, create unified AURA initialization command, and support custom instructions for /log:develop slash command"

## Overview
Extended the conversation export system with structured export functionality for agent-to-agent context sharing, created a unified initialization command orchestrating multi-step project setup, and added custom instruction support to workflow processes enabling users to guide agent behavior. The implementation maintains system consistency patterns while improving developer experience through unified setup and runtime customization.

## Decisions

### Add Markdown Export to Conversation Export System
- **Context**: Agents need clean conversation formats; raw data parsing is complex
- **Solution**: Added structured export method supporting configurable message limits and optional summaries
- **Rationale**: Markdown provides readable format for agent consumption while preserving conversation structure

### Create Unified Initialization Command
- **Context**: New projects require multi-step setup (hooks, registry, vector database checks)
- **Solution**: Created single initialization command orchestrating all setup steps sequentially
- **Alternative**: Keep manual setup steps documented separately
- **Rationale**: Single entry point reduces onboarding friction and ensures consistent setup

### Support Custom Instructions in Changelog Workflow
- **Context**: Users needed to guide agent focus without modifying core system prompts
- **Solution**: Added optional instruction parameter allowing runtime guidance appended to agent prompt
- **Rationale**: Provides flexibility for use-case customization without changing core behavior

### Allow Non-Git Initialization with Force Flag
- **Context**: Testing and non-repository projects required initialization
- **Solution**: Optional force flag enables initialization without version control detection
- **Rationale**: Supports edge cases while maintaining best practice defaults

## Implementation

### Architecture
1. Export method → Clean markdown with configurable sections
2. CLI export command → Calls export method with user options
3. Initialization command → Hook installation + registry initialization + vector database check (no indexing)
4. Workflow instructions parameter → Parse arguments → Pass to agent workflow → Append to prompt
5. Session hook → Simplified system paths for installed packages

### Code Signatures

**Markdown Export Method** (`aura-v2/src/aura/services/trace/conversation_query.py`)
```python
def export_to_markdown(
    self,
    conversation_file: Path,
    output_path: Path = None,
    max_messages: int = None,
    include_tools: bool = False,
    include_files: bool = False
) -> Path:
    """Export conversation to clean Markdown for agent consumption"""
    # Format conversation context (all messages if max_messages=None)
    # Build markdown with session metadata header
    # Optionally append tool usage and file operation summaries
    # Write to <session_id>.md or specified path
    return output_path
```

**TRACE CLI Export Flags** (`aura-v2/src/aura/cli/trace.py`)
```python
@click.option('--export', type=click.Path(), help='Export to markdown file')
@click.option('--all-messages', is_flag=True, help='Include all messages')
@click.option('--include-tools', is_flag=True, help='Include tool summary')
@click.option('--include-files', is_flag=True, help='Include file ops summary')
def trace(..., export, all_messages, include_tools, include_files):
    # If export flag present, call export_to_markdown()
    # Default: last 20 messages; --all-messages overrides
```

**AURA Init Command** (`aura-v2/src/aura/cli/aura.py`)
```python
@click.command()
@click.option('--force', is_flag=True, help='Overwrite OR skip git requirement')
def init(force):
    """Initialize AURA for current project"""
    # 1. Detect project root (git repo) or use cwd with --force
    # 2. Install SessionStart hook template
    # 3. Initialize session registry
    # 4. Check Qdrant status (don't index - project empty)
```

**Custom Instructions Flow** (`aura-v2/src/orchestrator/workflows/log_develop.py`)
```python
def run_log_develop_workflow(
    session_id: str,
    timestamp: str,
    iso_timestamp: str,
    additional_instructions: Optional[str] = None
) -> Dict:
    base_prompt = f"Create comprehensive changelog for session {session_prefix}"

    # Append custom instructions if provided
    if additional_instructions:
        prompt = f"{base_prompt}\n\nADDITIONAL INSTRUCTIONS:\n{additional_instructions}"

    result = agent.run(prompt)
```

**Slash Command Integration** (`/log/develop.md`)
```bash
# Parse custom instructions from $ARGUMENTS
if [ -n "$ARGUMENTS" ]; then
  orca workflow log-develop --session [id] --instructions "$ARGUMENTS" &
else
  orca workflow log-develop --session [id] &
fi
```

## Patterns

### Structured Export with Optional Sections
- **Pattern**: Export system offers configurable output with optional detailed sections
- **When**: Downstream consumers need conversation context in customizable detail levels
- **Approach**: Core export includes base data; optional flags add metadata, operation summaries
- **Why**: Different agents need different detail levels; optional sections prevent bloat
- **Benefit**: Flexible consumption without forcing unnecessary data through pipelines

### Sequential Multi-Step Initialization
- **Pattern**: Single command orchestrates interdependent setup steps
- **When**: New projects require multiple coordinated configuration steps
- **Approach**: Entry point calls specialized functions sequentially with dependency awareness
- **Why**: Prevents missed steps and reduces cognitive load during onboarding
- **Benefit**: Reliable setup with reduced error surface

### Optional Runtime Customization via Parameters
- **Pattern**: Base system behavior + optional instruction override at invocation
- **When**: Users need to customize behavior without system prompt modification
- **Approach**: Accept optional parameter, append to base prompt if provided
- **Why**: Maintains backward compatibility while enabling customization
- **Benefit**: Flexible workflows without requiring prompt engineering or restarts

## Audit

### Created
- `aura-v2/src/aura/cli/aura.py` - Unified initialization command (4 CLIs total: aura, imem, trace, orca)

### Modified
- `aura-v2/src/aura/services/trace/conversation_query.py` - Added export_to_markdown() method
- `aura-v2/src/aura/cli/trace.py` - Added --export, --all-messages, --include-tools, --include-files flags
- `aura-v2/src/orchestrator/workflows/log_develop.py` - Added additional_instructions parameter
- `aura-v2/src/aura/cli/orca.py` - Added --instructions flag to log-develop command
- `aura-v2/src/orchestrator/agents.yaml` - Removed premature "read prior changelog" instruction (not yet implemented)
- `.claude/commands/log/develop.md` - Documented custom instructions usage pattern
- `.claude/hooks/session-start.sh` - Simplified Python path (uses installed package)
- `aura-v2/setup.py` - Added aura CLI entry point, included hook templates in package data
- `CLAUDE.md` - Documented /log:develop with arguments workflow

### Configuration
- **TRACE Export Usage**:
  ```bash
  trace --session <id> --export output.md                    # Last 20 messages
  trace --session <id> --export output.md --all-messages     # Full conversation
  trace --session <id> --export output.md --include-tools --include-files
  ```

- **AURA Init Usage**:
  ```bash
  cd /my/project
  aura              # Requires git repository
  aura --force      # Works without git (uses current directory)
  ```

- **Custom Instructions Usage**:
  ```bash
  /log:develop                                      # Standard workflow
  /log:develop Focus only on code changes           # Custom focus
  /log:develop Ignore research, document architecture only
  ```
