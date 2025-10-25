#!/usr/bin/env python3
"""
Conversation Formatter - Single format for all outputs

ONE FORMAT FOR EVERYTHING:
- AI agents (primary user)
- IMEM indexing
- File exports
- Terminal display (rare, but still readable)

Optimized for AI, works for all.
"""

from typing import List, Dict, Any


class ConversationFormatter:
    """Format conversation timelines into chronological markdown

    This is the ONLY formatter. One format for all use cases.
    Optimized for AI agents and LlamaIndex, but human-readable too.
    """

    def format(self, timeline: List[Dict[str, Any]],
               session_id: str = None,
               metadata: Dict[str, Any] = None) -> str:
        """Format timeline as chronological markdown

        ONE FORMAT FOR EVERYTHING:
        - Creates H2 sections for each message/patch
        - Numbered (Message 1, Message 2, Patch 1, etc.)
        - Chronological order preserved
        - Optimized for LlamaIndex chunking
        - Still human-readable

        Each H2 section becomes a separate LlamaIndex chunk,
        preserving conversation context for semantic search.

        Args:
            timeline: Chronological list of events from get_timeline()
            session_id: Session identifier (optional)
            metadata: Conversation metadata - duration, message count (optional)

        Returns:
            Markdown string with numbered H2 sections
        """
        md = []

        # Header
        if session_id:
            md.append(f"# Conversation: {session_id[:12]}\n")
        else:
            md.append("# Conversation\n")

        if metadata:
            duration = metadata.get('duration_minutes', 0)
            msg_count = metadata.get('message_count', 0)
            md.append(f"**Duration:** {duration:.0f}min | **Messages:** {msg_count}\n")

        md.append("")  # Blank line

        # Process timeline chronologically
        message_num = 1
        patch_num = 1

        for event in timeline:
            event_type = event.get('type')

            if event_type == 'message':
                role = event.get('role', 'unknown').upper()
                text = event.get('text', '')

                # Each message = separate H2 section
                md.append(f"## Message {message_num}: {role}\n")
                md.append(f"{text}\n")
                md.append("")  # Blank line between sections

                message_num += 1

            elif event_type == 'patch':
                file = event.get('file', 'unknown')
                diff_lines = event.get('diff_lines', [])

                # Each patch = separate H2 section
                md.append(f"## Code Patch {patch_num}: {file}\n")

                # Format diff
                if diff_lines:
                    md.append("```diff")
                    md.append("\n".join(diff_lines))
                    md.append("```\n")
                else:
                    md.append("*No diff content*\n")

                md.append("")  # Blank line

                patch_num += 1

            elif event_type == 'file':
                # File operations (if included)
                path = event.get('path', 'unknown')
                operation = event.get('operation', 'unknown')
                md.append(f"## File Operation: {operation} {path}\n")
                md.append("")

            elif event_type == 'tool':
                # Tool usage (if included)
                name = event.get('name', 'unknown')
                md.append(f"## Tool Used: {name}\n")
                md.append("")

        return "\n".join(md)

    def format_metadata(self, metadata: Dict[str, Any]) -> str:
        """Format conversation metadata for display

        Args:
            metadata: Metadata dict from get_metadata()

        Returns:
            Formatted metadata string
        """
        lines = []

        summary = metadata.get('summary', 'N/A')
        session_id = metadata.get('session_id', 'N/A')
        duration = metadata.get('duration_minutes', 0)
        duration_str = f"{duration:.1f} minutes" if duration else "N/A"

        start_time = metadata.get('start_time')
        end_time = metadata.get('end_time')
        start_str = start_time.strftime('%Y-%m-%d %H:%M:%S') if start_time else "N/A"
        end_str = end_time.strftime('%Y-%m-%d %H:%M:%S') if end_time else "N/A"

        working_dir = metadata.get('working_directory', 'N/A')

        lines.append("\n📊 Conversation Metadata\n")
        lines.append(f"**Topic:** {summary}")
        lines.append(f"**Session:** {session_id}")
        lines.append(f"**Working Directory:** {working_dir}")
        lines.append(f"\n**Timing:**")
        lines.append(f"  - Started: {start_str}")
        lines.append(f"  - Ended: {end_str}")
        lines.append(f"  - Duration: {duration_str}")
        lines.append(f"\n**Messages:** {metadata.get('message_count', 0)} total")
        lines.append(f"  - User: {metadata.get('user_messages', 0)}")
        lines.append(f"  - Assistant: {metadata.get('assistant_messages', 0)}")

        return "\n".join(lines)

    def format_messages(self, messages: List[Dict[str, Any]]) -> str:
        """Format messages for display

        Args:
            messages: List of message dicts from get_messages()

        Returns:
            Formatted messages string
        """
        lines = []

        for msg in messages:
            role = msg.get('role', '').upper()
            lines.append(f"\n## {role}\n")

            content = msg.get('content', '')
            if isinstance(content, str):
                lines.append(content)
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get('type') == 'text':
                        lines.append(item.get('text', ''))

        return "\n".join(lines)

    def format_patches(self, patches: List[Dict[str, Any]]) -> str:
        """Format code patches for display

        Args:
            patches: List of patch dicts from get_patches()

        Returns:
            Formatted patches string
        """
        lines = []

        for i, patch_data in enumerate(patches, 1):
            file_path = patch_data['file']
            timestamp = patch_data['timestamp'].strftime('%Y-%m-%d %H:%M:%S') if patch_data['timestamp'] else 'N/A'

            lines.append(f"## Patch {i}: {file_path}")
            lines.append(f"**Time:** {timestamp}")
            lines.append(f"**Lines:** @@ -{patch_data['old_start']},{patch_data['old_lines']} +{patch_data['new_start']},{patch_data['new_lines']} @@\n")

            for line in patch_data['diff_lines']:
                lines.append(f"  {line}")

            lines.append("")

        return "\n".join(lines)

    def format_files(self, file_ops: List[Dict[str, Any]]) -> str:
        """Format file operations for display

        Args:
            file_ops: List of file operation dicts from get_file_operations()

        Returns:
            Formatted file operations string
        """
        lines = []

        for op in file_ops:
            lines.append(f"  {op['operation']}: {op['path']}")

        return "\n".join(lines)

    def format_tools(self, tool_usage: List[Dict[str, Any]]) -> str:
        """Format tool usage for display

        Args:
            tool_usage: List of tool usage dicts from get_tool_usage()

        Returns:
            Formatted tool usage string
        """
        lines = []

        tool_counts = {}
        for tool in tool_usage:
            name = tool['name']
            tool_counts[name] = tool_counts.get(name, 0) + 1

        for tool_name, count in sorted(tool_counts.items()):
            lines.append(f"  {tool_name}: {count} uses")

        return "\n".join(lines)
