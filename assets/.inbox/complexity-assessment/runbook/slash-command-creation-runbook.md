# Slash Command Creation Runbook (From Conversation Analysis)

## Core Methodology Extracted

### Workflow Steps from Actual Implementation Discussion

1. **Requirements Analysis & Complexity Assessment**
   - Use Command Architecture Framework: MONO/MODU/MULT (coupling 1-9) × LEAN/ARCH/INTL (methodology +0/+3/+6)
   - Calculate total complexity score to determine resource allocation
   - Example: MULT-9 + INTL-6 = 15 (maximum complexity, 4+ hours development)

2. **File Structure Setup**  
   - Project commands: `.claude/commands/[name].md`
   - Personal commands: `~/.claude/commands/[name].md`
   - Namespacing via subdirectories: `.claude/commands/[namespace]/[name].md`

3. **Template Selection Based on Complexity**
   - **MONO-LEAN (Score 1-3)**: Single function, basic objective, minimal process
   - **MULT-INTL (Score 13-15)**: Multi-agent orchestration, 4-phase protocols, validation requirements

4. **Content Structure Implementation**
   - **Header**: Clear title with `$ARGUMENTS` integration
   - **Objective/Mission**: What the command accomplishes
   - **Process/Protocol**: Step-by-step workflow (phases for complex commands)
   - **Implementation**: Specific instructions using available tools
   - **Usage Examples**: Concrete command invocations

### Tools/Commands Used in Practice

**From Conversation Evidence:**
- `TodoWrite` - Progress tracking for multi-step command creation
- `Read` - Source analysis and template examination  
- `Write` - Command file creation
- `Edit` - Iterative refinement of command content
- `Bash` - Directory structure creation (`mkdir -p .claude/commands`)
- `LS` - File system verification
- `Grep` - Pattern search for methodology extraction

### Implementation Pattern That Worked

**Proven Sequence:**
1. **Assessment** → Use complexity framework to determine approach
2. **Structure** → Create appropriate directory and file naming
3. **Template** → Select base pattern matching complexity score
4. **Content** → Build systematic workflow with `$ARGUMENTS` integration
5. **Validation** → Test command structure and usage patterns
6. **Refinement** → Iterate based on complexity requirements

### Examples from Successful Executions

**MONO-LEAN Success Pattern:**
```markdown
# Quick [Action] - $ARGUMENTS
**Fast [purpose]**: $ARGUMENTS

## Objective
[Single clear goal]

## Process
1. [Step 1]
2. [Step 2] 
3. [Step 3]

## Implementation
[Direct instructions without agent orchestration]

Ready to [action]: $ARGUMENTS
```

**MULT-INTL Success Pattern:**
```markdown
# [Comprehensive Title] - $ARGUMENTS
**Systematic [purpose]**: $ARGUMENTS

## Mission Objective
[Clear statement with confidence threshold]

## Orchestration Architecture
### Agent Roles
- **[Agent 1]**: [Specific function]
- **[Agent 2]**: [Specific function]

## 4-Phase Protocol
### Phase 1: [Name]
**Tools Required**: [Specific tools]
- [Systematic steps]

**Tasks**:
Task 1: "[Detailed agent instruction]"

[Repeat for all phases]

## Success Metrics
- [Measurable outcomes with thresholds]

Ready to [action]: $ARGUMENTS
```

## Key Discovery from Conversation Patterns

**Critical Success Factors:**
- Consistent `$ARGUMENTS` integration throughout command
- Complexity-appropriate resource allocation (MONO-LEAN vs MULT-INTL)
- Systematic validation protocols for high-complexity commands
- Tool-specific implementation using available MCP capabilities
- Concrete usage examples showing actual command invocation patterns

**Proven Development Timeline:**
- MONO-LEAN: 15-60 minutes (conversation evidence: extract-quick creation)
- MULT-INTL: 4+ hours (conversation evidence: original extract-runbook development)

**File Naming Evolution:**
- Original: `extract-runbook.md`
- Complexity-aware: `extract-runbook_mult-intl.md` 
- Source-specific final: `docs_mono-lean.md`, `docs_mult-intl.md`, `conv_mono-lean.md`, `conv_mult-intl.md`

This runbook represents methodology derived from actual successful command creation conversations, validated through multiple implementation cycles.