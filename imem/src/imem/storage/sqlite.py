"""SQLite storage for fast metadata queries without vectors

Stores chunks with rich metadata for sub-10ms queries.
Indexes on phase, section_type, file_path, timestamp for fast filtering.

Storage location: ~/.imem/namespaces/{namespace}/projects/{hash}/metadata.db
"""

import sqlite3
import json
import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from ..config import config

logger = logging.getLogger(__name__)


class SQLiteStore:
    """Store chunks in SQLite for fast metadata queries"""

    def __init__(self, project_root: Path):
        """Initialize SQLite store

        Args:
            project_root: Project root directory (used to compute project hash)

        Storage path: ~/.imem/namespaces/{namespace}/projects/{hash}/metadata.db
        - No pollution of project directories
        - Namespace isolation prevents conflicts between v2/v3/etc.
        """
        # Compute project hash for unique directory
        project_key = str(project_root.resolve())
        project_hash = hashlib.md5(project_key.encode()).hexdigest()[:8]

        # Store in namespace-based central location
        project_dir = config.namespace_dir / 'projects' / project_hash
        project_dir.mkdir(parents=True, exist_ok=True)

        self.db_path = project_dir / 'metadata.db'
        self.project_root = project_root  # Keep reference for debugging
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
                indexed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Migrate existing tables to add temporal columns if missing (BEFORE indexes)
        try:
            cursor = self.conn.execute("PRAGMA table_info(chunks)")
            columns = {row[1] for row in cursor.fetchall()}

            if 'created_at' not in columns:
                self.conn.execute('ALTER TABLE chunks ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
            if 'updated_at' not in columns:
                self.conn.execute('ALTER TABLE chunks ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
        except Exception:
            pass

        # Indexes for fast filtering (AFTER migration)
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_phase ON chunks(phase)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_section_type ON chunks(section_type)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_file_path ON chunks(file_path)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON chunks(timestamp)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_session_id ON chunks(session_id)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_created_at ON chunks(created_at)')

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

    # Discovery: Query SQL directly when needed. Don't wrap until usage patterns emerge.
    # Examples:
    #   SELECT * FROM chunks WHERE file_path = ?  -- same document
    #   SELECT * FROM chunks WHERE session_id = ? -- same session
    #   SELECT * FROM chunks WHERE timestamp BETWEEN ? AND ? -- time window

    def close(self):
        """Close database connection"""
        self.conn.close()

    def __enter__(self):
        """Context manager support"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close connection on context exit"""
        self.close()
