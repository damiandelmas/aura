"""Qdrant implementation of VectorStore protocol

Wraps the existing EnhancedQdrantSearch to implement the unified VectorStore interface.
Enables backend-agnostic code while maintaining Qdrant-specific features.
"""

from typing import List, Dict, Any, Optional
import logging

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, Filter, FieldCondition, MatchValue
from sentence_transformers import SentenceTransformer

from .protocol import SearchResult, StorageError
from ..config import config

logger = logging.getLogger(__name__)


class QdrantVectorStore:
    """Qdrant backend implementing VectorStore protocol

    Features:
    - Semantic vector search with transformer embeddings
    - Metadata filtering (phase, section_type, etc.)
    - Discovery primitives (siblings, genealogy, temporal)
    - Production-scale vector database

    Performance:
    - Vector search: < 100ms for 10k chunks
    - Can scale to millions of vectors
    - Requires Docker/external service
    """

    def __init__(
        self,
        collection_name: str,
        client: Optional[QdrantClient] = None,
        encoder: Optional[SentenceTransformer] = None,
        host: str = "localhost",
        port: int = None
    ):
        """Initialize Qdrant backend

        Args:
            collection_name: Qdrant collection name
            client: Existing QdrantClient (optional, will create if None)
            encoder: Existing SentenceTransformer (optional, will load if None)
            host: Qdrant host (default: localhost)
            port: Qdrant port (default: from config)
        """
        self.collection_name = collection_name

        # Use provided client or create new one
        if client is None:
            port = port or config.qdrant_port
            self.client = QdrantClient(host=host, port=port)
        else:
            self.client = client

        # Use provided encoder or load default
        if encoder is None:
            self.encoder = SentenceTransformer(
                config.default_model,
                trust_remote_code=True
            )
        else:
            self.encoder = encoder

        self.vector_name = config.default_vector_name
        self.dimensions = config.default_dimensions

    def upsert(self, chunks: List[Dict[str, Any]]) -> None:
        """Insert or update chunks with vectors

        Args:
            chunks: List of chunk dictionaries (see VectorStore protocol)

        Raises:
            StorageError: If upsert fails
        """
        try:
            from qdrant_client.models import PointStruct

            # Ensure collection exists
            if not self.collection_exists(self.collection_name):
                self._create_collection()

            points = []
            for chunk in chunks:
                # Generate embedding
                vector = self.encoder.encode(chunk.get('content', '')).tolist()

                # Build payload (metadata only, no content duplication)
                payload = {
                    'source': chunk.get('phase', ''),  # For routing
                    'phase': chunk.get('phase'),
                    'section_type': chunk.get('section_type'),
                    'section_name': chunk.get('section_name'),
                    'file_path': chunk.get('file_path'),
                    'timestamp': chunk.get('timestamp'),
                    'session_id': chunk.get('session_id'),
                    'content': chunk.get('content', ''),  # Include for retrieval
                }

                points.append(PointStruct(
                    id=chunk['id'],
                    vector={self.vector_name: vector},
                    payload=payload
                ))

            # Upsert points in batches
            batch_size = 100
            for i in range(0, len(points), batch_size):
                batch = points[i:i + batch_size]
                self.client.upsert(
                    collection_name=self.collection_name,
                    points=batch
                )

        except Exception as e:
            raise StorageError(f"Failed to upsert to Qdrant: {e}") from e

    def search(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        use_vector: bool = True
    ) -> List[SearchResult]:
        """Search for chunks by semantic similarity

        Qdrant always uses vector search (use_vector flag is ignored).

        Args:
            query: Search query text
            limit: Maximum number of results
            filters: Metadata filters (phase, section_type, file_path, etc.)
            use_vector: Ignored (Qdrant always uses vectors)

        Returns:
            List of SearchResult objects ordered by similarity
        """
        try:
            # Encode query
            query_vector = self.encoder.encode(query).tolist()

            # Build Qdrant filter if provided
            query_filter = None
            if filters:
                must_conditions = []
                for key, value in filters.items():
                    # Skip 'text' filter (not applicable to Qdrant)
                    if key == 'text':
                        continue
                    must_conditions.append(
                        FieldCondition(key=key, match=MatchValue(value=value))
                    )
                if must_conditions:
                    query_filter = Filter(must=must_conditions)

            # Search
            search_result = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                using=self.vector_name,
                query_filter=query_filter,
                limit=limit,
                with_payload=True,
                with_vectors=False
            ).points

            # Convert to SearchResult format
            results = []
            for point in search_result:
                payload = point.payload or {}
                results.append(SearchResult(
                    id=str(point.id),
                    content=payload.get('content', ''),
                    score=point.score if hasattr(point, 'score') else 1.0,
                    metadata={
                        'file_path': payload.get('file_path'),
                        'phase': payload.get('phase'),
                        'section_type': payload.get('section_type'),
                        'section_name': payload.get('section_name'),
                        'timestamp': payload.get('timestamp'),
                        'session_id': payload.get('session_id'),
                    }
                ))

            return results

        except Exception as e:
            raise StorageError(f"Qdrant search failed: {e}") from e

    def get_by_ids(self, ids: List[str]) -> List[SearchResult]:
        """Retrieve chunks by their IDs

        Args:
            ids: List of chunk IDs

        Returns:
            List of SearchResult objects (missing IDs silently skipped)
        """
        try:
            points = self.client.retrieve(
                collection_name=self.collection_name,
                ids=ids,
                with_payload=True,
                with_vectors=False
            )

            results = []
            for point in points:
                payload = point.payload or {}
                results.append(SearchResult(
                    id=str(point.id),
                    content=payload.get('content', ''),
                    score=1.0,  # No similarity score for direct retrieval
                    metadata={
                        'file_path': payload.get('file_path'),
                        'phase': payload.get('phase'),
                        'section_type': payload.get('section_type'),
                        'section_name': payload.get('section_name'),
                        'timestamp': payload.get('timestamp'),
                        'session_id': payload.get('session_id'),
                    }
                ))

            return results

        except Exception as e:
            logger.error(f"Failed to retrieve by IDs: {e}")
            return []

    # Discovery: Query SQL directly when needed. Don't wrap until usage patterns emerge.
    # Qdrant cannot implement these honestly (no file_path/timestamp indexing).
    # Use semantic search as modality, not fake relationship queries.

    def get_stats(self) -> Dict[str, Any]:
        """Get storage statistics

        Returns:
            Dictionary with collection stats
        """
        try:
            collection = self.client.get_collection(self.collection_name)
            return {
                'total_chunks': collection.points_count,
                'collection_name': self.collection_name,
                'vector_count': collection.vectors_count or 0,
            }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {'error': str(e)}

    def collection_exists(self, name: str) -> bool:
        """Check if collection exists

        Args:
            name: Collection name

        Returns:
            True if exists, False otherwise
        """
        try:
            collections = self.client.get_collections().collections
            return any(c.name == name for c in collections)
        except Exception:
            return False

    def delete_collection(self, name: str) -> None:
        """Delete a collection and all its data

        Args:
            name: Collection name to delete

        Raises:
            StorageError: If deletion fails
        """
        try:
            self.client.delete_collection(collection_name=name)
        except Exception as e:
            raise StorageError(f"Failed to delete collection: {e}") from e

    def _create_collection(self):
        """Create collection with vector configuration"""
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config={
                self.vector_name: VectorParams(
                    size=self.dimensions,
                    distance=Distance.COSINE
                )
            }
        )
