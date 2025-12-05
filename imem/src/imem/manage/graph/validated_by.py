"""ValidatedByBuilder - Link narrative chunks to git proof

EPIC 2: Graph Edges

Creates edges from narrative chunks to git chunks that validate them.
A narrative chunk describing a code change points to the git chunk
containing the actual implementation. This enables provenance queries:
"what proves this claim?"

Edge semantics:
- Direction: narrative → git (narrative claims, git proves)
- Weight: file overlap confidence (0.0-1.0)
- Type: 'validated_by'

Logic:
1. Find narrative chunks (source='markdown' or 'conversation') with commit_sha
2. Find git chunks (source='git') with same commit_sha
3. Compute file overlap between them
4. Create edge: narrative → git with weight = overlap score
"""

import logging
import re
from typing import Any, Dict, List, Set, TYPE_CHECKING

from ...protocols import Builder, Edge

if TYPE_CHECKING:
    from ...context import IndexContext

logger = logging.getLogger(__name__)


class ValidatedByBuilder(Builder):
    """Creates validated_by edges linking narrative to git proof

    Connects documentation claims to codebase reality via shared commit_sha.
    Weight reflects file overlap - how many files does the narrative mention
    that also appear in the git chunk.
    """

    @property
    def name(self) -> str:
        return "validated_by"

    @property
    def edge_type(self) -> str:
        return "validated_by"

    def applies(self, chunks: List[Dict[str, Any]], context: 'IndexContext') -> bool:
        """Check if we have both narrative and git chunks with commit_sha

        Args:
            chunks: All chunks being indexed
            context: Index context with infrastructure

        Returns:
            True if there are narrative chunks with commit_sha AND git chunks
        """
        has_narrative_with_sha = any(
            chunk.get('commit_sha') and chunk.get('source') != 'git'
            for chunk in chunks
        )

        has_git_chunks = any(
            chunk.get('source') == 'git'
            for chunk in chunks
        )

        return has_narrative_with_sha and has_git_chunks

    def build(self, chunks: List[Dict[str, Any]], context: 'IndexContext') -> List[Edge]:
        """Build validated_by edges between narrative and git chunks

        Args:
            chunks: All chunks to consider
            context: Index context with infrastructure

        Returns:
            List of Edge objects (narrative → git)
        """
        edges: List[Edge] = []

        # Index git chunks by commit_sha for O(1) lookup
        git_chunks_by_sha: Dict[str, List[Dict[str, Any]]] = {}
        for chunk in chunks:
            if chunk.get('source') == 'git' and chunk.get('commit_sha'):
                sha = chunk['commit_sha']
                if sha not in git_chunks_by_sha:
                    git_chunks_by_sha[sha] = []
                git_chunks_by_sha[sha].append(chunk)

        # Also check database for existing git chunks
        db = context.infrastructure.db
        try:
            cursor = db.conn.execute("""
                SELECT id, file_path, content, commit_sha
                FROM chunks
                WHERE commit_sha IS NOT NULL
                AND (metadata LIKE '%"source": "git"%' OR file_path LIKE '%.git/%')
            """)
            for row in cursor.fetchall():
                sha = row['commit_sha']
                if sha not in git_chunks_by_sha:
                    git_chunks_by_sha[sha] = []
                git_chunks_by_sha[sha].append(dict(row))
        except Exception as e:
            logger.debug(f"Could not query existing git chunks: {e}")

        # Find narrative chunks with commit_sha
        narrative_chunks = [
            chunk for chunk in chunks
            if chunk.get('commit_sha') and chunk.get('source') != 'git'
        ]

        for narrative in narrative_chunks:
            sha = narrative['commit_sha']
            git_chunks = git_chunks_by_sha.get(sha, [])

            for git_chunk in git_chunks:
                # Compute file overlap weight
                weight = self._compute_file_overlap(narrative, git_chunk)

                if weight > 0:
                    edge = Edge(
                        from_id=narrative['id'],
                        to_id=git_chunk['id'],
                        type=self.edge_type,
                        weight=weight
                    )
                    edges.append(edge)
                    logger.debug(
                        f"validated_by edge: {narrative['id'][:8]}... → "
                        f"{git_chunk['id'][:8]}... (weight={weight:.2f})"
                    )

        logger.info(f"ValidatedByBuilder created {len(edges)} edges")
        return edges

    def _compute_file_overlap(
        self,
        narrative: Dict[str, Any],
        git_chunk: Dict[str, Any]
    ) -> float:
        """Compute file overlap between narrative and git chunks

        Looks for file path references in the narrative content and compares
        to the git chunk's file_path.

        Args:
            narrative: Narrative chunk (markdown/conversation)
            git_chunk: Git chunk (source='git')

        Returns:
            Overlap score 0.0-1.0
        """
        # Extract file references from narrative content
        narrative_files = self._extract_file_refs(narrative.get('content', ''))

        # Get git chunk's file path
        git_file = git_chunk.get('file_path', '')

        if not git_file:
            return 0.3  # Base score when git has no file_path

        # Check for direct match
        if git_file in narrative_files:
            return 1.0

        # Check for directory/prefix match
        git_dir = '/'.join(git_file.split('/')[:-1]) if '/' in git_file else ''
        for ref in narrative_files:
            if git_dir and ref.startswith(git_dir):
                return 0.8
            # Basename match
            if ref.split('/')[-1] == git_file.split('/')[-1]:
                return 0.7

        # Same commit_sha implies some relationship
        return 0.5

    def _extract_file_refs(self, content: str) -> Set[str]:
        """Extract file path references from content

        Looks for:
        - Code fence language hints (```python means .py file)
        - Explicit file paths (src/foo/bar.py)
        - Import statements

        Args:
            content: Text content to scan

        Returns:
            Set of file path references
        """
        refs: Set[str] = set()

        # Match explicit file paths
        # Pattern: word characters, slashes, dots, hyphens forming paths
        path_pattern = r'(?:src|lib|tests?|pkg|cmd|internal)/[\w/.-]+\.\w+'
        for match in re.finditer(path_pattern, content):
            refs.add(match.group())

        # Match standalone file names with extensions
        file_pattern = r'\b[\w-]+\.(py|js|ts|go|rs|java|rb|cpp|c|h)\b'
        for match in re.finditer(file_pattern, content):
            refs.add(match.group())

        # Match code fence file annotations like: ```python # file: src/foo.py
        annotation_pattern = r'#\s*file:\s*([\w/.-]+)'
        for match in re.finditer(annotation_pattern, content, re.IGNORECASE):
            refs.add(match.group(1))

        return refs
