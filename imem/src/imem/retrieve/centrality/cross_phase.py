"""CrossPhaseSignal - Centrality from phase diversity of references

Chunks referenced across multiple phases are foundational.
A decision referenced in design, developed in develop, documented in document
is more central than one only mentioned once.

Cross-phase references indicate durable, important knowledge
that persists through the lifecycle.

Phases: design, designate, develop, document
"""

from typing import Any, Dict, Set, TYPE_CHECKING
import logging

from .signals import CentralitySignal, CentralityResult

if TYPE_CHECKING:
    from ...context import QueryContext
    from ...storage.sqlite import SQLiteStore

logger = logging.getLogger(__name__)


# All lifecycle phases
PHASES = {'design', 'designate', 'develop', 'document'}


class CrossPhaseSignal(CentralitySignal):
    """Compute centrality from phase diversity of referencing chunks

    Score based on how many different phases reference this chunk:
    - 1 phase  -> 0.0 (baseline)
    - 2 phases -> 0.2
    - 3 phases -> 0.4
    - 4+ phases -> 0.6 (capped)

    Cross-phase references indicate foundational chunks.
    """

    def __init__(self, db: 'SQLiteStore'):
        """Initialize CrossPhaseSignal

        Args:
            db: SQLite database for edge and chunk queries
        """
        self.db = db

    @property
    def name(self) -> str:
        return "cross_phase"

    def applies(self, chunk: Dict[str, Any], context: 'QueryContext') -> bool:
        """Always applies if chunk has an ID"""
        return chunk.get('id') is not None

    def score(self, chunk: Dict[str, Any], context: 'QueryContext') -> CentralityResult:
        """Find phases of chunks that reference this chunk

        1. Find all chunks that have edges TO this chunk
        2. Collect unique phases of those referencing chunks
        3. Score by phase count

        Returns:
            CentralityResult with diversity score
        """
        chunk_id = chunk.get('id')
        if not chunk_id:
            return CentralityResult(
                score=0.0,
                confidence=0.0,
                reason="No chunk ID"
            )

        try:
            # Find phases of referencing chunks
            cursor = self.db.conn.execute('''
                SELECT DISTINCT c.phase
                FROM edges e
                JOIN chunks c ON c.id = e.from_id
                WHERE e.to_id = ?
                  AND c.phase IS NOT NULL
            ''', (chunk_id,))

            phases: Set[str] = {row[0] for row in cursor.fetchall()}
            phase_count = len(phases)

            # Score by diversity:
            # 0-1 phases = 0.0, 2 = 0.2, 3 = 0.4, 4+ = 0.6
            if phase_count <= 1:
                score = 0.0
            elif phase_count == 2:
                score = 0.2
            elif phase_count == 3:
                score = 0.4
            else:
                score = 0.6

            return CentralityResult(
                score=score,
                confidence=0.7,  # Medium-high confidence
                reason=f"Referenced from {phase_count} phases: {sorted(phases)}"
            )

        except Exception as e:
            logger.warning(f"CrossPhaseSignal failed for {chunk_id}: {e}")
            return CentralityResult(
                score=0.0,
                confidence=0.0,
                reason=f"Query failed: {e}"
            )


__all__ = ['CrossPhaseSignal']
