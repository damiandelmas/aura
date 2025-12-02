"""Infrastructure domain - Shared resources for domain orchestrators

Provides:
- GitInterface: Abstract interface for git repository access
- SubprocessGitInterface: Real git implementation with caching
- NoOpGitInterface: Graceful degradation when no git repo
- create_git_interface: Factory function to create appropriate interface
"""

from .git import (
    GitInterface,
    SubprocessGitInterface,
    NoOpGitInterface,
    create_git_interface,
    Commit,
    Match,
    BlobNote,
    GitResult,
)

__all__ = [
    'GitInterface',
    'SubprocessGitInterface',
    'NoOpGitInterface',
    'create_git_interface',
    'Commit',
    'Match',
    'BlobNote',
    'GitResult',
]
