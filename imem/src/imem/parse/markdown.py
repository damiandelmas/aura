"""Lightweight markdown parser without vectorization

Parses markdown files into typed chunks with rich metadata.
No ML, no vectors, just metadata extraction and section splitting.
"""

import frontmatter
import hashlib
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime


class MarkdownParser:
    """Parse markdown without vectorization for fast metadata indexing"""

    def parse_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """Parse single markdown file into chunks with inherited metadata

        Args:
            file_path: Path to markdown file

        Returns:
            List of chunks, each containing:
                - id: Unique identifier (file_path + section hash)
                - file_path: Relative or absolute path
                - phase: Lifecycle phase (design/designate/develop/document)
                - section_type: Type of section (from header or inferred)
                - section_name: Header text
                - content: Section content
                - timestamp: From frontmatter or file mtime
                - metadata: All frontmatter + inherited context
        """
        # Load with frontmatter
        try:
            post = frontmatter.load(file_path)
        except Exception as e:
            # Fallback: treat as plain markdown
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            post = frontmatter.Post(content)

        # Detect phase from path
        phase = self._detect_phase(file_path)

        # Document-level metadata
        doc_metadata = {
            'file_path': str(file_path),
            'phase': phase,
            'timestamp': post.get('timestamp') or self._get_mtime(file_path),
            'session_id': post.get('session_id'),
            'frontmatter': dict(post.metadata)
        }

        # Split into sections
        sections = self._split_sections(post.content, phase)

        # Create chunks (section + inherited doc metadata)
        chunks = []
        for section in sections:
            chunk = {
                'id': self._generate_id(file_path, section),
                'section_type': section['type'],
                'section_name': section['name'],
                'content': section['content'],
                **doc_metadata  # Inherit document metadata
            }
            chunks.append(chunk)

        return chunks

    def _detect_phase(self, file_path: Path) -> str:
        """Extract phase from path (.context/design/ → design)"""
        parts = file_path.parts
        if '.context' in parts:
            idx = parts.index('.context')
            if idx + 1 < len(parts):
                phase = parts[idx + 1]
                # Normalize phase names
                if phase in ('design', 'designate', 'develop', 'document'):
                    return phase
        return 'unknown'

    def _get_mtime(self, file_path: Path) -> str:
        """Get file modification time as ISO timestamp"""
        try:
            mtime = file_path.stat().st_mtime
            return datetime.fromtimestamp(mtime).isoformat()
        except:
            return None

    def _split_sections(self, content: str, phase: str) -> List[Dict[str, str]]:
        """Split by headers (H2 or H3 depending on document type)

        Changelogs: H3 level (### Decision, ### Implementation)
        Conversations: H2 level (## Message 1)
        Architecture: H2 level (## Core Capabilities)
        """
        # Detect document type from content patterns
        doc_type = self._detect_document_type(content)

        if doc_type == 'changelog':
            return self._split_by_h3(content)
        else:
            return self._split_by_h2(content)

    def _split_by_h2(self, content: str) -> List[Dict[str, str]]:
        """Split by ## headers"""
        sections = []
        current_section = None

        for line in content.split('\n'):
            if line.startswith('## '):
                if current_section and current_section['content'].strip():
                    sections.append(current_section)
                current_section = {
                    'type': self._infer_type(line),
                    'name': line[3:].strip(),
                    'content': ''
                }
            elif current_section:
                current_section['content'] += line + '\n'

        if current_section and current_section['content'].strip():
            sections.append(current_section)

        return sections if sections else [{'type': 'document', 'name': 'Full Document', 'content': content}]

    def _split_by_h3(self, content: str) -> List[Dict[str, str]]:
        """Split by ### headers (for changelogs)"""
        sections = []
        current_section = None
        current_h2 = None

        for line in content.split('\n'):
            # Track H2 context (e.g., "## Decisions")
            if line.startswith('## '):
                current_h2 = line[3:].strip()
            # Split on H3
            elif line.startswith('### '):
                if current_section and current_section['content'].strip():
                    sections.append(current_section)
                section_name = line[4:].strip()
                current_section = {
                    'type': self._infer_type(line),
                    'name': section_name,
                    'h2_parent': current_h2,
                    'content': ''
                }
            elif current_section:
                current_section['content'] += line + '\n'

        if current_section and current_section['content'].strip():
            sections.append(current_section)

        return sections if sections else [{'type': 'document', 'name': 'Full Document', 'content': content}]

    def _infer_type(self, header: str) -> str:
        """Infer section_type from header text

        "## Decision" → "Decision"
        "## Core Capabilities" → "Core Capabilities"
        "### Implementation" → "Implementation"
        """
        # Strip markdown, clean
        clean = header.replace('#', '').strip()
        # Take first part before colon
        return clean.split(':')[0].strip()

    def _detect_document_type(self, content: str) -> str:
        """Detect if changelog, architecture, conversation, etc.

        Heuristics:
        - Has "### Decision" or "### Implementation" → changelog
        - Has "## Message" → conversation
        - Else → generic architecture/design doc
        """
        if '### Decision' in content or '### Implementation' in content or '### Context' in content:
            return 'changelog'
        elif '## Message' in content:
            return 'conversation'
        return 'architecture'

    def _generate_id(self, file_path: Path, section: Dict[str, str]) -> str:
        """Generate unique ID from file path + section content hash"""
        # Hash the section content for uniqueness
        content_hash = hashlib.md5(
            section['content'].encode('utf-8')
        ).hexdigest()[:12]

        # Combine file name + section name + content hash
        base = f"{file_path.stem}_{section['name']}_{content_hash}"

        # Sanitize for use as ID
        base = re.sub(r'[^\w\-]', '_', base)

        return base
