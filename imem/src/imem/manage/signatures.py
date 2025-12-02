"""Signature Extractor - Extract code blocks as validation anchors

SignatureExtractor extracts code blocks from markdown chunks and creates
validation anchors. These anchors link documentation to ground truth:
- Extract ```language code blocks
- Infer file_path via git search
- Store in chunk_signatures table

Chunks with signatures are "anchored" - they can be validated directly
against the codebase. Chunks without signatures derive validity through
graph proximity.

EPIC 1 implementation.
"""

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING
import logging
import re

from ..protocols import Module

if TYPE_CHECKING:
    from ..context import IndexContext

logger = logging.getLogger(__name__)


@dataclass
class Signature:
    """Code signature extracted from a chunk

    Attributes:
        chunk_id: ID of source chunk
        content: The extracted code
        language: Programming language (if detected)
        file_path: Resolved file path in repo (nullable)
        signature_hash: Hash of the content for deduplication
    """
    chunk_id: str
    content: str
    language: Optional[str]
    file_path: Optional[str]
    signature_hash: str


# Code fence regex: ```language\ncode\n```
CODE_FENCE_PATTERN = re.compile(
    r'```(\w+)?\s*\n(.*?)\n```',
    re.DOTALL
)

# Path annotation patterns (e.g., "# file: src/foo.py" in first line)
PATH_ANNOTATION_PATTERNS = [
    re.compile(r'^#\s*file:\s*(.+)$', re.IGNORECASE | re.MULTILINE),
    re.compile(r'^//\s*file:\s*(.+)$', re.IGNORECASE | re.MULTILINE),
    re.compile(r'^<!--\s*file:\s*(.+?)\s*-->$', re.IGNORECASE | re.MULTILINE),
]


class SignatureExtractor(Module):
    """Extract code signatures from chunks

    Creates validation anchors by:
    1. Finding ```code blocks``` in chunk content
    2. Extracting language and code
    3. Inferring file_path via git search
    4. Storing signatures in chunk_signatures table
    """

    # Minimum code length to consider as signature
    MIN_CODE_LENGTH = 20

    # Maximum code length for git search (avoid huge snippets)
    MAX_SEARCH_LENGTH = 100

    @property
    def name(self) -> str:
        return "signatures"

    def execute(
        self,
        chunks: List[Dict[str, Any]],
        context: 'IndexContext'
    ) -> List[Dict[str, Any]]:
        """Extract signatures from chunks and persist to database

        Args:
            chunks: Chunks to process
            context: Index context with infrastructure

        Returns:
            Chunks unchanged (signatures stored in separate table)
        """
        db = context.infrastructure.db

        total_signatures = 0

        for chunk in chunks:
            try:
                signatures = self.extract(chunk, context)

                if signatures:
                    self._persist_signatures(signatures, db)
                    total_signatures += len(signatures)

            except Exception as e:
                logger.warning(f"Signature extraction failed for chunk {chunk.get('id', 'unknown')}: {e}")

        logger.debug(f"SignatureExtractor created {total_signatures} signatures from {len(chunks)} chunks")
        return chunks

    def extract(
        self,
        chunk: Dict[str, Any],
        context: 'IndexContext'
    ) -> List[Signature]:
        """Extract code signatures from a single chunk

        Args:
            chunk: Chunk to analyze
            context: Index context

        Returns:
            List of extracted signatures
        """
        content = chunk.get('content', '')
        chunk_id = chunk.get('id')

        if not content or not chunk_id:
            return []

        signatures = []

        # Find all code fences
        for match in CODE_FENCE_PATTERN.finditer(content):
            language = match.group(1)  # May be None
            code = match.group(2).strip()

            # Skip short snippets
            if len(code) < self.MIN_CODE_LENGTH:
                continue

            # Compute hash
            sig_hash = sha256(code.encode()).hexdigest()[:16]

            # Try to infer file_path
            file_path = self._infer_file_path(code, language, context)

            signatures.append(Signature(
                chunk_id=chunk_id,
                content=code,
                language=language,
                file_path=file_path,
                signature_hash=sig_hash,
            ))

        return signatures

    def _infer_file_path(
        self,
        code: str,
        language: Optional[str],
        context: 'IndexContext'
    ) -> Optional[str]:
        """Infer file_path for code snippet

        Strategy:
        1. Check for path annotation in code
        2. Fall back to git.search_content()
        3. Return None if ambiguous (multiple matches)
        """
        # 1. Check for explicit path annotation
        for pattern in PATH_ANNOTATION_PATTERNS:
            match = pattern.search(code)
            if match:
                return match.group(1).strip()

        # 2. Git search
        git = context.infrastructure.git

        # Use first line(s) of code for search (more unique)
        search_snippet = self._extract_search_snippet(code)
        if not search_snippet:
            return None

        # Build glob filter based on language
        glob_filter = self._language_to_glob(language)

        matches = git.search_content(search_snippet, glob=glob_filter)

        # Single match = confident
        if len(matches) == 1:
            return str(matches[0].path)

        # Multiple matches = ambiguous, return None
        if len(matches) > 1:
            logger.debug(f"Ambiguous file_path: {len(matches)} matches for signature")
            return None

        return None

    def _extract_search_snippet(self, code: str) -> Optional[str]:
        """Extract a unique snippet for git search

        Takes first non-empty, non-comment line up to MAX_SEARCH_LENGTH.
        """
        for line in code.split('\n'):
            line = line.strip()

            # Skip empty lines
            if not line:
                continue

            # Skip common comment patterns
            if line.startswith('#') or line.startswith('//') or line.startswith('/*'):
                continue

            # Skip import/include statements (too common)
            if line.startswith(('import ', 'from ', '#include', 'use ', 'require ')):
                continue

            # Found a candidate line
            if len(line) >= 10:
                # Escape regex special chars for git grep
                snippet = re.escape(line[:self.MAX_SEARCH_LENGTH])
                return snippet

        return None

    def _language_to_glob(self, language: Optional[str]) -> Optional[str]:
        """Convert language hint to glob pattern"""
        if not language:
            return None

        mapping = {
            'python': '*.py',
            'py': '*.py',
            'javascript': '*.js',
            'js': '*.js',
            'typescript': '*.ts',
            'ts': '*.ts',
            'tsx': '*.tsx',
            'jsx': '*.jsx',
            'rust': '*.rs',
            'go': '*.go',
            'java': '*.java',
            'c': '*.c',
            'cpp': '*.cpp',
            'c++': '*.cpp',
            'sql': '*.sql',
            'ruby': '*.rb',
            'rb': '*.rb',
            'shell': '*.sh',
            'bash': '*.sh',
            'sh': '*.sh',
            'yaml': '*.yaml',
            'yml': '*.yml',
            'json': '*.json',
            'toml': '*.toml',
            'markdown': '*.md',
            'md': '*.md',
        }

        return mapping.get(language.lower())

    def _persist_signatures(self, signatures: List[Signature], db: Any) -> None:
        """Persist signatures to chunk_signatures table"""
        for sig in signatures:
            try:
                db.conn.execute('''
                    INSERT OR REPLACE INTO chunk_signatures
                    (chunk_id, content, language, file_path, signature_hash)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    sig.chunk_id,
                    sig.content,
                    sig.language,
                    sig.file_path,
                    sig.signature_hash,
                ))
            except Exception as e:
                logger.warning(f"Failed to persist signature: {e}")

        db.conn.commit()


__all__ = ['SignatureExtractor', 'Signature']
