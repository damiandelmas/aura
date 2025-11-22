"""Markdown parsing for knowledge compilation

Pure parsing functions - no ML dependencies.
Uses lightweight custom parser instead of LlamaIndex.
Returns data structures for VectorStore.upsert().
"""

import re
import yaml
import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from .parse.markdown import MarkdownParser

logger = logging.getLogger(__name__)

# Chunk size limit (Nomic Embed v1.5: 8k tokens ~ 32k chars)
MAX_CHUNK_SIZE = 30000

# Shared parser instance
_parser = MarkdownParser()


def extract_phase(file_path: Path) -> str:
    """Extract lifecycle phase from file path

    Args:
        file_path: Path to markdown file

    Returns:
        Phase name ('design', 'designate', 'develop', 'document', 'unknown')
    """
    path_str = str(file_path)

    if '/design/' in path_str:
        return 'design'
    elif '/designate/' in path_str:
        return 'designate'
    elif '/develop/' in path_str:
        return 'develop'
    elif '/document/' in path_str:
        return 'document'
    else:
        return 'unknown'


def extract_frontmatter(content: str) -> dict:
    """Extract YAML frontmatter from markdown

    Args:
        content: Raw markdown content

    Returns:
        Parsed frontmatter dict (empty if none)
    """
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
    if not match:
        return {}

    try:
        return yaml.safe_load(match.group(1)) or {}
    except Exception:
        return {}


def detect_layer(file_path: Path, phase: str) -> str:
    """Detect layer (implementation/pattern) based on filename and phase

    Only develop phase has pattern mirrors. Other phases are always 'implementation'.

    Args:
        file_path: Path to markdown file
        phase: Lifecycle phase

    Returns:
        'implementation' or 'pattern'
    """
    if phase != 'develop':
        return 'implementation'

    if '.pattern.md' in str(file_path):
        return 'pattern'
    return 'implementation'


def _generate_chunk_id(file_path: Path, section_name: str, content: str) -> str:
    """Generate deterministic ID from file path + section + content hash"""
    content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()[:12]
    base = f"{file_path.stem}_{section_name}_{content_hash}"
    return re.sub(r'[^\w\-]', '_', base)


def _detect_structured_fields(content: str) -> dict:
    """Detect presence of structured documentation fields"""
    return {
        'has_context': '**Context**' in content or '- **Context**:' in content,
        'has_solution': '**Solution**' in content or '- **Solution**:' in content,
        'has_rationale': '**Rationale**' in content or '- **Rationale**:' in content,
        'has_alternatives': '**Alternatives**' in content or '- **Alternatives**:' in content,
        'has_approach': '**Approach**' in content or '- **Approach**:' in content,
        'has_benefits': '**Benefits**' in content or '- **Benefits**:' in content,
        'has_drawbacks': '**Drawbacks**' in content or '- **Drawbacks**:' in content,
    }


def parse_markdown_file(
    file_path: Path,
    phase: Optional[str] = None,
    collection_name: str = "imem"
) -> List[Dict[str, Any]]:
    """Parse markdown file into chunks ready for VectorStore.upsert()

    Args:
        file_path: Path to markdown file
        phase: Override phase detection (if None, auto-detect from path)
        collection_name: Base collection name for layer routing

    Returns:
        List of chunk dicts with: id, content, metadata (ready for upsert)

    Note:
        Does NOT generate embeddings. Caller should batch-encode content
        and add 'vector' key before upserting to vector-enabled stores.
    """
    # Auto-detect phase if not provided
    if not phase:
        phase = extract_phase(file_path)

    # Detect layer for collection routing
    layer = detect_layer(file_path, phase)
    target_collection = f"{collection_name}_pattern" if layer == 'pattern' else f"{collection_name}_impl"

    # Read file for frontmatter extraction
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            raw_content = f.read()
    except Exception as e:
        logger.error(f"Error reading {file_path}: {e}")
        return []

    # Extract frontmatter
    frontmatter = extract_frontmatter(raw_content)

    # Parse with lightweight custom parser
    raw_chunks = _parser.parse_file(file_path)

    if not raw_chunks:
        logger.warning(f"No chunks parsed from {file_path}")
        return []

    # Convert to flat structure for SQLite
    chunks = []
    large_chunks = []

    for raw_chunk in raw_chunks:
        content = raw_chunk['content']
        section_name = raw_chunk['section_name']
        section_type = raw_chunk['section_type']

        # Skip empty sections
        if len(content.strip()) < 20:
            continue

        # Warn about large chunks
        char_count = len(content)
        if char_count > MAX_CHUNK_SIZE:
            large_chunks.append({
                'section': section_name,
                'size': char_count,
                'file': str(file_path)
            })

        # Detect structured fields
        structured = _detect_structured_fields(content)

        # Extract type category/subtype from frontmatter
        doc_type = frontmatter.get('type', '')
        category = doc_type.split('.')[0] if '.' in doc_type else doc_type
        subtype = doc_type.split('.')[1] if '.' in doc_type else None

        # Get H2 parent if available (from custom parser)
        h2_parent = raw_chunk.get('h2_parent')

        # Build chunk - FLAT structure for SQLite indexed columns
        chunk = {
            'id': _generate_chunk_id(file_path, section_name, content),
            'content': content,
            # Top-level fields (SQLite indexed columns)
            'file_path': str(file_path),
            'phase': phase,
            'section_type': h2_parent or section_type,
            'section_name': section_name,
            'timestamp': frontmatter.get('timestamp'),
            'session_id': frontmatter.get('session_id'),
            # Metadata blob (JSON column for extras)
            'metadata': {
                'source': 'context',
                'layer': layer,
                'collection': target_collection,
                'category': category,
                'subtype': subtype,
                **structured,
                'schema_version': 'v1.0',
                'word_count': len(content.split()),
                'char_count': char_count,
            }
        }
        chunks.append(chunk)

    # Log warnings for large chunks
    for chunk_info in large_chunks:
        logger.warning(
            f"Large chunk ({chunk_info['size']} chars) may exceed token limit: "
            f"{chunk_info['section']} in {Path(chunk_info['file']).name}"
        )

    logger.debug(f"Parsed {len(chunks)} chunks from {file_path.name}")
    return chunks


