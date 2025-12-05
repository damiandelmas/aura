"""Propagation Signal - Derive validity for unanchored chunks via graph traversal

Unanchored chunks (no code signatures with file_path) derive validity from their
graph neighborhood. BFS traversal finds anchored neighbors, hop decay weights
by distance. Transitive trust: if nearby chunks are git-validated, this one
probably is too.

CRITICAL DISTINCTIONS:
- Degree does NOT affect validity. Validity ≠ centrality.
- An isolated anchored chunk with perfect git match propagates full validity.
- superseded_by edges don't propagate — they override, not transfer.
- No threshold pruning on intermediate chunks.

Formula:
    validity = Σ (anchored_validity × edge_weight × hop_decay) / Σ weights
    where:
        hop_decay = 1 / (1 + hops)
        max_hops = 3 (configurable)
        no neighbors → 0.5 (neutral)

EPIC 3 implementation.
"""

from collections import deque
from typing import Any, Dict, List, Optional, Set, Tuple, TYPE_CHECKING
import logging

from ...protocols import Signal, SignalResult

if TYPE_CHECKING:
    from ...context import IndexContext

logger = logging.getLogger(__name__)


def is_anchored(chunk_id: str, context: 'IndexContext') -> bool:
    """Check if a chunk is anchored (has signatures with file_path)

    Anchored chunks can be validated directly against the codebase.
    Unanchored chunks derive validity through graph proximity.

    Args:
        chunk_id: Chunk ID to check
        context: Index context with infrastructure

    Returns:
        True if chunk has at least one signature with file_path
    """
    db = context.infrastructure.db
    try:
        cursor = db.conn.execute('''
            SELECT COUNT(*) FROM chunk_signatures
            WHERE chunk_id = ? AND file_path IS NOT NULL
        ''', (chunk_id,))
        result = cursor.fetchone()
        return result[0] > 0 if result else False
    except Exception as e:
        logger.warning(f"Failed to check anchored status for {chunk_id}: {e}")
        return False


def get_anchored_ids(chunks: List[Dict[str, Any]], context: 'IndexContext') -> Set[str]:
    """Compute set of anchored chunk IDs

    Called once at start of validity phase to classify chunks.

    Args:
        chunks: Chunks to classify
        context: Index context with infrastructure

    Returns:
        Set of chunk IDs that are anchored
    """
    anchored = set()
    for chunk in chunks:
        chunk_id = chunk.get('id')
        if chunk_id and is_anchored(chunk_id, context):
            anchored.add(chunk_id)
    return anchored


