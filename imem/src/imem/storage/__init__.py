"""Storage backends for metadata and vector indexes

SQLite-first storage. All data lives in SQLite.
EPIC 4: HNSW vector support via sqlite-vec extension.
"""

from .protocol import VectorStore, SearchResult, StorageError
from .sqlite import SQLiteStore  # Legacy compatibility
from .sqlite_backend import SQLiteVectorStore
from .factory import create_store, create_store_from_config
from .vectors import (
    VectorStorage,
    SQLiteVecStorage,
    NoOpVectorStorage,
    Neighbor,
    VectorFilters,
    create_vector_storage,
)

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
    # Vector Storage (EPIC 4)
    'VectorStorage',
    'SQLiteVecStorage',
    'NoOpVectorStorage',
    'Neighbor',
    'VectorFilters',
    'create_vector_storage',
]
