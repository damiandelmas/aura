"""COMPILE resolution - Structural normalization at indexing time

Maps phase and section_type variations to canonical forms:
- Phase: 'planning' → 'design', 'spec' → 'designate', etc.
- Section: 'Decisions' → 'Decision', 'Best Practice' → 'Pattern', etc.

Uses resolution tables for evolution tracking and confidence scoring.
"""

import sqlite3
import logging
from typing import Optional, Dict, List
from pathlib import Path

logger = logging.getLogger(__name__)


class CompileResolver:
    """Normalizes document structure to canonical 4-phase + section types

    COMPILE resolution (structural):
    - Universal canonical taxonomy (not project-specific)
    - Applied at indexing time (structure normalization)
    - Seeded with known variations, learns new ones over time
    """

    # Canonical 4-phase taxonomy with known variations
    PHASE_MAPPINGS = {
        'design': [
            'design', 'planning', 'research', 'exploration',
            'ideation', 'brainstorm', 'investigation'
        ],
        'designate': [
            'designate', 'spec', 'specification', 'architecture',
            'blueprint', 'plan', 'design-doc', 'rfc', 'adr'
        ],
        'develop': [
            'develop', 'implementation', 'code', 'build',
            'coding', 'dev', 'development', 'impl'
        ],
        'document': [
            'document', 'docs', 'documentation', 'readme',
            'guide', 'tutorial', 'reference', 'wiki'
        ]
    }

    # Canonical section types with known variations
    SECTION_MAPPINGS = {
        'Decision': [
            'Decision', 'Decisions', 'Decision:', 'Choice', 'We Decided',
            'Resolution', 'Verdict', 'Conclusion', 'Call'
        ],
        'Pattern': [
            'Pattern', 'Patterns', 'Best Practice', 'Best Practices',
            'Approach', 'Strategy', 'Technique', 'Method'
        ],
        'Implementation': [
            'Implementation', 'Code', 'Solution', 'How We Built',
            'Technical Details', 'Implementation Details', 'Build'
        ],
        'Context': [
            'Context', 'Background', 'Why', 'Situation', 'Problem',
            'Motivation', 'Rationale', 'Setting'
        ],
        'Failure': [
            'Failure', 'Mistake', 'What Went Wrong', 'Error', 'Issue',
            'Problem', 'Bug', 'Anti-Pattern', 'Pitfall'
        ],
        'Consequence': [
            'Consequence', 'Consequences', 'Impact', 'Result', 'Outcome',
            'Effect', 'Implications', 'Ramifications'
        ],
        'Alternative': [
            'Alternative', 'Alternatives', 'Other Options', 'Trade-off',
            'Trade-offs', 'Rejected', 'Considered'
        ]
    }

    def __init__(self, db_conn: sqlite3.Connection):
        """Initialize resolver with database connection

        Args:
            db_conn: SQLite connection (should already have chunks table)
        """
        self.conn = db_conn
        self._create_resolution_tables()
        self._seed_resolution_tables()

    def _create_resolution_tables(self):
        """Create resolution tables for phase and section_type normalization"""

        # Phase resolution table
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS phase_resolution (
                variation TEXT PRIMARY KEY COLLATE NOCASE,
                canonical TEXT NOT NULL CHECK (canonical IN ('design', 'designate', 'develop', 'document')),
                confidence REAL DEFAULT 1.0,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                usage_count INTEGER DEFAULT 0
            )
        ''')

        # Section type resolution table
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS section_type_resolution (
                variation TEXT PRIMARY KEY COLLATE NOCASE,
                canonical TEXT NOT NULL,
                confidence REAL DEFAULT 1.0,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                usage_count INTEGER DEFAULT 0
            )
        ''')

        self.conn.commit()

    def _seed_resolution_tables(self):
        """Seed resolution tables with known variations

        Only inserts if tables are empty (idempotent).
        """
        # Check if already seeded
        phase_count = self.conn.execute(
            'SELECT COUNT(*) FROM phase_resolution'
        ).fetchone()[0]

        if phase_count > 0:
            logger.debug("Resolution tables already seeded")
            return

        # Seed phase mappings
        for canonical, variations in self.PHASE_MAPPINGS.items():
            for variation in variations:
                self.conn.execute('''
                    INSERT OR IGNORE INTO phase_resolution (variation, canonical, confidence)
                    VALUES (?, ?, ?)
                ''', (variation, canonical, 1.0))

        # Seed section type mappings
        for canonical, variations in self.SECTION_MAPPINGS.items():
            for variation in variations:
                self.conn.execute('''
                    INSERT OR IGNORE INTO section_type_resolution (variation, canonical, confidence)
                    VALUES (?, ?, ?)
                ''', (variation, canonical, 1.0))

        self.conn.commit()
        logger.info("Seeded resolution tables with known variations")

    def resolve_phase(self, raw_phase: Optional[str]) -> Optional[str]:
        """Resolve phase variation to canonical form

        Args:
            raw_phase: Raw phase string from document

        Returns:
            Canonical phase ('design', 'designate', 'develop', 'document') or None

        Example:
            'planning' → 'design'
            'spec' → 'designate'
            'implementation' → 'develop'
        """
        if not raw_phase:
            return None

        # Lookup in resolution table (case-insensitive)
        result = self.conn.execute('''
            SELECT canonical FROM phase_resolution
            WHERE variation = ? COLLATE NOCASE
        ''', (raw_phase,)).fetchone()

        if result:
            # Update usage stats
            self.conn.execute('''
                UPDATE phase_resolution
                SET last_used = CURRENT_TIMESTAMP,
                    usage_count = usage_count + 1
                WHERE variation = ? COLLATE NOCASE
            ''', (raw_phase,))
            self.conn.commit()

            return result[0]

        # Unknown variation - log for future learning
        logger.warning(f"Unknown phase variation: '{raw_phase}' (not in resolution table)")
        return raw_phase  # Return as-is (no normalization)

    def resolve_section_type(self, raw_section: Optional[str]) -> Optional[str]:
        """Resolve section type variation to canonical form

        Args:
            raw_section: Raw section header from document

        Returns:
            Canonical section type or None

        Example:
            'Decisions' → 'Decision'
            'We Decided:' → 'Decision'
            'Best Practice' → 'Pattern'
        """
        if not raw_section:
            return None

        # Strip common suffixes (colons, etc.)
        cleaned = raw_section.rstrip(':').strip()

        # Lookup in resolution table (case-insensitive)
        result = self.conn.execute('''
            SELECT canonical FROM section_type_resolution
            WHERE variation = ? COLLATE NOCASE
        ''', (cleaned,)).fetchone()

        if result:
            # Update usage stats
            self.conn.execute('''
                UPDATE section_type_resolution
                SET last_used = CURRENT_TIMESTAMP,
                    usage_count = usage_count + 1
                WHERE variation = ? COLLATE NOCASE
            ''', (cleaned,))
            self.conn.commit()

            return result[0]

        # Unknown variation - log for future learning
        logger.warning(f"Unknown section variation: '{cleaned}' (not in resolution table)")
        return raw_section  # Return as-is (no normalization)

    def add_phase_variation(self, variation: str, canonical: str, confidence: float = 0.8):
        """Learn new phase variation (for future auto-consolidation)

        Args:
            variation: New variation discovered
            canonical: Canonical phase to map to
            confidence: Confidence score (0-1)
        """
        self.conn.execute('''
            INSERT OR IGNORE INTO phase_resolution (variation, canonical, confidence)
            VALUES (?, ?, ?)
        ''', (variation, canonical, confidence))
        self.conn.commit()
        logger.info(f"Learned new phase variation: '{variation}' → '{canonical}' (confidence: {confidence})")

    def add_section_variation(self, variation: str, canonical: str, confidence: float = 0.8):
        """Learn new section type variation (for future auto-consolidation)

        Args:
            variation: New variation discovered
            canonical: Canonical section type to map to
            confidence: Confidence score (0-1)
        """
        self.conn.execute('''
            INSERT OR IGNORE INTO section_type_resolution (variation, canonical, confidence)
            VALUES (?, ?, ?)
        ''', (variation, canonical, confidence))
        self.conn.commit()
        logger.info(f"Learned new section variation: '{variation}' → '{canonical}' (confidence: {confidence})")

    def get_phase_stats(self) -> Dict[str, List[str]]:
        """Get statistics on phase resolution usage

        Returns:
            Dict mapping canonical phases to list of variations with usage counts
        """
        stats = {}
        for canonical in ['design', 'designate', 'develop', 'document']:
            rows = self.conn.execute('''
                SELECT variation, usage_count
                FROM phase_resolution
                WHERE canonical = ?
                ORDER BY usage_count DESC
            ''', (canonical,)).fetchall()

            stats[canonical] = [
                f"{row[0]} ({row[1]} uses)" for row in rows
            ]

        return stats

    def get_section_stats(self) -> Dict[str, List[str]]:
        """Get statistics on section type resolution usage

        Returns:
            Dict mapping canonical section types to variations with usage counts
        """
        stats = {}
        rows = self.conn.execute('''
            SELECT canonical, GROUP_CONCAT(variation || ' (' || usage_count || ')', ', ') as variations
            FROM section_type_resolution
            GROUP BY canonical
            ORDER BY canonical
        ''').fetchall()

        for row in rows:
            stats[row[0]] = row[1].split(', ') if row[1] else []

        return stats
