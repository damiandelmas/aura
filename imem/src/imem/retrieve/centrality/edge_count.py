"""EdgeCountSignal - Centrality from inbound edge count

The simplest centrality signal: count how many edges point to this chunk.
Chunks that many others reference are important.

This is NOT about truth (validity). A chunk can be highly referenced
but outdated. Edge count measures importance, not correctness.

Schema dependency:
    edges table: from_id, to_id, type, weight
"""

from typing import Any, Dict, TYPE_CHECKING
import logging

from .signals import CentralitySignal, CentralityResult

if TYPE_CHECKING:
    from ...context import QueryContext
    from ...storage.sqlite import SQLiteStore

logger = logging.getLogger(__name__)


class EdgeCountSignal(CentralitySignal):
    """Compute centrality from inbound edge count

    More inbound refs = higher centrality.
    Normalized to 0.0-1.0 by capping at max_edges.

    Attributes:
        max_edges: Cap for normalization (default 10)
                   Prevents outlier dominance
    """

    def __init__(self, db: 'SQLiteStore', max_edges: int = 10):
        """Initialize EdgeCountSignal

        Args:
            db: SQLite database for edge queries
            max_edges: Normalization cap (default 10)
        """
        self.db = db
        self.max_edges = max_edges

    @property
    def name(self) -> str:
        return "edge_count"

    def applies(self, chunk: Dict[str, Any], context: 'QueryContext') -> bool:
        """Always applies if chunk has an ID"""
        return chunk.get('id') is not None

    def score(self, chunk: Dict[str, Any], context: 'QueryContext') -> CentralityResult:
        """Count inbound edges and normalize

        SQL: SELECT COUNT(*) FROM edges WHERE to_id = ?

        Returns:
            CentralityResult with normalized score
        """
        chunk_id = chunk.get('id')
        if not chunk_id:
            return CentralityResult(
                score=0.0,
                confidence=0.0,
                reason="No chunk ID"
            )

        try:
            cursor = self.db.conn.execute(
                'SELECT COUNT(*) FROM edges WHERE to_id = ?',
                (chunk_id,)
            )
            count = cursor.fetchone()[0]

            # Normalize to 0.0-1.0, capped at max_edges
            normalized_score = min(count / self.max_edges, 1.0)

            return CentralityResult(
                score=normalized_score,
                confidence=0.8,  # High confidence - deterministic count
                reason=f"{count} inbound edges"
            )

        except Exception as e:
            logger.warning(f"EdgeCountSignal failed for {chunk_id}: {e}")
            return CentralityResult(
                score=0.5,
                confidence=0.0,
                reason=f"Query failed: {e}"
            )


__all__ = ['EdgeCountSignal']
