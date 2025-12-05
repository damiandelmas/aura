"""Infrastructure domain - Shared resources for domain orchestrators

Provides:
- GitInterface: Abstract interface for git repository access
- SubprocessGitInterface: Real git implementation with caching
- NoOpGitInterface: Graceful degradation when no git repo
- create_git_interface: Factory function to create appropriate interface
- Embedder: Abstract interface for embedding operations
- LocalEmbedder: sentence-transformers based embedder
- NoOpEmbedder: Graceful degradation when no embedder available
- create_embedder: Factory function to create appropriate embedder
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

from .embedder import (
    Embedder,
    LocalEmbedder,
    NoOpEmbedder,
    EmbedderConfig,
    create_embedder,
)

__all__ = [
    # Git
    'GitInterface',
    'SubprocessGitInterface',
    'NoOpGitInterface',
    'create_git_interface',
    'Commit',
    'Match',
    'BlobNote',
    'GitResult',
    # Embedder (EPIC 4)
    'Embedder',
    'LocalEmbedder',
    'NoOpEmbedder',
    'EmbedderConfig',
    'create_embedder',
]
