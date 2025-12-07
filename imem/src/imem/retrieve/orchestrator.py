"""Retrieve orchestrator - Build and execute retrieval pipelines via processor chain

EPIC 5: Centrality & Ranking

Replaces hardcoded pipeline with declarative chain configuration.
Enables config-driven composition, reorderable stages, independent testing.

Flow: search → discovery → centrality → ranking

Centrality is computed at query-time on result chunks, then RankingModule
combines validity (stored) × centrality (computed) × recency (timestamp).
"""

from typing import Dict, Any, List, Optional, TYPE_CHECKING
import logging

from ..core import Chain, RetrievalContext
from ..storage import VectorStore
from ..storage.sqlite_backend import SQLiteVectorStore
from .processors import SearchProcessor, MultiPhaseRanker, RankingPhase, RankingModule
from .processors.discovery import DiscoveryProcessor
from .centrality import CentralityComputer, create_centrality_computer

if TYPE_CHECKING:
    from ..context import QueryContext

logger = logging.getLogger(__name__)


def build_chain(config: Dict[str, Any], store: VectorStore) -> Chain:
    """Build processor chain from config

    Args:
        config: Pipeline configuration with keys:
            - search: {mode: 'metadata'|'semantic', filters: {...}}
            - discovery: {siblings: bool, temporal: bool, genealogy: bool}
            - ranking: {phases: [{name, scorer, rerank_count}]}
        store: VectorStore backend (SQLite)

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

    # 2. Discovery processor (optional) - enrich results with related chunks
    discovery_config = config.get('discovery')
    if discovery_config and isinstance(store, SQLiteVectorStore):
        processors.append(DiscoveryProcessor(store, discovery_config))

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
            "Implement at imem/retrieve/processors/ranking.py"
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
    store: VectorStore,
    centrality_computer: Optional[CentralityComputer] = None,
    ranking_module: Optional[RankingModule] = None,
    vector_storage=None,
) -> Dict[str, Any]:
    """Execute retrieval pipeline via processor chain

    EPIC 5: Centrality & Ranking

    Flow: search → discovery → centrality → ranking

    Args:
        query: Search query text
        config: Pipeline configuration
        store: VectorStore backend
        centrality_computer: Optional CentralityComputer for importance scoring
        ranking_module: Optional RankingModule for final ranking
        vector_storage: Optional VectorStorage for sibling density (Tier 3)

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
        from imem.retrieve import compose

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

    # Execute chain (search → discovery)
    result_ctx = chain.execute(ctx)

    # Preserve similarity score before ranking (similarity comes from semantic search)
    # RankingModule will add 'rank' but we want to keep original similarity visible
    for chunk in result_ctx.results:
        if 'similarity' not in chunk:
            chunk['similarity'] = chunk.get('score', 0.5)

    # EPIC 5: Compute centrality for each result
    if centrality_computer is not None and result_ctx.results:
        # Create a mock QueryContext for signal evaluation
        from ..context import Infrastructure, QueryContext
        try:
            # If we have SQLite store, get db from it
            # SQLiteVectorStore wraps SQLiteStore in .store attribute
            db = getattr(store, 'store', None) or getattr(store, '_store', None) or getattr(store, 'db', None)
            if db is None and hasattr(store, 'conn'):
                db = store

            if db is not None:
                # Create minimal infrastructure for centrality
                class MinimalInfra:
                    def __init__(self, db):
                        self.db = db
                        self.git = None
                        self.config = {}

                mock_ctx = QueryContext(
                    infrastructure=MinimalInfra(db),
                    query=config,
                    results=result_ctx.results,
                    metadata={},
                )

                for chunk in result_ctx.results:
                    centrality = centrality_computer.compute(chunk, mock_ctx)
                    chunk['centrality'] = centrality

                logger.debug(f"Computed centrality for {len(result_ctx.results)} chunks")
        except Exception as e:
            logger.warning(f"Centrality computation failed: {e}")

    # EPIC 5: Apply final ranking (validity × centrality × recency)
    if ranking_module is not None and result_ctx.results:
        try:
            result_ctx.results = ranking_module.rank(result_ctx.results, ctx)
            logger.debug(f"Applied ranking to {len(result_ctx.results)} results")
        except Exception as e:
            logger.warning(f"Ranking failed: {e}")

    # Enforce limit after discovery expansion and ranking
    # Discovery may expand beyond original limit; this ensures final count matches request
    limit = config.get('limit')
    if limit and result_ctx.results:
        result_ctx.results = result_ctx.results[:limit]

    # Format response
    return {
        'results': result_ctx.results,
        'metadata': {
            'query': query,
            'stage_count': len(chain.processors),
            **result_ctx.metadata
        }
    }
