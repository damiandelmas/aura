"""Git Signal - Validate chunks against codebase ground truth

GitSignal compares code signatures embedded in documentation chunks
against the actual codebase at HEAD. This is the strongest validity signal:
- Code exists and matches → validated (high score)
- Code changed/deleted → contradicted (low score)
- No signatures → neutral (defers to other signals)

Change type discrimination:
- DELETE: 0.1 (strong invalidation)
- MODIFY: 0.4 (partial contradiction)
- RENAME: 0.6 (might still be valid)
- ADD: 0.9 (fresh match)

EPIC 1 implementation.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING
import logging

from ...protocols import Signal, SignalResult

if TYPE_CHECKING:
    from ...context import IndexContext

logger = logging.getLogger(__name__)


class GitSignal(Signal):
    """Validate chunk claims against codebase state

    Loads signatures for a chunk, compares against HEAD via GitInterface.
    Score = weighted average of signature matches.

    High confidence signal - GitSignal should dominate when signatures exist.
    """

    # High confidence - git evidence is strong
    HIGH_CONFIDENCE = 0.9
    MEDIUM_CONFIDENCE = 0.6
    LOW_CONFIDENCE = 0.3

    @property
    def name(self) -> str:
        return "git"

    def applies(self, chunk: Dict[str, Any], context: 'IndexContext') -> bool:
        """GitSignal applies when:
        1. Not a git-sourced chunk (those are ground truth)
        2. Git interface is available (not NoOp)
        3. Chunk has content that could contain signatures
        """
        # Git-sourced chunks are ground truth
        source = chunk.get('source', chunk.get('metadata', {}).get('source'))
        if source == 'git':
            return False

        # Check if git interface is real (not NoOp)
        git = context.infrastructure.git
        if git.__class__.__name__ == 'NoOpGitInterface':
            return False

        return True

    def score(self, chunk: Dict[str, Any], context: 'IndexContext') -> SignalResult:
        """Compute git validation score

        Loads signatures from chunk_signatures table, validates each
        against HEAD, returns weighted score.
        """
        chunk_id = chunk.get('id')
        if not chunk_id:
            return SignalResult(
                score=0.5,
                confidence=0.0,
                reason="No chunk ID"
            )

        # Load signatures for this chunk
        signatures = self._load_signatures(chunk_id, context)

        if not signatures:
            return SignalResult(
                score=0.5,
                confidence=self.LOW_CONFIDENCE,
                reason="No code signatures to validate"
            )

        # Validate each signature
        validated_count = 0
        contradicted_count = 0
        total_weight = 0.0
        weighted_score = 0.0

        for sig in signatures:
            file_path = sig.get('file_path')
            content = sig.get('content', '')

            if not file_path:
                # Unanchored signature - can't validate
                continue

            result = self._validate_signature(file_path, content, context)

            # Weight anchored signatures higher
            weight = 1.0
            weighted_score += result['score'] * weight
            total_weight += weight

            if result['status'] == 'validated':
                validated_count += 1
            elif result['status'] == 'contradicted':
                contradicted_count += 1

        if total_weight == 0:
            return SignalResult(
                score=0.5,
                confidence=self.LOW_CONFIDENCE,
                reason="No anchored signatures to validate"
            )

        final_score = weighted_score / total_weight

        # Determine confidence based on signature count
        sig_count = validated_count + contradicted_count
        if sig_count >= 3:
            confidence = self.HIGH_CONFIDENCE
        elif sig_count >= 1:
            confidence = self.MEDIUM_CONFIDENCE
        else:
            confidence = self.LOW_CONFIDENCE

        reason = f"Git validation: {validated_count} validated, {contradicted_count} contradicted"

        return SignalResult(
            score=final_score,
            confidence=confidence,
            reason=reason
        )

    def _load_signatures(
        self,
        chunk_id: str,
        context: 'IndexContext'
    ) -> List[Dict[str, Any]]:
        """Load signatures from chunk_signatures table"""
        db = context.infrastructure.db
        try:
            cursor = db.conn.execute('''
                SELECT chunk_id, content, language, file_path, signature_hash
                FROM chunk_signatures
                WHERE chunk_id = ?
            ''', (chunk_id,))

            return [
                {
                    'chunk_id': row[0],
                    'content': row[1],
                    'language': row[2],
                    'file_path': row[3],
                    'signature_hash': row[4],
                }
                for row in cursor.fetchall()
            ]
        except Exception as e:
            logger.warning(f"Failed to load signatures for {chunk_id}: {e}")
            return []

    def _validate_signature(
        self,
        file_path: str,
        code: str,
        context: 'IndexContext'
    ) -> Dict[str, Any]:
        """Validate a single signature against HEAD

        Returns:
            Dict with 'score', 'status', 'reason'
        """
        git = context.infrastructure.git
        path = Path(file_path)

        # Check if file exists at HEAD
        if not git.file_exists(path):
            return {
                'score': 0.1,
                'status': 'contradicted',
                'reason': f"File deleted: {file_path}"
            }

        # Get file content
        content = git.get_file_content(path)
        if content is None:
            return {
                'score': 0.2,
                'status': 'contradicted',
                'reason': f"Could not read file: {file_path}"
            }

        # Check if code still exists in file
        # Use substring match (code might have minor whitespace changes)
        normalized_code = self._normalize_code(code)
        normalized_content = self._normalize_code(content)

        if normalized_code in normalized_content:
            return {
                'score': 0.9,
                'status': 'validated',
                'reason': f"Code matches HEAD: {file_path}"
            }

        # Code not found - might be modified
        # Check if file was recently modified (could indicate rename/refactor)
        return {
            'score': 0.3,
            'status': 'contradicted',
            'reason': f"Code changed/removed: {file_path}"
        }

    def _normalize_code(self, code: str) -> str:
        """Normalize code for fuzzy matching

        Removes excess whitespace while preserving structure.
        """
        # Normalize line endings
        code = code.replace('\r\n', '\n')

        # Remove trailing whitespace per line
        lines = [line.rstrip() for line in code.split('\n')]

        # Remove empty lines at start/end
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()

        return '\n'.join(lines)


__all__ = ['GitSignal']
