"""Document compilation and indexing

Extracts the indexing logic from cli.py into a focused domain module.
Handles both phase-based documentation (develop/design/document) and
conversation indexing (JSONL files).
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
import logging

from ..storage import VectorStore, create_store
from ..registry import SimpleRegistry
from ..config import config

logger = logging.getLogger(__name__)


class DocumentIndexer:
    """Compiles markdown documents into searchable chunks

    Handles:
    - Phase-based indexing (.context/develop, .context/design, .context/document)
    - Conversation indexing (Claude Code JSONL files)
    - Collection management (create, force recreate)
    - Pattern vs implementation layer routing
    """

    def __init__(self, store: Optional[VectorStore] = None):
        """Initialize indexer

        Args:
            store: VectorStore backend (if None, will create Qdrant backend)
        """
        self.store = store
        self.registry = SimpleRegistry()

    def index_phase(
        self,
        phase_name: str,
        project_root: Optional[Path] = None,
        force: bool = False,
        limit: Optional[int] = None,
        collection_override: Optional[str] = None
    ) -> Dict[str, Any]:
        """Index a specific phase (develop, design, document) or all context

        Args:
            phase_name: Phase to index ('develop', 'design', 'document', 'context')
            project_root: Project root (if None, uses registry)
            force: If True, recreate collection
            limit: Optional limit for number of documents
            collection_override: Optional collection name override for A/B testing

        Returns:
            Dictionary with:
                - indexed: Number of documents indexed
                - skipped: Number of documents skipped
                - errors: List of error messages
                - collection_name: Collection used

        Raises:
            ValueError: If project not registered or phase directory missing
        """
        # TODO: Remove EnhancedModularIngest dependency - use self.store.upsert() via protocol
        from ..legacy.v2.ingest import EnhancedModularIngest

        # Get project root
        if project_root is None:
            project_root = self.registry.get_project_root()
            if not project_root:
                raise ValueError("Not in a registered project. Run 'imem init' first.")

        # Get or create collection
        if collection_override:
            collection_name = collection_override
        else:
            collections = self.registry.get_project_info(project_root).get('collections')
            if not collections:
                collections = self.registry.register_project(project_root)
            collection_name = collections['context']

        # Determine phases to index
        if phase_name == 'context':
            phases_to_index = ['develop', 'design', 'document']
        else:
            phases_to_index = [phase_name]

        # Initialize ingester (uses Qdrant backend)
        ingester = EnhancedModularIngest()

        # Create collections if needed
        self._ensure_collections_exist(
            ingester,
            collection_name,
            force=force
        )

        # Index each phase
        total_indexed = 0
        errors = []

        for phase in phases_to_index:
            phase_path = project_root / '.context' / phase
            if not phase_path.exists():
                logger.warning(f"Phase directory not found: {phase_path}")
                errors.append(f"Phase directory not found: {phase}")
                continue

            logger.info(f"Indexing {phase} phase...")

            # Find all .md files
            md_files = list(phase_path.rglob("*.md"))
            if limit:
                md_files = md_files[:limit]

            for md_file in md_files:
                try:
                    ingester.ingest_markdown_chunked(
                        md_file,
                        phase=phase,
                        base_collection=collection_name
                    )
                    total_indexed += 1
                except Exception as e:
                    error_msg = f"{md_file.name}: {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)

        # Update registry
        self.registry.update_doc_count(project_root, 'context', total_indexed)

        return {
            'indexed': total_indexed,
            'skipped': 0,
            'errors': errors,
            'collection_name': collection_name
        }

    def index_conversations(
        self,
        project_root: Optional[Path] = None,
        force: bool = False,
        limit: Optional[int] = None,
        collection_override: Optional[str] = None,
        project_filter: Optional[str] = None,
        folder_path: Optional[str] = None,
        session_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Index Claude Code conversations from JSONL files

        Args:
            project_root: Project root (if None, uses registry)
            force: If True, recreate collection
            limit: Optional limit for number of conversations
            collection_override: Optional collection name override
            project_filter: Filter to specific project path
            folder_path: Custom folder to search for conversations
            session_ids: List of specific session IDs to index

        Returns:
            Dictionary with indexing results (indexed, skipped, errors)

        Raises:
            ValueError: If project not registered
        """
        # TODO: Remove EnhancedModularIngest dependency - use self.store.upsert() via protocol
        from ..legacy.v2.ingest import EnhancedModularIngest

        # Get project root
        if project_root is None:
            project_root = self.registry.get_project_root()
            if not project_root:
                raise ValueError("Not in a registered project. Run 'imem init' first.")

        # Get or create collection
        if collection_override:
            collection_name = collection_override
        else:
            collections = self.registry.get_project_info(project_root).get('collections')
            if not collections:
                collections = self.registry.register_project(project_root)
            collection_name = collections['conversations']

        # Initialize ingester
        ingester = EnhancedModularIngest()

        # Create collection if needed
        self._ensure_collections_exist(
            ingester,
            collection_name,
            force=force
        )

        # Index conversations (delegate to ingester)
        try:
            result = ingester.ingest_conversations(
                collection_name=collection_name,
                limit=limit,
                project_filter=project_filter,
                folder_path=folder_path,
                session_ids=session_ids
            )

            # Update registry
            self.registry.update_doc_count(project_root, 'conversations', result.get('indexed', 0))

            return result

        except Exception as e:
            logger.error(f"Failed to index conversations: {e}")
            return {
                'indexed': 0,
                'skipped': 0,
                'errors': [str(e)]
            }

    def _ensure_collections_exist(
        self,
        ingester,
        collection_name: str,
        force: bool = False
    ):
        """Ensure Qdrant collections exist (impl and pattern)

        Args:
            ingester: EnhancedModularIngest instance with client
            collection_name: Base collection name
            force: If True, recreate collections
        """
        from qdrant_client.models import Distance, VectorParams, HnswConfigDiff

        # Create both impl and pattern collections
        impl_collection = f"{collection_name}_impl"
        pattern_collection = f"{collection_name}_pattern"

        for coll_name in [impl_collection, pattern_collection]:
            collection_exists = ingester.client.collection_exists(coll_name)

            if force and collection_exists:
                logger.info(f"Recreating collection {coll_name}...")
                ingester.client.delete_collection(coll_name)
                collection_exists = False

            if not collection_exists:
                logger.info(f"Creating collection {coll_name}...")
                ingester.client.create_collection(
                    collection_name=coll_name,
                    vectors_config={
                        config.default_vector_name: VectorParams(
                            size=config.default_dimensions,
                            distance=Distance.COSINE,
                            hnsw_config=HnswConfigDiff(m=16, ef_construct=100)
                        )
                    }
                )
                logger.info(f"Collection created: {coll_name}")