def parse_conversation_section(section_name: str) -> dict:
    """Parse TRACE H2 headers into structured metadata

    Args:
        section_name: H2 header like "Message 1: USER" or "Code Patch 1: src/cli.py"

    Returns:
        Dict with chunk_type, role (for messages), or file_path (for patches)

    Examples:
        "Message 1: USER" -> {'chunk_type': 'message', 'role': 'user'}
        "Message 2: ASSISTANT" -> {'chunk_type': 'message', 'role': 'assistant'}
        "Message 2 Extended Thinking" -> {'chunk_type': 'thinking', 'role': 'assistant'}
        "Code Patch 1: src/cli.py" -> {'chunk_type': 'patch', 'file_path': 'src/cli.py'}
    """
    metadata = {}

    if section_name.startswith('Message'):
        if 'Extended Thinking' in section_name:
            metadata['chunk_type'] = 'thinking'
            metadata['role'] = 'assistant'
        elif ' Tools' in section_name:
            metadata['chunk_type'] = 'tools'
            metadata['role'] = 'assistant'
        else:
            metadata['chunk_type'] = 'message'
            if 'USER' in section_name:
                metadata['role'] = 'user'
            elif 'ASSISTANT' in section_name:
                metadata['role'] = 'assistant'

    elif section_name.startswith('Code Patch'):
        metadata['chunk_type'] = 'patch'
        match = re.match(r'Code Patch \d+:\s*(.+)', section_name)
        if match:
            metadata['file_path'] = match.group(1).strip()

    return metadata


def parse_conversation_file(
    markdown_path: Path,
    session_id: str,
    conv_metadata: dict,
    collection_name: str = "imem"
) -> List[Dict[str, Any]]:
    """Parse conversation markdown into chunks ready for VectorStore.upsert()

    Args:
        markdown_path: Path to conversation markdown (from TRACE export)
        session_id: Session ID from JSONL
        conv_metadata: Conversation metadata (start_time, duration, message_count, etc.)
        collection_name: Collection name for conversations

    Returns:
        List of chunk dicts with: id, content, metadata (ready for upsert)
    """
    # Parse with lightweight custom parser
    raw_chunks = _parser.parse_file(markdown_path)

    if not raw_chunks:
        logger.warning(f"No chunks parsed from conversation {session_id}")
        return []

    chunks = []
    for raw_chunk in raw_chunks:
        content = raw_chunk['content']
        section_name = raw_chunk['section_name']

        # Parse section for rich metadata
        parsed_meta = parse_conversation_section(section_name)

        # FLAT structure for SQLite indexed columns
        chunk = {
            'id': _generate_chunk_id(markdown_path, section_name, content),
            'content': content,
            # Top-level fields (SQLite indexed columns)
            'file_path': str(markdown_path),
            'phase': None,  # Conversations don't have phase
            'section_type': section_name,
            'section_name': section_name,
            'timestamp': conv_metadata.get('start_time'),
            'session_id': session_id,
            # Metadata blob (JSON column for extras)
            'metadata': {
                'source': 'conversation',
                'collection': collection_name,
                'duration_minutes': conv_metadata.get('duration_minutes'),
                'message_count': conv_metadata.get('message_count'),
                'has_changelog': conv_metadata.get('has_changelog', False),
                'changelog_path': conv_metadata.get('changelog_path'),
                **parsed_meta  # chunk_type, role
            }
        }
        chunks.append(chunk)

    logger.debug(f"Parsed {len(chunks)} chunks from conversation {session_id[:12]}")
    return chunks
