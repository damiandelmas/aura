"""SQLite implementation of VectorStore protocol

Wraps the existing SQLiteStore class to implement the unified VectorStore interface.
Enables backend-agnostic code while maintaining all SQLite-specific functionality.

EPIC 4/Review Pass 2: Semantic search via sqlite-vec + sentence-transformers.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional, TYPE_CHECKING
import logging

from .protocol import SearchResult, StorageError
from .sqlite import SQLiteStore

if TYPE_CHECKING:
    from ..infrastructure.embedder import Embedder
    from .vectors import VectorStorage

logger = logging.getLogger(__name__)


class SQLiteVectorStore:
    """SQLite backend implementing VectorStore protocol

    Features:
    - Fast metadata-only queries (< 10ms for 10k chunks)
    - Full discovery primitives (siblings, genealogy, temporal)
    - Semantic vector search via sqlite-vec (Tier 3)
    - Graceful degradation when vectors unavailable

    Performance:
    - Metadata search: < 10ms
    - Semantic search: ~50-100ms (KNN query)
    - Index 10k chunks: ~2 seconds
    """

    def __init__(
        self,
        project_root: Path,
        enable_vectors: bool = False,
        embedder: Optional['Embedder'] = None,
        vector_storage: Optional['VectorStorage'] = None,
    ):
        """Initialize SQLite backend

        Args:
            project_root: Project root directory (creates .imem/metadata.db)
            enable_vectors: If True, enable vector similarity search
            embedder: Embedder for generating query embeddings (Tier 3)
            vector_storage: VectorStorage for KNN queries (Tier 3)
        """
        self.store = SQLiteStore(project_root)
        self.enable_vectors = enable_vectors
        self._embedder = embedder
        self._vector_storage = vector_storage

        # Log vector capability status
        if embedder and vector_storage:
            if embedder.is_available and vector_storage.is_available:
                logger.info("SQLiteVectorStore: Semantic search enabled (Tier 3)")
            else:
                logger.info("SQLiteVectorStore: Vector infrastructure available but not ready")
        elif enable_vectors:
            logger.warning(
                "enable_vectors=True but embedder/vector_storage not provided. "
                "Semantic search will fall back to text search."
            )

    def upsert(self, chunks: List[Dict[str, Any]]) -> None:
        """Insert or update chunks with metadata

        Args:
            chunks: List of chunk dictionaries (see VectorStore protocol)

        Raises:
            StorageError: If upsert fails
        """
        try:
            self.store.upsert_chunks(chunks)
        except Exception as e:
            raise StorageError(f"Failed to upsert chunks to SQLite: {e}") from e

    def search(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        mode: str = 'semantic'
    ) -> List[SearchResult]:
        """Search for chunks by metadata or vector similarity

        SQLite search strategy:
        1. mode='metadata': Pure metadata + text substring filters (< 10ms)
        2. mode='semantic' AND vector infrastructure available:
           Semantic KNN search via sqlite-vec (~50-100ms)
        3. Graceful fallback to text search if vectors unavailable

        Args:
            query: Search query text
            limit: Maximum number of results
            filters: Metadata filters (phase, section_type, file_path, etc.)
            mode: Search mode - 'semantic' (vector KNN) or 'metadata' (text/SQL)

        Returns:
            List of SearchResult objects ordered by relevance/similarity
        """
        if filters is None:
            filters = {}

        # Attempt semantic search if requested and available
        if mode == 'semantic' and query and query.strip():
            semantic_results = self._semantic_search(query, limit, filters)
            if semantic_results is not None:
                return semantic_results
            # Fall through to text search if semantic search not available

        # Text/metadata search (fallback or explicit)
        return self._text_search(query, limit, filters)

    def _semantic_search(
        self,
        query: str,
        limit: int,
        filters: Dict[str, Any]
    ) -> Optional[List[SearchResult]]:
        """Semantic vector similarity search via sqlite-vec

        Returns None if vector infrastructure unavailable (graceful degradation).
        """
        # Check vector infrastructure availability
        if not self._embedder or not self._vector_storage:
            return None
        if not self._embedder.is_available or not self._vector_storage.is_available:
            return None

        try:
            # 1. Embed the query
            query_embedding = self._embedder.embed_single(query)

            # 2. Build vector filters from metadata filters
            from .vectors import VectorFilters
            vector_filters = VectorFilters(
                phase=filters.get('phase'),
                section_type=filters.get('section_type'),
            )

            # 3. KNN query
            # Note: threshold=0.0 returns all k neighbors, let ranking handle filtering
            neighbors = self._vector_storage.query_knn(
                embedding=query_embedding,
                k=limit,
                threshold=0.0,  # No threshold - return all k, ranking handles quality
                filters=vector_filters,
            )

            if not neighbors:
                logger.debug(f"Semantic search returned 0 results for '{query[:50]}...'")
                return None  # Fall back to text search

            # 4. Fetch full chunk data for neighbors
            neighbor_ids = [n.chunk_id for n in neighbors]
            similarity_map = {n.chunk_id: n.similarity for n in neighbors}

            # Get chunks by IDs
            results = self.get_by_ids(neighbor_ids)

            # Update scores with similarity
            for result in results:
                result.score = similarity_map.get(result.id, 0.5)

            # Sort by similarity (highest first)
            results.sort(key=lambda r: r.score, reverse=True)

            logger.info(f"search.semantic: k={len(results)} query='{query[:50]}' filters={filters}")
            return results

        except Exception as e:
            logger.warning(f"Semantic search failed, falling back to text: {e}")
            return None

    def _text_search(
        self,
        query: str,
        limit: int,
        filters: Dict[str, Any]
    ) -> List[SearchResult]:
        """Text substring + metadata search (fallback)"""
        # Add text query to filters if provided
        if query and query.strip():
            filters['text'] = query

        try:
            # Query SQLite store
            raw_results = self.store.query(filters=filters, limit=limit)

            # Convert to SearchResult format
            results = []
            for chunk in raw_results:
                results.append(SearchResult(
                    id=chunk['id'],
                    content=chunk.get('content', ''),
                    score=1.0,  # Text search doesn't have similarity scores
                    metadata={
                        'file_path': chunk.get('file_path'),
                        'phase': chunk.get('phase'),
                        'section_type': chunk.get('section_type'),
                        'section_name': chunk.get('section_name'),
                        'timestamp': chunk.get('timestamp'),
                        'session_id': chunk.get('session_id'),
                        # EPIC 0: Enrichment fields
                        'validity': chunk.get('validity'),
                        'centrality': chunk.get('centrality'),
                        'rank': chunk.get('rank'),
                        'git_status': chunk.get('git_status'),
                        'commit_sha': chunk.get('commit_sha'),
                        **chunk.get('metadata', {})
                    }
                ))

            return results

        except Exception as e:
            raise StorageError(f"SQLite search failed: {e}") from e

    def get_by_ids(self, ids: List[str]) -> List[SearchResult]:
        """Retrieve chunks by their IDs (O(n) with single SQL query)

        Args:
            ids: List of chunk IDs

        Returns:
            List of SearchResult objects (missing IDs silently skipped)
        """
        if not ids:
            return []

        # Single SQL query with WHERE IN clause (O(n) instead of O(n²))
        import json

        placeholders = ','.join('?' * len(ids))
        query = f"""
            SELECT
                id, content, file_path, phase, section_type,
                section_name, timestamp, session_id, metadata,
                validity, centrality, rank, git_status, commit_sha
            FROM chunks
            WHERE id IN ({placeholders})
        """

        # Access underlying SQLite connection
        conn = self.store.conn
        cursor = conn.execute(query, ids)
        rows = cursor.fetchall()

        # Convert to SearchResult objects
        results = []
        for row in rows:
            results.append(SearchResult(
                id=row['id'],
                content=row['content'] or '',
                score=1.0,
                metadata={
                    'file_path': row['file_path'],
                    'phase': row['phase'],
                    'section_type': row['section_type'],
                    'section_name': row['section_name'],
                    'timestamp': row['timestamp'],
                    'session_id': row['session_id'],
                    # EPIC 0: Enrichment fields
                    'validity': row['validity'],
                    'centrality': row['centrality'],
                    'rank': row['rank'],
                    'git_status': row['git_status'],
                    'commit_sha': row['commit_sha'],
                    **json.loads(row['metadata'] or '{}')
                }
            ))

        return results

    # Discovery: Query SQL directly when needed. Don't wrap until usage patterns emerge.
    # Examples:
    #   SELECT * FROM chunks WHERE file_path = ?  -- same document
    #   SELECT * FROM chunks WHERE session_id = ? -- same session
    #   SELECT * FROM chunks WHERE timestamp BETWEEN ? AND ? -- time window

    def get_stats(self) -> Dict[str, Any]:
        """Get storage statistics

        Returns:
            Dictionary with indexing stats (total_chunks, by_phase, etc.)
        """
        try:
            return self.store.get_stats()
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {'error': str(e)}

    def collection_exists(self, name: str) -> bool:
        """Check if collection exists

        Note: SQLite backend uses single database, so this always returns True
              if any chunks exist. For proper collection support, would need
              collection_name column in schema.

        Args:
            name: Collection name (ignored)

        Returns:
            True if database exists and has chunks
        """
        try:
            stats = self.store.get_stats()
            return stats.get('total_chunks', 0) > 0
        except Exception:
            return False

    def delete_collection(self, name: str) -> None:
        """Delete collection

        Note: SQLite backend uses single database, so this clears ALL chunks.
              For proper collection support, would need collection_name column.

        Args:
            name: Collection name (ignored - clears all)

        Raises:
            StorageError: If deletion fails
        """
        try:
            logger.warning(
                f"SQLite backend doesn't support collections. "
                f"delete_collection('{name}') will clear ALL chunks."
            )
            self.store.clear_all()
        except Exception as e:
            raise StorageError(f"Failed to delete collection: {e}") from e

    def close(self):
        """Close database connection"""
        self.store.close()

    def __enter__(self):
        """Context manager support"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close connection on context exit"""
        self.close()