class PropagationSignal(Signal):
    """Derive validity for unanchored chunks via graph proximity

    BFS traversal finds anchored neighbors within max_hops.
    Weighted average with hop decay: closer anchors influence more.

    Key behaviors:
    - Only applies to unanchored chunks
    - Skips superseded_by edges (they override, don't propagate)
    - Stops traversal at anchored nodes (don't go beyond)
    - No degree weighting (validity ≠ centrality)

    Confidence is 0.7 — lower than git (0.9), higher than temporal (0.3).
    """

    # Medium-high confidence for propagated validity
    PROPAGATION_CONFIDENCE = 0.7
    NO_NEIGHBORS_CONFIDENCE = 0.3

    # Default max hops for BFS
    DEFAULT_MAX_HOPS = 3

    def __init__(self, max_hops: int = DEFAULT_MAX_HOPS):
        self.max_hops = max_hops
        self._anchored_ids: Optional[Set[str]] = None

    @property
    def name(self) -> str:
        return "propagation"

    def set_anchored_ids(self, anchored_ids: Set[str]) -> None:
        """Set the pre-computed anchored IDs

        Called by ManageOrchestrator after Phase 1 (anchored validation).
        """
        self._anchored_ids = anchored_ids

    def applies(self, chunk: Dict[str, Any], context: 'IndexContext') -> bool:
        """PropagationSignal applies only to unanchored chunks

        Anchored chunks get their validity from GitSignal directly.
        Git-sourced chunks are ground truth and skip all signals.
        """
        # Git-sourced chunks are ground truth
        source = chunk.get('source', chunk.get('metadata', {}).get('source'))
        if source == 'git':
            return False

        chunk_id = chunk.get('id')
        if not chunk_id:
            return False

        # Check against pre-computed anchored set if available
        if self._anchored_ids is not None:
            return chunk_id not in self._anchored_ids

        # Fall back to database check
        return not is_anchored(chunk_id, context)

    def score(self, chunk: Dict[str, Any], context: 'IndexContext') -> SignalResult:
        """Compute propagated validity via BFS

        Finds anchored neighbors within max_hops, computes weighted average
        of their validities with hop decay.
        """
        chunk_id = chunk.get('id')
        if not chunk_id:
            return SignalResult(
                score=0.5,
                confidence=0.0,
                reason="No chunk ID"
            )

        # BFS to find anchored neighbors
        neighbors = self._bfs_anchored_neighbors(chunk_id, context)

        if not neighbors:
            return SignalResult(
                score=0.5,
                confidence=self.NO_NEIGHBORS_CONFIDENCE,
                reason="No anchored neighbors within reach"
            )

        # Compute weighted average with hop decay
        total_weight = 0.0
        weighted_sum = 0.0

        for neighbor_id, hops, path_weight in neighbors:
            neighbor_validity = self._get_chunk_validity(neighbor_id, context)

            # Hop decay: closer = stronger influence
            hop_decay = 1.0 / (1 + hops)

            # Combined weight: edge strength × distance
            weight = path_weight * hop_decay

            weighted_sum += neighbor_validity * weight
            total_weight += weight

        if total_weight == 0:
            return SignalResult(
                score=0.5,
                confidence=self.NO_NEIGHBORS_CONFIDENCE,
                reason="Zero total weight from neighbors"
            )

        score = weighted_sum / total_weight

        return SignalResult(
            score=score,
            confidence=self.PROPAGATION_CONFIDENCE,
            reason=f"{len(neighbors)} anchored neighbors via graph (max {self.max_hops} hops)"
        )

    def _bfs_anchored_neighbors(
        self,
        start_id: str,
        context: 'IndexContext'
    ) -> List[Tuple[str, int, float]]:
        """BFS traversal to find anchored neighbors

        Returns:
            List of (chunk_id, hops, path_weight) tuples for anchored neighbors
        """
        visited: Set[str] = set()
        queue: deque = deque()
        queue.append((start_id, 0, 1.0))  # (chunk_id, hops, cumulative_weight)

        anchored_neighbors: List[Tuple[str, int, float]] = []

        while queue:
            current_id, hops, path_weight = queue.popleft()

            # Skip if already visited or too far
            if current_id in visited or hops > self.max_hops:
                continue
            visited.add(current_id)

            # Skip the start node itself
            if current_id != start_id:
                # Check if this is an anchored node
                is_current_anchored = (
                    current_id in self._anchored_ids
                    if self._anchored_ids is not None
                    else is_anchored(current_id, context)
                )

                if is_current_anchored:
                    anchored_neighbors.append((current_id, hops, path_weight))
                    continue  # Don't traverse beyond anchored nodes

            # Get edges from current node
            edges = self._get_edges(current_id, context)

            for neighbor_id, edge_type, edge_weight in edges:
                # Skip superseded_by edges — they override, don't propagate
                if edge_type == 'superseded_by':
                    continue

                if neighbor_id not in visited:
                    new_weight = path_weight * edge_weight
                    queue.append((neighbor_id, hops + 1, new_weight))

        return anchored_neighbors

    def _get_edges(
        self,
        chunk_id: str,
        context: 'IndexContext'
    ) -> List[Tuple[str, str, float]]:
        """Get edges for a chunk (both directions)

        Returns:
            List of (neighbor_id, edge_type, weight) tuples
        """
        db = context.infrastructure.db
        edges: List[Tuple[str, str, float]] = []

        try:
            # Edges where chunk is source
            cursor = db.conn.execute('''
                SELECT to_id, type, weight FROM edges WHERE from_id = ?
            ''', (chunk_id,))
            for row in cursor.fetchall():
                edges.append((row[0], row[1], row[2] or 1.0))

            # Edges where chunk is target (bidirectional traversal)
            cursor = db.conn.execute('''
                SELECT from_id, type, weight FROM edges WHERE to_id = ?
            ''', (chunk_id,))
            for row in cursor.fetchall():
                edges.append((row[0], row[1], row[2] or 1.0))

        except Exception as e:
            logger.warning(f"Failed to get edges for {chunk_id}: {e}")

        return edges

    def _get_chunk_validity(self, chunk_id: str, context: 'IndexContext') -> float:
        """Get validity score for a chunk from database

        Returns:
            Validity score (0.0-1.0), default 0.5 if not found
        """
        db = context.infrastructure.db
        try:
            cursor = db.conn.execute('''
                SELECT validity FROM chunks WHERE id = ?
            ''', (chunk_id,))
            result = cursor.fetchone()
            return result[0] if result and result[0] is not None else 0.5
        except Exception as e:
            logger.warning(f"Failed to get validity for {chunk_id}: {e}")
            return 0.5


__all__ = ['PropagationSignal', 'is_anchored', 'get_anchored_ids']
