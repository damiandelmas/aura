"""
JSONL slicing library for Claude Code session manipulation.

Provides functions to find, count, slice, and extract metadata from
Claude Code JSONL session files.
"""

import json
import uuid
from pathlib import Path


CLAUDE_DIR = Path.home() / ".claude/projects"


def find_jsonl(session_id: str) -> Path | None:
    """Find JSONL file for session ID (partial match).

    Args:
        session_id: Full or partial session ID to search for

    Returns:
        Path to matching JSONL file, or None if not found
    """
    if not CLAUDE_DIR.exists():
        return None

    # Search all subdirectories for matching JSONL files
    for jsonl_path in CLAUDE_DIR.glob("*/*.jsonl"):
        # Check if session_id appears in filename
        if session_id in jsonl_path.stem:
            return jsonl_path

    # Also check content - sessionId field in first few lines
    for jsonl_path in CLAUDE_DIR.glob("*/*.jsonl"):
        try:
            with open(jsonl_path, 'r') as f:
                for _ in range(5):  # Check first 5 lines
                    line = f.readline()
                    if not line:
                        break
                    entry = json.loads(line)
                    if session_id in entry.get("sessionId", ""):
                        return jsonl_path
        except (json.JSONDecodeError, IOError):
            continue

    return None


def count_messages(jsonl_path: Path) -> int:
    """Count user/assistant messages (top-level type field).

    Args:
        jsonl_path: Path to JSONL file

    Returns:
        Number of user/assistant messages in the file
    """
    count = 0
    try:
        with open(jsonl_path, 'r') as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    msg_type = entry.get("type")
                    if msg_type in ("user", "assistant"):
                        count += 1
                except json.JSONDecodeError:
                    continue
    except IOError:
        return 0

    return count


def slice_at(jsonl_path: Path, at_message: int) -> str:
    """Create sliced copy at message N, return new session ID.

    Mimics the old bash approach: copy lines verbatim, only modify
    sessionId via regex replacement. This preserves JSON formatting
    which Claude Code may validate.

    IMPORTANT: Sessions must start with a 'summary' type line for
    Claude Code to load history on resume. If the source session
    starts with 'file-history-snapshot', we prepend a summary.

    Args:
        jsonl_path: Path to original JSONL file
        at_message: Message number to slice at (1-indexed)

    Returns:
        New UUID for the sliced session
    """
    import re

    new_session_id = str(uuid.uuid4())

    # Phase 1: Find cutoff line number (like grep -n | head -n N | tail -1)
    message_count = 0
    cutoff_line = 0
    existing_summary = None  # Track if we find a summary to copy

    with open(jsonl_path, 'r') as f:
        for line_num, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                msg_type = entry.get("type")

                # Capture existing summary text if we find one
                if msg_type == "summary" and existing_summary is None:
                    existing_summary = entry.get("summary", "Sliced session")

                if msg_type in ("user", "assistant"):
                    message_count += 1
                    cutoff_line = line_num
                    if message_count >= at_message:
                        break
            except json.JSONDecodeError:
                continue

    if cutoff_line == 0:
        raise ValueError(f"Could not find message {at_message}")

    # Phase 2: Copy lines verbatim up to cutoff (like head -n)
    lines_to_keep = []
    with open(jsonl_path, 'r') as f:
        for line_num, line in enumerate(f, 1):
            if line_num > cutoff_line:
                break
            lines_to_keep.append(line)

    # Phase 3: Replace sessionId via regex (like sed -i)
    # Pattern matches: "sessionId": "any-uuid-here"
    session_pattern = re.compile(r'"sessionId"\s*:\s*"[^"]*"')
    replacement = f'"sessionId": "{new_session_id}"'

    for i, line in enumerate(lines_to_keep):
        lines_to_keep[i] = session_pattern.sub(replacement, line)

    # Phase 4: Find the last uuid in the slice for leafUuid
    last_uuid = None
    for line in reversed(lines_to_keep):
        try:
            entry = json.loads(line)
            if entry.get("uuid"):
                last_uuid = entry["uuid"]
                break
        except json.JSONDecodeError:
            continue

    # Phase 5: Ensure proper structure for history loading
    # Claude Code requires:
    # 1. First line must be "summary" type
    # 2. file-history-snapshot must NOT be before first user/assistant message

    # Separate entries by type
    summary_lines = []
    fhs_lines = []  # file-history-snapshot
    message_lines = []

    for line in lines_to_keep:
        try:
            entry = json.loads(line)
            entry_type = entry.get("type")
            if entry_type == "summary":
                summary_lines.append(line)
            elif entry_type == "file-history-snapshot":
                fhs_lines.append(line)
            else:
                message_lines.append(line)
        except json.JSONDecodeError:
            message_lines.append(line)

    # If no summary, create one
    if not summary_lines:
        summary_text = existing_summary or "Sliced session"
        summary_entry = {
            "type": "summary",
            "summary": summary_text,
            "leafUuid": last_uuid or new_session_id
        }
        summary_lines = [json.dumps(summary_entry) + "\n"]
    else:
        # Update leafUuid in existing summary
        if last_uuid:
            leaf_pattern = re.compile(r'"leafUuid"\s*:\s*"[^"]*"')
            leaf_replacement = f'"leafUuid": "{last_uuid}"'
            summary_lines[0] = leaf_pattern.sub(leaf_replacement, summary_lines[0])

    # Rebuild: summaries first, then messages, then file-history-snapshots at end
    lines_to_keep = summary_lines + message_lines + fhs_lines

    # Save to same directory as original
    output_path = jsonl_path.parent / f"{new_session_id}.jsonl"
    with open(output_path, 'w') as f:
        f.writelines(lines_to_keep)

    return new_session_id


def extract_workdir(jsonl_path: Path) -> str:
    """Extract working directory from JSONL cwd field or decode from path.

    Args:
        jsonl_path: Path to JSONL file

    Returns:
        Working directory path as string
    """
    # First try to extract from cwd field in entries
    try:
        with open(jsonl_path, 'r') as f:
            for _ in range(10):  # Check first 10 lines
                line = f.readline()
                if not line:
                    break
                try:
                    entry = json.loads(line)
                    cwd = entry.get("cwd")
                    if cwd:
                        return cwd
                except json.JSONDecodeError:
                    continue
    except IOError:
        pass

    # Fall back to decoding from path
    # Path encoding: -home-axp-projects-foo -> /home/axp/projects/foo
    parent_name = jsonl_path.parent.name
    if parent_name.startswith("-"):
        # Convert dashes back to slashes (except first one which is just prefix)
        decoded = parent_name.replace("-", "/")
        return decoded

    return ""
