"""Shared context structures for domain orchestrators

IndexContext: Passed through MANAGE during index flow
QueryContext: Passed through RETRIEVE during query flow
Infrastructure: Container for shared resources (db, git, config)
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .infrastructure.git import GitInterface
    from .storage.sqlite import SQLiteStore


@dataclass
class Infrastructure:
    """Shared resources injected into domain orchestrators

    Attributes:
        db: SQLite database connection
        git: Git interface (or NoOpGitInterface)
        config: Runtime configuration
    """
    db: 'SQLiteStore'
    git: 'GitInterface'
    config: Dict[str, Any]


@dataclass
class IndexContext:
    """Context passed through MANAGE during index flow

    Attributes:
        infrastructure: Shared resources
        all_chunks: Chunks being indexed in this run
        existing_chunks: Previously indexed chunks (for diffing)
    """
    infrastructure: Infrastructure
    all_chunks: List[Dict[str, Any]]
    existing_chunks: List[Dict[str, Any]] = field(default_factory=list)

    # Lazy-computed git state (populated on first access if needed)
    _git_state: Optional[Dict[str, Any]] = field(default=None, repr=False)

    @property
    def git_state(self) -> Dict[str, Any]:
        """Lazily compute git state on first access"""
        if self._git_state is None:
            git = self.infrastructure.git
            self._git_state = {
                'head_files': git.get_head_files(),
            }
        return self._git_state


@dataclass
class QueryContext:
    """Context passed through RETRIEVE during query flow

    Attributes:
        infrastructure: Shared resources
        query: Query configuration (filters, limits, etc.)
        results: Accumulated results (mutated by processors)
        metadata: Pipeline metadata (timings, errors, etc.)
    """
    infrastructure: Infrastructure
    query: Dict[str, Any]
    results: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
