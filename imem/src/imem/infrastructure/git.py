"""Git interface infrastructure - Access to codebase ground truth

GitInterface is the single point of contact between IMEM and git reality.
When no git repo exists, NoOpGitInterface returns empty/null values
and git-dependent signals gracefully degrade.

EPIC 0: Only NoOpGitInterface implemented.
EPIC 1: Real GitInterface with subprocess git calls.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Set, List


@dataclass
class Commit:
    """Git commit metadata"""
    sha: str
    timestamp: datetime
    message: str
    files_changed: List[Path]


@dataclass
class Match:
    """Content search result"""
    path: Path
    line: int
    content: str


@dataclass
class BlobNote:
    """Git blob note with session provenance"""
    session_id: str
    msg_num: int
    timestamp: datetime
    path: str


class GitInterface(ABC):
    """Abstract interface for git repository access

    Provides file queries, commit queries, and content search.
    All git-backed validation flows through this interface.

    Implementation in EPIC 1.
    """

    @property
    @abstractmethod
    def root(self) -> Path:
        """Repository root path"""
        pass

    # File queries
    @abstractmethod
    def file_exists(self, path: Path) -> bool:
        """Check if file exists at HEAD"""
        pass

    @abstractmethod
    def get_file_content(self, path: Path, commit: Optional[str] = None) -> Optional[str]:
        """Get file content at HEAD or specific commit"""
        pass

    @abstractmethod
    def get_head_files(self) -> Set[Path]:
        """Get all files tracked at HEAD"""
        pass

    # Commit queries
    @abstractmethod
    def get_commits_for_file(
        self,
        path: Path,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None
    ) -> List[Commit]:
        """Get commit history for a file"""
        pass

    @abstractmethod
    def get_commit_timestamp(self, path: Path) -> Optional[datetime]:
        """Get most recent commit timestamp for a file"""
        pass

    # Content search
    @abstractmethod
    def search_content(self, pattern: str, glob: Optional[str] = None) -> List[Match]:
        """Search file contents for pattern"""
        pass

    # Session provenance
    @abstractmethod
    def extract_session_trailer(self, commit_sha: str) -> Optional[str]:
        """Extract Session-ID from commit message trailer"""
        pass

    @abstractmethod
    def get_blob_note(self, blob_hash: str) -> Optional[BlobNote]:
        """Get blob note with session:msg provenance"""
        pass


class NoOpGitInterface(GitInterface):
    """Fallback when no git repository is available

    All methods return empty/None values.
    Git-dependent signals gracefully degrade with this interface.

    Usage:
        git = NoOpGitInterface()
        git.file_exists(Path("foo.py"))  # Returns False
        git.get_file_content(Path("foo.py"))  # Returns None
    """

    def __init__(self, root: Optional[Path] = None):
        """Initialize NoOp interface

        Args:
            root: Optional root path (stored but not used)
        """
        self._root = root or Path(".")

    @property
    def root(self) -> Path:
        return self._root

    def file_exists(self, path: Path) -> bool:
        return False

    def get_file_content(self, path: Path, commit: Optional[str] = None) -> Optional[str]:
        return None

    def get_head_files(self) -> Set[Path]:
        return set()

    def get_commits_for_file(
        self,
        path: Path,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None
    ) -> List[Commit]:
        return []

    def get_commit_timestamp(self, path: Path) -> Optional[datetime]:
        return None

    def search_content(self, pattern: str, glob: Optional[str] = None) -> List[Match]:
        return []

    def extract_session_trailer(self, commit_sha: str) -> Optional[str]:
        return None

    def get_blob_note(self, blob_hash: str) -> Optional[BlobNote]:
        return None
