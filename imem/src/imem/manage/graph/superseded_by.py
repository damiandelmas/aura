"""SupersededByBuilder - Link old chunks to newer replacements

EPIC 2: Graph Edges (Basic, metadata-based version)

Creates edges from old chunks to newer chunks that replace them.
Knowledge evolves - a decision made in January may be revised in March.
This enables freshness queries: "is there a newer version?"

Edge semantics:
- Direction: old → new (old points to its replacement)
- Weight: confidence score (0.6-0.8 based on grouping method)
- Type: 'superseded_by'

EPIC 2 Logic (no vectors):
1. Group chunks by (directory of file_path, section_type)
2. Within each group, sort by timestamp
3. If newer chunk exists >7 days apart, older is superseded
4. Weight = 0.8 (same file prefix) or 0.6 (same directory)

EPIC 4 will add vector-based similarity for better supersession detection.
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from ...protocols import Builder, Edge

if TYPE_CHECKING:
    from ...context import IndexContext

logger = logging.getLogger(__name__)


class SupersededByBuilder(Builder):
    """Creates superseded_by edges linking old chunks to replacements

    Basic version using metadata grouping (EPIC 2).
    Groups chunks by directory and section_type, then finds temporal
    supersession within groups.

    When superseded_by edge exists, validity pipeline (Phase 4) will:
    - Set validity = 0.2 (hard cap)
    - Set git_status = 'superseded'
    - Set use_pattern_layer = True
    """

    # Configuration
    MIN_SUPERSESSION_DAYS = 7  # Chunks must be >7 days apart
    SAME_FILE_WEIGHT = 0.8
    SAME_DIR_WEIGHT = 0.6

    @property
    def name(self) -> str:
        return "superseded_by"

    @property
    def edge_type(self) -> str:
        return "superseded_by"

    def applies(self, chunks: List[Dict[str, Any]], context: 'IndexContext') -> bool:
        """Check if we have enough chunks with timestamps for supersession

        Args:
            chunks: All chunks being indexed
            context: Index context with infrastructure

        Returns:
            True if there are multiple timestamped chunks
        """
        timestamped = [c for c in chunks if c.get('timestamp')]
        return len(timestamped) >= 2

    def build(self, chunks: List[Dict[str, Any]], context: 'IndexContext') -> List[Edge]:
        """Build superseded_by edges between old and new chunks

        Groups chunks by (directory, section_type), then within each group
        finds temporal supersession relationships.

        Args:
            chunks: All chunks to consider
            context: Index context with infrastructure

        Returns:
            List of Edge objects (old → new)
        """
        edges: List[Edge] = []

        # Get all chunks with timestamps (including from database)
        all_chunks = self._get_all_timestamped_chunks(chunks, context)

        # Group by (directory, section_type)
        groups = self._group_chunks(all_chunks)

        # Within each group, find supersession
        for group_key, group_chunks in groups.items():
            group_edges = self._find_supersession_in_group(group_chunks)
            edges.extend(group_edges)

        logger.info(f"SupersededByBuilder created {len(edges)} edges")
        return edges

    def _get_all_timestamped_chunks(
        self,
        new_chunks: List[Dict[str, Any]],
        context: 'IndexContext'
    ) -> List[Dict[str, Any]]:
        """Combine new chunks with existing timestamped chunks from DB

        Args:
            new_chunks: Chunks being indexed in current run
            context: Index context with infrastructure

        Returns:
            All chunks with valid timestamps
        """
        all_chunks = [c for c in new_chunks if c.get('timestamp')]

        # Query existing chunks from database
        db = context.infrastructure.db
        try:
            cursor = db.conn.execute("""
                SELECT id, file_path, section_type, timestamp, validity
                FROM chunks
                WHERE timestamp IS NOT NULL
            """)
            for row in cursor.fetchall():
                # Avoid duplicates
                if not any(c['id'] == row['id'] for c in all_chunks):
                    all_chunks.append(dict(row))
        except Exception as e:
            logger.debug(f"Could not query existing chunks: {e}")

        return all_chunks

    def _group_chunks(
        self,
        chunks: List[Dict[str, Any]]
    ) -> Dict[Tuple[str, Optional[str]], List[Dict[str, Any]]]:
        """Group chunks by (directory, section_type)

        Args:
            chunks: Chunks with timestamps

        Returns:
            Dict mapping (dir, section_type) to list of chunks
        """
        groups: Dict[Tuple[str, Optional[str]], List[Dict[str, Any]]] = defaultdict(list)

        for chunk in chunks:
            file_path = chunk.get('file_path', '')
            section_type = chunk.get('section_type')

            # Extract directory from file_path
            directory = self._get_directory(file_path)

            key = (directory, section_type)
            groups[key].append(chunk)

        return groups

    def _get_directory(self, file_path: str) -> str:
        """Extract directory from file path

        Args:
            file_path: Full file path

        Returns:
            Directory portion, or empty string if no directory
        """
        if not file_path:
            return ''
        parts = file_path.rsplit('/', 1)
        return parts[0] if len(parts) > 1 else ''

    def _find_supersession_in_group(
        self,
        chunks: List[Dict[str, Any]]
    ) -> List[Edge]:
        """Find supersession relationships within a group

        Sort by timestamp, then check if newer chunks supersede older ones.
        Chunks must be >7 days apart to avoid flagging rapid iterations.

        Args:
            chunks: Chunks in the same (directory, section_type) group

        Returns:
            List of superseded_by edges
        """
        edges: List[Edge] = []

        if len(chunks) < 2:
            return edges

        # Sort by timestamp (oldest first)
        sorted_chunks = sorted(
            chunks,
            key=lambda c: self._parse_timestamp(c.get('timestamp', ''))
        )

        # For each chunk, check if there's a newer superseding chunk
        for i, old_chunk in enumerate(sorted_chunks[:-1]):
            old_ts = self._parse_timestamp(old_chunk.get('timestamp', ''))
            if not old_ts:
                continue

            # Find the first newer chunk that supersedes this one
            for new_chunk in sorted_chunks[i + 1:]:
                new_ts = self._parse_timestamp(new_chunk.get('timestamp', ''))
                if not new_ts:
                    continue

                # Check time gap
                days_apart = (new_ts - old_ts).days
                if days_apart < self.MIN_SUPERSESSION_DAYS:
                    continue

                # Compute weight based on file path similarity
                weight = self._compute_weight(old_chunk, new_chunk)

                edge = Edge(
                    from_id=old_chunk['id'],
                    to_id=new_chunk['id'],
                    type=self.edge_type,
                    weight=weight
                )
                edges.append(edge)
                logger.debug(
                    f"superseded_by edge: {old_chunk['id'][:8]}... → "
                    f"{new_chunk['id'][:8]}... ({days_apart}d apart, weight={weight:.2f})"
                )
                break  # One supersession is enough per chunk

        return edges

    def _parse_timestamp(self, ts_str: str) -> Optional[datetime]:
        """Parse timestamp string to datetime

        Args:
            ts_str: ISO format timestamp string

        Returns:
            datetime object, or None if parsing fails
        """
        if not ts_str:
            return None

        try:
            # Handle various ISO formats
            if 'T' in ts_str:
                # Full ISO format
                ts_str = ts_str.replace('Z', '+00:00')
                if '+' in ts_str or ts_str.endswith('00:00'):
                    return datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                return datetime.fromisoformat(ts_str)
            else:
                # Date only
                return datetime.strptime(ts_str, '%Y-%m-%d')
        except (ValueError, TypeError) as e:
            logger.debug(f"Could not parse timestamp '{ts_str}': {e}")
            return None

    def _compute_weight(
        self,
        old_chunk: Dict[str, Any],
        new_chunk: Dict[str, Any]
    ) -> float:
        """Compute supersession confidence weight

        Higher weight for more similar file paths.

        Args:
            old_chunk: The superseded chunk
            new_chunk: The superseding chunk

        Returns:
            Weight 0.6-0.8
        """
        old_path = old_chunk.get('file_path', '')
        new_path = new_chunk.get('file_path', '')

        # Same file prefix (same file, different versions/sections)
        if old_path and new_path:
            old_base = old_path.rsplit('.', 1)[0] if '.' in old_path else old_path
            new_base = new_path.rsplit('.', 1)[0] if '.' in new_path else new_path
            if old_base == new_base:
                return self.SAME_FILE_WEIGHT

        # Same directory (already guaranteed by grouping, but double-check)
        return self.SAME_DIR_WEIGHT
