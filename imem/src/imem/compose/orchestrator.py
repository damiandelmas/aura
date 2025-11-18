"""Compose orchestrator - Build and execute retrieval pipelines via processor chain

Replaces hardcoded compose.py pipeline with declarative chain configuration.
Enables config-driven composition, reorderable stages, independent testing.
"""

from typing import Dict, Any, List, Optional
import logging

from ..core import Chain, RetrievalContext
from ..storage import VectorStore
from .processors import SearchProcessor, MultiPhaseRanker, RankingPhase

logger = logging.getLogger(__name__)


def build_chain(config: Dict[str, Any], store: VectorStore) -> Chain:
    """Build processor chain from config

    Args:
        config: Pipeline configuration with keys:
            - search: {mode: 'metadata'|'semantic', filters: {...}}
            - discovery: {siblings: bool, temporal: bool, genealogy: bool}
            - ranking: {phases: [{name, scorer, rerank_count}]}
        store: VectorStore backend (SQLite or Qdrant)

    Returns:
        Configured processor chain

    Example config:
        {
            "search": {
                "mode": "metadata",
                "filters": {"phase": "develop"}
            },
            "discovery": {
                "siblings": true
            },
            "ranking": {
                "phases": [
                    {"name": "metadata", "rerank_count": 100},
                    {"name": "authority", "rerank_count": 10}
                ]
            }
        }
    """
    processors = []

    # 1. Search processor (required)
    search_config = config.get('search', {})
    mode = search_config.get('mode', 'metadata')
    processors.append(SearchProcessor(store, mode=mode))

    # 2. Discovery processors (optional, conditional)
    discovery_config = config.get('discovery', {})

    if discovery_config.get('siblings'):
        # TODO: Implement SiblingDiscovery processor
        # from .processors.discovery import SiblingDiscovery
        # processors.append(SiblingDiscovery(store))
        logger.warning("SiblingDiscovery not yet implemented")

    if discovery_config.get('temporal'):
        # TODO: Implement TemporalDiscovery processor
        # from .processors.discovery import TemporalDiscovery
        # processors.append(TemporalDiscovery(store))
        logger.warning("TemporalDiscovery not yet implemented")

    if discovery_config.get('genealogy'):
        # TODO: Implement GenealogyDiscovery processor
        # from .processors.discovery import GenealogyDiscovery
        # processors.append(GenealogyDiscovery(store))
        logger.warning("GenealogyDiscovery not yet implemented")

    # 3. Ranking processor (optional, multi-phase)
    ranking_config = config.get('ranking')
    if ranking_config:
        phases = []
        for phase_cfg in ranking_config.get('phases', []):
            # Map phase name to scorer function
            scorer = _get_scorer_for_phase(phase_cfg['name'])
            phases.append(RankingPhase(
                name=phase_cfg['name'],
                scorer=scorer,
                rerank_count=phase_cfg.get('rerank_count')
            ))

        if phases:
            processors.append(MultiPhaseRanker(phases))

    return Chain(processors)


def _get_scorer_for_phase(phase_name: str):
    """Map phase name to scorer function

    Args:
        phase_name: Name of ranking phase ('metadata', 'references', 'authority')

    Returns:
        Scorer function compatible with RankingPhase
    """
    # TODO: Implement actual scoring functions
    # For now, return identity function
    def identity_scorer(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return results

    return identity_scorer


def compose(
    query: str,
    config: Dict[str, Any],
    store: VectorStore
) -> Dict[str, Any]:
    """Execute retrieval pipeline via processor chain

    Args:
        query: Search query text
        config: Pipeline configuration
        store: VectorStore backend

    Returns:
        Retrieval results with metadata:
            {
                'results': [...],
                'metadata': {
                    'query': str,
                    'stage_count': int,
                    'errors': [...]
                }
            }

    Example:
        from imem.storage import create_store
        from imem.compose.orchestrator import compose

        store = create_store('sqlite', {'project_root': '...'})
        config = {
            'search': {'mode': 'metadata', 'filters': {'phase': 'develop'}}
        }

        results = compose('authentication patterns', config, store)
    """
    # Build pipeline from config
    chain = build_chain(config, store)

    # Create initial context
    ctx = RetrievalContext(
        query=query,
        config=config
    )

    # Execute chain
    result_ctx = chain.execute(ctx)

    # Format response
    return {
        'results': result_ctx.results,
        'metadata': {
            'query': query,
            'stage_count': len(chain.processors),
            **result_ctx.metadata
        }
    }
