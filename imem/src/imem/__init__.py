"""
IMEM - Knowledge compiler for AI agent memories

SQLite-first architecture: All data lives in SQLite.
Future: HNSW vectors via sqlite-vss extension.
"""

from .registry import SimpleRegistry
from .storage import VectorStore, create_store

__all__ = ['SimpleRegistry', 'VectorStore', 'create_store']
