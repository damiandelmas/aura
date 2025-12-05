"""Retrieve domain - Retrieval pipeline orchestration

EPIC 5: Centrality & Ranking

Provides composable retrieval pipeline through processor chain pattern.
Flow: search → discovery → centrality → ranking

Centrality measures "how important?" through graph connectivity.
This is SEPARATE from validity which measures "is this true?".

Ranking formula: rank = validity × w_v + centrality × w_c + recency × w_r

Usage:
    from imem.retrieve import compose, build_chain
    from imem.storage import create_store

    store = create_store('sqlite', {'project_root': '...'})
    config = {'search': {'mode': 'metadata'}}
    results = compose('query', config, store)

Or use chain directly:
    from imem.retrieve import SearchProcessor, MultiPhaseRanker
    from imem.core import Chain, RetrievalContext

    chain = Chain([
        SearchProcessor(store),
        MultiPhaseRanker([...])
    ])

    result = chain.execute(RetrievalContext(query, config))
"""

# Export orchestrator and processor chain components
from .orchestrator import compose, build_chain
from .processors import (
    SearchProcessor,
    MultiPhaseRanker,
    RankingPhase,
    RankingModule,
    NoOpRankingModule,
)

# EPIC 5: Centrality exports
from .centrality import (
    CentralityComputer,
    NoOpCentralityComputer,
    create_centrality_computer,
    CentralitySignal,
    CentralityResult,
    NoOpCentralitySignal,
    DEFAULT_WEIGHTS as CENTRALITY_WEIGHTS,
)

__all__ = [
    # Orchestration
    'compose',
    'build_chain',
    # Processors
    'SearchProcessor',
    'MultiPhaseRanker',
    'RankingPhase',
    # EPIC 5: Ranking
    'RankingModule',
    'NoOpRankingModule',
    # EPIC 5: Centrality
    'CentralityComputer',
    'NoOpCentralityComputer',
    'create_centrality_computer',
    'CentralitySignal',
    'CentralityResult',
    'NoOpCentralitySignal',
    'CENTRALITY_WEIGHTS',
]
