"""Discovery processor - Enrich search results with related chunks via SQL

Implements relationship discovery using metadata predicates:
- same_document: Chunks from same file (file_path)
- same_conversation: Chunks from same session (session_id)
- temporal_after/before: Chunks nearby in time (timestamp)
- cross_phase: Chunks from different phase with similar content
"""

from typing import Dict, Any, List, Optional
import logging

from ...core.chain import Processor, RetrievalContext
from ...storage.sqlite_backend import SQLiteVectorStore

logger = logging.getLogger(__name__)


class DiscoveryProcessor(Processor):
    """Enrich search results with related chunks via SQL queries"""

    def __init__(self, store: SQLiteVectorStore, config: Dict[str, Any]):
        """Initialize discovery processor

        Args:
            store: SQLiteVectorStore instance (needs .store.conn for SQL)
            config: Discovery configuration:
                - same_document: bool or {limit: int}
                - same_conversation: bool or {limit: int}
                - temporal_after: bool or {limit: int}
                - temporal_before: bool or {limit: int}
                - cross_phase: {phase: str, limit: int}
        """
        self.store = store
        self.config = config

    def process(self, ctx: RetrievalContext) -> RetrievalContext:
        """Enrich each result with related chunks"""
        conn = self.store.store.conn

        for result in ctx.results:
            # Same document (siblings)
            if self.config.get('same_document'):
                cfg = self.config['same_document']
                limit = cfg.get('limit', 5) if isinstance(cfg, dict) else 5
                result['same_document'] = self._get_same_document(
                    conn, result.get('file_path'), result.get('id'), limit
                )

            # Same conversation (genealogy)
            if self.config.get('same_conversation'):
                session_id = result.get('session_id')
                if session_id:
                    cfg = self.config['same_conversation']
                    limit = cfg.get('limit', 5) if isinstance(cfg, dict) else 5
                    result['same_conversation'] = self._get_same_conversation(
                        conn, session_id, result.get('id'), limit
                    )

            # Temporal after
            if self.config.get('temporal_after'):
                timestamp = result.get('timestamp')
                if timestamp:
                    cfg = self.config['temporal_after']
                    limit = cfg.get('limit', 5) if isinstance(cfg, dict) else 5
                    result['temporal_after'] = self._get_temporal_after(
                        conn, timestamp, result.get('id'), limit
                    )

            # Temporal before
            if self.config.get('temporal_before'):
                timestamp = result.get('timestamp')
                if timestamp:
                    cfg = self.config['temporal_before']
                    limit = cfg.get('limit', 5) if isinstance(cfg, dict) else 5
                    result['temporal_before'] = self._get_temporal_before(
                        conn, timestamp, result.get('id'), limit
                    )

            # Cross-phase
            if cross := self.config.get('cross_phase'):
                target_phase = cross.get('phase')
                if target_phase:
                    limit = cross.get('limit', 5)
                    result['cross_phase'] = self._get_cross_phase(
                        conn, result, target_phase, limit
                    )

        ctx.metadata['discovery'] = {
            'config': self.config,
            'enriched_count': len(ctx.results)
        }

        return ctx

    def _get_same_document(self, conn, file_path: str, exclude_id: str, limit: int) -> List[Dict]:
        """Get chunks from same file"""
        if not file_path:
            return []

        cursor = conn.execute("""
            SELECT id, section_type, section_name, content, timestamp
            FROM chunks
            WHERE file_path = ? AND id != ?
            ORDER BY ROWID
            LIMIT ?
        """, (file_path, exclude_id, limit))

        return [dict(row) for row in cursor.fetchall()]

    def _get_same_conversation(self, conn, session_id: str, exclude_id: str, limit: int) -> List[Dict]:
        """Get chunks from same conversation"""
        cursor = conn.execute("""
            SELECT id, section_type, section_name, file_path, timestamp
            FROM chunks
            WHERE session_id = ? AND id != ?
            ORDER BY timestamp
            LIMIT ?
        """, (session_id, exclude_id, limit))

        return [dict(row) for row in cursor.fetchall()]

    def _get_temporal_after(self, conn, timestamp: str, exclude_id: str, limit: int) -> List[Dict]:
        """Get chunks after timestamp"""
        cursor = conn.execute("""
            SELECT id, section_type, section_name, file_path, phase, timestamp
            FROM chunks
            WHERE timestamp > ? AND id != ?
            ORDER BY timestamp ASC
            LIMIT ?
        """, (timestamp, exclude_id, limit))

        return [dict(row) for row in cursor.fetchall()]

    def _get_temporal_before(self, conn, timestamp: str, exclude_id: str, limit: int) -> List[Dict]:
        """Get chunks before timestamp"""
        cursor = conn.execute("""
            SELECT id, section_type, section_name, file_path, phase, timestamp
            FROM chunks
            WHERE timestamp < ? AND id != ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (timestamp, exclude_id, limit))

        return [dict(row) for row in cursor.fetchall()]

    def _get_cross_phase(self, conn, result: Dict, target_phase: str, limit: int) -> List[Dict]:
        """Get chunks from different phase with similar content"""
        # Use section_name for matching
        section_name = result.get('section_name', '')
        if not section_name or len(section_name) < 5:
            return []

        # Search for similar section names in target phase
        search_term = f"%{section_name[:30]}%"

        cursor = conn.execute("""
            SELECT id, section_type, section_name, file_path, timestamp
            FROM chunks
            WHERE phase = ? AND (section_name LIKE ? OR content LIKE ?)
            LIMIT ?
        """, (target_phase, search_term, search_term, limit))

        return [dict(row) for row in cursor.fetchall()]
