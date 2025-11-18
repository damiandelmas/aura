"""Composable pipeline processors

Individual stages for the retrieval pipeline:
- SearchProcessor: Initial search (metadata or semantic)
- DiscoveryProcessor: Sibling/genealogy/temporal enrichment
- RankingProcessor: Multi-phase re-ranking
- FilterProcessor: Post-processing filters
"""

from .search import SearchProcessor
from .ranking import MultiPhaseRanker, RankingPhase

__all__ = [
    'SearchProcessor',
    'MultiPhaseRanker',
    'RankingPhase',
]
