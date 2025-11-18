"""MANAGE resolution - Entity normalization at query time

Maps entity variations to canonical forms within project scope:
- 'jwt' / 'JWT' / 'json-web-tokens' → canonical 'jwt'
- 'redis' / 'Redis' / 'Redis-DB' → canonical 'redis'

Project-scoped (different projects may have different entity taxonomies).
"""

import sqlite3
import logging
from typing import Optional, List, Dict, Set
from pathlib import Path

logger = logging.getLogger(__name__)


class EntityResolver:
    """Normalizes entity references within project scope

    MANAGE resolution (entities):
    - Project-scoped taxonomy (emergent from corpus)
    - Applied at query time (query expansion)
    - Discovered via SQL analytics + clustering
    """

    def __init__(self, db_conn: sqlite3.Connection, project_id: str):
        """Initialize entity resolver

        Args:
            db_conn: SQLite connection
            project_id: Project identifier for scoping entities
        """
        self.conn = db_conn
        self.project_id = project_id
        self._create_entity_resolution_table()

    def _create_entity_resolution_table(self):
        """Create entity resolution table for project-scoped entity normalization"""

        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS entity_resolution (
                project_id TEXT NOT NULL,
                variation TEXT NOT NULL,
                canonical TEXT NOT NULL,
                context TEXT,
                confidence REAL DEFAULT 1.0,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                usage_count INTEGER DEFAULT 0,
                PRIMARY KEY (project_id, variation)
            )
        ''')

        # Index for fast lookup by project
        self.conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_entity_project_canonical
            ON entity_resolution(project_id, canonical)
        ''')

        self.conn.commit()

    def resolve_entity(self, term: str) -> str:
        """Resolve entity variation to canonical form within project

        Args:
            term: Entity term from query or document

        Returns:
            Canonical entity form (or original if not found)

        Example:
            'JWT' → 'jwt'
            'json-web-tokens' → 'jwt'
        """
        if not term:
            return term

        # Lookup in resolution table (case-sensitive for project scope)
        result = self.conn.execute('''
            SELECT canonical FROM entity_resolution
            WHERE project_id = ? AND variation = ?
        ''', (self.project_id, term)).fetchone()

        if result:
            # Update usage stats
            self.conn.execute('''
                UPDATE entity_resolution
                SET last_used = CURRENT_TIMESTAMP,
                    usage_count = usage_count + 1
                WHERE project_id = ? AND variation = ?
            ''', (self.project_id, term))
            self.conn.commit()

            return result[0]

        # Not found - return as-is
        return term

    def expand_query(self, canonical: str) -> List[str]:
        """Expand canonical entity to all known variations for search

        Args:
            canonical: Canonical entity form

        Returns:
            List of all variations (including canonical)

        Example:
            'jwt' → ['jwt', 'JWT', 'json-web-tokens', 'jwt-auth']
        """
        rows = self.conn.execute('''
            SELECT DISTINCT variation
            FROM entity_resolution
            WHERE project_id = ? AND canonical = ?
            ORDER BY usage_count DESC
        ''', (self.project_id, canonical)).fetchall()

        variations = [row[0] for row in rows]

        # Always include canonical itself
        if canonical not in variations:
            variations.insert(0, canonical)

        return variations

    def add_entity_mapping(
        self,
        variation: str,
        canonical: str,
        context: Optional[str] = None,
        confidence: float = 1.0
    ):
        """Add entity variation mapping

        Args:
            variation: Entity variation
            canonical: Canonical entity form
            context: Optional context hint (e.g., 'authentication', 'database')
            confidence: Confidence score (0-1)
        """
        self.conn.execute('''
            INSERT OR REPLACE INTO entity_resolution
            (project_id, variation, canonical, context, confidence)
            VALUES (?, ?, ?, ?, ?)
        ''', (self.project_id, variation, canonical, context, confidence))
        self.conn.commit()

        logger.info(
            f"Mapped entity: '{variation}' → '{canonical}' "
            f"(project: {self.project_id}, confidence: {confidence})"
        )

    def consolidate_from_corpus(self, min_mentions: int = 5) -> Dict[str, List[str]]:
        """Auto-discover and consolidate entities from corpus via SQL analytics

        Uses frequency analysis and string similarity to cluster entity variations.

        Args:
            min_mentions: Minimum mentions required to consider an entity

        Returns:
            Dict mapping canonical entities to discovered variations

        Example:
            {
                'jwt': ['JWT', 'jwt', 'json-web-tokens'],
                'redis': ['Redis', 'redis', 'redis-cache']
            }
        """
        # TODO: Implement corpus analysis
        # 1. Extract frequent terms (capitalized, acronyms)
        # 2. Cluster by Levenshtein distance
        # 3. Group variations by canonical (lowercase most common)
        # 4. Store in entity_resolution table

        logger.warning("Entity consolidation from corpus not yet implemented")
        return {}

    def get_entity_stats(self) -> List[Dict[str, any]]:
        """Get entity resolution statistics for project

        Returns:
            List of entity groups with variations and usage counts
        """
        rows = self.conn.execute('''
            SELECT
                canonical,
                COUNT(*) as variation_count,
                SUM(usage_count) as total_uses,
                GROUP_CONCAT(variation || ' (' || usage_count || ')', ', ') as variations
            FROM entity_resolution
            WHERE project_id = ?
            GROUP BY canonical
            ORDER BY total_uses DESC
        ''', (self.project_id,)).fetchall()

        return [
            {
                'canonical': row[0],
                'variation_count': row[1],
                'total_uses': row[2],
                'variations': row[3].split(', ') if row[3] else []
            }
            for row in rows
        ]

    def merge_entities(self, from_canonical: str, to_canonical: str):
        """Merge two canonical entities (consolidate duplicates)

        Args:
            from_canonical: Canonical entity to merge from
            to_canonical: Canonical entity to merge into

        Example:
            merge_entities('JWT', 'jwt')  # Consolidate uppercase to lowercase
        """
        self.conn.execute('''
            UPDATE entity_resolution
            SET canonical = ?
            WHERE project_id = ? AND canonical = ?
        ''', (to_canonical, self.project_id, from_canonical))
        self.conn.commit()

        logger.info(f"Merged entity: '{from_canonical}' → '{to_canonical}'")
