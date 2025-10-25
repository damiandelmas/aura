#!/usr/bin/env python3
"""
TRACE - Standalone CLI for conversation archaeology
Clean agent-to-agent conversation memory for Claude Code sessions

Subcommand structure optimized for AI agents:
  trace show [content] [session-id]     - Display to terminal
  trace export [content] [session-id]   - Export to file
  trace list [--marker keyword]         - List conversations
"""

import sys
import json
import click
from pathlib import Path

# Microservice imports (within trace package)
from .finder import ConversationFinder
from .retrieval import ConversationRetrieval
from .formatter import ConversationFormatter


# ============================================================================
# CLI Group - Main entry point
# ============================================================================

@click.group()
def trace():
    """TRACE: Agent-to-agent conversation memory for Claude Code sessions

    Optimized for AI agents with clear verb-noun structure.
    """
    pass


# ============================================================================
# LIST command - Discovery
# ============================================================================

@trace.command()
@click.option('--marker', help='Filter conversations containing this marker')
@click.option('--limit', type=int, default=20, help='Maximum number of results to show')
def list(marker, limit):
    """List available conversations

    Examples:
        trace list
        trace list --marker "architecture"
        trace list --limit 10
    """
    finder = ConversationFinder()

    if marker:
        conversations = finder.find_by_marker(marker)
        click.echo(f"🔍 Found {len(conversations)} conversations with marker '{marker}':")
    else:
        conversations = finder.list_all()
        click.echo(f"📚 Found {len(conversations)} conversations:")

    if not conversations:
        click.echo("  No conversations found")
        return

    for i, conv_file in enumerate(conversations[:limit], 1):
        info = finder.get_conversation_info(conv_file)
        session_id = info['session_id']
        modified = info['modified_time'].strftime('%Y-%m-%d %H:%M')
        size_kb = info['file_size'] // 1024
        click.echo(f"  {i}. {session_id} - {modified} ({size_kb}KB)")

    if len(conversations) > limit:
        click.echo(f"  ... and {len(conversations) - limit} more (use --limit to see more)")


# ============================================================================
# SHOW command - Display to terminal
# ============================================================================

@trace.command()
@click.argument('content', type=click.Choice(['messages', 'patches', 'chronicle', 'metadata', 'files', 'tools']))
@click.argument('session_id')
def show(content, session_id):
    """Display conversation content to terminal

    Arguments:
        content     What to show (messages, patches, chronicle, metadata, files, tools)
        session_id  Session identifier (full or partial)

    Examples:
        trace show messages abc123
        trace show chronicle abc123
        trace show metadata abc123
        trace show patches abc123
    """
    finder = ConversationFinder()
    conv_file = finder.find_by_session_id(session_id)

    if not conv_file:
        click.echo(f"❌ Session '{session_id}' not found")
        click.echo("\n💡 Use 'trace list' to see available sessions")
        sys.exit(1)

    click.echo(f"📁 Found: {conv_file.name}\n")

    retrieval = ConversationRetrieval()
    entries = retrieval.load_conversation(conv_file)

    # Route to appropriate handler
    if content == 'metadata':
        _show_metadata(retrieval, entries)
    elif content == 'files':
        _show_files(retrieval, entries)
    elif content == 'tools':
        _show_tools(retrieval, entries)
    elif content == 'patches':
        _show_patches(retrieval, entries)
    elif content == 'messages':
        _show_messages(retrieval, entries)
    elif content == 'chronicle':
        _show_chronicle(retrieval, entries)


def _show_metadata(retrieval, entries):
    """Display metadata to terminal"""
    formatter = ConversationFormatter()
    metadata_data = retrieval.get_metadata(entries)
    output = formatter.format_metadata(metadata_data)
    click.echo(output)


def _show_files(retrieval, entries):
    """Display file operations to terminal"""
    formatter = ConversationFormatter()
    file_ops = retrieval.get_file_operations(entries)

    if not file_ops:
        click.echo("📁 File Operations:\n  No file operations found")
        return

    click.echo("📁 File Operations:")
    output = formatter.format_files(file_ops)
    click.echo(output)
    click.echo(f"\nTotal: {len(file_ops)} file operations")


def _show_tools(retrieval, entries):
    """Display tool usage to terminal"""
    formatter = ConversationFormatter()
    tool_usage = retrieval.get_tool_usage(entries)

    if not tool_usage:
        click.echo("🔧 Tool Usage:\n  No tools used")
        return

    click.echo("🔧 Tool Usage:")
    output = formatter.format_tools(tool_usage)
    click.echo(output)


def _show_patches(retrieval, entries):
    """Display code patches to terminal"""
    formatter = ConversationFormatter()
    patch_list = retrieval.get_patches(entries)

    if not patch_list:
        click.echo("📝 Code Patches (File Edits):\n  No code patches found")
        return

    click.echo(f"📝 Code Patches (File Edits):\n  Found {len(patch_list)} patches\n")
    output = formatter.format_patches(patch_list)
    click.echo(output)


