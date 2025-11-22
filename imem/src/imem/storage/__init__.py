"""Storage backends for metadata and vector indexes

SQLite-first storage. All data lives in SQLite.
Future: HNSW vector support via sqlite-vss extension.
"""

from .protocol import VectorStore, SearchResult, StorageError
from .sqlite import SQLiteStore  # Legacy compatibility
from .sqlite_backend import SQLiteVectorStore
from .factory import create_store, create_store_from_config

__all__ = [
    # Protocol
    'VectorStore',
    'SearchResult',
    'StorageError',
    # Backend
    'SQLiteVectorStore',
    # Factory
    'create_store',
    'create_store_from_config',
    # Legacy
    'SQLiteStore',
]
