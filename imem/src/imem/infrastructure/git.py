"""Git interface infrastructure - Access to codebase ground truth

GitInterface is the single point of contact between IMEM and git reality.
When no git repo exists, NoOpGitInterface returns empty/null values
and git-dependent signals gracefully degrade.

EPIC 0: NoOpGitInterface implemented.
EPIC 1: Real SubprocessGitInterface with caching.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Set, List, Dict
import subprocess
import logging
import re

logger = logging.getLogger(__name__)


@dataclass
class Commit:
    """Git commit metadata"""
    sha: str
    timestamp: datetime
    message: str
    files_changed: List[Path] = field(default_factory=list)


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


@dataclass
class GitResult:
    """Result from git subprocess call"""
    success: bool
    stdout: str
    stderr: str


class GitInterface(ABC):
    """Abstract interface for git repository access

    Provides file queries, commit queries, and content search.
    All git-backed validation flows through this interface.
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

    # Cache management
    @abstractmethod
    def refresh(self) -> None:
        """Invalidate caches. Call after git operations that change HEAD."""
        pass


# ============================================================================
# Real Git Interface (EPIC 1)
# ============================================================================

class SubprocessGitInterface(GitInterface):
    """Real git interface using subprocess calls

    Features:
    - Lazy caching of HEAD files and content
    - Subprocess isolation with timeout and error handling
    - Graceful handling of malformed repos
    """

    DEFAULT_TIMEOUT = 30  # seconds

    def __init__(self, root: Path):
        self._root = root
        self._head_files: Optional[Set[Path]] = None
        self._file_cache: Dict[Path, str] = {}

    @property
    def root(self) -> Path:
        return self._root

    # === File Queries ===

    def file_exists(self, path: Path) -> bool:
        """Check if file exists at HEAD"""
        return path in self.get_head_files()

    def get_file_content(self, path: Path, commit: Optional[str] = None) -> Optional[str]:
        """Get file content at HEAD or specific commit"""
        # Use cache for HEAD
        if commit is None and path in self._file_cache:
            return self._file_cache[path]

        ref = commit or "HEAD"
        result = self._run_git(["show", f"{ref}:{path}"])

        if result.success:
            content = result.stdout
            # Cache HEAD content
            if commit is None:
                self._file_cache[path] = content
            return content
        return None

    def get_head_files(self) -> Set[Path]:
        """Get all files tracked at HEAD (cached)"""
        if self._head_files is None:
            result = self._run_git(["ls-tree", "-r", "--name-only", "HEAD"])
            if result.success:
                self._head_files = {Path(f) for f in result.stdout.splitlines() if f}
            else:
                self._head_files = set()
        return self._head_files

    # === Commit Queries ===

    def get_commits_for_file(
        self,
        path: Path,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None
    ) -> List[Commit]:
        """Get commit history for a file within optional time range"""
        args = ["log", "--format=%H|%at|%s", "--follow", "--", str(path)]

        if since:
            args.insert(1, f"--since={since.isoformat()}")
        if until:
            args.insert(1, f"--until={until.isoformat()}")

        result = self._run_git(args)

        if not result.success:
            return []

        commits = []
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            parts = line.split("|", 2)
            if len(parts) >= 3:
                sha, timestamp_str, message = parts
                try:
                    timestamp = datetime.fromtimestamp(int(timestamp_str))
                    commits.append(Commit(
                        sha=sha,
                        timestamp=timestamp,
                        message=message,
                        files_changed=[],  # Not populated for efficiency
                    ))
                except (ValueError, OSError):
                    logger.warning(f"Invalid timestamp in commit: {line}")
        return commits

    def get_commit_timestamp(self, path: Path) -> Optional[datetime]:
        """Get first commit timestamp for file (creation time)"""
        result = self._run_git([
            "log", "--format=%at", "--follow", "--diff-filter=A",
            "--", str(path)
        ])

        if result.success and result.stdout.strip():
            try:
                timestamps = result.stdout.strip().split()
                if timestamps:
                    return datetime.fromtimestamp(int(timestamps[0]))
            except (ValueError, OSError):
                pass
        return None

    # === Content Search ===

    def search_content(self, pattern: str, glob: Optional[str] = None) -> List[Match]:
        """Search file contents for pattern using git grep"""
        args = ["grep", "-n", "-I", pattern]

        if glob:
            args.extend(["--", glob])

        result = self._run_git(args)

        if not result.success:
            return []

        matches = []
        for line in result.stdout.splitlines():
            # Format: path:line:content
            parts = line.split(":", 2)
            if len(parts) >= 3:
                try:
                    matches.append(Match(
                        path=Path(parts[0]),
                        line=int(parts[1]),
                        content=parts[2],
                    ))
                except ValueError:
                    continue
        return matches

    # === Session Provenance ===

    def extract_session_trailer(self, commit_sha: str) -> Optional[str]:
        """Extract Session-ID from commit message trailer"""
        result = self._run_git(["log", "-1", "--format=%B", commit_sha])

        if not result.success:
            return None

        # Look for Session-Id: trailer in commit message
        for line in result.stdout.splitlines():
            match = re.match(r'^Session-Id:\s*(.+)$', line, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    def get_blob_note(self, blob_hash: str) -> Optional[BlobNote]:
        """Get blob note with session:msg provenance"""
        result = self._run_git(["notes", "show", blob_hash])

        if not result.success:
            return None

        # Parse note content: session_id:msg_num:timestamp:path
        note_content = result.stdout.strip()
        if not note_content:
            return None

        parts = note_content.split(":", 3)
        if len(parts) >= 4:
            try:
                return BlobNote(
                    session_id=parts[0],
                    msg_num=int(parts[1]),
                    timestamp=datetime.fromisoformat(parts[2]),
                    path=parts[3],
                )
            except (ValueError, IndexError):
                pass
        return None

    # === Cache Management ===

    def refresh(self) -> None:
        """Invalidate caches"""
        self._head_files = None
        self._file_cache = {}

    # === Internal ===

    def _run_git(self, args: List[str], timeout: int = DEFAULT_TIMEOUT) -> GitResult:
        """Run git command with error handling"""
        try:
            result = subprocess.run(
                ["git", "-C", str(self._root)] + args,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace",  # Handle malformed unicode
            )
            return GitResult(
                success=result.returncode == 0,
                stdout=result.stdout,
                stderr=result.stderr,
            )
        except subprocess.TimeoutExpired:
            logger.warning(f"Git command timed out: {args}")
            return GitResult(success=False, stdout="", stderr="timeout")
        except Exception as e:
            logger.error(f"Git command failed: {args}, {e}")
            return GitResult(success=False, stdout="", stderr=str(e))


# ============================================================================
# NoOp Git Interface (fallback)
# ============================================================================

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

    def refresh(self) -> None:
        pass


# ============================================================================
# Factory Function
# ============================================================================

def create_git_interface(root: Path) -> GitInterface:
    """Create appropriate git interface based on repo existence

    Returns SubprocessGitInterface if valid git repo, else NoOpGitInterface.

    Args:
        root: Directory to check for git repository

    Returns:
        GitInterface implementation
    """
    git_dir = root / ".git"

    # Handle regular repos and worktrees
    if git_dir.exists() or git_dir.is_file():
        try:
            result = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "--git-dir"],
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0:
                logger.debug(f"Git repo detected at {root}")
                return SubprocessGitInterface(root)
        except Exception as e:
            logger.warning(f"Git check failed: {e}")

    logger.info(f"No git repo at {root}, using NoOpGitInterface")
    return NoOpGitInterface(root)
