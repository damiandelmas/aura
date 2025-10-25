# AURA TRACE - Conversation Archaeology

**TRACE** provides clean access to Claude Code conversation data for analysis, context loading, and documentation generation.

## Features

- 🔍 **Session Discovery**: Find conversations by session ID or markers
- 📋 **Smart Parsing**: Extract summaries, files, tools, and patches
- 💬 **Clean Export**: Generate markdown exports for documentation
- 🎯 **Filtered Views**: Show conversation text without tool noise
- 📁 **File Operations**: Track which files were modified

## Installation

```bash
# Install from source
cd trace/
pip install -e .

# Verify installation
trace --help
```

## Dependencies

- `click>=8.0.0` - CLI framework only (lightweight!)

## Quick Start

```bash
# List all conversations
trace --list

# Query specific session
trace --session abc123 --summary

# Find by keyword
trace --marker "architecture" --summary

# Export to markdown
trace --session abc123 --export conversation.md
```

## Commands

### Discovery

```bash
# List all conversations
trace --list

# Find by keyword/marker
trace --marker "authentication"
trace --marker "bug fix"
```

### Query Session

```bash
# Summary
trace --session <id> --summary

# File operations
trace --session <id> --files

# Tool usage
trace --session <id> --tools

# Code patches (diffs)
trace --session <id> --patches

# Clean conversation text (no tools)
trace --session <id> --conversation

# Raw debug (everything)
trace --session <id> --raw
```

### Export

```bash
# Export last 20 messages
trace --session <id> --export output.md

# Export all messages
trace --session <id> --export output.md --all-messages

# Include metadata
trace --session <id> --export output.md --include-tools --include-files
```

## How It Works

TRACE reads Claude Code conversation files from `~/.claude/projects/`:

```
~/.claude/projects/
└── project-name/
    └── conversations/
        └── <session-id>.jsonl  # TRACE reads this
```

## Data Access

TRACE provides 4 levels of data access:

1. **Summary** (`--summary`): High-level overview (timing, message counts, topic)
2. **Metadata** (`--files`, `--tools`): Operations and tool usage
3. **Filtered** (`--conversation`): Text only, no tool interactions
4. **Raw** (`--raw`): Everything, for debugging

## Use Cases

### Documentation

```bash
# Export conversation for changelog
trace --session abc123 --export session.md --all-messages
```

### Debugging

```bash
# See all file operations
trace --session abc123 --files

# See all tool calls
trace --session abc123 --tools

# Get raw JSONL structure
trace --session abc123 --raw
```

### Analysis

```bash
# Find all conversations about feature X
trace --marker "feature-x" --summary

# Get conversation duration and message count
trace --session abc123 --summary
```

## Output Format

### Summary Output

```markdown
**Topic:** Implement authentication flow
**Session:** abc123def456...
**Working Directory:** /path/to/project

**Timing:**
  - Started: 2025-10-21 14:30:00
  - Ended: 2025-10-21 15:45:00
  - Duration: 75.0 minutes

**Messages:** 42 total
  - User: 12
  - Assistant: 30
```

### Export Format

Markdown files with:
- Metadata header
- User and Assistant messages
- Optional: Tool usage summary
- Optional: File operations summary

## Architecture

```
trace/
├── finder.py      # Session discovery
├── retrieval.py   # JSONL parsing
├── query.py       # Agent interface
└── cli.py         # User interface
```

## Troubleshooting

**No conversations found**:
- Check `~/.claude/projects/` exists
- Verify you have conversations saved

**Session not found**:
- Session IDs can be partial: `abc123` instead of full UUID
- Use `--list` to see all available sessions

**Import errors**:
```bash
# Reinstall
cd trace/
pip install -e . --force-reinstall
```

## Development

```bash
# Install in editable mode
pip install -e .

# Run tests
pytest tests/
```

## Related Microservices

- **IMEM**: Vector search (`../imem/`)
- **Qdrant**: Database manager (`../qdrant/`)
