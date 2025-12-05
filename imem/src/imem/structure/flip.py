"""FlipModule - Layer selection for presentation

EPIC 6: Serve implementation or pattern layer based on chunk validity state.

FlipModule is the second stage in the STRUCTURE pipeline. It decides which
layer to serve for each chunk:
- Implementation layer: Full detail, current specifics
- Pattern layer: Language-agnostic abstraction

Superseded chunks serve pattern layer — the insight without stale specifics.
This prevents AI overfitting on outdated code while preserving wisdom.

Philosophy: "Obsolescence is promotion to abstraction."
"""

import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from ..protocols import Module

if TYPE_CHECKING:
    from ..context import QueryContext
    from ..storage.sqlite import SQLiteStore

logger = logging.getLogger(__name__)


class FlipModule(Module):
    """Serve implementation or pattern layer based on validity state

    Superseded chunks still have value — as abstracted patterns, not stale
    specifics. FlipModule decides which layer to serve:
    - High-validity chunks → implementation layer (current truth)
    - Low-validity/superseded chunks → pattern layer (abstraction)

    Pattern lookup requires db access to find pattern_layer content.
    When pattern_layer is unavailable, gracefully degrades to implementation.

    Attributes:
        db: SQLiteStore for pattern lookup (optional)
        validity_threshold: Below this, prefer pattern layer (default 0.3)
    """

    def __init__(
        self,
        db: Optional['SQLiteStore'] = None,
        validity_threshold: float = 0.3,
    ):
        """Initialize FlipModule

        Args:
            db: SQLiteStore for pattern lookup (None = no pattern lookup)
            validity_threshold: Validity below this triggers pattern serving
        """
        self.db = db
        self.validity_threshold = validity_threshold

    @property
    def name(self) -> str:
        return "flip"

    def execute(
        self,
        chunks: List[Dict[str, Any]],
        context: 'QueryContext'
    ) -> List[Dict[str, Any]]:
        """Execute layer selection for each chunk

        For each chunk:
        1. Check if should flip to pattern layer
        2. If yes and pattern available, substitute content
        3. Mark chunk with _layer metadata

        Args:
            chunks: Curated chunks from CurateModule
            context: Query context

        Returns:
            Chunks with layer selection applied
        """
        if not chunks:
            return []

        result = []
        flipped_count = 0

        for chunk in chunks:
            should_flip = self._should_flip(chunk)

            if should_flip:
                # Try to get pattern layer
                pattern = self._get_pattern(chunk)
                if pattern:
                    flipped_chunk = self._apply_pattern(chunk, pattern)
                    flipped_chunk['_layer'] = 'pattern'
                    result.append(flipped_chunk)
                    flipped_count += 1
                else:
                    # No pattern available, keep implementation
                    chunk['_layer'] = 'implementation'
                    result.append(chunk)
            else:
                # Keep implementation layer
                chunk['_layer'] = 'implementation'
                result.append(chunk)

        if flipped_count > 0:
            logger.info(f"FlipModule: {flipped_count}/{len(chunks)} chunks flipped to pattern layer")

        return result

    def _should_flip(self, chunk: Dict[str, Any]) -> bool:
        """Determine if chunk should serve pattern layer

        Flip to pattern if:
        - use_pattern_file flag is set
        - OR validity < threshold
        - OR is_superseded flag is set

        Args:
            chunk: Chunk to evaluate

        Returns:
            True if should serve pattern layer
        """
        # Check explicit flag
        if chunk.get('use_pattern_file', False):
            return True

        # Check validity threshold
        validity = chunk.get('validity', 0.5)
        if validity < self.validity_threshold:
            return True

        # Check presentation flags
        flags = chunk.get('_flags', {})
        if flags.get('is_superseded', False):
            return True

        return False

    def _get_pattern(self, chunk: Dict[str, Any]) -> Optional[str]:
        """Look up pattern layer content for chunk

        Pattern lookup strategy:
        1. Check chunk's own pattern_layer field (EPIC 7 populates this)
        2. Query by header_path + layer='pattern' (future)

        Args:
            chunk: Chunk needing pattern layer

        Returns:
            Pattern layer content if available, None otherwise
        """
        # Strategy 1: Check chunk's own pattern_layer field
        # EPIC 7 (Pattern Extraction) populates this at index time
        pattern_layer = chunk.get('pattern_layer')
        if pattern_layer:
            return pattern_layer

        # Strategy 2: Query database for pattern chunk
        # This is for when patterns are stored as separate chunks
        if self.db is not None:
            try:
                pattern_chunk = self._query_pattern_chunk(chunk)
                if pattern_chunk:
                    return pattern_chunk.get('content')
            except Exception as e:
                logger.debug(f"Pattern lookup failed: {e}")

        # No pattern available - graceful degradation
        return None

    def _query_pattern_chunk(self, chunk: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Query database for pattern layer chunk

        Looks for a chunk with:
        - Same header_path (section lineage)
        - layer = 'pattern'

        Args:
            chunk: Source chunk

        Returns:
            Pattern chunk if found, None otherwise
        """
        # Build query for pattern chunk
        # Pattern files follow naming: {filename}.pattern.md
        file_path = chunk.get('file_path', '')
        if not file_path:
            return None

        # Try to find corresponding pattern file
        # Example: 251029_auth.md → 251029_auth.pattern.md
        import os
        base, ext = os.path.splitext(file_path)
        pattern_path = f"{base}.pattern{ext}"

        try:
            cursor = self.db.conn.execute('''
                SELECT * FROM chunks
                WHERE file_path = ?
                AND section_name = ?
                LIMIT 1
            ''', (pattern_path, chunk.get('section_name', '')))

            row = cursor.fetchone()
            if row:
                return dict(row)
        except Exception as e:
            logger.debug(f"Pattern query failed: {e}")

        return None

    def _apply_pattern(self, chunk: Dict[str, Any], pattern: str) -> Dict[str, Any]:
        """Apply pattern layer to chunk

        Replaces content with pattern while preserving metadata.
        Adds markers indicating this is pattern layer.

        Args:
            chunk: Original chunk
            pattern: Pattern layer content

        Returns:
            Chunk with pattern content
        """
        return {
            **chunk,
            'content': pattern,
            '_original_content': chunk.get('content'),  # Preserve for archaeology
        }


class NoOpFlipModule(Module):
    """No-op flip module that returns chunks unchanged"""

    @property
    def name(self) -> str:
        return "noop_flip"

    def execute(
        self,
        chunks: List[Dict[str, Any]],
        context: 'QueryContext'
    ) -> List[Dict[str, Any]]:
        # Add default layer marker
        for chunk in chunks:
            chunk['_layer'] = 'implementation'
        return chunks


__all__ = ['FlipModule', 'NoOpFlipModule']
