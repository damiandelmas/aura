"""Storage backend factory for creating VectorStore instances

Provides a unified entry point for creating storage backends based on
configuration. Supports SQLite (local, fast) and Qdrant (distributed, semantic).
"""

from pathlib import Path
from typing import Optional, Any
import logging

from .protocol import VectorStore
from .sqlite_backend import SQLiteVectorStore
from .qdrant_backend import QdrantVectorStore
from ..config import config

logger = logging.getLogger(__name__)


def create_store(
    backend: str = "sqlite",
    project_root: Optional[Path] = None,
    collection_name: str = "docs_default",
    **kwargs
) -> VectorStore:
    """Create a storage backend instance

    Args:
        backend: Backend type - "sqlite" or "qdrant"
        project_root: Project root directory (required for SQLite)
        collection_name: Collection/database name (used by both backends)
        **kwargs: Backend-specific options:
            SQLite:
                - enable_vectors: bool (default: False) - Enable vector similarity
            Qdrant:
                - client: QdrantClient instance (optional)
                - encoder: SentenceTransformer instance (optional)
                - host: str (default: "localhost")
                - port: int (default: from config)

    Returns:
        VectorStore instance implementing the protocol

    Raises:
        ValueError: If backend is unknown or required params missing

    Examples:
        # SQLite backend (fast metadata queries)
        >>> store = create_store(backend="sqlite", project_root=Path("/path"))
        >>> results = store.search("query", use_vector=False)

        # Qdrant backend (semantic search)
        >>> store = create_store(backend="qdrant", collection_name="my_docs")
        >>> results = store.search("query", use_vector=True)

        # With custom client
        >>> from qdrant_client import QdrantClient
        >>> client = QdrantClient(host="localhost", port=6333)
        >>> store = create_store(backend="qdrant", collection_name="docs", client=client)
    """
    backend = backend.lower()

    if backend == "sqlite":
        if project_root is None:
            raise ValueError("SQLite backend requires project_root parameter")

        return SQLiteVectorStore(
            project_root=project_root,
            enable_vectors=kwargs.get('enable_vectors', False)
        )

    elif backend == "qdrant":
        return QdrantVectorStore(
            collection_name=collection_name,
            client=kwargs.get('client'),
            encoder=kwargs.get('encoder'),
            host=kwargs.get('host', 'localhost'),
            port=kwargs.get('port', config.qdrant_port)
        )

    else:
        raise ValueError(
            f"Unknown backend: {backend}. "
            f"Supported backends: 'sqlite', 'qdrant'"
        )


def create_store_from_config(config_dict: dict) -> VectorStore:
    """Create storage backend from configuration dictionary

    Convenience function for creating stores from config files or dicts.

    Args:
        config_dict: Configuration dictionary with keys:
            - backend: "sqlite" or "qdrant" (required)
            - project_root: str or Path (required for sqlite)
            - collection_name: str (optional, default: "docs_default")
            - ... other backend-specific options

    Returns:
        VectorStore instance

    Example:
        >>> config = {
        ...     "backend": "sqlite",
        ...     "project_root": "/path/to/project",
        ...     "enable_vectors": False
        ... }
        >>> store = create_store_from_config(config)
    """
    backend = config_dict.get('backend', 'sqlite')
    project_root = config_dict.get('project_root')

    if project_root and isinstance(project_root, str):
        project_root = Path(project_root)

    collection_name = config_dict.get('collection_name', 'docs_default')

    # Remove known keys to pass rest as **kwargs
    kwargs = {k: v for k, v in config_dict.items()
              if k not in ('backend', 'project_root', 'collection_name')}

    return create_store(
        backend=backend,
        project_root=project_root,
        collection_name=collection_name,
        **kwargs
    )
