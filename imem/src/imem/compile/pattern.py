"""PatternExtractor - Extract pattern layers at compile time

EPIC 7: Extracts pattern layer from implementation content during indexing.

PatternExtractor is a COMPILE domain module that runs after parsing,
before storage. It calls the pattern extraction service to abstract
implementation details into reusable patterns.

The pattern_layer field is consumed by STRUCTURE/FlipModule to serve
abstracted content when implementation becomes stale.

Philosophy: "Obsolescence is promotion to abstraction."
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from .pattern_client import PatternClient, create_pattern_client, PatternResponse

logger = logging.getLogger(__name__)


class PatternExtractor:
    """Extract pattern layers from implementation chunks

    Called during Router.index() after parsing, populates pattern_layer
    field on chunks before storage.

    Attributes:
        client: PatternClient for service calls
        min_content_length: Minimum content length for extraction (default 50)
    """

    name = "pattern"

    def __init__(
        self,
        client: Optional[PatternClient] = None,
        min_content_length: int = 50,
    ):
        """Initialize PatternExtractor

        Args:
            client: PatternClient (default: auto-created from env)
            min_content_length: Skip chunks shorter than this
        """
        self.client = client or create_pattern_client()
        self.min_content_length = min_content_length

    @property
    def is_available(self) -> bool:
        """Check if pattern extraction is available"""
        return self.client.is_available

    def applies(self, chunk: Dict[str, Any]) -> bool:
        """Check if chunk should have pattern extracted

        Applies to chunks with:
        - Content field present
        - Content longer than min_content_length

        Args:
            chunk: Chunk to check

        Returns:
            True if pattern extraction should run
        """
        content = chunk.get('content', '')
        return bool(content and len(content) >= self.min_content_length)

    async def execute(
        self,
        chunk: Dict[str, Any],
    ) -> None:
        """Extract pattern for single chunk (mutates chunk)

        Sets chunk['pattern_layer'] to extracted pattern.
        On failure, leaves pattern_layer unset (graceful degradation).

        Args:
            chunk: Chunk dict (mutated in place)
        """
        if not self.applies(chunk):
            return

        try:
            response = await self.client.extract_pattern(
                chunk_id=chunk['id'],
                content=chunk['content'],
            )
            if response.pattern_layer and not response.error:
                chunk['pattern_layer'] = response.pattern_layer
            elif response.error:
                logger.debug(f"Pattern extraction failed for {chunk['id']}: {response.error}")
        except Exception as e:
            logger.warning(f"Pattern extraction error for {chunk['id']}: {e}")

    async def execute_batch(
        self,
        chunks: List[Dict[str, Any]],
    ) -> None:
        """Extract patterns for batch of chunks (mutates chunks)

        More efficient than calling execute() individually.
        Uses client's bounded concurrency.

        Args:
            chunks: List of chunk dicts (mutated in place)
        """
        # Filter applicable chunks
        applicable = [c for c in chunks if self.applies(c)]
        if not applicable:
            logger.debug("No chunks applicable for pattern extraction")
            return

        logger.info(f"Extracting patterns for {len(applicable)} chunks...")

        # Batch extraction
        responses = await self.client.extract_batch(applicable)

        # Map responses back to chunks
        response_map = {r.id: r for r in responses}
        for chunk in applicable:
            response = response_map.get(chunk['id'])
            if response and response.pattern_layer and not response.error:
                chunk['pattern_layer'] = response.pattern_layer

        # Log results
        success_count = sum(1 for c in applicable if c.get('pattern_layer'))
        logger.info(f"Pattern extraction: {success_count}/{len(applicable)} chunks enriched")

    async def close(self):
        """Close client connection"""
        if self.client:
            await self.client.close()


class NoOpPatternExtractor:
    """No-op pattern extractor for graceful degradation"""

    name = "noop_pattern"

    @property
    def is_available(self) -> bool:
        return False

    def applies(self, chunk: Dict[str, Any]) -> bool:
        return False

    async def execute(self, chunk: Dict[str, Any]) -> None:
        pass

    async def execute_batch(self, chunks: List[Dict[str, Any]]) -> None:
        pass

    async def close(self):
        pass


def create_pattern_extractor(
    enabled: bool = True,
    api_url: Optional[str] = None,
) -> PatternExtractor:
    """Factory for pattern extractor

    Args:
        enabled: Whether to enable pattern extraction
        api_url: Optional service URL override

    Returns:
        PatternExtractor or NoOpPatternExtractor
    """
    if not enabled:
        return NoOpPatternExtractor()

    client = create_pattern_client(api_url=api_url, enabled=enabled)
    if not client.is_available:
        return NoOpPatternExtractor()

    return PatternExtractor(client=client)


__all__ = [
    'PatternExtractor',
    'NoOpPatternExtractor',
    'create_pattern_extractor',
]
