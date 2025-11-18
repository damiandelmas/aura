"""CLI Composition Root - Single initialization point for all dependencies

Implements the composition root pattern to manage shared resources:
- Database connection (once, with pragmas)
- Embedder model (once, expensive ~2s)
- Domain controllers (injected with dependencies)

This eliminates per-command initialization overhead and enables shared resource pooling.
"""

import sqlite3
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from ..config import config, IMEMConfig
from ..registry import SimpleRegistry
from ..storage import create_store, VectorStore


@dataclass
class AppState:
    """Shared application state"""
    db: Optional[sqlite3.Connection] = None
    embedder: Optional[any] = None  # SentenceTransformer, lazy-loaded
    sqlite_store: Optional[VectorStore] = None
    qdrant_store: Optional[VectorStore] = None
    project_root: Optional[Path] = None


class IMEMCLI:
    """Composition root for IMEM CLI

    Centralizes dependency initialization and provides controllers
    with properly injected dependencies.
    """

    def __init__(self, config_instance: IMEMConfig = None):
        """Initialize CLI with config

        Args:
            config_instance: Config instance (defaults to global config)
        """
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
        """Get or create database connection with optimal pragmas

        Args:
            db_path: Optional database path (defaults to project .imem/corpus.db)

        Returns:
            Configured SQLite connection
        """
        if self.state.db is None:
            if db_path is None:
                project_root = self.get_project_root()
                if not project_root:
                    raise ValueError("Not in a registered project. Run 'imem init' first.")
                db_path = project_root / '.imem' / 'corpus.db'

            # Create connection with optimal pragmas (ONCE)
            self.state.db = sqlite3.connect(str(db_path))
            self.state.db.row_factory = sqlite3.Row  # Dict-like access

            # Performance pragmas
            self.state.db.execute("PRAGMA journal_mode = WAL")
            self.state.db.execute("PRAGMA synchronous = NORMAL")
            self.state.db.execute("PRAGMA cache_size = -64000")  # 64MB cache
            self.state.db.execute("PRAGMA temp_store = MEMORY")

        return self.state.db

    def get_embedder(self, force_load: bool = False):
        """Get or create embedder model (lazy-loaded, expensive ~2s)

        Args:
            force_load: Force loading even if not needed

        Returns:
            SentenceTransformer model or None if embeddings disabled
        """
        if self.state.embedder is None and (force_load or self._should_load_embedder()):
            from sentence_transformers import SentenceTransformer

            # Load model (expensive, do ONCE)
            model_config = self.config.default_model
            self.state.embedder = SentenceTransformer(
                model_config,
                trust_remote_code=True
            )
            self._embedder_loaded = True

        return self.state.embedder

    def _should_load_embedder(self) -> bool:
        """Determine if embedder should be loaded"""
        # TODO: Add logic to check if command needs embeddings
        # For now, lazy-load on first request
        return False

    def get_sqlite_store(self) -> VectorStore:
        """Get or create SQLite backend store

        Returns:
            SQLite VectorStore implementation
        """
        if self.state.sqlite_store is None:
            project_root = self.get_project_root()
            if not project_root:
                raise ValueError("Not in a registered project. Run 'imem init' first.")

            self.state.sqlite_store = create_store(
                backend='sqlite',
                project_root=project_root
            )

        return self.state.sqlite_store

    def get_qdrant_store(self) -> VectorStore:
        """Get or create Qdrant backend store

        Returns:
            Qdrant VectorStore implementation
        """
        if self.state.qdrant_store is None:
            project_root = self.get_project_root()
            if not project_root:
                raise ValueError("Not in a registered project. Run 'imem init' first.")

            self.state.qdrant_store = create_store(
                backend='qdrant',
                collection_name='docs_default',
                host=self.config.qdrant_host,
                port=self.config.qdrant_port
            )

        return self.state.qdrant_store

    def get_compile_controller(self):
        """Get compile domain controller with injected dependencies

        Returns:
            DocumentIndexer with configured store
        """
        from ..compile import DocumentIndexer

        # Use Qdrant for indexing (existing pattern)
        store = self.get_qdrant_store()
        return DocumentIndexer(store=store)

    def get_manage_controller(self):
        """Get manage domain controller

        Returns:
            Manage controller (introspection, stats)
        """
        # TODO: Create ManageController class
        # For now, return dict of functions
        from .. import manage
        return {
            'introspect': manage.introspect,
            'get_system_and_landscape': manage.get_system_and_landscape,
            'get_concept_topology': manage.get_concept_topology,
            'get_coverage_stats': manage.get_coverage_stats
        }

    def get_compose_controller(self):
        """Get compose domain controller

        Returns:
            Compose orchestrator (retrieval pipeline)
        """
        # TODO: Create ComposeController using processor chain
        from ..compose import compose as compose_pipeline
        return compose_pipeline

    def cleanup(self):
        """Cleanup resources on shutdown"""
        if self.state.db:
            self.state.db.close()
            self.state.db = None


# Global application instance
app = IMEMCLI()
