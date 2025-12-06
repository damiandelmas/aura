"""Storage abstraction protocol for metadata + vector backends

SQLite-first: Defines the unified interface for storage operations.
Future: HNSW vector support via sqlite-vss extension.
"""

from typing import Protocol, List, Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class SearchResult:
    """Unified search result format"""

    id: str
    """Unique chunk identifier"""

    content: str
    """Chunk text content"""

    score: float
    """Relevance score (1.0 for metadata-only, 0.0-1.0 for vector similarity)"""

    metadata: Dict[str, Any] = field(default_factory=dict)
    """Chunk metadata (phase, section_type, file_path, etc.)"""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'id': self.id,
            'content': self.content,
            'score': self.score,
            **self.metadata
        }


class VectorStore(Protocol):
    """Backend-agnostic storage interface for metadata + vector operations

    Design principles:
    - SQLite-first: All queries use SQLite
    - Optional vectors: use_vector=False for fast metadata-only search (default)
    - Unified results: SearchResult format regardless of backend
    - Discovery: Write SQL directly for complex queries (YAGNI wrappers)
    """

    def upsert(self, chunks: List[Dict[str, Any]]) -> None:
        """Insert or update chunks with metadata

        Args:
            chunks: List of chunk dictionaries containing:
                - id: Unique identifier
                - content: Text content
                - file_path: Source file path
                - phase: 'design', 'designate', 'develop', 'document'
                - section_type: 'Decision', 'Pattern', 'Implementation', etc.
                - section_name: Human-readable section title
                - timestamp: ISO format datetime
                - session_id: Conversation session ID (for JSONL sources)
                - metadata: Additional metadata dict

        Raises:
            StorageError: If upsert fails
        """
        ...

    def search(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        mode: str = 'semantic'
    ) -> List[SearchResult]:
        """Search for chunks by metadata filters or vector similarity

        Args:
            query: Search query text
            limit: Maximum number of results
            filters: Metadata filters:
                - phase: Filter by phase (exact match)
                - section_type: Filter by section type (exact match)
                - file_path: Filter by file path (substring match)
                - timestamp_after: Only chunks after this timestamp
                - timestamp_before: Only chunks before this timestamp
                - session_id: Filter by conversation session
            mode: Search mode:
                - 'semantic': Vector KNN similarity search (~50-100ms)
                - 'metadata': Pure text + SQL filters (< 10ms)

        Returns:
            List of SearchResult objects, ordered by relevance

        Performance:
            - Metadata-only queries: < 10ms for 10k chunks
            - Text search: < 50ms with proper indexes
        """
        ...

    def get_by_ids(self, ids: List[str]) -> List[SearchResult]:
        """Retrieve chunks by their IDs

        Args:
            ids: List of chunk IDs to retrieve

        Returns:
            List of SearchResult objects (missing IDs silently skipped)
        """
        ...

    # Discovery: Query SQL directly when needed. Don't wrap until usage patterns emerge.
    # Examples:
    #   SELECT * FROM chunks WHERE file_path = ?  -- same document
    #   SELECT * FROM chunks WHERE session_id = ? -- same session
    #   SELECT * FROM chunks WHERE timestamp BETWEEN ? AND ? -- time window

    def get_stats(self) -> Dict[str, Any]:
        """Get storage statistics

        Returns:
            Dictionary with stats:
                - total_chunks: Total indexed chunks
                - by_phase: Breakdown by phase
                - by_section_type: Breakdown by section type
                - indexed_files: Number of source files
        """
        ...

    def collection_exists(self, name: str) -> bool:
        """Check if collection/table exists

        Args:
            name: Collection or table name

        Returns:
            True if exists, False otherwise
        """
        ...

    def delete_collection(self, name: str) -> None:
        """Delete collection and all its data

        Args:
            name: Collection or table name

        Raises:
            StorageError: If deletion fails
        """
        ...


class StorageError(Exception):
    """Base exception for storage backend errors"""
    pass