def _show_messages(retrieval, entries):
    """Display messages to terminal"""
    formatter = ConversationFormatter()
    all_messages = retrieval.get_messages(entries)

    # Filter to text-only messages
    text_messages = []
    for msg in all_messages:
        role = msg.get('role')
        if role not in ['user', 'assistant']:
            continue

        content = msg.get('content', [])

        # Skip tool use/results
        if isinstance(content, list):
            has_tools = any(
                isinstance(item, dict) and item.get('type') in ['tool_use', 'tool_result']
                for item in content
            )
            if has_tools:
                continue

        # Skip meta/command messages
        if isinstance(content, str):
            if '<command-name>' in content or 'Caveat:' in content:
                continue

        # Check for actual text content
        has_text = False
        if isinstance(content, str) and content.strip():
            has_text = True
        elif isinstance(content, list):
            has_text = any(
                isinstance(item, dict) and item.get('type') == 'text' and item.get('text', '').strip()
                for item in content
            )

        if has_text:
            text_messages.append(msg)

    click.echo(f"💬 Conversation ({len(text_messages)} messages):\n")
    output = formatter.format_messages(text_messages)
    click.echo(output)


def _show_chronicle(retrieval, entries):
    """Display complete chronicle to terminal"""
    formatter = ConversationFormatter()

    timeline = retrieval.get_timeline(
        entries,
        include_messages=True,
        include_patches=True,
        include_files=False,
        include_tools=False
    )

    metadata = retrieval.get_metadata(entries)
    output = formatter.format(timeline, metadata.get('session_id'), metadata)

    click.echo(f"📜 Complete Chronicle ({len(timeline)} events):\n")
    click.echo(output)


# ============================================================================
# EXPORT command - Save to file
# ============================================================================

@trace.command()
@click.argument('content', type=click.Choice(['chronicle', 'messages', 'patches', 'metadata']))
@click.argument('session_id')
@click.option('--output', '-o', 'output_path', type=click.Path(), help='Output file path (default: auto-generated)')
def export(content, session_id, output_path):
    """Export conversation content to file

    Arguments:
        content     What to export (chronicle, messages, patches, metadata)
        session_id  Session identifier (full or partial)

    Options:
        --output, -o    Output file path (default: <session>-<content>.md)

    Examples:
        trace export chronicle abc123
        trace export chronicle abc123 --output context.md
        trace export messages abc123 -o messages.md
    """
    finder = ConversationFinder()
    conv_file = finder.find_by_session_id(session_id)

    if not conv_file:
        click.echo(f"❌ Session '{session_id}' not found")
        click.echo("\n💡 Use 'trace list' to see available sessions")
        sys.exit(1)

    click.echo(f"📁 Found: {conv_file.name}")

    # Auto-generate filename if not provided
    if not output_path:
        output_path = f"{session_id[:12]}-{content}.md"

    output_file = Path(output_path)

    try:
        retrieval = ConversationRetrieval()
        formatter = ConversationFormatter()

        if content == 'chronicle':
            # Export chronological markdown (primary use case for IMEM)
            entries = retrieval.load_conversation(conv_file)
            timeline = retrieval.get_timeline(
                entries,
                include_messages=True,
                include_patches=True,
                include_files=False,
                include_tools=False
            )
            metadata = retrieval.get_metadata(entries)
            md = formatter.format(timeline, metadata.get('session_id'), metadata)

            output_file.write_text(md, encoding='utf-8')
            click.echo(f"\n✅ Exported to: {output_file}")
            click.echo(f"   Format: Chronological markdown (LlamaIndex-ready)")

        elif content == 'messages':
            # Export messages only
            entries = retrieval.load_conversation(conv_file)
            timeline = retrieval.get_timeline(
                entries,
                include_messages=True,
                include_patches=False,
                include_files=False,
                include_tools=False
            )
            metadata = retrieval.get_metadata(entries)
            md = formatter.format(timeline, metadata.get('session_id'), metadata)

            output_file.write_text(md, encoding='utf-8')
            click.echo(f"\n✅ Exported to: {output_file}")
            click.echo(f"   Format: Messages only")

        elif content == 'patches':
            # Export patches only
            entries = retrieval.load_conversation(conv_file)
            timeline = retrieval.get_timeline(
                entries,
                include_messages=False,
                include_patches=True,
                include_files=False,
                include_tools=False
            )
            metadata = retrieval.get_metadata(entries)
            md = formatter.format(timeline, metadata.get('session_id'), metadata)

            output_file.write_text(md, encoding='utf-8')
            click.echo(f"\n✅ Exported to: {output_file}")
            click.echo(f"   Format: Patches only")

        elif content == 'metadata':
            # Export metadata as JSON
            entries = retrieval.load_conversation(conv_file)
            metadata = retrieval.get_metadata(entries)

            # Convert datetime objects to strings
            import datetime
            def serialize_datetime(obj):
                if isinstance(obj, datetime.datetime):
                    return obj.isoformat()
                raise TypeError(f"Type {type(obj)} not serializable")

            json_output = json.dumps(metadata, indent=2, default=serialize_datetime)
            output_file.write_text(json_output, encoding='utf-8')
            click.echo(f"\n✅ Exported to: {output_file}")
            click.echo(f"   Format: JSON metadata")

    except Exception as e:
        click.echo(f"\n❌ Export failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


# ============================================================================
# Entry point
# ============================================================================

if __name__ == '__main__':
    trace()
