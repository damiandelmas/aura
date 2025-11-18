"""SQLite storage for fast metadata queries without vectors

Stores chunks with rich metadata for sub-10ms queries.
Indexes on phase, section_type, file_path, timestamp for fast filtering.
"""

import sqlite3
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class SQLiteStore:
    """Store chunks in SQLite for fast metadata queries"""

    def __init__(self, project_root: Path):
        """Initialize SQLite store

        Args:
            project_root: Project root directory (creates .imem/metadata.db)
        """
        self.db_path = project_root / '.imem' / 'metadata.db'
        self.db_path.parent.mkdir(exist_ok=True, parents=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row  # Enable dict-like access
        self._create_schema()

    def _create_schema(self):
        """Create chunks table with indexes for fast queries"""
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS chunks (
                id TEXT PRIMARY KEY,
                file_path TEXT NOT NULL,
                phase TEXT,
                section_type TEXT,
                section_name TEXT,
                content TEXT,
                timestamp TEXT,
                session_id TEXT,
                metadata JSON,
                indexed_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Indexes for fast filtering
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_phase ON chunks(phase)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_section_type ON chunks(section_type)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_file_path ON chunks(file_path)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON chunks(timestamp)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_session_id ON chunks(session_id)')

        self.conn.commit()

    def upsert_chunks(self, chunks: List[Dict[str, Any]]):
        """Insert or update chunks

        Args:
            chunks: List of chunk dictionaries with metadata
        """
        for chunk in chunks:
            # Extract metadata to JSON column
            metadata = {
                'frontmatter': chunk.get('frontmatter', {}),
                'h2_parent': chunk.get('h2_parent'),  # For changelog sections
                # Add other metadata fields
            }

            self.conn.execute('''
                INSERT OR REPLACE INTO chunks
                (id, file_path, phase, section_type, section_name, content, timestamp, session_id, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                chunk['id'],
                chunk['file_path'],
                chunk.get('phase'),
                chunk.get('section_type'),
                chunk.get('section_name'),
                chunk.get('content'),
                chunk.get('timestamp'),
                chunk.get('session_id'),
                json.dumps(metadata, default=str)  # Handle datetime serialization
            ))

        self.conn.commit()

    def query(self, filters: Optional[Dict[str, Any]] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Query chunks by metadata filters

        Args:
            filters: Dictionary of filter conditions:
                - phase: Exact phase match
                - section_type: Exact section type match
                - file_path: Substring match (LIKE)
                - timestamp_after: Greater than or equal to timestamp
                - text: Content search (substring)
            limit: Maximum number of results

        Returns:
            List of chunk dictionaries with all metadata
        """
        if filters is None:
            filters = {}

        sql = "SELECT * FROM chunks WHERE 1=1"
        params = []

        if filters.get('phase'):
            sql += " AND phase = ?"
            params.append(filters['phase'])

        if filters.get('section_type'):
            sql += " AND section_type = ?"
            params.append(filters['section_type'])

        if filters.get('file_path'):
            sql += " AND file_path LIKE ?"
            params.append(f"%{filters['file_path']}%")

        if filters.get('timestamp_after'):
            sql += " AND timestamp >= ?"
            params.append(filters['timestamp_after'])

        if filters.get('session_id'):
            sql += " AND session_id = ?"
            params.append(filters['session_id'])

        # Content search (SQLite substring match)
        if filters.get('text'):
            sql += " AND content LIKE ?"
            params.append(f"%{filters['text']}%")

        # Order by timestamp descending (most recent first)
        sql += " ORDER BY timestamp DESC"

        # Limit results
        sql += f" LIMIT {limit}"

        cursor = self.conn.execute(sql, params)

        # Convert rows to dicts
        results = []
        for row in cursor.fetchall():
            chunk = dict(row)
            # Parse JSON metadata
            if chunk.get('metadata'):
                chunk['metadata'] = json.loads(chunk['metadata'])
            results.append(chunk)

        return results

    def get_stats(self) -> Dict[str, Any]:
        """Get indexing statistics

        Returns:
            Dictionary with:
                - total_chunks: Total number of chunks
                - by_phase: Count per phase
                - by_section_type: Top section types
                - file_count: Number of unique files
        """
        total = self.conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]

        phases = self.conn.execute('''
            SELECT phase, COUNT(*) as count
            FROM chunks
            GROUP BY phase
            ORDER BY count DESC
        ''').fetchall()

        section_types = self.conn.execute('''
            SELECT section_type, COUNT(*) as count
            FROM chunks
            GROUP BY section_type
            ORDER BY count DESC
            LIMIT 10
        ''').fetchall()

        file_count = self.conn.execute('''
            SELECT COUNT(DISTINCT file_path) as count
            FROM chunks
        ''').fetchone()[0]

        return {
            'total_chunks': total,
            'by_phase': {row['phase']: row['count'] for row in phases if row['phase']},
            'by_section_type': {row['section_type']: row['count'] for row in section_types if row['section_type']},
            'file_count': file_count
        }

    def get_unique_values(self, field: str) -> List[str]:
        """Get all unique values for a field (for introspection)

        Args:
            field: Field name (phase, section_type, etc.)

        Returns:
            List of unique values
        """
        if field not in ('phase', 'section_type', 'file_path'):
            raise ValueError(f"Field '{field}' not supported for unique value queries")

        cursor = self.conn.execute(f'''
            SELECT DISTINCT {field}
            FROM chunks
            WHERE {field} IS NOT NULL
            ORDER BY {field}
        ''')

        return [row[0] for row in cursor.fetchall()]

    def delete_by_file(self, file_path: str):
        """Delete all chunks from a specific file

        Args:
            file_path: Path to file whose chunks should be deleted
        """
        self.conn.execute('DELETE FROM chunks WHERE file_path = ?', (file_path,))
        self.conn.commit()

    def clear_all(self):
        """Delete all chunks (use with caution)"""
        self.conn.execute('DELETE FROM chunks')
        self.conn.commit()

    def get_siblings(self, chunk_id: str,
                     section_types: Optional[List[str]] = None,
                     order_by: str = 'section_level',
                     limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get sibling chunks (same file_path) with filtering and ordering

        Args:
            chunk_id: Target chunk ID
            section_types: Filter by section types (e.g., ["Patterns", "Implementation"])
            order_by: Order results by 'section_level', 'timestamp', or None
            limit: Limit number of results returned

        Returns:
            List of sibling chunks in standard format
        """
        # Get target chunk to find its file_path
        target = self.conn.execute(
            'SELECT file_path FROM chunks WHERE id = ?',
            (chunk_id,)
        ).fetchone()

        if not target:
            return []

        file_path = target['file_path']

        # Build query
        sql = 'SELECT * FROM chunks WHERE file_path = ? AND id != ?'
        params = [file_path, chunk_id]

        # Add section_type filter if specified
        if section_types:
            placeholders = ','.join('?' * len(section_types))
            sql += f' AND section_type IN ({placeholders})'
            params.extend(section_types)

        # Order results
        if order_by == 'timestamp':
            sql += ' ORDER BY timestamp DESC'
        # Note: section_level not yet in SQLite schema, skip for now

        # Apply limit
        if limit:
            sql += f' LIMIT {limit}'

        cursor = self.conn.execute(sql, params)

        # Convert to standard format
        siblings = []
        for row in cursor.fetchall():
            chunk = dict(row)
            if chunk.get('metadata'):
                chunk['metadata'] = json.loads(chunk['metadata'])

            # Format as discovery result
            siblings.append({
                'id': chunk['id'],
                'score': 0.9,  # Sibling weight from architecture
                'payload': {
                    'source': chunk.get('phase'),
                    'phase': chunk.get('phase'),
                    'section_type': chunk.get('section_type'),
                    'section_name': chunk.get('section_name'),
                    'content': chunk.get('content'),
                    'file_path': chunk.get('file_path'),
                    'timestamp': chunk.get('timestamp'),
                    'session_id': chunk.get('session_id'),
                    'metadata': chunk.get('metadata', {})
                }
            })

        return siblings

    def get_genealogy(self, chunk_id: str,
                      order_by: str = 'timestamp',
                      limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get genealogy chunks (same session_id, from conversations)

        Args:
            chunk_id: Target chunk ID
            order_by: Order results by 'timestamp' (default) or None
            limit: Limit number of results returned

        Returns:
            List of conversation chunks from same session
        """
        # Get target chunk to find its session_id
        target = self.conn.execute(
            'SELECT session_id FROM chunks WHERE id = ?',
            (chunk_id,)
        ).fetchone()

        if not target or not target['session_id']:
            return []

        session_id = target['session_id']

        # Build query - find all chunks with same session_id
        sql = 'SELECT * FROM chunks WHERE session_id = ?'
        params = [session_id]

        # Order by timestamp
        if order_by == 'timestamp':
            sql += ' ORDER BY timestamp ASC'

        # Apply limit
        if limit:
            sql += f' LIMIT {limit}'

        cursor = self.conn.execute(sql, params)

        # Convert to standard format
        genealogy = []
        for row in cursor.fetchall():
            chunk = dict(row)
            if chunk.get('metadata'):
                chunk['metadata'] = json.loads(chunk['metadata'])

            genealogy.append({
                'id': chunk['id'],
                'score': 0.85,  # Genealogy weight from architecture
                'payload': {
                    'source': chunk.get('phase'),
                    'phase': chunk.get('phase'),
                    'section_type': chunk.get('section_type'),
                    'section_name': chunk.get('section_name'),
                    'content': chunk.get('content'),
                    'file_path': chunk.get('file_path'),
                    'timestamp': chunk.get('timestamp'),
                    'session_id': chunk.get('session_id'),
                    'metadata': chunk.get('metadata', {})
                }
            })

        return genealogy

    def get_temporal(self, chunk_id: str,
                     direction: str = 'after',
                     limit: int = 10) -> List[Dict[str, Any]]:
        """Get temporally related chunks (chronologically before/after)

        Note: SQLite version uses pure chronological ordering.
        For semantic similarity, use Qdrant's get_temporal.

        Args:
            chunk_id: Target chunk ID
            direction: 'after' (later) or 'before' (earlier) or 'both'
            limit: Limit number of results returned

        Returns:
            List of temporal chunks ordered by timestamp
        """
        # Get target chunk timestamp
        target = self.conn.execute(
            'SELECT timestamp, phase FROM chunks WHERE id = ?',
            (chunk_id,)
        ).fetchone()

        if not target or not target['timestamp']:
            return []

        timestamp = target['timestamp']
        phase = target['phase']

        # Build query based on direction
        if direction == 'after':
            sql = 'SELECT * FROM chunks WHERE timestamp > ? AND phase = ? ORDER BY timestamp ASC'
            params = [timestamp, phase]
        elif direction == 'before':
            sql = 'SELECT * FROM chunks WHERE timestamp < ? AND phase = ? ORDER BY timestamp DESC'
            params = [timestamp, phase]
        else:  # both
            sql = '''
                SELECT * FROM chunks
                WHERE timestamp != ? AND phase = ?
                ORDER BY ABS(JULIANDAY(timestamp) - JULIANDAY(?))
            '''
            params = [timestamp, phase, timestamp]

        # Apply limit
        sql += f' LIMIT {limit}'

        cursor = self.conn.execute(sql, params)

        # Convert to standard format
        temporal = []
        for row in cursor.fetchall():
            chunk = dict(row)
            if chunk.get('metadata'):
                chunk['metadata'] = json.loads(chunk['metadata'])

            temporal.append({
                'id': chunk['id'],
                'score': 0.8,  # Temporal weight from architecture
                'payload': {
                    'source': chunk.get('phase'),
                    'phase': chunk.get('phase'),
                    'section_type': chunk.get('section_type'),
                    'section_name': chunk.get('section_name'),
                    'content': chunk.get('content'),
                    'file_path': chunk.get('file_path'),
                    'timestamp': chunk.get('timestamp'),
                    'session_id': chunk.get('session_id'),
                    'metadata': chunk.get('metadata', {})
                }
            })

        return temporal

    def close(self):
        """Close database connection"""
        self.conn.close()

    def __enter__(self):
        """Context manager support"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close connection on context exit"""
        self.close()
