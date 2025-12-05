"""SiblingBuilder - Create edges between semantically similar chunks

EPIC 4: sqlite-vec Vectors

Creates bidirectional edges between chunks that are semantically similar.
Sibling relationships enable context expansion - when retrieving a chunk,
sibling edges surface related content. They also contribute to centrality.

Edge semantics:
- Direction: bidirectional (sorted normalization: min(a,b), max(a,b))
- Weight: cosine similarity (0.7-1.0)
- Type: 'sibling'

Logic:
1. For each chunk with embedding, query HNSW for k neighbors
2. Filter by similarity threshold (default 0.7)
3. Create bidirectional edges with weight = similarity
4. Sorted normalization prevents duplicate (A,B) and (B,A) entries

Tier 3: Requires VectorStorage (sqlite-vec) and Embedder.
If vectors unavailable, applies() returns False - graceful skip.
"""

import logging
from typing import Any, Dict, List, Set, Tuple, Optional, TYPE_CHECKING

from ...protocols import Builder, Edge

if TYPE_CHECKING:
    from ...context import IndexContext
    from ...storage.vectors import VectorStorage
    from ...infrastructure.embedder import Embedder

logger = logging.getLogger(__name__)


class SiblingBuilder(Builder):
    """Creates sibling edges linking semantically similar chunks

    Uses HNSW vector similarity to find related chunks across the corpus.
    Sibling edges are bidirectional - stored with sorted(from_id, to_id)
    to prevent duplicate edges.

    This is a Tier 3 builder - requires vectors. If VectorStorage is
    unavailable, applies() returns False and builder is skipped.
    """

    # Default configuration
    DEFAULT_SIMILARITY_THRESHOLD = 0.7  # Minimum similarity for sibling edge
    DEFAULT_MAX_NEIGHBORS = 20  # K for KNN query
    DEFAULT_MAX_SIBLINGS = 10  # Max sibling edges per chunk

    def __init__(
        self,
        vector_storage: Optional['VectorStorage'] = None,
        embedder: Optional['Embedder'] = None,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        max_neighbors: int = DEFAULT_MAX_NEIGHBORS,
        max_siblings: int = DEFAULT_MAX_SIBLINGS,
    ):
        """Initialize SiblingBuilder

        Args:
            vector_storage: VectorStorage for KNN queries
            embedder: Embedder for generating embeddings
            similarity_threshold: Minimum similarity for edge creation
            max_neighbors: K for KNN query
            max_siblings: Maximum siblings per chunk
        """
        self._vector_storage = vector_storage
        self._embedder = embedder
        self.similarity_threshold = similarity_threshold
        self.max_neighbors = max_neighbors
        self.max_siblings = max_siblings

    @property
    def name(self) -> str:
        return "sibling"

    @property
    def edge_type(self) -> str:
        return "sibling"

    def set_vector_storage(self, storage: 'VectorStorage') -> None:
        """Set vector storage (for late binding)"""
        self._vector_storage = storage

    def set_embedder(self, embedder: 'Embedder') -> None:
        """Set embedder (for late binding)"""
        self._embedder = embedder

    def applies(self, chunks: List[Dict[str, Any]], context: 'IndexContext') -> bool:
        """Check if vector infrastructure is available

        Tier 3 gate: Only run if VectorStorage is functional.

        Args:
            chunks: All chunks being indexed
            context: Index context with infrastructure

        Returns:
            True if vectors available and chunks exist
        """
        # Check if we have vector infrastructure
        if self._vector_storage is None or not self._vector_storage.is_available:
            logger.debug("SiblingBuilder skipped: VectorStorage not available")
            return False

        if self._embedder is None or not self._embedder.is_available:
            logger.debug("SiblingBuilder skipped: Embedder not available")
            return False

        # Need at least 2 chunks to create sibling relationships
        if len(chunks) < 2:
            logger.debug("SiblingBuilder skipped: Not enough chunks")
            return False

        return True

    def build(self, chunks: List[Dict[str, Any]], context: 'IndexContext') -> List[Edge]:
        """Build sibling edges via HNSW similarity search

        Args:
            chunks: All chunks to consider
            context: Index context with infrastructure

        Returns:
            List of Edge objects (bidirectional, sorted normalization)
        """
        if not self._vector_storage or not self._embedder:
            return []

        edges: List[Edge] = []
        seen_pairs: Set[Tuple[str, str]] = set()

        # First, ensure all chunks have embeddings stored
        self._ensure_embeddings(chunks, context)

        # Build chunk lookup for quick access
        chunk_map = {c['id']: c for c in chunks}

        # For each chunk, find similar neighbors
        for chunk in chunks:
            chunk_id = chunk['id']
            content = chunk.get('content', '')

            if not content:
                continue

            # Get embedding for this chunk
            embedding = self._embedder.embed_single(content)
            if not embedding:
                continue

            # Query for similar chunks
            neighbors = self._vector_storage.query_knn(
                embedding=embedding,
                k=self.max_neighbors,
                threshold=self.similarity_threshold,
            )

            # Create edges for top neighbors
            sibling_count = 0
            for neighbor in neighbors:
                neighbor_id = neighbor.chunk_id

                # Skip self-loops
                if neighbor_id == chunk_id:
                    continue

                # Skip if we've already created this edge (either direction)
                pair = self._normalize_pair(chunk_id, neighbor_id)
                if pair in seen_pairs:
                    continue

                seen_pairs.add(pair)

                # Create edge with sorted normalization
                from_id, to_id = pair
                edge = Edge(
                    from_id=from_id,
                    to_id=to_id,
                    type=self.edge_type,
                    weight=neighbor.similarity,
                )
                edges.append(edge)

                logger.debug(
                    f"sibling edge: {from_id[:8]}... ↔ {to_id[:8]}... "
                    f"(similarity={neighbor.similarity:.3f})"
                )

                sibling_count += 1
                if sibling_count >= self.max_siblings:
                    break

        logger.info(f"SiblingBuilder created {len(edges)} edges")
        return edges

    def _normalize_pair(self, a: str, b: str) -> Tuple[str, str]:
        """Normalize edge pair for bidirectional storage

        Uses sorted order (min, max) to ensure A→B and B→A
        result in the same stored edge.

        Args:
            a: First chunk ID
            b: Second chunk ID

        Returns:
            Tuple (min_id, max_id)
        """
        if a < b:
            return (a, b)
        return (b, a)

    def _ensure_embeddings(
        self,
        chunks: List[Dict[str, Any]],
        context: 'IndexContext',
    ) -> None:
        """Ensure all chunks have embeddings stored

        Generates and stores embeddings for chunks that don't
        have them yet.

        Args:
            chunks: Chunks to check/embed
            context: Index context
        """
        if not self._vector_storage or not self._embedder:
            return

        # Collect chunks needing embeddings
        to_embed = []
        for chunk in chunks:
            content = chunk.get('content', '')
            if content and len(content.strip()) > 10:  # Skip trivial content
                to_embed.append(chunk)

        if not to_embed:
            return

        # Batch embed
        logger.debug(f"Generating embeddings for {len(to_embed)} chunks")
        texts = [c.get('content', '') for c in to_embed]
        embeddings = self._embedder.embed(texts)

        # Store embeddings
        self._vector_storage.store_batch(to_embed, embeddings)
        logger.debug(f"Stored {len(embeddings)} embeddings")


