"""Centrality domain - Chunk importance via connectedness

EPIC 5: Centrality & Ranking

Centrality measures "how important?" through graph connectivity.
This is SEPARATE from validity which measures "is this true?" (MANAGE domain).

Critical philosophy (graph-epistemology.md):
- Degree/connectivity informs CENTRALITY (importance), NOT validity (truth)
- A chunk can be: high validity + low centrality (true but peripheral)
- A chunk can be: low validity + high centrality (outdated but central)

CentralityComputer aggregates signals with configurable weights:
- EdgeCountSignal (0.5): Inbound edge count, normalized
- CrossPhaseSignal (0.3): Phase diversity of referencing chunks
- SiblingDensitySignal (0.2): HNSW neighbor density (Tier 3)

Default weights: edge_count=0.5, cross_phase=0.3, sibling_density=0.2
"""

from typing import Any, Dict, List, Optional, TYPE_CHECKING
import logging

from .signals import CentralitySignal, CentralityResult, NoOpCentralitySignal

if TYPE_CHECKING:
    from ...context import QueryContext

logger = logging.getLogger(__name__)


# Default weights for centrality signals
DEFAULT_WEIGHTS = {
    'edge_count': 0.5,
    'cross_phase': 0.3,
    'sibling_density': 0.2,
}


class CentralityComputer:
    """Aggregates centrality signals into a single score

    Mirrors ValidityComputer pattern from MANAGE domain.
    Uses confidence-weighted averaging across signals.

    Usage:
        computer = CentralityComputer(
            signals=[EdgeCountSignal(db), CrossPhaseSignal(db)]
        )
        centrality = computer.compute(chunk, context)
    """

    def __init__(
        self,
        signals: Optional[List[CentralitySignal]] = None,
        weights: Optional[Dict[str, float]] = None,
    ):
        """Initialize CentralityComputer

        Args:
            signals: List of centrality signals to aggregate
            weights: Optional per-signal weight overrides {signal_name: weight}
        """
        self.signals = signals or [NoOpCentralitySignal()]
        self.weights = weights or DEFAULT_WEIGHTS

    def compute(
        self,
        chunk: Dict[str, Any],
        context: 'QueryContext',
    ) -> float:
        """Compute centrality for a chunk

        Aggregates applicable signals using confidence-weighted averaging,
        then applies per-signal weights from configuration.

        Args:
            chunk: Chunk to score
            context: Query context with infrastructure

        Returns:
            Centrality score (0.0-1.0)
        """
        total_score = 0.0
        total_weight = 0.0

        for signal in self.signals:
            if signal.applies(chunk, context):
                result = signal.score(chunk, context)

                # Get signal weight from config (default 1.0)
                signal_weight = self.weights.get(signal.name, 1.0)

                # Combined weight = signal_weight * confidence
                combined_weight = signal_weight * result.confidence
                total_score += result.score * combined_weight
                total_weight += combined_weight

                logger.debug(
                    f"Centrality signal '{signal.name}': "
                    f"score={result.score:.2f}, confidence={result.confidence:.2f}"
                )

        if total_weight > 0:
            centrality = total_score / total_weight
        else:
            centrality = 0.5  # Neutral default

        return centrality


class NoOpCentralityComputer(CentralityComputer):
    """No-op centrality computer returning neutral values"""

    def __init__(self):
        super().__init__([NoOpCentralitySignal()])


# Lazy imports for concrete signals (avoid circular imports)
def _import_signals():
    """Import concrete signal implementations"""
    from .edge_count import EdgeCountSignal
    from .cross_phase import CrossPhaseSignal
    from .sibling_density import SiblingDensitySignal, NoOpSiblingDensitySignal
    return EdgeCountSignal, CrossPhaseSignal, SiblingDensitySignal, NoOpSiblingDensitySignal


def create_centrality_computer(
    db=None,
    vector_storage=None,
) -> CentralityComputer:
    """Factory for CentralityComputer with EPIC 5 implementations

    Args:
        db: SQLiteStore for edge queries
        vector_storage: Optional VectorStorage for sibling density (Tier 3)

    Returns:
        Configured CentralityComputer
    """
    EdgeCountSignal, CrossPhaseSignal, SiblingDensitySignal, NoOpSiblingDensitySignal = _import_signals()

    signals: List[CentralitySignal] = []

    # EdgeCountSignal: always available if we have db
    if db is not None:
        signals.append(EdgeCountSignal(db))
        signals.append(CrossPhaseSignal(db))

    # SiblingDensitySignal: Tier 3 (requires vectors)
    if vector_storage is not None and hasattr(vector_storage, 'is_available') and vector_storage.is_available:
        signals.append(SiblingDensitySignal(vector_storage))
    else:
        signals.append(NoOpSiblingDensitySignal())

    if not signals:
        signals = [NoOpCentralitySignal()]

    return CentralityComputer(signals=signals)


__all__ = [
    # Core
    'CentralityComputer',
    'NoOpCentralityComputer',
    'create_centrality_computer',
    # Signals
    'CentralitySignal',
    'CentralityResult',
    'NoOpCentralitySignal',
    # Weights
    'DEFAULT_WEIGHTS',
]
