"""Link Module - Attach git provenance to chunks

LinkModule connects documentation chunks to git history:
- Timestamp resolution cascade: frontmatter → git → mtime → indexed
- commit_sha attachment: Find nearest commit to chunk timestamp
- session_id extraction: From commit message trailers (if present)

EPIC 1 implementation.
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING
import logging
import os

from ..protocols import Module

if TYPE_CHECKING:
    from ..context import IndexContext

logger = logging.getLogger(__name__)


class LinkModule(Module):
    """Attach git SHA and resolve timestamps for chunks

    Timestamp resolution cascade:
    1. Frontmatter field ('created_at', 'timestamp', 'date')
    2. Git commit timestamp (first commit touching source file)
    3. File modification time (mtime)
    4. Index time (fallback)

    Commit SHA attachment:
    - Find commits near chunk.timestamp (±7 days default)
    - Attach nearest commit's SHA to chunk
    """

    # Default search window for commit_sha attachment
    COMMIT_WINDOW_DAYS = 7

    @property
    def name(self) -> str:
        return "link"

    def execute(
        self,
        chunks: List[Dict[str, Any]],
        context: 'IndexContext'
    ) -> List[Dict[str, Any]]:
        """Execute link module on chunks

        Resolves timestamps and attaches commit_sha for each chunk.

        Args:
            chunks: Chunks to process
            context: Index context with infrastructure

        Returns:
            Chunks with timestamp and commit_sha populated
        """
        git = context.infrastructure.git

        for chunk in chunks:
            try:
                # 1. Resolve timestamp
                timestamp, source = self._resolve_timestamp(chunk, context)
                chunk['timestamp'] = timestamp.isoformat() if timestamp else None
                chunk['timestamp_source'] = source

                # 2. Attach commit_sha
                if timestamp:
                    commit_sha = self._find_nearest_commit(chunk, timestamp, context)
                    if commit_sha:
                        chunk['commit_sha'] = commit_sha

                        # 3. Extract session_id from commit trailer
                        session_id = git.extract_session_trailer(commit_sha)
                        if session_id:
                            # Only set if not already present (conversations have their own)
                            if not chunk.get('session_id'):
                                chunk['session_id'] = session_id

            except Exception as e:
                logger.warning(f"Link failed for chunk {chunk.get('id', 'unknown')}: {e}")

        logger.debug(f"LinkModule processed {len(chunks)} chunks")
        return chunks

    def _resolve_timestamp(
        self,
        chunk: Dict[str, Any],
        context: 'IndexContext'
    ) -> tuple[Optional[datetime], str]:
        """Resolve timestamp via cascade

        Returns:
            Tuple of (timestamp, source) where source indicates provenance
        """
        # 1. Frontmatter timestamp
        metadata = chunk.get('metadata', {})
        for field in ['created_at', 'timestamp', 'date', 'created']:
            value = metadata.get(field)
            if value:
                ts = self._parse_timestamp(value)
                if ts:
                    return ts, 'frontmatter'

        # Also check top-level timestamp field
        if chunk.get('timestamp'):
            ts = self._parse_timestamp(chunk['timestamp'])
            if ts:
                return ts, 'frontmatter'

        # 2. Git commit timestamp
        file_path = chunk.get('file_path')
        if file_path:
            git = context.infrastructure.git
            git_ts = git.get_commit_timestamp(Path(file_path))
            if git_ts:
                return git_ts, 'git'

            # 3. File modification time
            try:
                full_path = context.infrastructure.config.get('project_root', Path('.'))
                if isinstance(full_path, str):
                    full_path = Path(full_path)
                file_full_path = full_path / file_path
                if file_full_path.exists():
                    mtime = datetime.fromtimestamp(os.path.getmtime(file_full_path))
                    return mtime, 'mtime'
            except (OSError, ValueError) as e:
                logger.debug(f"Could not get mtime for {file_path}: {e}")

        # 4. Index time (fallback)
        indexed_at = chunk.get('indexed_at')
        if indexed_at:
            ts = self._parse_timestamp(indexed_at)
            if ts:
                return ts, 'indexed'

        return datetime.now(), 'indexed'

    def _parse_timestamp(self, value: Any) -> Optional[datetime]:
        """Parse timestamp from various formats"""
        if isinstance(value, datetime):
            return value

        if isinstance(value, str):
            # Try ISO format
            try:
                return datetime.fromisoformat(value.replace('Z', '+00:00'))
            except ValueError:
                pass

            # Try common date formats
            for fmt in ['%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%Y/%m/%d']:
                try:
                    return datetime.strptime(value, fmt)
                except ValueError:
                    continue

        return None

    def _find_nearest_commit(
        self,
        chunk: Dict[str, Any],
        timestamp: datetime,
        context: 'IndexContext'
    ) -> Optional[str]:
        """Find nearest commit to chunk timestamp

        Searches commits for the source file within ±COMMIT_WINDOW_DAYS.
        Returns the commit closest in time to the chunk's timestamp.
        """
        file_path = chunk.get('file_path')
        if not file_path:
            return None

        git = context.infrastructure.git

        # Search within time window
        since = timestamp - timedelta(days=self.COMMIT_WINDOW_DAYS)
        until = timestamp + timedelta(days=self.COMMIT_WINDOW_DAYS)

        commits = git.get_commits_for_file(Path(file_path), since=since, until=until)

        if not commits:
            # Fallback: get most recent commit for file (no time filter)
            commits = git.get_commits_for_file(Path(file_path))

        if not commits:
            return None

        # Find commit nearest to timestamp
        nearest = min(
            commits,
            key=lambda c: abs((c.timestamp - timestamp).total_seconds())
        )

        return nearest.sha


__all__ = ['LinkModule']
