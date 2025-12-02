"""Infrastructure domain - Shared resources for domain orchestrators

Provides:
- GitInterface: Access to git repository state
- NoOpGitInterface: Graceful degradation when no git repo
- Infrastructure: Container for db, git, config
"""

from .git import GitInterface, NoOpGitInterface

__all__ = [
    'GitInterface',
    'NoOpGitInterface',
]
