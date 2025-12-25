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

    Args:
        jsonl_path: Path to original JSONL file
        at_message: Message number to slice at (1-indexed)

    Returns:
        New UUID for the sliced session
    """
    new_session_id = str(uuid.uuid4())

    # Read all lines and find cutoff point
    lines_to_keep = []
    message_count = 0

    with open(jsonl_path, 'r') as f:
        for line in f:
            if not line.strip():
                continue

            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                # Keep non-JSON lines as-is
                lines_to_keep.append(line)
                continue

            msg_type = entry.get("type")

            # Count user/assistant messages
            if msg_type in ("user", "assistant"):
                message_count += 1

                # Stop if we've reached the cutoff
                if message_count > at_message:
                    break

            # Rewrite sessionId in all entries
            if "sessionId" in entry:
                entry["sessionId"] = new_session_id

            lines_to_keep.append(json.dumps(entry) + "\n")

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
