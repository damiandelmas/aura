"""Storage backends for metadata and vector indexes

Provides unified VectorStore protocol implemented by multiple backends:
- SQLiteVectorStore: Fast metadata queries, optional vectors
- QdrantVectorStore: Semantic vector search with transformer embeddings

Use create_store() factory for backend-agnostic initialization.
"""

from .protocol import VectorStore, SearchResult, StorageError
from .sqlite import SQLiteStore  # Legacy compatibility
from .sqlite_backend import SQLiteVectorStore
from .qdrant_backend import QdrantVectorStore
from .factory import create_store, create_store_from_config

__all__ = [
    # Protocol
    'VectorStore',
    'SearchResult',
    'StorageError',
    # Backends
    'SQLiteVectorStore',
    'QdrantVectorStore',
    # Factory
    'create_store',
    'create_store_from_config',
    # Legacy
    'SQLiteStore',
]
