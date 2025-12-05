"""Router - Composition root for IMEM domains

Router is the top-level entry point that wires together all IMEM domains.
It owns shared infrastructure (database, git access, configuration) and
injects these into domain orchestrators.

Two primary flows:
- index(): COMPILE → STORAGE → MANAGE
- query(): RETRIEVE → STRUCTURE

EPIC 0 establishes the wiring with NoOp plugins.
EPIC 4 adds vector infrastructure (Tier 3).
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
import logging

from .context import Infrastructure, IndexContext, QueryContext
from .infrastructure.git import GitInterface, NoOpGitInterface, create_git_interface
from .infrastructure.embedder import Embedder, create_embedder
from .storage.sqlite import SQLiteStore
from .storage.vectors import VectorStorage, create_vector_storage
from .manage import ManageOrchestrator, create_manage_orchestrator
from .structure import StructureOrchestrator, create_structure_orchestrator
from .retrieve import compose as retrieve_compose

logger = logging.getLogger(__name__)


class Router:
    """Composition root — coordinates domain orchestrators

    Owns infrastructure (db, git, config) and injects into domains.
    Two flows: index() and query().

    Usage:
        router = create_router(project_root)
        chunks = router.index(files)
        results = router.query(config)
    """

    def __init__(
        self,
        infrastructure: Infrastructure,
        manage: Optional[ManageOrchestrator] = None,
        structure: Optional[StructureOrchestrator] = None,
    ):
        """Initialize Router with infrastructure and orchestrators

        Args:
            infrastructure: Shared resources (db, git, config)
            manage: ManageOrchestrator (default: NoOp)
            structure: StructureOrchestrator (default: NoOp)
        """
        self.infrastructure = infrastructure
        self.manage = manage or create_manage_orchestrator()
        self.structure = structure or create_structure_orchestrator()

    def index(self, files: List[Path]) -> List[Dict[str, Any]]:
        """Index files: COMPILE → STORAGE → MANAGE

        Args:
            files: List of file paths to index

        Returns:
            List of indexed chunks with enrichment
        """
        from .compile import DocumentIndexer
        from .storage import create_store

        # 1. Get or create store
        store = create_store(project_root=self.infrastructure.db.project_root)

        # 2. Parse files into chunks via DocumentIndexer
        indexer = DocumentIndexer(store=store)

        all_chunks = []
        for file_path in files:
            try:
                # Parse single file
                chunks = indexer._parse_file(file_path)
                all_chunks.extend(chunks)
            except Exception as e:
                logger.warning(f"Failed to parse {file_path}: {e}")

        if not all_chunks:
            logger.info("No chunks parsed from files")
            return []

        # 3. Store chunks
        store.upsert(all_chunks)
        logger.info(f"Stored {len(all_chunks)} chunks")

        # 4. Enrich via MANAGE
        context = IndexContext(
            infrastructure=self.infrastructure,
            all_chunks=all_chunks,
            existing_chunks=[],  # TODO: Load existing chunks for diffing
        )
        self.manage.enrich(all_chunks, context)

        # 5. Update stored chunks with enrichment
        self._update_enriched_chunks(all_chunks)

        return all_chunks

    def index_phase(
        self,
        phase_name: str,
        force: bool = False,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Index a documentation phase

        Delegates to DocumentIndexer.index_phase for backward compatibility.

        Args:
            phase_name: Phase to index (develop, design, etc.)
            force: Clear existing chunks first
            limit: Limit number of documents

        Returns:
            Result dict with indexed count
        """
        from .compile import DocumentIndexer
        from .storage import create_store

        store = create_store(project_root=self.infrastructure.db.project_root)
        indexer = DocumentIndexer(store=store)

        result = indexer.index_phase(
            phase_name=phase_name,
            force=force,
            limit=limit,
        )

        # Enrich the indexed chunks
        if result.get('chunks', 0) > 0:
            # Fetch recently indexed chunks
            chunks = store.search(
                query='',
                limit=result.get('chunks', 100),
                filters={'phase': phase_name},
                use_vector=False,
            )

            # Convert SearchResult to dicts
            chunk_dicts = [
                {
                    'id': c.id,
                    'content': c.content,
                    **c.metadata
                }
                for c in chunks
            ]

            context = IndexContext(
                infrastructure=self.infrastructure,
                all_chunks=chunk_dicts,
                existing_chunks=[],
            )
            self.manage.enrich(chunk_dicts, context)
            self._update_enriched_chunks(chunk_dicts)

        return result

    def query(self, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Query: RETRIEVE → STRUCTURE

        Args:
            config: Query configuration with:
                - search: {text, mode, filters}
                - discovery: {siblings, temporal, genealogy}
                - ranking: {phases: [...]}

        Returns:
            Presented results
        """
        from .storage import create_store

        # 1. Get store
        store = create_store(project_root=self.infrastructure.db.project_root)

        # 2. Execute RETRIEVE via existing compose()
        query_text = config.get('search', {}).get('text', '')
        result = retrieve_compose(query_text, config, store)
        chunks = result.get('results', [])

        # 3. Apply STRUCTURE (NoOp for EPIC 0)
        context = QueryContext(
            infrastructure=self.infrastructure,
            query=config,
            results=chunks,
            metadata=result.get('metadata', {}),
        )
        presented = self.structure.present(chunks, context)

        return presented

    def _update_enriched_chunks(self, chunks: List[Dict[str, Any]]) -> None:
        """Update stored chunks with enrichment fields"""
        db = self.infrastructure.db
        for chunk in chunks:
            try:
                db.conn.execute('''
                    UPDATE chunks SET
                        commit_sha = ?,
                        validity = ?,
                        git_status = ?,
                        centrality = ?,
                        rank = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (
                    chunk.get('commit_sha'),
                    chunk.get('validity', 0.5),
                    chunk.get('git_status', 'unvalidated'),
                    chunk.get('centrality', 0.5),
                    chunk.get('rank', 0.5),
                    chunk['id'],
                ))
            except Exception as e:
                logger.warning(f"Failed to update chunk {chunk.get('id')}: {e}")
        db.conn.commit()


def create_router(
    project_root: Path,
    git_root: Optional[Path] = None,
    config: Optional[Dict[str, Any]] = None,
    enable_vectors: bool = True,
) -> Router:
    """Factory function to create Router with default configuration

    EPIC 4: Adds vector infrastructure (Tier 3 - graceful degradation).

    Args:
        project_root: Project root directory
        git_root: Git repository root (default: project_root)
        config: Runtime configuration overrides
        enable_vectors: Whether to attempt loading vector infrastructure

    Returns:
        Configured Router instance
    """
    # Create database
    db = SQLiteStore(project_root)

    # Create git interface (real if repo exists, NoOp otherwise)
    effective_git_root = git_root or project_root
    git: GitInterface = create_git_interface(effective_git_root)

    # Build config with project_root for timestamp resolution
    effective_config = config or {}
    effective_config.setdefault('project_root', project_root)

    # Build infrastructure
    infrastructure = Infrastructure(
        db=db,
        git=git,
        config=effective_config,
    )

    # EPIC 4: Create vector infrastructure (Tier 3)
    embedder: Optional[Embedder] = None
    vector_storage: Optional[VectorStorage] = None

    if enable_vectors:
        embedder = create_embedder()
        if embedder.is_available:
            vector_storage = create_vector_storage(db, embedder)
            if vector_storage.is_available:
                logger.info("Vector infrastructure enabled (Tier 3)")
            else:
                logger.info("VectorStorage unavailable, sibling edges disabled")
        else:
            logger.info("Embedder unavailable, vector features disabled")

    # Create orchestrators with EPIC 4 implementations
    manage = create_manage_orchestrator(
        vector_storage=vector_storage,
        embedder=embedder,
    )
    structure = create_structure_orchestrator()

    return Router(
        infrastructure=infrastructure,
        manage=manage,
        structure=structure,
    )


__all__ = [
    'Router',
    'create_router',
]
