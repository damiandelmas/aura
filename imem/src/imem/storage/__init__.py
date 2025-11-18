"""Storage backends for metadata and vector indexes"""
from .sqlite import SQLiteStore

__all__ = ['SQLiteStore']