class NoOpSiblingBuilder(Builder):
    """No-op sibling builder for graceful degradation

    Used when vector infrastructure is not available.
    Never applies, never creates edges.
    """

    @property
    def name(self) -> str:
        return "sibling_noop"

    @property
    def edge_type(self) -> str:
        return "sibling"

    def applies(self, chunks: List[Dict[str, Any]], context: 'IndexContext') -> bool:
        """Always returns False - never runs"""
        return False

    def build(self, chunks: List[Dict[str, Any]], context: 'IndexContext') -> List[Edge]:
        """Never called - returns empty list"""
        return []


def create_sibling_builder(
    vector_storage: Optional['VectorStorage'] = None,
    embedder: Optional['Embedder'] = None,
    similarity_threshold: float = SiblingBuilder.DEFAULT_SIMILARITY_THRESHOLD,
) -> Builder:
    """Factory function to create sibling builder

    Returns SiblingBuilder if vector infrastructure is provided,
    otherwise returns NoOpSiblingBuilder for graceful degradation.

    Args:
        vector_storage: Optional VectorStorage instance
        embedder: Optional Embedder instance
        similarity_threshold: Minimum similarity for edges

    Returns:
        SiblingBuilder or NoOpSiblingBuilder
    """
    if vector_storage is None or embedder is None:
        logger.info("Using NoOpSiblingBuilder (vector infrastructure not provided)")
        return NoOpSiblingBuilder()

    if not vector_storage.is_available or not embedder.is_available:
        logger.info("Using NoOpSiblingBuilder (vector infrastructure not available)")
        return NoOpSiblingBuilder()

    return SiblingBuilder(
        vector_storage=vector_storage,
        embedder=embedder,
        similarity_threshold=similarity_threshold,
    )


__all__ = [
    'SiblingBuilder',
    'NoOpSiblingBuilder',
    'create_sibling_builder',
]
