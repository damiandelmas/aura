# TRACE Markdown Export Feature - Implementation Complete

**Session:** cafba9b5-2c9a-4b4c-a2e5-9b690590f5d1
**Date:** 2025-10-18 17:05
**Type:** Feature Addition
**Status:** ✅ Complete

---

## Summary

Added markdown export to TRACE system after comparing with ZeroSumQuant's claude-conversation-extractor. **Verdict: TRACE is superior** for agent orchestration - just needed export capability.

---

## Comparative Analysis

### Your TRACE System (Superior)

**Strengths:**
- Agent-ready formatting for brother spawning
- Project-scoped (auto-detects git root)
- Advanced extraction: patches, threading, tools
- Modular architecture: finder → retrieval → query
- Global cross-project search

### ZeroSumQuant (Limited for Our Use Case)

**Strengths:** Markdown export, search indexing
**Weaknesses:** No agent integration, no project-scoping, no patch extraction

---

## Implementation

### Added to `conversation_query.py`

```python
def export_to_markdown(self, conversation_file: Path, 
                      output_path: Path = None,
                      max_messages: int = None,
                      include_tools: bool = False,
                      include_files: bool = False) -> Path:
    """Export conversation to markdown for agent consumption"""
```

### CLI Flags Added

```bash
trace --session <id> --export output.md              # Last 20 messages
trace --session <id> --export output.md --all-messages  # All messages
trace --session <id> --export output.md --include-tools --include-files
```

---

## Test Results

**Session:** 3f7d3dd5-d57 (591 messages, 141 minutes)

- Last 20 messages: 264 lines
- All messages: 2,669 lines
- Output quality: ✅ Clean markdown, proper formatting, metadata headers

---

## Usage for Conversation Querying MVP

```python
from aura.services.trace import ConversationFinder, ConversationQuery

@tool
def query_conversation(session_id: str, question: str) -> str:
    finder = ConversationFinder()
    conv = finder.find_by_session_id(session_id, search_globally=True)
    
    query = ConversationQuery()
    md_path = query.export_to_markdown(conv)
    
    return subprocess.run(
        ['claude', '-p', f'{question}\n\n{md_path.read_text()}'],
        capture_output=True, text=True
    ).stdout
```

---

## Files Changed

1. `aura-v2/src/aura/services/trace/conversation_query.py` - Added export method
2. `aura-v2/src/aura/cli/trace.py` - Added CLI flags

---

## Recommendation

**Keep TRACE. Don't use ZeroSumQuant.** TRACE is architecturally superior for agent workflows. Now has feature parity + advanced capabilities ZeroSumQuant lacks.

**Ready for MVP** - All primitives in place for conversation querying MCP tool.
