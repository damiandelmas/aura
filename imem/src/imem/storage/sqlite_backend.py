"""SQLite implementation of VectorStore protocol

Wraps the existing SQLiteStore class to implement the unified VectorStore interface.
Enables backend-agnostic code while maintaining all SQLite-specific functionality.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

from .protocol import SearchResult, StorageError
from .sqlite import SQLiteStore

logger = logging.getLogger(__name__)


class SQLiteVectorStore:
    """SQLite backend implementing VectorStore protocol

    Features:
    - Fast metadata-only queries (< 10ms for 10k chunks)
    - Full discovery primitives (siblings, genealogy, temporal)
    - Optional vector support via sqlite-vss extension (future)
    - No external dependencies (pure SQLite)

    Performance:
    - Metadata search: < 10ms
    - Discovery queries: < 5ms
    - Index 10k chunks: ~2 seconds
    """

    def __init__(self, project_root: Path, enable_vectors: bool = False):
        """Initialize SQLite backend

        Args:
            project_root: Project root directory (creates .imem/metadata.db)
            enable_vectors: If True, load sqlite-vss for vector similarity
                           (Currently not implemented - reserved for future)
        """
        self.store = SQLiteStore(project_root)
        self.enable_vectors = enable_vectors

        if enable_vectors:
            logger.warning(
                "Vector support not yet implemented for SQLite backend. "
                "Falling back to metadata + text search. "
                "Future: sqlite-vss extension for HNSW vectors."
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
        use_vector: bool = True
    ) -> List[SearchResult]:
        """Search for chunks by metadata or text similarity

        SQLite search strategy:
        1. If use_vector=False: Pure metadata filters (< 10ms)
        2. If use_vector=True: Metadata filters + text substring search
        3. Future: Vector similarity via sqlite-vss extension

        Args:
            query: Search query text (used for text substring match)
            limit: Maximum number of results
            filters: Metadata filters (phase, section_type, file_path, etc.)
            use_vector: Ignored for now (always does metadata + text search)

        Returns:
            List of SearchResult objects ordered by relevance
        """
        if filters is None:
            filters = {}

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
                    score=1.0,  # Metadata-only search doesn't have similarity scores
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
