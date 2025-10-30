---
schema_version: "v3_adaptive"
type: "implementation.trace-export-and-custom-instructions"
status: "completed"
keywords: "trace markdown-export custom-instructions changelog conversation-export agent-communication"
timestamp: "2025-10-18T18:45:24-0700"
session_id: "37c4246b-8445-4627-ad4e-0e3e91b938f3"
---

# TRACE Markdown Export and Custom Instructions

## Request
> "Add markdown export for conversations and implement custom instructions for ChangelogAgent to enable user-directed changelog generation"

## Overview
Two complementary features enable users to direct agent behavior and export conversation data. First, conversations can be exported to readable formatted text instead of requiring agents to parse internal message structures. Second, a custom instructions parameter flows from the user interface through the workflow to the agent, allowing users to provide focused guidance (e.g., "analyze security changes only"). Together, these features establish patterns for user-guided agent orchestration and inter-agent communication without tight coupling to internal formats.

## Decisions

### Readable Format Export Over Raw Parsing
- **Context**: Agents need to consume conversation data but raw internal format requires deep knowledge of system architecture
- **Solution**: Implement export to readable formatted text with optional metadata sections (tool summaries, file operations)
- **Alternatives**: Document internal format (high cognitive load), provide parsing library (adds dependency), stream raw data (difficult for agents)
- **Rationale**: Readable format matches natural language processing strengths; optional sections prevent unnecessary token consumption
- **Benefit**: Establishes pattern for agent-to-agent communication without coupling to internal schemas

### Flexible Message Limiting Strategy
- **Context**: Full conversations can be long; agents may only need recent context
- **Solution**: Default to last 20 messages, allow --all-messages flag for full export
- **Rationale**: Reduces token usage by default while enabling full context when needed
- **Implications**: Agents must handle partial conversation exports; full context available when required

### Custom Instructions Via Parameter Appending
- **Context**: Need to allow users to guide agent behavior without breaking core competencies
- **Solution**: Append additional_instructions to base prompt rather than replacing prompt template
- **Alternatives**: Modify agents.yaml prompts (breaks careful tuning), use special instruction tokens (adds complexity), replace entire prompt (loses core behavior)
- **Rationale**: Preserves agent base behavior while adding user-specific constraints
- **Trade-offs**: Custom instructions could conflict with base prompts (mitigated by documentation)

### Parameter Propagation Architecture
- **Context**: Custom instructions must flow from CLI through workflow to agent
- **Solution**: Clean separation—CLI layer accepts flag, workflow layer constructs prompt, agent layer executes
- **Why**: Each layer has single responsibility; workflow owns prompt composition logic; enables independent testing
- **Pattern**: Establishes template for all future workflows accepting user input

### Why Not Modify System Prompts
- **Context**: agents.yaml contains carefully tuned ChangelogAgent prompts
- **Solution**: Keep base prompts unchanged; custom instructions extend them
- **Rationale**: Preserves core agent competencies while adding user-directed focus
- **Implication**: Custom instructions are additive constraints, not behavior replacement

## Implementation

### Architecture
The system enables two independent but complementary flows:

**Markdown Export Flow**:
1. User invokes `trace --session <id> --export output.md [--all-messages] [--include-tools] [--include-files]`
2. ConversationQuery.export_to_markdown() reads JSONL file and formats conversation
3. Optional metadata sections added based on flags
4. Clean markdown file written to disk

**Custom Instructions Flow**:
1. User invokes `/log:develop Focus on security changes only`
2. SessionStart hook captures command arguments
3. Workflow receives additional_instructions parameter
4. Prompt constructed: base_prompt + "\n\nADDITIONAL INSTRUCTIONS:\n" + instructions
5. Agent executes prompt with combined instructions

### Code Signatures

**Export Method Pattern** (Conversation service layer)
```python
def export_to_format(
    conversation_data: ConversationData,
    max_recent: int = 20,
    include_metadata: bool = False
) -> FormattedExport:
    """Convert conversation to readable format for external consumption"""
    # Filters to recent messages if max_recent specified
    # Includes optional metadata sections
```

