"""Document compilation and indexing

SQLite-first indexer using pure parsing functions.
No Qdrant dependency - uses VectorStore protocol.
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
import logging

from ..storage import VectorStore
from ..registry import SimpleRegistry
from .parser import parse_markdown_file, parse_conversation_file

logger = logging.getLogger(__name__)


class DocumentIndexer:
    """Compiles markdown documents into searchable chunks

    Handles:
    - Phase-based indexing (.context/develop, .context/design, .context/document)
    - Conversation indexing (Claude Code JSONL files)
    - Uses VectorStore protocol for backend-agnostic storage
    """

    def __init__(self, store: VectorStore):
        """Initialize indexer

        Args:
            store: VectorStore backend (SQLite or future HNSW)
        """
        if store is None:
            raise ValueError("VectorStore is required. Use SQLiteVectorStore.")
        self.store = store
        self.registry = SimpleRegistry()

    def index_phase(
        self,
        phase_name: str,
        project_root: Optional[Path] = None,
        force: bool = False,
        limit: Optional[int] = None,
        collection_override: Optional[str] = None
    ) -> Dict[str, Any]:
        """Index a specific phase (develop, design, document) or all context

        Args:
            phase_name: Phase to index ('develop', 'design', 'document', 'context')
            project_root: Project root (if None, uses registry)
            force: If True, clear existing chunks before indexing
            limit: Optional limit for number of documents
            collection_override: Optional collection name override for A/B testing

        Returns:
            Dictionary with:
                - indexed: Number of documents indexed
                - chunks: Total chunks created
                - skipped: Number of documents skipped
                - errors: List of error messages
                - collection_name: Collection used

        Raises:
            ValueError: If project not registered or phase directory missing
        """
        # Get project root
        if project_root is None:
            project_root = self.registry.get_project_root()
            if not project_root:
                raise ValueError("Not in a registered project. Run 'imem init' first.")

        # Get collection name
        if collection_override:
            collection_name = collection_override
        else:
            collections = self.registry.get_project_info(project_root).get('collections')
            if not collections:
                collections = self.registry.register_project(project_root)
            collection_name = collections['context']

        # Determine phases to index
        if phase_name == 'context':
            phases_to_index = ['develop', 'design', 'document']
        else:
            phases_to_index = [phase_name]

        # Clear existing if force
        if force:
            logger.info(f"Force mode: clearing existing chunks...")
            try:
                self.store.delete_collection(collection_name)
            except Exception as e:
                logger.warning(f"Could not clear collection: {e}")

        # Index each phase
        total_indexed = 0
        total_chunks = 0
        errors = []

        for phase in phases_to_index:
            phase_path = project_root / '.context' / phase
            if not phase_path.exists():
                logger.warning(f"Phase directory not found: {phase_path}")
                errors.append(f"Phase directory not found: {phase}")
                continue

            logger.info(f"Indexing {phase} phase...")

            # Find all .md files
            md_files = list(phase_path.rglob("*.md"))
            if limit:
                md_files = md_files[:limit]

            for md_file in md_files:
                try:
                    # Parse file into chunks
                    chunks = parse_markdown_file(
                        md_file,
                        phase=phase,
                        collection_name=collection_name
                    )

                    if chunks:
                        # Upsert via protocol
                        self.store.upsert(chunks)
                        total_indexed += 1
                        total_chunks += len(chunks)
                        logger.debug(f"Indexed {len(chunks)} chunks from {md_file.name}")

                except Exception as e:
                    error_msg = f"{md_file.name}: {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)

        # Update registry
        self.registry.update_doc_count(project_root, 'context', total_indexed)

        logger.info(f"Indexed {total_indexed} files, {total_chunks} chunks")

        return {
            'indexed': total_indexed,
            'chunks': total_chunks,
            'skipped': 0,
            'errors': errors,
            'collection_name': collection_name
        }

    def index_conversations(
        self,
        project_root: Optional[Path] = None,
        force: bool = False,
        limit: Optional[int] = None,
        collection_override: Optional[str] = None,
        project_filter: Optional[str] = None,
        folder_path: Optional[str] = None,
        session_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Index Claude Code conversations from JSONL files

        Args:
            project_root: Project root (if None, uses registry)
            force: If True, clear collection before indexing
            limit: Optional limit for number of conversations
            collection_override: Optional collection name override
            project_filter: Filter to specific project path
            folder_path: Custom folder to search for conversations
            session_ids: List of specific session IDs to index

        Returns:
            Dictionary with indexing results (indexed, skipped, errors)

        Raises:
            ValueError: If project not registered
        """
        # Get project root
        if project_root is None:
            project_root = self.registry.get_project_root()
            if not project_root:
                raise ValueError("Not in a registered project. Run 'imem init' first.")

        # Get collection name
        if collection_override:
            collection_name = collection_override
        else:
            collections = self.registry.get_project_info(project_root).get('collections')
            if not collections:
                collections = self.registry.register_project(project_root)
            collection_name = collections['conversations']

        # Clear existing if force
        if force:
            logger.info(f"Force mode: clearing conversation collection...")
            try:
                self.store.delete_collection(collection_name)
            except Exception as e:
                logger.warning(f"Could not clear collection: {e}")

        # Find conversation files
        # Default: ~/.claude/projects/*/conversations/*.jsonl
        if folder_path:
            search_path = Path(folder_path)
        else:
            search_path = Path.home() / '.claude' / 'projects'

        if not search_path.exists():
            return {
                'indexed': 0,
                'chunks': 0,
                'skipped': 0,
                'errors': [f"Conversation path not found: {search_path}"]
            }

        # Collect JSONL files
        jsonl_files = list(search_path.rglob("*.jsonl"))
        if project_filter:
            jsonl_files = [f for f in jsonl_files if project_filter in str(f)]
        if session_ids:
            jsonl_files = [f for f in jsonl_files if f.stem in session_ids]
        if limit:
            jsonl_files = jsonl_files[:limit]

        logger.info(f"Found {len(jsonl_files)} conversation files")

        # Index conversations
        total_indexed = 0
        total_chunks = 0
        errors = []

        for jsonl_file in jsonl_files:
            try:
                # Extract session metadata from JSONL
                import json
                messages = []
                with open(jsonl_file, 'r') as f:
                    for line in f:
                        if line.strip():
                            messages.append(json.loads(line))

                if not messages:
                    continue

                session_id = jsonl_file.stem
                first_msg = messages[0] if messages else {}
                last_msg = messages[-1] if messages else {}

                conv_metadata = {
                    'start_time': first_msg.get('timestamp'),
                    'message_count': len(messages),
                    'duration_minutes': None,  # TODO: Calculate from timestamps
                    'has_changelog': False,
                    'changelog_path': None
                }

                # For now, create simple chunks from JSONL directly
                # (Full TRACE markdown conversion would be separate step)
                chunks = []
                for i, msg in enumerate(messages):
                    role = msg.get('type', 'unknown')
                    content = ''

                    if role == 'human':
                        content = msg.get('message', {}).get('content', '')
                        if isinstance(content, list):
                            content = ' '.join([
                                c.get('text', '') for c in content
                                if isinstance(c, dict) and c.get('type') == 'text'
                            ])
                    elif role == 'assistant':
                        content = msg.get('message', {}).get('content', '')
                        if isinstance(content, list):
                            content = ' '.join([
                                c.get('text', '') for c in content
                                if isinstance(c, dict) and c.get('type') == 'text'
                            ])

                    if content and len(content) > 50:  # Skip tiny messages
                        from uuid import uuid4
                        # FLAT structure for SQLite indexed columns
                        chunks.append({
                            'id': str(uuid4()),
                            'content': content[:10000],  # Limit chunk size
                            # Top-level fields (SQLite indexed columns)
                            'file_path': str(jsonl_file),
                            'phase': None,  # Conversations don't have phase
                            'section_type': 'message',
                            'section_name': f"Message {i}",
                            'timestamp': conv_metadata.get('start_time'),
                            'session_id': session_id,
                            # Metadata blob (JSON column for extras)
                            'metadata': {
                                'source': 'conversation',
                                'collection': collection_name,
                                'message_index': i,
                                'role': 'user' if role == 'human' else 'assistant',
                                'chunk_type': 'message',
                                'message_count': conv_metadata.get('message_count'),
                            }
                        })

                if chunks:
                    self.store.upsert(chunks)
                    total_indexed += 1
                    total_chunks += len(chunks)
                    logger.debug(f"Indexed {len(chunks)} chunks from {session_id[:12]}")

            except Exception as e:
                error_msg = f"{jsonl_file.name}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)

        # Update registry
        self.registry.update_doc_count(project_root, 'conversations', total_indexed)

        logger.info(f"Indexed {total_indexed} conversations, {total_chunks} chunks")

        return {
            'indexed': total_indexed,
            'chunks': total_chunks,
            'skipped': 0,
            'errors': errors,
            'collection_name': collection_name
        }
