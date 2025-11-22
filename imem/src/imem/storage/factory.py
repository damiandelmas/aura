"""Storage backend factory for creating VectorStore instances

SQLite-first storage factory. SQLite is THE store.
Future: HNSW vector support via sqlite-vss extension.
"""

from pathlib import Path
from typing import Optional
import logging

from .protocol import VectorStore
from .sqlite_backend import SQLiteVectorStore

logger = logging.getLogger(__name__)


def create_store(
    project_root: Optional[Path] = None,
    enable_vectors: bool = False,
    **kwargs
) -> VectorStore:
    """Create SQLite storage backend

    Args:
        project_root: Project root directory (required)
        enable_vectors: Enable vector similarity (future: sqlite-vss)
        **kwargs: Reserved for future options

    Returns:
        SQLiteVectorStore instance

    Raises:
        ValueError: If project_root missing

    Example:
        >>> store = create_store(project_root=Path("/path/to/project"))
        >>> results = store.search("query", filters={"phase": "develop"})
    """
    if project_root is None:
        raise ValueError("project_root is required for SQLite store")

    return SQLiteVectorStore(
        project_root=project_root,
        enable_vectors=enable_vectors
    )


def create_store_from_config(config_dict: dict) -> VectorStore:
    """Create storage backend from configuration dictionary

    Args:
        config_dict: Configuration dictionary with keys:
            - project_root: str or Path (required)
            - enable_vectors: bool (optional, default: False)

    Returns:
        VectorStore instance

    Example:
        >>> config = {
        ...     "project_root": "/path/to/project",
        ...     "enable_vectors": False
        ... }
        >>> store = create_store_from_config(config)
    """
    project_root = config_dict.get('project_root')

    if project_root and isinstance(project_root, str):
        project_root = Path(project_root)

    return create_store(
        project_root=project_root,
        enable_vectors=config_dict.get('enable_vectors', False)
    )
