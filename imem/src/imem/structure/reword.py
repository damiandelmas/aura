"""RewordModule - Language adjustment for uncertainty and consistency

EPIC 6: Adjust language for low-validity and superseded content.

RewordModule is the third stage in the STRUCTURE pipeline. It:
1. Adds hedging for low-validity chunks ("may be outdated")
2. Adds temporal framing for superseded content ("previously...")
3. Optionally uses LLM for sophisticated rewording (gated)

Raw chunk content may need adjustment before presentation. Low-validity
content should hedge, superseded content should be framed as historical.
"""

import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from ..protocols import Module

if TYPE_CHECKING:
    from ..context import QueryContext

logger = logging.getLogger(__name__)


# ============================================================================
# Hedging Templates
# ============================================================================

# Strong hedging for low validity (< 0.3)
STRONG_HEDGE_PREFIX = "**⚠️ May be outdated:** "

# Moderate hedging for medium-low validity (0.3 - 0.5)
MODERATE_HEDGE_PREFIX = "*Note: This may have changed.* "

# Superseded framing
SUPERSEDED_PREFIX = "*Previously:* "

# High centrality highlight
CENTRALITY_MARKER = "**[Key Insight]** "


class RewordModule(Module):
    """Adjust language for uncertainty and consistency

    Adds hedging markers to low-validity content and temporal framing
    to superseded content. No LLM required — uses static prefixes.

    Future: LLM integration for sophisticated rewording (gated by config).

    Attributes:
        use_llm: Whether to use LLM for rewording (default False)
        strong_threshold: Validity below this gets strong hedging (default 0.3)
        moderate_threshold: Validity below this gets moderate hedging (default 0.5)
    """

    def __init__(
        self,
        use_llm: bool = False,
        strong_threshold: float = 0.3,
        moderate_threshold: float = 0.5,
    ):
        """Initialize RewordModule

        Args:
            use_llm: Enable LLM-based rewording (default False)
            strong_threshold: Validity below this gets strong hedging
            moderate_threshold: Validity below this gets moderate hedging
        """
        self.use_llm = use_llm
        self.strong_threshold = strong_threshold
        self.moderate_threshold = moderate_threshold

    @property
    def name(self) -> str:
        return "reword"

    def execute(
        self,
        chunks: List[Dict[str, Any]],
        context: 'QueryContext'
    ) -> List[Dict[str, Any]]:
        """Execute language adjustment

        For each chunk:
        1. Check flags for needs_hedging, is_superseded, high_centrality
        2. Apply appropriate prefixes/markers
        3. Record what was applied in _reword metadata

        Args:
            chunks: Chunks from FlipModule
            context: Query context

        Returns:
            Chunks with adjusted language
        """
        if not chunks:
            return []

        result = []
        hedged_count = 0
        superseded_count = 0

        for chunk in chunks:
            reworded = self._reword_chunk(chunk)
            result.append(reworded)

            # Track statistics
            reword_info = reworded.get('_reword', {})
            if reword_info.get('hedged'):
                hedged_count += 1
            if reword_info.get('superseded_framing'):
                superseded_count += 1

        if hedged_count > 0 or superseded_count > 0:
            logger.info(
                f"RewordModule: {hedged_count} hedged, "
                f"{superseded_count} superseded-framed"
            )

        return result

    def _reword_chunk(self, chunk: Dict[str, Any]) -> Dict[str, Any]:
        """Reword a single chunk

        Applies hedging and framing based on flags and validity.

        Args:
            chunk: Chunk to reword

        Returns:
            Reworded chunk with _reword metadata
        """
        content = chunk.get('content', '')
        validity = chunk.get('validity', 0.5)
        flags = chunk.get('_flags', {})

        reword_info = {
            'hedged': False,
            'hedge_strength': None,
            'superseded_framing': False,
            'centrality_marked': False,
            'prefixes_applied': [],
        }

        new_content = content
        prefixes = []

        # 1. Check for superseded framing first (before hedging)
        if flags.get('is_superseded', False):
            prefixes.append(SUPERSEDED_PREFIX)
            reword_info['superseded_framing'] = True

        # 2. Apply hedging based on validity
        if flags.get('needs_hedging', False):
            if validity < self.strong_threshold:
                prefixes.append(STRONG_HEDGE_PREFIX)
                reword_info['hedged'] = True
                reword_info['hedge_strength'] = 'strong'
            elif validity < self.moderate_threshold:
                prefixes.append(MODERATE_HEDGE_PREFIX)
                reword_info['hedged'] = True
                reword_info['hedge_strength'] = 'moderate'

        # 3. Add centrality marker for high-authority chunks
        if flags.get('high_centrality', False):
            prefixes.append(CENTRALITY_MARKER)
            reword_info['centrality_marked'] = True

        # Apply prefixes (in order: centrality, then superseded, then hedging)
        # Reverse because we want centrality first visually
        if prefixes:
            # Order: [CENTRALITY] [SUPERSEDED] [HEDGING] content
            ordered_prefixes = []
            if CENTRALITY_MARKER in prefixes:
                ordered_prefixes.append(CENTRALITY_MARKER)
            if SUPERSEDED_PREFIX in prefixes:
                ordered_prefixes.append(SUPERSEDED_PREFIX)
            if STRONG_HEDGE_PREFIX in prefixes:
                ordered_prefixes.append(STRONG_HEDGE_PREFIX)
            elif MODERATE_HEDGE_PREFIX in prefixes:
                ordered_prefixes.append(MODERATE_HEDGE_PREFIX)

            prefix_str = ''.join(ordered_prefixes)
            new_content = prefix_str + content
            reword_info['prefixes_applied'] = ordered_prefixes

        return {
            **chunk,
            'content': new_content,
            '_reword': reword_info,
        }


class LLMRewordModule(Module):
    """LLM-powered reword module for sophisticated language adjustment

    NOT IMPLEMENTED - placeholder for future EPIC.

    Would use LLM to:
    - Reword with context-aware hedging
    - Resolve contradictions between chunks
    - Normalize terminology
    """

    def __init__(self, llm_provider: Optional[Any] = None):
        self.llm = llm_provider

    @property
    def name(self) -> str:
        return "llm_reword"

    def execute(
        self,
        chunks: List[Dict[str, Any]],
        context: 'QueryContext'
    ) -> List[Dict[str, Any]]:
        # Fallback to static rewording
        static_reword = RewordModule()
        return static_reword.execute(chunks, context)


class NoOpRewordModule(Module):
    """No-op reword module that returns chunks unchanged"""

    @property
    def name(self) -> str:
        return "noop_reword"

    def execute(
        self,
        chunks: List[Dict[str, Any]],
        context: 'QueryContext'
    ) -> List[Dict[str, Any]]:
        return chunks


__all__ = ['RewordModule', 'LLMRewordModule', 'NoOpRewordModule']