**Instructions Composition Pattern** (Workflow layer)
```python
base_instructions = "Process conversation and document outcomes"

if user_guidance:
    final_instructions = f"{base_instructions}\n\nUSER FOCUS:\n{user_guidance}"
else:
    final_instructions = base_instructions

agent.execute(final_instructions)
```

## Patterns

### Agent-Consumable Format Pattern
- **Pattern**: Export conversation data to agent-friendly format (markdown, structured text) rather than exposing internal data structures
- **When**: Building agent-to-agent communication or agent consumption of system data
- **Approach**: Create high-level export methods with granular control (optional sections, message limits)
- **Benefit**: Agents can consume data without learning internal schemas; reduces coupling between agent and system
- **Occurrences**: Conversation export, future log/trace exports, inter-agent communication

### User-Guided Agent Behavior Pattern
- **Pattern**: Accept additional_instructions parameter that appends to base prompt
- **When**: Need to allow users to direct agent focus without modifying core behavior
- **Approach**: Accept string parameter, append to prompt with clear separator
- **Why**: Preserves tuned base behavior while enabling user control; simple to implement and understand
- **Benefit**: Establishes reusable pattern for all workflows accepting user input
- **Anti-Pattern**: Replacing entire prompt or modifying agents.yaml templates

### Layered Parameter Propagation
- **Pattern**: Parameter flows through clean layers—CLI accepts input, workflow composes behavior, agent executes
- **When**: Building CLI-driven workflow systems with multi-step parameter handling
- **Approach**: Each layer transforms or composes parameters without leaking logic to other layers
- **Benefit**: Enables independent testing, clear responsibility, future flexibility
- **Occurrences**: Custom instructions flow, session ID parameter handling (previous session)

## Audit

### Created
- Markdown export method in conversation_query.py - Enables agents to consume conversations in structured format
- Export convenience function - Quick wrapper for export_to_markdown() with defaults

### Modified
- `aura-v2/src/aura/services/trace/conversation_query.py` - Added export_to_markdown() method (+82 lines); handles message filtering, optional metadata sections, markdown formatting
- `aura-v2/src/aura/cli/trace.py` - Added four CLI options (--export, --all-messages, --include-tools, --include-files) (+30 lines); implements export invocation with error handling
- `aura-v2/src/orchestrator/workflows/log_develop.py` - Added additional_instructions parameter (+16 lines); implements prompt concatenation logic
- `aura-v2/src/aura/cli/orca.py` - Added --instructions option to log-develop command (+6 lines); passes instructions to workflow
- `CLAUDE.md` - Added section on handling /log:develop with arguments (+27 lines); documents usage patterns and argument extraction

### Deployment
No deployment configuration changes needed. Export features are CLI-driven and opt-in. Custom instructions flow through existing workflow infrastructure.

### Usage Examples
```bash
# Export last 20 messages
trace --session abc123-def --export output.md

# Export all messages with metadata
trace --session abc123-def --export output.md --all-messages --include-tools --include-files

# Custom changelog instructions
orca workflow log-develop --session abc123-def456 --instructions "Focus on code changes only"

# User-facing slash command
/log:develop Focus on security changes only
```

### Impact
**Export system enables**: Research agents analyzing patterns, documentation agents creating guides, summary agents condensing threads, external tools consuming Claude Code data

**Custom instructions enable**: User-guided research workflows, scoped analysis tasks, iterative agent output refinement, context-aware steering

### Validation
This changelog was created using the custom instructions feature, demonstrating: instructions properly passed through workflow, focused documentation on code changes, structured file modification summary, continuity with previous changelog context.

### Future Implications
Export pattern extends to other data types (logs, traces, audit records). Custom instructions pattern establishes template for all future user-steerable workflows. Both features enable progression toward intelligent, user-guided agent orchestration rather than rigid automation.
