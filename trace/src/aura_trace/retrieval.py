#!/usr/bin/env python3
"""
Conversation Retrieval Service - Direct access to Claude Code JSONL data
Simple, clean retrieval with minimal intelligent manipulation.
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Any, Union
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ConversationEntry:
    """Raw conversation entry from JSONL"""
    type: str  # 'user' | 'assistant' | 'summary'
    timestamp: Optional[datetime] = None
    session_id: Optional[str] = None
    uuid: Optional[str] = None
    parent_uuid: Optional[str] = None
    cwd: Optional[str] = None
    message: Optional[Dict[str, Any]] = None
    tool_use_result: Optional[Dict[str, Any]] = None
    thinking_metadata: Optional[Dict[str, Any]] = None
    raw_data: Optional[Dict[str, Any]] = None

@dataclass
class RetrievalOptions:
    """Simple options for data manipulation"""
    # Messages
    message_limit: Optional[int] = None  # Last N messages
    include_thinking: bool = False       # Include thinking metadata
    
    # Tools
    tool_filter: Optional[List[str]] = None  # Filter by tool names
    include_tool_results: bool = True        # Include tool execution results
    
    # Content
    content_types: Optional[List[str]] = None  # ['text', 'tool_use', 'tool_result']
    
    # Threading
    follow_thread: bool = False  # Follow conversation thread from a specific message


class ConversationRetrieval:
    """Direct retrieval service for Claude Code conversations"""
    
    def __init__(self, project_root: Path = None):
        self.project_root = project_root or self._find_project_root()
        
    def _find_project_root(self) -> Path:
        """Find git project root"""
        current = Path.cwd()
        for parent in [current] + list(current.parents):
            if (parent / '.git').exists():
                return parent
        return current
    
    def load_conversation(self, file_path: Path) -> List[ConversationEntry]:
        """Load raw conversation from JSONL file"""
        entries = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                        
                    try:
                        data = json.loads(line)
                        entry = self._parse_entry(data)
                        if entry:
                            entries.append(entry)
                    except json.JSONDecodeError as e:
                        logger.warning(f"Invalid JSON on line {line_num}: {e}")
                        continue
                        
        except Exception as e:
            logger.error(f"Failed to load conversation {file_path}: {e}")
            
        return entries
    
    def _parse_entry(self, data: Dict[str, Any]) -> Optional[ConversationEntry]:
        """Parse a single JSONL entry"""
        try:
            # Extract timestamp
            timestamp = None
            if 'timestamp' in data:
                timestamp = datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00'))
            
            # Extract tool use result if present
            tool_use_result = data.get('toolUseResult')
            
            # Extract thinking metadata if present
            thinking_metadata = data.get('thinkingMetadata')
            
            return ConversationEntry(
                type=data.get('type', 'unknown'),
                timestamp=timestamp,
                session_id=data.get('sessionId'),
                uuid=data.get('uuid'),
                parent_uuid=data.get('parentUuid'),
                cwd=data.get('cwd'),
                message=data.get('message'),
                tool_use_result=tool_use_result,
                thinking_metadata=thinking_metadata,
                raw_data=data
            )
            
        except Exception as e:
            logger.warning(f"Failed to parse entry: {e}")
            return None
    
    def get_messages(self, entries: List[ConversationEntry], options: RetrievalOptions = None) -> List[Dict[str, Any]]:
        """Extract messages with optional filtering"""
        options = options or RetrievalOptions()
        messages = []
        
        for entry in entries:
            if not entry.message:
                continue
                
            message = entry.message.copy()
            
            # Add metadata
            message['_timestamp'] = entry.timestamp
            message['_uuid'] = entry.uuid
            message['_cwd'] = entry.cwd
            
            # Include thinking if requested
            if options.include_thinking and entry.thinking_metadata:
                message['_thinking'] = entry.thinking_metadata
            
            # Filter content types if specified
            if options.content_types and 'content' in message:
                filtered_content = []
                for content_item in message['content']:
                    if isinstance(content_item, dict) and content_item.get('type') in options.content_types:
                        filtered_content.append(content_item)
                message['content'] = filtered_content
            
            messages.append(message)
        
        # Apply message limit
        if options.message_limit:
            messages = messages[-options.message_limit:]
            
        return messages
    
    def get_tool_usage(self, entries: List[ConversationEntry], options: RetrievalOptions = None) -> List[Dict[str, Any]]:
        """Extract tool usage from conversation"""
        options = options or RetrievalOptions()
        tools = []

        for entry in entries:
            if not entry.message or 'content' not in entry.message:
                continue

            content = entry.message['content']
            if not isinstance(content, list):
                continue

            for content_item in content:
                if not isinstance(content_item, dict):
                    continue

                if content_item.get('type') == 'tool_use':
                    tool_name = content_item.get('name')

                    # Apply tool filter
                    if options.tool_filter and tool_name not in options.tool_filter:
                        continue

                    tool_data = {
                        'name': tool_name,
                        'id': content_item.get('id'),
                        'input': content_item.get('input', {}),
                        'timestamp': entry.timestamp,
                        'uuid': entry.uuid,
                        'cwd': entry.cwd
                    }

                    # Include tool result if available and requested
                    if options.include_tool_results and entry.tool_use_result:
                        tool_data['result'] = entry.tool_use_result

                    tools.append(tool_data)

        return tools
    
    def get_file_operations(self, entries: List[ConversationEntry]) -> List[Dict[str, Any]]:
        """Extract file operations from tool usage and results"""
        file_ops = []
        seen = set()  # Track (path, operation) to avoid duplicates

        for entry in entries:
            # From tool use results
            if entry.tool_use_result and isinstance(entry.tool_use_result, dict):
                result = entry.tool_use_result
                file_path = result.get('filePath')

                if file_path:
                    operation = result.get('type', 'unknown')
                    key = (file_path, operation)
                    if key not in seen:
                        seen.add(key)
                        file_ops.append({
                            'path': file_path,
                            'operation': operation,
                            'timestamp': entry.timestamp,
                            'uuid': entry.uuid,
                            'cwd': entry.cwd,
                            'details': result
                        })

            # From tool use inputs (Write, Edit tools)
            if entry.message and 'content' in entry.message:
                content = entry.message['content']
                if not isinstance(content, list):
                    continue

                for content_item in content:
                    if not isinstance(content_item, dict):
                        continue

                    if content_item.get('type') == 'tool_use':
                        tool_name = content_item.get('name')
                        tool_input = content_item.get('input', {})

                        # Extract file path from common tools
                        file_path = None
                        operation = None

                        if tool_name in ['Write', 'save-file']:
                            file_path = tool_input.get('file_path') or tool_input.get('path')
                            operation = 'create'
                        elif tool_name in ['Edit', 'str-replace-editor']:
                            file_path = tool_input.get('file_path') or tool_input.get('path')
                            operation = 'edit'
                        elif tool_name in ['remove-files']:
                            file_paths = tool_input.get('file_paths', [])
                            for fp in file_paths:
                                key = (fp, 'delete')
                                if key not in seen:
                                    seen.add(key)
                                    file_ops.append({
                                        'path': fp,
                                        'operation': 'delete',
                                        'timestamp': entry.timestamp,
                                        'uuid': entry.uuid,
                                        'cwd': entry.cwd,
                                        'tool': tool_name
                                    })
                            continue

                        if file_path:
                            key = (file_path, operation)
                            if key not in seen:
                                seen.add(key)
                                file_ops.append({
                                    'path': file_path,
                                    'operation': operation,
                                    'timestamp': entry.timestamp,
                                    'uuid': entry.uuid,
                                    'cwd': entry.cwd,
                                    'tool': tool_name,
                                    'input': tool_input
                                })

        return file_ops
    
    def get_conversation_thread(self, entries: List[ConversationEntry], start_uuid: str) -> List[ConversationEntry]:
        """Follow conversation thread from a specific message"""
        # Build UUID to entry mapping
        uuid_map = {entry.uuid: entry for entry in entries if entry.uuid}
        
        # Find starting entry
        if start_uuid not in uuid_map:
            return []
        
        # Follow thread forward
        thread = []
        current = uuid_map[start_uuid]
        
        while current:
            thread.append(current)
            
            # Find next entry that has current as parent
            next_entry = None
            for entry in entries:
                if entry.parent_uuid == current.uuid:
                    next_entry = entry
                    break
            
            current = next_entry
        
        return thread
    
    def get_patches(self, entries: List[ConversationEntry], options: RetrievalOptions = None) -> List[Dict[str, Any]]:
        """Extract code patches (edits) from conversation

        Returns structured diff data for all file edits.
        """
        patches = []

        for entry in entries:
            # Only look at entries with tool results
            if not entry.tool_use_result or not isinstance(entry.tool_use_result, dict):
                continue

            result = entry.tool_use_result

            # Check if this entry has patch data
            if 'structuredPatch' not in result:
                continue

            structured_patches = result.get('structuredPatch', [])

            # Skip empty patches
            if not structured_patches:
                continue

            # Extract file path and operation type
            file_path = result.get('filePath', 'unknown')
            operation = result.get('type', 'unknown')

            # Build patch record
            for patch in structured_patches:
                patches.append({
                    'file': file_path,
                    'operation': operation,
                    'timestamp': entry.timestamp,
                    'uuid': entry.uuid,
                    'cwd': entry.cwd,
                    'patch': patch,
                    'old_start': patch.get('oldStart'),
                    'old_lines': patch.get('oldLines'),
                    'new_start': patch.get('newStart'),
                    'new_lines': patch.get('newLines'),
                    'diff_lines': patch.get('lines', [])
                })

        return patches

    def get_metadata(self, entries: List[ConversationEntry]) -> Dict[str, Any]:
        """Get conversation metadata (session info, timing, message counts)"""
        if not entries:
            return {}

        # Find summary entry
        summary_entry = None
        for entry in entries:
            if entry.type == 'summary':
                summary_entry = entry
                break
        
        # Count message types
        user_messages = sum(1 for e in entries if e.type == 'user')
        assistant_messages = sum(1 for e in entries if e.type == 'assistant')
        
        # Get time range
        timestamps = [e.timestamp for e in entries if e.timestamp]
        start_time = min(timestamps) if timestamps else None
        end_time = max(timestamps) if timestamps else None
        
        # Get session info
        session_id = next((e.session_id for e in entries if e.session_id), None)
        cwd = next((e.cwd for e in entries if e.cwd), None)
        
        return {
            'summary': summary_entry.raw_data.get('summary') if summary_entry else None,
            'session_id': session_id,
            'working_directory': cwd,
            'message_count': user_messages + assistant_messages,
            'user_messages': user_messages,
            'assistant_messages': assistant_messages,
            'start_time': start_time,
            'end_time': end_time,
            'duration_minutes': (end_time - start_time).total_seconds() / 60 if start_time and end_time else None
        }

    def get_timeline(self, entries: List[ConversationEntry],
                     include_messages: bool = True,
                     include_patches: bool = True,
                     include_files: bool = False,
                     include_tools: bool = False) -> List[Dict[str, Any]]:
        """Get chronological timeline of all conversation events

        This is the SINGLE SOURCE OF TRUTH for conversation data.
        All other methods (--messages, --patches, --chronicle) filter this timeline.

        Args:
            entries: Raw conversation entries
            include_messages: Include user/assistant messages
            include_patches: Include code patches (diffs)
            include_files: Include file operations
            include_tools: Include tool usage

        Returns:
            List of chronologically sorted events, each with:
            - type: 'message' | 'patch' | 'file' | 'tool'
            - timestamp: datetime or ISO string
            - event-specific fields (role, text, file, diff, etc.)
            - raw: original data for debugging
        """
        timeline = []

        # Add messages
        if include_messages:
            messages = self.get_messages(entries)
            for msg in messages:
                if msg.get('role') in ['user', 'assistant']:
                    # Extract text content
                    text = ''
                    content = msg.get('content', [])
                    if isinstance(content, str):
                        text = content
                    elif isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and item.get('type') == 'text':
                                text = item.get('text', '')
                                break

                    if text:  # Only add if has text content
                        timeline.append({
                            'type': 'message',
                            'timestamp': msg.get('_timestamp'),
                            'role': msg.get('role'),
                            'text': text,
                            'raw': msg
                        })

        # Add patches
        if include_patches:
            patches = self.get_patches(entries)
            for patch in patches:
                timeline.append({
                    'type': 'patch',
                    'timestamp': patch.get('timestamp'),
                    'file': patch.get('file'),
                    'operation': 'edit',
                    'old_start': patch.get('old_start'),
                    'old_lines': patch.get('old_lines'),
                    'new_start': patch.get('new_start'),
                    'new_lines': patch.get('new_lines'),
                    'diff_lines': patch.get('diff_lines', []),
                    'raw': patch
                })

        # Add file operations
        if include_files:
            files = self.get_file_operations(entries)
            for file_op in files:
                timeline.append({
                    'type': 'file',
                    'timestamp': file_op.get('timestamp'),
                    'path': file_op.get('path'),
                    'operation': file_op.get('operation'),
                    'raw': file_op
                })

        # Add tool usage
        if include_tools:
            tools = self.get_tool_usage(entries)
            for tool in tools:
                timeline.append({
                    'type': 'tool',
                    'timestamp': tool.get('timestamp'),
                    'name': tool.get('name'),
                    'raw': tool
                })

        # Sort chronologically (handle both datetime and string timestamps)
        def get_sort_key(event):
            ts = event.get('timestamp')
            if ts is None:
                return datetime.min
            if isinstance(ts, datetime):
                return ts
            if isinstance(ts, str):
                try:
                    return datetime.fromisoformat(ts.replace('Z', '+00:00'))
                except:
                    return datetime.min
            return datetime.min

        timeline.sort(key=get_sort_key)

        return timeline


# Convenience functions for common use cases
def get_conversation_data(file_path: Path, options: RetrievalOptions = None) -> Dict[str, Any]:
    """Get all conversation data in one call"""
    retrieval = ConversationRetrieval()
    entries = retrieval.load_conversation(file_path)

    return {
        'metadata': retrieval.get_metadata(entries),
        'messages': retrieval.get_messages(entries, options),
        'tools': retrieval.get_tool_usage(entries, options),
        'files': retrieval.get_file_operations(entries),
        'raw_entries': entries
    }

def get_recent_messages(file_path: Path, count: int = 10, include_thinking: bool = False) -> List[Dict[str, Any]]:
    """Quick access to recent messages"""
    options = RetrievalOptions(message_limit=count, include_thinking=include_thinking)
    retrieval = ConversationRetrieval()
    entries = retrieval.load_conversation(file_path)
    return retrieval.get_messages(entries, options)

def get_file_changes(file_path: Path) -> List[Dict[str, Any]]:
    """Quick access to file operations"""
    retrieval = ConversationRetrieval()
    entries = retrieval.load_conversation(file_path)
    return retrieval.get_file_operations(entries)
