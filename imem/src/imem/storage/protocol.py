"""Storage abstraction protocol for vector + metadata backends

Defines the unified interface that both SQLite and Qdrant backends implement.
This enables backend-agnostic code and easy switching between storage systems.
"""

from typing import Protocol, List, Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class SearchResult:
    """Unified search result format across all backends"""

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
            **self.metadata  # Flatten metadata into result
        }


class VectorStore(Protocol):
    """Backend-agnostic storage interface for vector + metadata operations

    Both SQLite and Qdrant backends implement this protocol, enabling:
    - Transparent backend switching via configuration
    - Backend-agnostic business logic in compile/, manage/, compose/
    - Easy testing with mock implementations

    Design principles:
    - SQLite-first: Metadata queries should work without vectors
    - Optional vectors: use_vector=False for fast metadata-only search
    - Unified results: SearchResult format regardless of backend
    """

    def upsert(self, chunks: List[Dict[str, Any]]) -> None:
        """Insert or update chunks with metadata (and optionally vectors)

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
        use_vector: bool = True
    ) -> List[SearchResult]:
        """Search for chunks by semantic similarity or metadata filters

        Args:
            query: Search query text (used for vector similarity or text search)
            limit: Maximum number of results to return
            filters: Metadata filters to apply:
                - phase: Filter by phase (exact match)
                - section_type: Filter by section type (exact match)
                - file_path: Filter by file path (substring match)
                - timestamp_after: Only chunks after this timestamp
                - timestamp_before: Only chunks before this timestamp
                - session_id: Filter by conversation session
            use_vector: If True, use vector similarity search (requires embeddings).
                       If False, use metadata + text search only (faster for SQLite)

        Returns:
            List of SearchResult objects, ordered by relevance (highest score first)

        Implementation notes:
            - SQLite backend: use_vector=False does pure SQL queries (< 10ms)
            - Qdrant backend: Always uses vectors (use_vector flag has no effect)
            - Empty query + filters: Returns best matches by metadata only
        """
        ...

    def get_by_ids(self, ids: List[str]) -> List[SearchResult]:
        """Retrieve chunks by their IDs

        Used by discovery primitives (siblings, genealogy, temporal) to fetch
        related chunks after identifying their IDs via metadata queries.

        Args:
            ids: List of chunk IDs to retrieve

        Returns:
            List of SearchResult objects (order matches input IDs)
            Missing IDs are silently skipped
        """
        ...

    def get_siblings(
        self,
        chunk_id: str,
        limit: int = 5,
        same_section: bool = True
    ) -> List[SearchResult]:
        """Get sibling chunks (chunks from same document/section)

        Discovery primitive for finding contextually related chunks.

        Args:
            chunk_id: ID of the anchor chunk
            limit: Maximum number of siblings to return
            same_section: If True, only return chunks from same section.
                         If False, return chunks from same file.

        Returns:
            List of sibling chunks, ordered by proximity to anchor
        """
        ...

    def get_genealogy(
        self,
        chunk_id: str,
        depth: int = 2,
        direction: str = 'both'
    ) -> List[SearchResult]:
        """Get genealogy (predecessor/successor chunks in time)

        Discovery primitive for tracing evolution of decisions/patterns.

        Args:
            chunk_id: ID of the anchor chunk
            depth: How many levels of ancestors/descendants to traverse
            direction: 'ancestors', 'descendants', or 'both'

        Returns:
            List of chunks in temporal relationship to anchor
        """
        ...

    def get_temporal(
        self,
        chunk_id: str,
        time_window_days: int = 7,
        limit: int = 10
    ) -> List[SearchResult]:
        """Get temporally related chunks (created around same time)

        Discovery primitive for finding concurrent work and cross-cutting concerns.

        Args:
            chunk_id: ID of the anchor chunk
            time_window_days: Look within ±N days of anchor timestamp
            limit: Maximum number of results

        Returns:
            List of chunks from similar timeframe, ordered by temporal proximity
        """
        ...

    def get_stats(self) -> Dict[str, Any]:
        """Get storage statistics for monitoring and debugging

        Returns:
            Dictionary with stats like:
                - total_chunks: Total number of indexed chunks
                - by_phase: Breakdown by phase
                - by_section_type: Breakdown by section type
                - indexed_files: Number of source files
                - last_updated: Most recent chunk timestamp
        """
        ...

    def collection_exists(self, name: str) -> bool:
        """Check if a collection/table exists

        Args:
            name: Collection or table name

        Returns:
            True if exists, False otherwise
        """
        ...

    def delete_collection(self, name: str) -> None:
        """Delete a collection and all its data

        Args:
            name: Collection or table name to delete

        Raises:
            StorageError: If deletion fails
        """
        ...


class StorageError(Exception):
    """Base exception for storage backend errors"""
    pass
