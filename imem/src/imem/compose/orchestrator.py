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
        raise NotImplementedError(
            "SiblingDiscovery processor not yet implemented. "
            "Remove 'discovery.siblings' from config or implement processor at "
            "imem/compose/processors/discovery.py"
        )

    if discovery_config.get('temporal'):
        raise NotImplementedError(
            "TemporalDiscovery processor not yet implemented. "
            "Remove 'discovery.temporal' from config or implement processor at "
            "imem/compose/processors/discovery.py"
        )

    if discovery_config.get('genealogy'):
        raise NotImplementedError(
            "GenealogyDiscovery processor not yet implemented. "
            "Remove 'discovery.genealogy' from config or implement processor at "
            "imem/compose/processors/discovery.py"
        )

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
        phase_name: Name of ranking phase ('recency', 'metadata', 'authority')

    Returns:
        Scorer function compatible with RankingPhase

    Raises:
        ValueError: If scorer name is unknown
    """
    if phase_name == 'recency':
        def recency_scorer(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            """Sort by timestamp (most recent first)"""
            return sorted(
                results,
                key=lambda r: r.get('metadata', {}).get('timestamp', ''),
                reverse=True
            )
        return recency_scorer

    elif phase_name == 'metadata':
        # Identity scorer (no reordering, metadata filtering handled by SearchProcessor)
        def metadata_scorer(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            return results
        return metadata_scorer

    elif phase_name == 'authority':
        # TODO: Implement PageRank or reference counting scorer
        logger.warning(
            "Authority scorer not yet implemented. Using identity (no reordering). "
            "Implement at imem/compose/processors/ranking.py"
        )
        def identity_scorer(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            return results
        return identity_scorer

    else:
        raise ValueError(
            f"Unknown scorer: '{phase_name}'. "
            f"Available: 'recency', 'metadata', 'authority'"
        )


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
