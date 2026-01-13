"""
JSONL slicing library for Claude Code session manipulation.

Provides functions to find, count, slice, and extract metadata from
Claude Code JSONL session files.

Uses Thread's database for message lookups when available.
"""

import json
import subprocess
import sys
import uuid
from pathlib import Path


CLAUDE_DIR = Path.home() / ".claude/projects"
THREAD_FIND = Path.home() / "projects/thread/main/scripts/find-message.py"


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


def query_thread(session_id: str, at: str) -> dict | None:
    """Query Thread's database to find slice point.

    Args:
        session_id: Session ID (prefix ok)
        at: Slice reference - can be:
            - Content string: "crossover solution"
            - Message number: "42"
            - UUID prefix: "4550d0e6"
            - Line number prefixed with 'L': "L225"

    Returns:
        Dict with jsonl_line, or None if not found
    """
    if not THREAD_FIND.exists():
        return None

    # Determine query type
    if at.startswith('L') and at[1:].isdigit():
        # Line number: L225
        cmd = [sys.executable, str(THREAD_FIND), session_id, "--line", at[1:]]
    elif at.isdigit():
        # Message number: 42
        cmd = [sys.executable, str(THREAD_FIND), session_id, "--msg", at]
    elif len(at) >= 8 and all(c in '0123456789abcdef-' for c in at[:8]):
        # UUID prefix: 4550d0e6
        cmd = [sys.executable, str(THREAD_FIND), "--uuid", at]
    else:
        # Content search - try user messages first, then assistant
        cmd = [sys.executable, str(THREAD_FIND), session_id, "--content", at, "--user"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            if data and 'jsonl_line' in data:
                return data
        # Fall back to assistant messages
        cmd = [sys.executable, str(THREAD_FIND), session_id, "--content", at]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return None

    try:
        data = json.loads(result.stdout)
        if 'error' in data:
            return None
        return data
    except json.JSONDecodeError:
        return None


def slice_at(jsonl_path: Path, at: str | int) -> str:
    """Create sliced copy at specified point, return new session ID.

    Uses Thread's database for smart lookups when available, falls back
    to line counting for legacy support.

    IMPORTANT: Sessions must start with a 'summary' type line for
    Claude Code to load history on resume. If the source session
    starts with 'file-history-snapshot', we prepend a summary.

    Args:
        jsonl_path: Path to original JSONL file
        at: Slice point - can be:
            - int: Legacy message number (1-indexed, counts user/assistant)
            - str starting with 'L': Line number (e.g., "L225")
            - str digits: Message number (e.g., "42")
            - str UUID: Message UUID prefix (e.g., "4550d0e6")
            - str other: Content search (e.g., "crossover solution")

    Returns:
        New UUID for the sliced session
    """
    import re

    new_session_id = str(uuid.uuid4())
    session_id = jsonl_path.stem
    cutoff_line = 0
    existing_summary = None

    # Try Thread lookup first for string arguments
    if isinstance(at, str):
        thread_result = query_thread(session_id, at)
        if thread_result and thread_result.get('jsonl_line'):
            cutoff_line = thread_result['jsonl_line']
            # Get existing summary while we're reading the file
            with open(jsonl_path, 'r') as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        if entry.get('type') == 'summary':
                            existing_summary = entry.get('summary', 'Sliced session')
                            break
                    except json.JSONDecodeError:
                        continue

    # Legacy fallback: count messages (for int or if Thread lookup failed)
    if cutoff_line == 0:
        # Handle direct line number (L76 syntax) without Thread
        if isinstance(at, str) and at.startswith('L') and at[1:].isdigit():
            cutoff_line = int(at[1:])
            # Get existing summary
            with open(jsonl_path, 'r') as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        if entry.get('type') == 'summary':
                            existing_summary = entry.get('summary', 'Sliced session')
                            break
                    except json.JSONDecodeError:
                        continue
        elif isinstance(at, str) and at.isdigit():
            at_message = int(at)
        elif isinstance(at, int):
            at_message = at
        else:
            raise ValueError(f"Could not find slice point: {at}")

        # Count messages if we still need cutoff_line
        if cutoff_line == 0 and 'at_message' in dir():
            message_count = 0
            with open(jsonl_path, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    if not line.strip():
                        continue
                    try:
                        entry = json.loads(line)
                        msg_type = entry.get("type")

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
        raise ValueError(f"Could not find slice point: {at}")

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

    # Phase 5: Fix parentUuid tree (ensure single root)
    # Sessions with Nexus injection may have multiple parentUuid: null entries
    # We need to relink them so only the first user/assistant is the root
    first_root_uuid = None
    prev_uuid = None
    fixed_lines = []

    # Use regex to preserve original JSON formatting
    null_parent_pattern = re.compile(r'"parentUuid"\s*:\s*null')

    for line in lines_to_keep:
        try:
            entry = json.loads(line)
            entry_type = entry.get("type")

            if entry_type in ("user", "assistant"):
                current_uuid = entry.get("uuid")
                parent_uuid = entry.get("parentUuid")

                # If this is a null parent entry
                if parent_uuid is None:
                    if first_root_uuid is None:
                        # First root - keep it as the root
                        first_root_uuid = current_uuid
                    else:
                        # Subsequent null parent - relink via regex (preserves formatting)
                        line = null_parent_pattern.sub(f'"parentUuid": "{prev_uuid}"', line)

                prev_uuid = current_uuid

            fixed_lines.append(line)
        except json.JSONDecodeError:
            fixed_lines.append(line)

    lines_to_keep = fixed_lines

    # Phase 6: Ensure proper structure for history loading
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

    # Recalculate last_uuid from message_lines (after all fixes applied)
    last_uuid = None
    for line in reversed(message_lines):
        try:
            entry = json.loads(line)
            if entry.get("uuid"):
                last_uuid = entry["uuid"]
                break
        except json.JSONDecodeError:
            continue

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
