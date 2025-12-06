"""Router - Composition root for IMEM domains

Router is the top-level entry point that wires together all IMEM domains.
It owns shared infrastructure (database, git access, configuration) and
injects these into domain orchestrators.

Two primary flows:
- index(): COMPILE → STORAGE → MANAGE (→ PATTERN if enabled)
- query(): RETRIEVE → STRUCTURE

EPIC 0 establishes the wiring with NoOp plugins.
EPIC 4 adds vector infrastructure (Tier 3).
EPIC 5 adds centrality & ranking.
EPIC 6 adds STRUCTURE domain (curate, flip, reword, narrate).
EPIC 7 adds pattern extraction (async, optional).
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
from .retrieve.centrality import CentralityComputer, create_centrality_computer
from .retrieve.processors.ranking import RankingModule

logger = logging.getLogger(__name__)


class Router:
    """Composition root — coordinates domain orchestrators

    Owns infrastructure (db, git, config) and injects into domains.
    Two flows: index() and query().

    EPIC 5: Centrality & Ranking
    - CentralityComputer: Computes importance from graph structure
    - RankingModule: Combines validity × centrality × recency

    Review Pass 2: Semantic search
    - Embedder + VectorStorage enable query-time semantic search

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
        centrality: Optional[CentralityComputer] = None,
        ranking: Optional[RankingModule] = None,
        vector_storage: Optional[VectorStorage] = None,
        embedder: Optional[Embedder] = None,
    ):
        """Initialize Router with infrastructure and orchestrators

        Args:
            infrastructure: Shared resources (db, git, config)
            manage: ManageOrchestrator (default: NoOp)
            structure: StructureOrchestrator (default: NoOp)
            centrality: CentralityComputer (EPIC 5)
            ranking: RankingModule (EPIC 5)
            vector_storage: VectorStorage for sibling density (Tier 3)
            embedder: Embedder for semantic search (Tier 3)
        """
        self.infrastructure = infrastructure
        self.manage = manage or create_manage_orchestrator()
        self.structure = structure or create_structure_orchestrator()
        # EPIC 5: Centrality & Ranking
        self.centrality = centrality
        self.ranking = ranking or RankingModule()
        # Tier 3: Vector infrastructure
        self.vector_storage = vector_storage
        self._embedder = embedder

    def index(
        self,
        files: List[Path],
        extract_patterns: bool = False,
    ) -> List[Dict[str, Any]]:
        """Index files: COMPILE → STORAGE → MANAGE (→ PATTERN if enabled)

        EPIC 7: Optional pattern extraction via extract_patterns flag.

        Args:
            files: List of file paths to index
            extract_patterns: If True, extract patterns after enrichment

        Returns:
            List of indexed chunks with enrichment
        """
        from .compile.parser import parse_markdown_file
        from .storage import create_store

        # 1. Get or create store
        store = create_store(project_root=self.infrastructure.db.project_root)

        # 2. Parse files into chunks via parse_markdown_file
        all_chunks = []
        for file_path in files:
            try:
                # Parse single file (auto-detects phase from path)
                chunks = parse_markdown_file(file_path)
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

        # 5. EPIC 7: Pattern extraction (async, optional)
        if extract_patterns:
            import asyncio
            try:
                asyncio.run(self._extract_patterns(all_chunks))
            except Exception as e:
                logger.warning(f"Pattern extraction failed: {e}")

        # 6. Update stored chunks with enrichment (including pattern_layer)
        self._update_enriched_chunks(all_chunks)

        return all_chunks

    async def _extract_patterns(self, chunks: List[Dict[str, Any]]) -> None:
        """Extract pattern layers for chunks (async)

        EPIC 7: Calls pattern extraction service to abstract implementation.
        Mutates chunks in place to add pattern_layer field.

        Args:
            chunks: Chunks to extract patterns for
        """
        from .compile.pattern import create_pattern_extractor

        extractor = create_pattern_extractor()
        if not extractor.is_available:
            logger.info("Pattern extraction service not available")
            return

        try:
            await extractor.execute_batch(chunks)
        finally:
            await extractor.close()

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

        EPIC 5: Flow includes centrality & ranking.
        Review Pass 2: Semantic search via sqlite-vec.

        search → discovery → centrality → ranking → structure

        Args:
            config: Query configuration with:
                - search: {text, mode, filters}
                  - mode: 'metadata' (text) or 'semantic' (vector)
                - discovery: {siblings, temporal, genealogy}
                - ranking: {phases: [...]}
                - weights: {validity, centrality, recency} (optional)

        Returns:
            Presented results
        """
        from .storage import create_store

        # 1. Get store with vector infrastructure for semantic search
        store = create_store(
            project_root=self.infrastructure.db.project_root,
            embedder=self._embedder,
            vector_storage=self.vector_storage,
        )

        # 2. Execute RETRIEVE via compose() with EPIC 5 centrality & ranking
        query_text = config.get('search', {}).get('text', '')
        result = retrieve_compose(
            query_text,
            config,
            store,
            centrality_computer=self.centrality,
            ranking_module=self.ranking,
            vector_storage=self.vector_storage,
        )
        chunks = result.get('results', [])

        # 3. Apply STRUCTURE
        context = QueryContext(
            infrastructure=self.infrastructure,
            query=config,
            results=chunks,
            metadata=result.get('metadata', {}),
        )
        presented = self.structure.present(chunks, context)

        return presented

    def _update_enriched_chunks(self, chunks: List[Dict[str, Any]]) -> None:
        """Update stored chunks with enrichment fields

        EPIC 7: Now includes pattern_layer field.
        """
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
                        pattern_layer = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (
                    chunk.get('commit_sha'),
                    chunk.get('validity', 0.5),
                    chunk.get('git_status', 'unvalidated'),
                    chunk.get('centrality', 0.5),
                    chunk.get('rank', 0.5),
                    chunk.get('pattern_layer'),  # EPIC 7
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
    EPIC 5: Adds centrality & ranking.

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

    # EPIC 6: Create STRUCTURE with real modules
    structure = create_structure_orchestrator(
        db=db,
        config=effective_config,
    )

    # EPIC 5: Create centrality & ranking
    centrality = create_centrality_computer(
        db=db,
        vector_storage=vector_storage,
    )
    ranking = RankingModule()

    logger.info("EPIC 5: Centrality & Ranking enabled")
    logger.info("EPIC 6: STRUCTURE domain enabled")

    return Router(
        infrastructure=infrastructure,
        manage=manage,
        structure=structure,
        centrality=centrality,
        ranking=ranking,
        vector_storage=vector_storage,
        embedder=embedder,
    )


__all__ = [
    'Router',
    'create_router',
]
