#!/usr/bin/env python3
"""
ConversationFinder - Simple project-specific conversation discovery
Finds Claude Code conversations for the current project using filesystem scanning.
"""

import logging
from pathlib import Path
from datetime import datetime, date
from typing import List, Optional
import re

logger = logging.getLogger(__name__)


class ConversationFinder:
    """Simple filesystem-based conversation discovery for current project"""
    
    def __init__(self, project_root: Path = None):
        self.project_root = project_root or self._find_git_root()
        self.conversation_folder = self._get_claude_conversation_folder()
        
    def _find_git_root(self) -> Path:
        """Find git project root by looking for .git directory"""
        current = Path.cwd()
        for parent in [current] + list(current.parents):
            if (parent / '.git').exists():
                return parent
        return current
    
    def _get_claude_conversation_folder(self) -> Path:
        """Get Claude projects folder (searches all projects, not just current)"""
        # Return the base projects folder to search all projects
        claude_folder = Path.home() / '.claude' / 'projects'

        logger.debug(f"Claude projects folder: {claude_folder}")

        return claude_folder

    def _find_project_folder_by_path(self, project_path: Path) -> Optional[Path]:
        """Find Claude project folder that corresponds to a git project path

        Claude stores projects as: ~/.claude/projects/<hash>/
        We need to find which hash matches our project path.

        Args:
            project_path: Absolute path to git project root

        Returns:
            Path to Claude project folder, or None if not found
        """
        claude_projects_dir = Path.home() / '.claude' / 'projects'

        if not claude_projects_dir.exists():
            logger.warning(f"Claude projects directory not found: {claude_projects_dir}")
            return None

        project_path = project_path.resolve()

        # Check each Claude project folder for matching path
        for project_folder in claude_projects_dir.iterdir():
            if not project_folder.is_dir():
                continue

            # Look for project.json which contains the project path
            project_json = project_folder / 'project.json'
            if project_json.exists():
                try:
                    import json
                    with open(project_json, 'r') as f:
                        data = json.load(f)
                        stored_path = Path(data.get('path', '')).resolve()
                        if stored_path == project_path:
                            logger.debug(f"Found Claude project folder: {project_folder.name}")
                            return project_folder
                except Exception as e:
                    logger.debug(f"Error reading {project_json}: {e}")
                    continue

        # Fallback: Match by converting folder name to path
        # Claude folders are named: -home-user-path-to-project → /home/user/path/to/project
        for project_folder in claude_projects_dir.iterdir():
            if not project_folder.is_dir():
                continue

            # Convert folder name to path
            folder_name = project_folder.name
            if folder_name.startswith('-'):
                # Convert: -home-user-projects-foo → /home/user/projects/foo
                reconstructed_path = Path('/' + folder_name[1:].replace('-', '/'))

                if reconstructed_path == project_path:
                    logger.debug(f"Found Claude project folder by path reconstruction: {project_folder.name}")
                    return project_folder

        return None
    
    def list_all(self, project_filter: Optional[Path] = None, folder_path: Optional[Path] = None) -> List[Path]:
        """List conversation files, optionally filtered by project or custom folder

        Args:
            project_filter: If provided, only return conversations from this project's git root
            folder_path: If provided, search this custom folder instead of Claude projects

        Returns:
            List of conversation file paths, sorted by modification time (newest first)
        """
        conversations = []

        # Custom folder search (highest priority)
        if folder_path:
            folder_path = Path(folder_path)
            if not folder_path.exists():
                logger.warning(f"Custom folder not found: {folder_path}")
                return []

            # Search for JSONL files in custom folder
            for file_path in folder_path.rglob("*.jsonl"):
                if file_path.is_file() and file_path.stat().st_size > 0:
                    conversations.append(file_path)

            logger.info(f"Found {len(conversations)} conversations in custom folder: {folder_path}")

        # Project-specific search
        elif project_filter:
            project_filter = Path(project_filter).resolve()

            # Find the Claude project folder that matches this git root
            project_folder = self._find_project_folder_by_path(project_filter)
            if not project_folder:
                logger.warning(f"No Claude project folder found for: {project_filter}")
                return []

            # Search only this project's conversations
            for file_path in project_folder.glob("*.jsonl"):
                if file_path.is_file() and file_path.stat().st_size > 0:
                    conversations.append(file_path)

            logger.info(f"Found {len(conversations)} conversations for project: {project_filter.name}")

        # Global search (default)
        else:
            if not self.conversation_folder.exists():
                logger.warning(f"Claude conversation folder not found: {self.conversation_folder}")
                return []

            # Search all project folders
            for project_folder in self.conversation_folder.iterdir():
                if not project_folder.is_dir():
                    continue

                # Look for JSONL files in each project
                for file_path in project_folder.glob("*.jsonl"):
                    if file_path.is_file() and file_path.stat().st_size > 0:
                        conversations.append(file_path)

            logger.info(f"Found {len(conversations)} conversations across all projects")

        # Sort by modification time (newest first)
        conversations.sort(key=lambda f: f.stat().st_mtime, reverse=True)

        return conversations

    def find_by_session_id(self, session_id: str, search_globally: bool = True) -> Optional[Path]:
        """Find conversation by session ID (filename matching)

        Args:
            session_id: Session ID to search for (full or partial)
            search_globally: If True, search all Claude projects when not found locally

        Returns:
            Path to conversation file, or None if not found
        """
        # First try local project folder
        if self.conversation_folder.exists():
            # Try exact match first
            exact_file = self.conversation_folder / f"{session_id}.jsonl"
            if exact_file.exists():
                return exact_file

            # Try partial match (8+ characters)
            if len(session_id) >= 8:
                for file_path in self.conversation_folder.glob("*.jsonl"):
                    if file_path.stem.startswith(session_id):
                        return file_path

        # If not found locally and global search enabled, search all projects
        if search_globally:
            logger.info(f"Session '{session_id}' not found in local project, searching globally...")
            return self._search_all_projects(session_id)

        return None

    def _search_all_projects(self, session_id: str) -> Optional[Path]:
        """Search for session ID across all Claude project folders

        Args:
            session_id: Session ID to search for (full or partial)

        Returns:
            Path to conversation file, or None if not found
        """
        claude_projects_dir = Path.home() / '.claude' / 'projects'

        if not claude_projects_dir.exists():
            logger.warning(f"Claude projects directory not found: {claude_projects_dir}")
            return None

        # Search all project folders
        for project_folder in claude_projects_dir.iterdir():
            if not project_folder.is_dir():
                continue

            # Try exact match
            exact_file = project_folder / f"{session_id}.jsonl"
            if exact_file.exists():
                logger.info(f"Found session in project: {project_folder.name}")
                return exact_file

            # Try partial match (8+ characters)
            if len(session_id) >= 8:
                for file_path in project_folder.glob("*.jsonl"):
                    if file_path.stem.startswith(session_id):
                        logger.info(f"Found session in project: {project_folder.name}")
                        return file_path

        logger.warning(f"Session '{session_id}' not found in any project")
        return None
    
    def find_by_marker(self, marker: str) -> List[Path]:
        """Find conversations containing specific content markers"""
        matching_conversations = []
        
        for conversation_file in self.list_all():
            try:
                with open(conversation_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if marker in content:
                        matching_conversations.append(conversation_file)
                        logger.debug(f"Found marker '{marker}' in {conversation_file.name}")
            except Exception as e:
                logger.warning(f"Error reading {conversation_file}: {e}")
                continue
        
        logger.info(f"Found {len(matching_conversations)} conversations with marker '{marker}'")
        return matching_conversations
    
    def find_by_date_range(self, start: date, end: date) -> List[Path]:
        """Find conversations within date range using file modification time"""
        start_timestamp = datetime.combine(start, datetime.min.time()).timestamp()
        end_timestamp = datetime.combine(end, datetime.max.time()).timestamp()
        
        matching_conversations = []
        
        for conversation_file in self.list_all():
            file_mtime = conversation_file.stat().st_mtime
            if start_timestamp <= file_mtime <= end_timestamp:
                matching_conversations.append(conversation_file)
        
        logger.info(f"Found {len(matching_conversations)} conversations between {start} and {end}")
        return matching_conversations
    
    def find_by_date(self, target_date: date) -> List[Path]:
        """Find conversations from a specific date"""
        return self.find_by_date_range(target_date, target_date)
    
    def get_conversation_info(self, conversation_file: Path) -> dict:
        """Get basic info about a conversation file"""
        if not conversation_file.exists():
            return {}
        
        stat = conversation_file.stat()
        session_id = conversation_file.stem
        
        return {
            'session_id': session_id,
            'file_path': str(conversation_file),
            'file_size': stat.st_size,
            'modified_time': datetime.fromtimestamp(stat.st_mtime),
            'created_time': datetime.fromtimestamp(stat.st_ctime)
        }
    
    def list_with_info(self, count: int = None) -> List[dict]:
        """List conversations with basic metadata"""
        conversations = self.list_all()
        if count:
            conversations = conversations[:count]
        
        return [self.get_conversation_info(conv) for conv in conversations]


# Convenience functions
def find_conversations_for_project(project_root: Path = None) -> List[Path]:
    """Quick function to find all conversations for a project"""
    finder = ConversationFinder(project_root)
    return finder.list_all()

def find_conversation_by_marker(marker: str, project_root: Path = None) -> List[Path]:
    """Quick function to find conversations by content marker"""
    finder = ConversationFinder(project_root)
    return finder.find_by_marker(marker)
