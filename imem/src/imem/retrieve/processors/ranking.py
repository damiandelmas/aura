"""Multi-phase ranking processor (Vespa pattern)

Progressive refinement through ranking phases.
Limits expensive operations (PageRank, graph centrality) to top-k finalists.

EPIC 5: RankingModule - Final rank computation
Formula: rank = validity × w_v + centrality × w_c + recency × w_r

Recency decay: recency = 1.0 / (1 + days_old / 30)
Default weights: validity=0.4, centrality=0.3, recency=0.3

Performance: 25x fewer graph computations vs single-pass ranking.
"""

from typing import Callable, Optional, List, Dict, Any
from datetime import datetime
import logging

from ...core.chain import Processor, RetrievalContext

logger = logging.getLogger(__name__)


# Default weights for ranking formula
DEFAULT_RANKING_WEIGHTS = {
    'validity': 0.4,
    'centrality': 0.3,
    'recency': 0.3,
}


def compute_recency(timestamp: Optional[str], half_life_days: float = 30.0) -> float:
    """Compute recency score from timestamp

    Formula: recency = 1.0 / (1 + days_old / half_life)

    Args:
        timestamp: ISO format timestamp string
        half_life_days: Days at which recency = 0.5

    Returns:
        Recency score (0.0-1.0)
    """
    if not timestamp:
        return 0.5  # Neutral default

    try:
        # Parse timestamp (try multiple formats)
        ts = None
        for fmt in ['%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d']:
            try:
                ts = datetime.strptime(timestamp[:19], fmt)
                break
            except ValueError:
                continue

        if ts is None:
            return 0.5

        # Calculate days old
        now = datetime.now()
        days_old = (now - ts).days

        # Recency formula: 1 / (1 + days_old / half_life)
        recency = 1.0 / (1 + days_old / half_life_days)
        return max(0.0, min(1.0, recency))

    except Exception:
        return 0.5


def compute_rank(
    validity: float,
    centrality: float,
    recency: float,
    weights: Optional[Dict[str, float]] = None,
) -> float:
    """Compute final rank score

    Formula: rank = validity × w_v + centrality × w_c + recency × w_r

    Args:
        validity: Validity score (0.0-1.0)
        centrality: Centrality score (0.0-1.0)
        recency: Recency score (0.0-1.0)
        weights: Optional weight overrides

    Returns:
        Rank score (0.0-1.0)
    """
    w = weights or DEFAULT_RANKING_WEIGHTS
    w_v = w.get('validity', DEFAULT_RANKING_WEIGHTS['validity'])
    w_c = w.get('centrality', DEFAULT_RANKING_WEIGHTS['centrality'])
    w_r = w.get('recency', DEFAULT_RANKING_WEIGHTS['recency'])

    rank = (validity * w_v) + (centrality * w_c) + (recency * w_r)
    return max(0.0, min(1.0, rank))


class RankingModule:
    """EPIC 5: Final rank computation

    Combines validity (is it true?), centrality (is it important?),
    and recency (is it current?) into a single rank score.

    Formula: rank = validity × w_v + centrality × w_c + recency × w_r

    Default weights: validity=0.4, centrality=0.3, recency=0.3
    Supports query-time weight override.

    Usage:
        module = RankingModule()
        ranked_chunks = module.rank(chunks, context)
    """

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        """Initialize RankingModule

        Args:
            weights: Default weight configuration
        """
        self.default_weights = weights or DEFAULT_RANKING_WEIGHTS

    def rank(
        self,
        chunks: List[Dict[str, Any]],
        context: Any,  # QueryContext or similar
    ) -> List[Dict[str, Any]]:
        """Compute rank for each chunk and sort

        Args:
            chunks: List of chunks with validity, centrality, timestamp
            context: Query context (may contain weight overrides)

        Returns:
            Chunks sorted by rank (highest first), with rank field set
        """
        # Get weights (config override > default)
        weights = self.default_weights.copy()
        if hasattr(context, 'config') and isinstance(context.config, dict):
            config_weights = context.config.get('weights', {})
            weights.update(config_weights)

        # Compute rank for each chunk
        for chunk in chunks:
            validity = chunk.get('validity', 0.5)
            centrality = chunk.get('centrality', 0.5)

            # Get timestamp from metadata or direct field
            timestamp = chunk.get('timestamp')
            if not timestamp and 'metadata' in chunk:
                timestamp = chunk.get('metadata', {}).get('timestamp')

            recency = compute_recency(timestamp)
            rank = compute_rank(validity, centrality, recency, weights)

            chunk['rank'] = rank
            chunk['recency'] = recency  # Store for debugging

        # Sort by rank descending
        ranked = sorted(chunks, key=lambda c: c.get('rank', 0), reverse=True)

        logger.debug(
            f"RankingModule: ranked {len(ranked)} chunks "
            f"(weights: v={weights['validity']}, c={weights['centrality']}, r={weights['recency']})"
        )

        return ranked


class NoOpRankingModule(RankingModule):
    """No-op ranking that returns chunks unchanged"""

    def rank(
        self,
        chunks: List[Dict[str, Any]],
        context: Any,
    ) -> List[Dict[str, Any]]:
        return chunks


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


__all__ = [
    # EPIC 5: Ranking formula
    'RankingModule',
    'NoOpRankingModule',
    'compute_rank',
    'compute_recency',
    'DEFAULT_RANKING_WEIGHTS',
    # Multi-phase ranking
    'RankingPhase',
    'MultiPhaseRanker',
    # Scorer functions
    'score_by_recency',
    'score_by_score',
]
