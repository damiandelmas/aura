"""CurateModule - Editorial selection for presentation

EPIC 6: Select and order chunks for presentation.

CurateModule is the first stage in the STRUCTURE pipeline. It performs:
1. Filtering: Drop chunks below validity threshold
2. Deduplication: Keep higher-ranked duplicates
3. Ordering: Sort by rank descending
4. Flagging: Mark chunks for hedging/highlighting

Not everything retrieved should be shown. This is editorial judgment
encoded in code.
"""

import logging
from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING

from ..protocols import Module

if TYPE_CHECKING:
    from ..context import QueryContext

logger = logging.getLogger(__name__)


class CurateModule(Module):
    """Select and order chunks for presentation

    Editorial selection based on validity, centrality, and rank scores.
    Low-validity chunks get flagged for hedging rather than dropped.
    High-centrality chunks get highlighted as authoritative.

    Attributes:
        min_validity: Minimum validity to include (default 0.3)
        max_results: Maximum chunks to return (default 20)
        hedging_threshold: Validity below this triggers hedging flag (default 0.5)
        centrality_threshold: Centrality above this triggers highlight (default 0.7)
    """

    def __init__(
        self,
        min_validity: float = 0.3,
        max_results: int = 20,
        hedging_threshold: float = 0.5,
        centrality_threshold: float = 0.7,
    ):
        """Initialize CurateModule

        Args:
            min_validity: Minimum validity threshold (chunks below are dropped)
            max_results: Maximum number of results to return
            hedging_threshold: Validity threshold for needs_hedging flag
            centrality_threshold: Centrality threshold for high_centrality flag
        """
        self.min_validity = min_validity
        self.max_results = max_results
        self.hedging_threshold = hedging_threshold
        self.centrality_threshold = centrality_threshold

    @property
    def name(self) -> str:
        return "curate"

    def execute(
        self,
        chunks: List[Dict[str, Any]],
        context: 'QueryContext'
    ) -> List[Dict[str, Any]]:
        """Execute curation pipeline

        Steps:
        1. Filter by validity threshold (drop contradicted)
        2. Deduplicate (prefer higher rank)
        3. Order by rank
        4. Limit to max_results
        5. Flag chunks for hedging/highlighting

        Args:
            chunks: Ranked chunks from RETRIEVE
            context: Query context

        Returns:
            Curated chunks with _flags metadata
        """
        if not chunks:
            return []

        # Get config overrides from context
        # Check both 'max_results' and 'limit' for flexibility
        query_config = getattr(context, 'query', {}) or {}
        max_results = query_config.get('max_results') or query_config.get('limit', self.max_results)

        # 1. Filter by validity threshold
        filtered = self._filter_by_validity(chunks)
        logger.debug(f"CurateModule: {len(chunks)} → {len(filtered)} after validity filter")

        # 2. Order by rank descending (should already be sorted, but ensure)
        ordered = self._order_by_rank(filtered)

        # 3. Limit to max_results
        limited = ordered[:max_results]

        # 4. Deduplicate (opt-in, off by default)
        # Dedup AFTER limit so it only operates on final result set
        enable_dedup = query_config.get('dedupe', False)
        if enable_dedup:
            deduped = self._deduplicate(limited)
            logger.debug(f"CurateModule: {len(limited)} → {len(deduped)} after dedup")
        else:
            deduped = limited

        # 5. Add presentation flags
        flagged = self._add_flags(deduped)

        logger.info(f"CurateModule: {len(chunks)} input → {len(flagged)} curated")

        return flagged

    def _filter_by_validity(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter chunks below validity threshold

        Drops chunks with:
        - validity < min_validity
        - git_status == 'contradicted'

        Args:
            chunks: Input chunks

        Returns:
            Filtered chunks
        """
        result = []
        for chunk in chunks:
            validity = chunk.get('validity', 0.5)
            git_status = chunk.get('git_status', 'unvalidated')

            # Always drop contradicted chunks
            if git_status == 'contradicted':
                continue

            # Drop below threshold
            if validity < self.min_validity:
                continue

            result.append(chunk)

        return result

    def _deduplicate(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicate chunks, keeping higher-ranked duplicates

        Deduplication key: (section_name, file_directory)
        This catches chunks from same file/section that were re-indexed.

        Args:
            chunks: Input chunks

        Returns:
            Deduplicated chunks
        """
        seen: Dict[str, Dict[str, Any]] = {}

        for chunk in chunks:
            # Build dedup key
            section_name = chunk.get('section_name', '')
            file_path = chunk.get('file_path', '')

            # Use file_path + section_name as key
            # This dedupes same section from same file (re-indexed)
            # but keeps sections from different files
            key = f"{file_path}:{section_name}"

            if key not in seen:
                seen[key] = chunk
            else:
                # Keep higher-ranked chunk
                existing_rank = seen[key].get('rank', 0.5)
                current_rank = chunk.get('rank', 0.5)
                if current_rank > existing_rank:
                    seen[key] = chunk

        return list(seen.values())

    def _order_by_rank(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Order chunks by rank descending

        Args:
            chunks: Input chunks

        Returns:
            Sorted chunks (highest rank first)
        """
        return sorted(
            chunks,
            key=lambda c: c.get('rank', 0.5),
            reverse=True
        )

    def _add_flags(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Add presentation flags to chunks

        Flags:
        - needs_hedging: validity < hedging_threshold
        - high_centrality: centrality > centrality_threshold
        - is_superseded: git_status == 'superseded'

        Args:
            chunks: Input chunks

        Returns:
            Chunks with _flags metadata
        """
        result = []
        for chunk in chunks:
            validity = chunk.get('validity', 0.5)
            centrality = chunk.get('centrality', 0.5)
            git_status = chunk.get('git_status', 'unvalidated')

            flags = {
                'needs_hedging': validity < self.hedging_threshold,
                'high_centrality': centrality > self.centrality_threshold,
                'is_superseded': git_status == 'superseded',
            }

            # Add flags to chunk
            flagged_chunk = {**chunk, '_flags': flags}
            result.append(flagged_chunk)

        return result


class NoOpCurateModule(Module):
    """No-op curate module that returns chunks unchanged"""

    @property
    def name(self) -> str:
        return "noop_curate"

    def execute(
        self,
        chunks: List[Dict[str, Any]],
        context: 'QueryContext'
    ) -> List[Dict[str, Any]]:
        return chunks


__all__ = ['CurateModule', 'NoOpCurateModule']
