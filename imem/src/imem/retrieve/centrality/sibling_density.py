"""SiblingDensitySignal - Centrality from semantic cluster density

Semantic clusters indicate established concepts.
A chunk surrounded by many similar chunks is in a well-developed
area of the corpus. Isolated chunks might be novel, tangential, or noise.

Density measures how central a chunk is within the semantic landscape.

Tier 3: Requires VectorStorage (sqlite-vec + embeddings).
Gracefully degrades via NoOpSiblingDensitySignal when unavailable.
"""

from typing import Any, Dict, TYPE_CHECKING
import logging

from .signals import CentralitySignal, CentralityResult

if TYPE_CHECKING:
    from ...context import QueryContext
    from ...storage.vectors import VectorStorage

logger = logging.getLogger(__name__)


class SiblingDensitySignal(CentralitySignal):
    """Compute centrality from semantic cluster density

    Query HNSW for k neighbors, count those above similarity threshold.
    Density = count / k_neighbors

    Dense clusters = well-connected concepts.
    Sparse regions = unique/outlier chunks.

    Tier 3: Requires VectorStorage.
    """

    def __init__(
        self,
        vector_storage: 'VectorStorage',
        k_neighbors: int = 20,
        threshold: float = 0.7,
    ):
        """Initialize SiblingDensitySignal

        Args:
            vector_storage: VectorStorage for KNN queries
            k_neighbors: Number of neighbors to query
            threshold: Similarity threshold for counting
        """
        self.vector_storage = vector_storage
        self.k_neighbors = k_neighbors
        self.threshold = threshold

    @property
    def name(self) -> str:
        return "sibling_density"

    def applies(self, chunk: Dict[str, Any], context: 'QueryContext') -> bool:
        """Applies if vector_storage is available and chunk has embedding"""
        if not hasattr(self.vector_storage, 'is_available') or not self.vector_storage.is_available:
            return False
        return chunk.get('id') is not None

    def score(self, chunk: Dict[str, Any], context: 'QueryContext') -> CentralityResult:
        """Query HNSW and compute density

        1. Query k neighbors
        2. Count neighbors above threshold
        3. Density = count / k

        Returns:
            CentralityResult with density score
        """
        chunk_id = chunk.get('id')
        if not chunk_id:
            return CentralityResult(
                score=0.0,
                confidence=0.0,
                reason="No chunk ID"
            )

        try:
            # Query for neighbors of this chunk
            neighbors = self.vector_storage.query_by_chunk_id(
                chunk_id=chunk_id,
                k=self.k_neighbors,
            )

            if not neighbors:
                return CentralityResult(
                    score=0.0,
                    confidence=0.5,
                    reason="No neighbors found"
                )

            # Count neighbors above similarity threshold
            # neighbors is list of (chunk_id, similarity)
            above_threshold = sum(
                1 for _, similarity in neighbors
                if similarity >= self.threshold
            )

            # Density = count / k
            density = above_threshold / self.k_neighbors

            return CentralityResult(
                score=density,
                confidence=0.6,  # Medium confidence - embedding quality varies
                reason=f"{above_threshold}/{self.k_neighbors} neighbors above {self.threshold}"
            )

        except Exception as e:
            logger.warning(f"SiblingDensitySignal failed for {chunk_id}: {e}")
            return CentralityResult(
                score=0.5,
                confidence=0.0,
                reason=f"Query failed: {e}"
            )


class NoOpSiblingDensitySignal(CentralitySignal):
    """No-op sibling density when vectors unavailable

    Tier 3 graceful degradation.
    """

    @property
    def name(self) -> str:
        return "sibling_density"

    def applies(self, chunk: Dict[str, Any], context: 'QueryContext') -> bool:
        return False  # Never applies

    def score(self, chunk: Dict[str, Any], context: 'QueryContext') -> CentralityResult:
        return CentralityResult(
            score=0.5,
            confidence=0.0,
            reason="Vectors unavailable (Tier 3)"
        )


__all__ = ['SiblingDensitySignal', 'NoOpSiblingDensitySignal']
