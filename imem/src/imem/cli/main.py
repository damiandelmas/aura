"""CLI Composition Root - Single initialization point for all dependencies

SQLite-first composition root:
- Database connection (once, with pragmas)
- Embedder model (once, expensive ~2s)
- Domain controllers (injected with dependencies)
"""

import sqlite3
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from ..config import config, IMEMConfig
from ..registry import SimpleRegistry
from ..storage import create_store, VectorStore, SQLiteVectorStore


@dataclass
class AppState:
    """Shared application state"""
    db: Optional[sqlite3.Connection] = None
    embedder: Optional[any] = None  # SentenceTransformer, lazy-loaded
    store: Optional[VectorStore] = None
    project_root: Optional[Path] = None


class IMEMCLI:
    """Composition root for IMEM CLI

    SQLite-first: All storage uses SQLite. No external services.
    """

    def __init__(self, config_instance: IMEMConfig = None):
        """Initialize CLI with config"""
        self.config = config_instance or config
        self.registry = SimpleRegistry()
        self.state = AppState()
        self._embedder_loaded = False

    def get_project_root(self) -> Optional[Path]:
        """Get current project root from registry"""
        if not self.state.project_root:
            self.state.project_root = self.registry.get_project_root()
        return self.state.project_root

    def get_db(self, db_path: Optional[Path] = None) -> sqlite3.Connection:
        """Get or create database connection with optimal pragmas"""
        if self.state.db is None:
            if db_path is None:
                project_root = self.get_project_root()
                if not project_root:
                    raise ValueError("Not in a registered project. Run 'imem init' first.")
                db_path = project_root / '.imem' / 'corpus.db'

            self.state.db = sqlite3.connect(str(db_path))
            self.state.db.row_factory = sqlite3.Row

            # Performance pragmas
            self.state.db.execute("PRAGMA journal_mode = WAL")
            self.state.db.execute("PRAGMA synchronous = NORMAL")
            self.state.db.execute("PRAGMA cache_size = -64000")
            self.state.db.execute("PRAGMA temp_store = MEMORY")

        return self.state.db

    def get_embedder(self, force_load: bool = False):
        """Get or create embedder model (lazy-loaded, expensive ~2s)"""
        if self.state.embedder is None and (force_load or self._should_load_embedder()):
            from sentence_transformers import SentenceTransformer

            model_config = self.config.default_model
            self.state.embedder = SentenceTransformer(
                model_config,
                trust_remote_code=True
            )
            self._embedder_loaded = True

        return self.state.embedder

    def _should_load_embedder(self) -> bool:
        """Determine if embedder should be loaded"""
        return False

    def get_store(self) -> VectorStore:
        """Get or create SQLite store

        Returns:
            SQLiteVectorStore implementation
        """
        if self.state.store is None:
            project_root = self.get_project_root()
            if not project_root:
                raise ValueError("Not in a registered project. Run 'imem init' first.")

            self.state.store = create_store(project_root=project_root)

        return self.state.store

    # Alias for backward compatibility
    def get_sqlite_store(self) -> VectorStore:
        """Alias for get_store()"""
        return self.get_store()

    def get_compile_controller(self):
        """Get compile domain controller with injected dependencies

        Returns:
            DocumentIndexer with SQLite store
        """
        from ..compile import DocumentIndexer

        store = self.get_store()
        return DocumentIndexer(store=store)

    def get_manage_controller(self):
        """Get manage domain controller

        Returns:
            Manage controller (introspection, stats)
        """
        from ..manage import introspect, get_coverage_stats
        return {
            'introspect': introspect,
            'get_coverage_stats': get_coverage_stats
        }

    def get_compose_controller(self):
        """Get compose domain controller

        Returns:
            Compose orchestrator (retrieval pipeline)
        """
        from ..compose import compose as compose_pipeline
        return compose_pipeline

    def cleanup(self):
        """Cleanup resources on shutdown"""
        if self.state.db:
            self.state.db.close()
            self.state.db = None


# Global application instance
app = IMEMCLI()
