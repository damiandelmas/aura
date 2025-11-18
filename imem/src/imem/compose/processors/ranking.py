"""Multi-phase ranking processor (Vespa pattern)

Progressive refinement through ranking phases.
Limits expensive operations (PageRank, graph centrality) to top-k finalists.

Performance: 25x fewer graph computations vs single-pass ranking.
"""

from typing import Callable, Optional, List, Dict, Any
import logging

from ...core.chain import Processor, RetrievalContext

logger = logging.getLogger(__name__)


class RankingPhase:
    """Single ranking phase with scorer and optional top-k limit

    Example phases:
        Phase 1: Metadata filter (1000s → 100 candidates)
        Phase 2: Reference counting (100 → 20 finalists)
        Phase 3: Graph centrality (20 → 10 final) - expensive, on finalists only
    """

    def __init__(
        self,
        name: str,
        scorer: Callable[[List[Dict[str, Any]]], List[Dict[str, Any]]],
        rerank_count: Optional[int] = None
    ):
        """Initialize ranking phase

        Args:
            name: Phase name (for logging/debugging)
            scorer: Function that takes results and returns re-ranked results
            rerank_count: Max results to pass to next phase (top-k cutoff)
                         If None, pass all results
        """
        self.name = name
        self.scorer = scorer
        self.rerank_count = rerank_count


class MultiPhaseRanker(Processor):
    """Progressive refinement through multiple ranking phases

    Vespa pattern: Apply cheap filters first, expensive operations last.

    Example pipeline:
        Phase 1: Metadata scoring (cheap, filters 1000s → 100)
        Phase 2: Reference counting (moderate, SQL query, 100 → 20)
        Phase 3: PageRank (expensive, graph computation, 20 → 10)

    Performance benefit:
        Without multi-phase: PageRank on 500 chunks = expensive
        With multi-phase: PageRank on 20 chunks = 25x cheaper

    Example:
        ranker = MultiPhaseRanker([
            RankingPhase("metadata", filter_by_recency, rerank_count=100),
            RankingPhase("references", count_references, rerank_count=20),
            RankingPhase("authority", apply_pagerank, rerank_count=10)
        ])

        ctx = ranker.process(ctx)  # 500 results → 10 final results
    """

    def __init__(self, phases: List[RankingPhase]):
        """Initialize multi-phase ranker

        Args:
            phases: List of ranking phases (executed in order)
        """
        self.phases = phases

    def process(self, ctx: RetrievalContext) -> RetrievalContext:
        """Execute multi-phase ranking

        Args:
            ctx: Context with results to rank

        Returns:
            Context with re-ranked and filtered results
        """
        if not ctx.results:
            return ctx

        initial_count = len(ctx.results)
        phase_metadata = []

        for phase in self.phases:
            try:
                # Apply top-k limit before scoring (saves computation)
                if phase.rerank_count and len(ctx.results) > phase.rerank_count:
                    ctx.results = ctx.results[:phase.rerank_count]

                before_count = len(ctx.results)

                # Score and re-rank
                ctx.results = phase.scorer(ctx.results)

                after_count = len(ctx.results)

                # Log phase execution
                phase_info = {
                    'name': phase.name,
                    'input_count': before_count,
                    'output_count': after_count,
                    'rerank_limit': phase.rerank_count
                }
                phase_metadata.append(phase_info)

                logger.debug(
                    f"Ranking phase '{phase.name}': "
                    f"{before_count} → {after_count} results"
                )

            except Exception as e:
                logger.error(f"Ranking phase '{phase.name}' failed: {e}")
                # Continue with unranked results
                phase_metadata.append({
                    'name': phase.name,
                    'error': str(e)
                })

        # Add ranking metadata
        ctx.metadata['ranking'] = {
            'initial_count': initial_count,
            'final_count': len(ctx.results),
            'phases': phase_metadata
        }

        logger.info(
            f"Multi-phase ranking: {initial_count} → {len(ctx.results)} results "
            f"({len(self.phases)} phases)"
        )

        return ctx


# Example scorer functions (reference implementations)

def score_by_recency(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Phase 1: Score by timestamp (cheap, fast)"""
    return sorted(
        results,
        key=lambda r: r.get('timestamp', ''),
        reverse=True
    )


def score_by_score(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Phase 1: Score by existing score field (from vector search)"""
    return sorted(
        results,
        key=lambda r: r.get('score', 0.0),
        reverse=True
    )


# TODO: Implement reference counting scorer (Phase 2)
# def count_references(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
#     """Phase 2: Count how many chunks reference each result (SQL query)"""
#     # Query: SELECT id, COUNT(*) FROM chunks WHERE content LIKE '%chunk_id%' GROUP BY id
#     pass

# TODO: Implement PageRank scorer (Phase 3)
# def apply_pagerank(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
#     """Phase 3: Graph centrality (expensive, run on finalists only)"""
#     # Use NetworkX to compute PageRank on result subgraph
#     pass
