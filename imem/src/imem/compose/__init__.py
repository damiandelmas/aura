"""Compose domain - Retrieval pipeline orchestration

Provides composable retrieval pipeline through processor chain pattern.

New architecture (processor chain):
    from imem.compose.orchestrator import compose
    from imem.storage import create_store

    store = create_store('sqlite', {'project_root': '...'})
    config = {'search': {'mode': 'metadata'}}
    results = compose('query', config, store)

Or use chain directly:
    from imem.compose.processors import SearchProcessor, MultiPhaseRanker
    from imem.core import Chain, RetrievalContext

    chain = Chain([
        SearchProcessor(store),
        MultiPhaseRanker([...])
    ])

    result = chain.execute(RetrievalContext(query, config))
"""

# Export orchestrator and processor chain components
from .orchestrator import compose, build_chain
from .processors import SearchProcessor, MultiPhaseRanker, RankingPhase

__all__ = [
    'compose',
    'build_chain',
    'SearchProcessor',
    'MultiPhaseRanker',
    'RankingPhase',
]
