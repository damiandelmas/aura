"""
IMEM - Knowledge compiler for AI agent memories

SQL-first architecture: SQLite for metadata, Qdrant optional for semantic search.
"""

from .registry import SimpleRegistry
from .storage import VectorStore, create_store

__all__ = ['SimpleRegistry', 'VectorStore', 'create_store']
