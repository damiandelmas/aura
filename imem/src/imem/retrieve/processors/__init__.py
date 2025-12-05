"""Composable pipeline processors

Individual stages for the retrieval pipeline:
- SearchProcessor: Initial search (metadata or semantic)
- DiscoveryProcessor: Sibling/genealogy/temporal enrichment
- RankingProcessor: Multi-phase re-ranking
- RankingModule: EPIC 5 final rank (validity × centrality × recency)
- FilterProcessor: Post-processing filters
"""

from .search import SearchProcessor
from .ranking import (
    MultiPhaseRanker,
    RankingPhase,
    RankingModule,
    NoOpRankingModule,
    compute_rank,
    compute_recency,
    DEFAULT_RANKING_WEIGHTS,
)
from .discovery import DiscoveryProcessor

__all__ = [
    'SearchProcessor',
    'DiscoveryProcessor',
    # Multi-phase ranking
    'MultiPhaseRanker',
    'RankingPhase',
    # EPIC 5: Ranking formula
    'RankingModule',
    'NoOpRankingModule',
    'compute_rank',
    'compute_recency',
    'DEFAULT_RANKING_WEIGHTS',
]
