"""Compose domain - Retrieval pipeline orchestration

Provides composable retrieval pipeline through processor chain pattern.

New architecture (processor chain):
    from imem.compose.processors import SearchProcessor, MultiPhaseRanker
    from imem.core import Chain, RetrievalContext

    chain = Chain([
        SearchProcessor(store),
        MultiPhaseRanker([...])
    ])

    result = chain.execute(RetrievalContext(query, config))

Legacy (backward compatibility):
    from imem.compose import compose  # Old procedural pipeline
"""

# Export processor chain components
from .processors import SearchProcessor, MultiPhaseRanker, RankingPhase

__all__ = [
    'SearchProcessor',
    'MultiPhaseRanker',
    'RankingPhase',
]
