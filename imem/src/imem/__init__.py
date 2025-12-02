"""
IMEM - Knowledge compiler for AI agent memories

EPIC 0: Router-based architecture.
Router is the composition root that coordinates five domains:
COMPILE, STORAGE, MANAGE, RETRIEVE, STRUCTURE.

SQLite-first: All data lives in SQLite.
Future: HNSW vectors via sqlite-vec extension.
"""

from .router import Router, create_router
from .registry import SimpleRegistry
from .storage import VectorStore, create_store
from .context import IndexContext, QueryContext, Infrastructure

__all__ = [
    # EPIC 0: Router
    'Router',
    'create_router',
    # Context structures
    'IndexContext',
    'QueryContext',
    'Infrastructure',
    # Storage
    'VectorStore',
    'create_store',
    # Legacy
    'SimpleRegistry',
]
