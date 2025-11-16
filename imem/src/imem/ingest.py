#!/usr/bin/env python3
"""
Enhanced Modular Ingestion System with Deduplication
- Tracks existing documents by file path
- Supports incremental ingestion
- Prevents duplicate document insertion
"""

import sys
import argparse
import glob
import json
import random
import hashlib
import os
import logging
import re
import yaml
from pathlib import Path
from typing import List, Dict, Any, Set
from datetime import datetime
from uuid import uuid4
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, CollectionParams, Filter, FieldCondition, MatchValue
from sentence_transformers import SentenceTransformer
from llama_index.core.node_parser import MarkdownNodeParser
from llama_index.core.schema import Document as LlamaDocument
from .search import SearchConfig, ModularSearch
from .registry import SimpleRegistry
from .config import config

logger = logging.getLogger(__name__)


class EnhancedModularIngest:
    """Enhanced ingestion system with deduplication and incremental updates"""

    def __init__(self):
        """Initialize the enhanced modular ingestion system.

        Creates a Qdrant client connection, initializes the modular search system,
        and sets up the project registry for path management during ingestion.

        Args:
            None

        Returns:
            None

        Attributes:
            client: QdrantClient instance connected to localhost:6334
            modular_search: ModularSearch instance for managing search configurations
            registry: SimpleRegistry for project path management
            parser: LlamaIndex MarkdownNodeParser for section-level chunking
            model: SentenceTransformer model for embeddings
        """
        self.client = QdrantClient(host="localhost", port=6334)
        self.modular_search = ModularSearch()
        self.registry = SimpleRegistry()
        self.parser = MarkdownNodeParser()
        self.model = None  # Lazy load when needed
        self.validation_stats = {
            'total_processed': 0,
            'validation_passed': 0,
            'validation_failed': 0,
            'validation_warnings': 0
        }
    
    def get_existing_file_paths(self, collection_name: str) -> Set[str]:
        """Get set of file paths already in collection.

        Scrolls through all points in the specified collection to extract unique
        file paths. Used for incremental ingestion to skip already-indexed documents.

        Args:
            collection_name: Name of the Qdrant collection to query

        Returns:
            Set of file path strings found in the collection's point payloads.
            Returns empty set if collection doesn't exist or on error.
        """
        try:
            # Scroll through all points to get file paths
            existing_paths = set()
            offset = None
            
            while True:
                points, next_offset = self.client.scroll(
                    collection_name=collection_name,
                    limit=100,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False
                )
                
                for point in points:
                    if 'file_path' in point.payload:
                        existing_paths.add(point.payload['file_path'])
                
                if next_offset is None:
                    break
                offset = next_offset
            
            return existing_paths
            
        except Exception as e:
            logger.error(f"Error getting existing file paths: {e}")
            return set()

    def get_existing_content_hashes(self, collection_name: str) -> Dict[str, Dict[str, str]]:
        """Get mapping of content_hash -> {file_path, point_id} for existing documents.

        Scrolls through all points in the collection to build a mapping of MD5
        content hashes to their corresponding file paths and point IDs. Used for
        content-based deduplication and path migration detection.

        Args:
            collection_name: Name of the Qdrant collection to query

        Returns:
            Dictionary mapping MD5 hash strings to dictionaries containing:
                - 'file_path': The document's current file path
                - 'point_id': The Qdrant point ID (int or str)
            Returns empty dict if collection doesn't exist or on error.
        """
        try:
            # Scroll through all points to get content hashes
            existing_hashes = {}
            offset = None

            while True:
                points, next_offset = self.client.scroll(
                    collection_name=collection_name,
                    limit=100,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False
                )

                for point in points:
                    payload = point.payload
                    if 'file_hash' in payload and 'file_path' in payload:
                        file_hash = payload['file_hash']
                        existing_hashes[file_hash] = {
                            'file_path': payload['file_path'],
                            'point_id': point.id  # Keep original type
                        }

                if next_offset is None:
                    break
                offset = next_offset

            return existing_hashes

        except Exception as e:
            logger.error(f"Error getting existing content hashes: {e}")
            return {}

    def update_file_path(self, collection_name: str, point_id: str, new_file_path: str) -> bool:
        """Update the file_path in an existing point's payload.

        Modifies an existing document's file_path metadata when the same content
        (same MD5 hash) is found at a new location. This avoids creating duplicate
        vectors and instead updates the path reference.

        Args:
            collection_name: Name of the Qdrant collection
            point_id: ID of the point to update (int or str format)
            new_file_path: New file path to set in the payload

        Returns:
            True if update succeeded, False if point not found or update failed.

        Notes:
            - Adds a 'path_updated_at' timestamp to track when path was changed
            - Handles both integer and string UUID point ID formats
            - Preserves all other payload fields
        """
        try:
            # Get the existing point
            points = self.client.retrieve(
                collection_name=collection_name,
                ids=[point_id],
                with_payload=True
            )

            if not points:
                logger.warning(f"Point {point_id} not found")
                return False

            # Update the payload with new file path
            existing_payload = points[0].payload
            existing_payload['file_path'] = new_file_path
            existing_payload['path_updated_at'] = datetime.now().isoformat()

            # Update the point - ensure point_id is converted to correct type
            try:
                # Try as integer first (newer Qdrant format)
                point_id_int = int(point_id)
                self.client.set_payload(
                    collection_name=collection_name,
                    points=[point_id_int],
                    payload=existing_payload
                )
            except ValueError:
                # Fall back to string UUID format
                self.client.set_payload(
                    collection_name=collection_name,
                    points=[point_id],
                    payload=existing_payload
                )

            return True

        except Exception as e:
            logger.error(f"Error updating file path for point {point_id}: {e}")
            return False

    def deduplicate_collection(self, collection_name: str, dry_run: bool = False) -> Dict[str, int]:
        """Remove duplicate content based on file hashes"""
        try:
            logger.info(f"Analyzing duplicates in collection '{collection_name}'...")

            # Get all points with their hashes
            hash_groups = {}
            file_paths = {}
            offset = None
            total_points = 0

            while True:
                points, next_offset = self.client.scroll(
                    collection_name=collection_name,
                    limit=100,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False
                )

                for point in points:
                    total_points += 1
                    payload = point.payload

                    # Group by file path
                    if 'file_path' in payload:
                        file_path = payload['file_path']
                        if file_path in file_paths:
                            file_paths[file_path].append(point.id)
                        else:
                            file_paths[file_path] = [point.id]

                    # Group by content hash
                    if 'file_hash' in payload:
                        file_hash = payload['file_hash']
                        if file_hash in hash_groups:
                            hash_groups[file_hash].append({
                                'id': point.id,
                                'file_path': payload.get('file_path', 'unknown'),
                                'ingestion_timestamp': payload.get('ingestion_timestamp', ''),
                                'path_updated_at': payload.get('path_updated_at', '')
                            })
                        else:
                            hash_groups[file_hash] = [{
                                'id': point.id,
                                'file_path': payload.get('file_path', 'unknown'),
                                'ingestion_timestamp': payload.get('ingestion_timestamp', ''),
                                'path_updated_at': payload.get('path_updated_at', '')
                            }]

                if next_offset is None:
                    break
                offset = next_offset

            # Find duplicates
            path_duplicates = {path: ids for path, ids in file_paths.items() if len(ids) > 1}
            hash_duplicates = {hash_val: points for hash_val, points in hash_groups.items() if len(points) > 1}

            logger.info(f"Collection Analysis:")
            logger.info(f"   Total points: {total_points}")
            logger.info(f"   Unique content hashes: {len(hash_groups)}")
            logger.info(f"   Path-based duplicates: {len(path_duplicates)} paths")
            logger.info(f"   Content-based duplicates: {len(hash_duplicates)} content groups")

            if not hash_duplicates and not path_duplicates:
                logger.info("No duplicates found!")
                return {'removed': 0, 'total': total_points}

            # Process content-based duplicates
            removed_count = 0
            if hash_duplicates:
                logger.info(f"Processing {len(hash_duplicates)} content duplicate groups...")

                for content_hash, duplicate_points in hash_duplicates.items():
                    if len(duplicate_points) < 2:
                        continue

                    # Sort by newest first (most recent ingestion or path update)
                    def sort_key(point):
                        path_updated = point.get('path_updated_at', '')
                        ingestion = point.get('ingestion_timestamp', '')
                        return max(path_updated, ingestion) if path_updated else ingestion

                    sorted_points = sorted(duplicate_points, key=sort_key, reverse=True)
                    keep_point = sorted_points[0]  # Keep the most recent
                    remove_points = sorted_points[1:]  # Remove the rest

                    logger.info(f"  Content hash {content_hash[:8]}...")
                    logger.info(f"    Keeping: {keep_point['file_path']}")

                    for remove_point in remove_points:
                        logger.info(f"    Removing: {remove_point['file_path']}")

                        if not dry_run:
                            try:
                                self.client.delete(
                                    collection_name=collection_name,
                                    points_selector=[remove_point['id']]
                                )
                                removed_count += 1
                            except Exception as e:
                                logger.error(f"Error removing point: {e}")

            result = {'removed': removed_count, 'total': total_points}

            if dry_run:
                logger.info(f"DRY RUN: Would remove {removed_count} duplicate points")
            else:
                logger.info(f"Removed {removed_count} duplicate points")

            return result

        except Exception as e:
            logger.error(f"Error during deduplication: {e}")
            return {'removed': 0, 'total': 0}
    
    def create_collection(self, config: SearchConfig, recreate: bool = False):
        """Create collection for given configuration.

        Creates a new Qdrant collection with the specified vector configuration.
        If collection already exists and recreate is False, does nothing. If
        recreate is True, deletes existing collection first.

        Args:
            config: SearchConfig object containing collection_name, vector_name,
                   and dimensions for the vector configuration
            recreate: If True, delete existing collection before creating new one

        Returns:
            None. Prints status messages to stdout.

        Notes:
            - Uses COSINE distance metric for vector similarity
            - Collection persists in Qdrant storage even after service restart
            - Prints document count if collection already exists
        """

        if recreate:
            try:
                self.client.delete_collection(config.collection_name)
                logger.info(f"Deleted existing collection: {config.collection_name}")
            except KeyboardInterrupt:
                raise  # Allow user to cancel
            except (ConnectionError, TimeoutError) as e:
                logger.debug(f"Collection delete failed (may not exist): {e}")
            except Exception as e:
                logger.debug(f"Error deleting collection: {e}")

        # Check if collection already exists
        try:
            info = self.client.get_collection(config.collection_name)
            logger.info(f"Collection '{config.collection_name}' already exists ({info.points_count} documents)")
            return
        except KeyboardInterrupt:
            raise  # Allow user to cancel
        except (ConnectionError, TimeoutError) as e:
            logger.debug(f"Collection does not exist or not accessible: {e}")
        except Exception as e:
            logger.debug(f"Collection check failed, will create: {e}")

        # Create new collection
        self.client.create_collection(
            collection_name=config.collection_name,
            vectors_config={
                config.vector_name: VectorParams(
                    size=config.dimensions,
                    distance=Distance.COSINE
                )
            }
        )

        logger.info(f"Created collection: {config.collection_name}")
        logger.info(f"   Vector: {config.vector_name} ({config.dimensions}D)")
    
    def ingest_documents(self, config_name: str, source_dir: str = None, 
                        batch_size: int = 100, sample_size: int = None,
                        incremental: bool = True, force_reindex: bool = False,
                        project_root: Path = None):
        """Ingest documents with deduplication support"""
        
        if config_name not in self.modular_search.configs:
            logger.error(f"Configuration '{config_name}' not found")
            self.modular_search.list_available_configs()
            return
        
        config = self.modular_search.configs[config_name]
        
        # Create collection
        self.create_collection(config, recreate=force_reindex)
        
        # Get existing file paths and content hashes for deduplication
        existing_paths = set()
        existing_hashes = {}
        if incremental and not force_reindex:
            logger.info("Checking for existing documents...")
            existing_paths = self.get_existing_file_paths(config.collection_name)
            existing_hashes = self.get_existing_content_hashes(config.collection_name)
            logger.info(f"   Found {len(existing_paths)} existing documents")
            logger.info(f"   Found {len(existing_hashes)} unique content hashes")
        
        # Load model
        logger.info(f"Loading model: {config.model_name}")
        model = SentenceTransformer(config.model_name, trust_remote_code=True)
        
        # Get document files using os.walk to include hidden directories
        if source_dir is None:
            source_dir = "/home/axp/projects/ADG_Qdrant/ingest"
        
        all_doc_files = []
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                if file.endswith('.md'):
                    all_doc_files.append(os.path.join(root, file))
        
        # Filter out existing documents if incremental
        if incremental and existing_paths:
            new_files = [f for f in all_doc_files if f not in existing_paths]
            logger.info(f"Document Analysis:")
            logger.info(f"   Total source files: {len(all_doc_files)}")
            logger.info(f"   Already indexed: {len(existing_paths)}")
            logger.info(f"   New files to process: {len(new_files)}")
            doc_files = new_files
        else:
            doc_files = all_doc_files
            logger.info(f"Processing {len(doc_files)} documents (full ingestion)")
        
        if sample_size:
            doc_files = doc_files[:sample_size]
            logger.info(f"Using sample of {len(doc_files)} documents")
        
        if not doc_files:
            logger.info("No new documents to process!")
            return
        
        # Process in batches
        total_processed = 0
        current_collection_size = len(existing_paths)
        
        for i in range(0, len(doc_files), batch_size):
            batch_files = doc_files[i:i + batch_size]
            batch_points = []
            
            logger.info(f"Processing batch {i//batch_size + 1}/{(len(doc_files)-1)//batch_size + 1}")
            
            for j, file_path in enumerate(batch_files):
                try:
                    # Skip if already exists by path (double-check)
                    if incremental and file_path in existing_paths:
                        continue
                    
                    # Try multiple encodings with error handling
                    content = None
                    encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1', 'utf-16']
                    
                    for encoding in encodings:
                        try:
                            with open(file_path, 'r', encoding=encoding) as f:
                                content = f.read()
                            break
                        except UnicodeDecodeError:
                            continue
                    
                    # Final fallback with error replacement
                    if content is None:
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                                content = f.read()
                            logger.warning(f"Used error replacement for {file_path}")
                        except KeyboardInterrupt:
                            raise  # Allow user to cancel
                        except (OSError, IOError) as e:
                            logger.error(f"Could not decode {file_path} with any method: {e}")
                            continue
                        except Exception as e:
                            logger.error(f"Unexpected error reading {file_path}: {e}")
                            continue

                    # Check for content-based duplicates
                    content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
                    if incremental and content_hash in existing_hashes:
                        # Same content, different path - update existing point instead of creating new
                        existing_info = existing_hashes[content_hash]
                        old_path = existing_info['file_path']
                        point_id = existing_info['point_id']

                        # Use relative path from project root if available
                        if project_root:
                            relative_file_path = self.registry.get_relative_path(Path(file_path), project_root)
                        else:
                            relative_file_path = file_path

                        if self.update_file_path(config.collection_name, point_id, relative_file_path):
                            logger.info(f"  Updated path: {old_path} → {relative_file_path}")
                            # Update our existing_hashes cache for this batch
                            existing_hashes[content_hash]['file_path'] = relative_file_path
                        else:
                            logger.warning(f"Failed to update path for duplicate content")
                        continue

                    # Create vector
                    vector = model.encode(content).tolist()
                    
                    # Create unique point ID based on current collection size + position
                    point_id = current_collection_size + total_processed + len(batch_points)
                    
                    # Use relative path from project root if available
                    if project_root:
                        relative_file_path = self.registry.get_relative_path(Path(file_path), project_root)
                    else:
                        relative_file_path = file_path
                    
                    batch_points.append({
                        "id": point_id,
                        "vector": {config.vector_name: vector},
                        "payload": {
                            "information": content,
                            "file_path": relative_file_path,
                            "config_name": config_name,
                            "model_name": config.model_name,
                            "ingestion_timestamp": datetime.now().isoformat(),
                            "file_hash": content_hash
                        }
                    })

                    # Update existing_hashes cache with new document
                    existing_hashes[content_hash] = {
                        'file_path': relative_file_path,
                        'point_id': point_id  # Keep original type
                    }
                    
                except Exception as e:
                    logger.error(f"Error processing {file_path}: {e}")
                    continue
            
            # Upload batch
            if batch_points:
                try:
                    self.client.upsert(
                        collection_name=config.collection_name, 
                        points=batch_points
                    )
                    total_processed += len(batch_points)
                    logger.info(f"  Uploaded {len(batch_points)} documents")
                except Exception as e:
                    logger.error(f"Error uploading batch: {e}")
        
        logger.info(f"Ingestion complete!")
        logger.info(f"   Configuration: {config_name}")
        logger.info(f"   Model: {config.model_name}")
        logger.info(f"   Collection: {config.collection_name}")
        logger.info(f"   New documents added: {total_processed}")

        # Validation statistics
        if self.validation_stats['total_processed'] > 0:
            logger.info(f"Metadata Validation Summary:")
            logger.info(f"   Documents validated: {self.validation_stats['total_processed']}")
            logger.info(f"   Validation passed: {self.validation_stats['validation_passed']} ({self.validation_stats['validation_passed']/self.validation_stats['total_processed']*100:.1f}%)")
            logger.info(f"   Validation failed: {self.validation_stats['validation_failed']} ({self.validation_stats['validation_failed']/self.validation_stats['total_processed']*100:.1f}%)")
            logger.info(f"   Total warnings: {self.validation_stats['validation_warnings']}")

        # Final status check
        final_info = self.client.get_collection(config.collection_name)
        logger.info(f"   Total documents in collection: {final_info.points_count}")
        
        # Return the processed document count
        return total_processed
    
    def _extract_phase(self, file_path: Path) -> str:
        """Extract lifecycle phase from file path"""
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

    def _extract_frontmatter(self, content: str) -> dict:
        """Extract YAML frontmatter from markdown"""
        match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
        if not match:
            return {}

        try:
            return yaml.safe_load(match.group(1))
        except:
            return {}

    def _detect_layer(self, file_path: Path, phase: str) -> str:
        """Detect layer (implementation/pattern) based on filename and phase.

        Only develop phase has pattern mirrors. Other phases are always 'implementation'.
        """
        # Only develop phase has pattern layers
        if phase != 'develop':
            return 'implementation'

        # Check filename
        if '.pattern.md' in str(file_path):
            return 'pattern'
        else:
            return 'implementation'

    def ingest_markdown_chunked(self, file_path: Path, phase: str = None, base_collection: str = "institutional_memory"):
        """Ingest markdown with section-level chunking using LlamaIndex"""

        # Lazy load model if not already loaded
        if self.model is None:
            logger.info(f"Loading embedding model: {config.default_model}")
            self.model = SentenceTransformer(config.default_model, trust_remote_code=True)

        # Auto-detect phase from path if not provided
        if not phase:
            phase = self._extract_phase(file_path)

        # Detect layer (implementation/pattern)
        layer = self._detect_layer(file_path, phase)

        # Route to separate collections based on layer
        if layer == 'pattern':
            collection_name = f"{base_collection}_pattern"
        else:
            collection_name = f"{base_collection}_impl"

        # Read file
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            logger.error(f"Error reading {file_path}: {e}")
            return

        # Extract frontmatter metadata
        frontmatter = self._extract_frontmatter(content)

        # Parse with LlamaIndex
        llama_doc = LlamaDocument(
            text=content,
            metadata={'file_path': str(file_path)}
        )

        nodes = self.parser.get_nodes_from_documents([llama_doc])

        if not nodes:
            logger.warning(f"No nodes parsed from {file_path}")
            return

        # Index each section (batch upsert for performance)
        # OPTIMIZATION: Batch encode all sections at once (2x faster!)
        # Extract all text first
        texts = [node.get_content() for node in nodes]

        # Batch encode (2x faster than encoding one at a time)
        embeddings = self.model.encode(texts)

        # Build points with pre-computed embeddings
        batch_points = []

        # Chunk size validation (Nomic Embed v1.5: 8k tokens ≈ 32k chars)
        MAX_CHUNK_SIZE = 30000
        large_chunks = []

        for node, embedding in zip(nodes, embeddings):
            # Extract type category/subtype
            doc_type = frontmatter.get('type', '')
            category = doc_type.split('.')[0] if '.' in doc_type else doc_type
            subtype = doc_type.split('.')[1] if '.' in doc_type else None

            # Extract clean section name from content (first line)
            content = node.get_content()
            first_line = content.split('\n')[0] if content else ''

            # Extract section name from markdown header (e.g., "## Decisions" -> "Decisions")
            import re
            header_match = re.match(r'^(#{1,6})\s+(.+)$', first_line)
            section_name = header_match.group(2).strip() if header_match else ''

            # Parse actual header level by counting # symbols in first line
            header_level = None
            if header_match:
                header_level = len(header_match.group(1))  # Count # characters

            # Extract actual content (excluding header line)
            content_lines = content.split('\n')
            actual_content = '\n'.join(content_lines[1:]).strip() if len(content_lines) > 1 else ''

            # FILTER: Skip chunks with no actual content (empty H2 parent headers)
            # This allows H2 sections with content (Overview, Request) while skipping
            # empty H2 parent headers (Decisions, Implementation that only contain H3s)
            if len(actual_content) < 20:  # Less than ~3 words of actual content
                continue  # Skip empty headers (H1 titles, H2 parent sections)

            # Re-assign header_level for H2 sections now that we're allowing them
            if header_level is None:
                continue  # Skip frontmatter/non-header chunks

            raw_header_path = node.metadata.get('header_path', '')

            # Extract H2 parent from header_path for semantic filtering
            # "/Provider-Agnostic Refactor/Decisions/Database..." → "Decisions"
            h2_section_type = None
            if raw_header_path and header_level:
                path_parts = [p.strip() for p in raw_header_path.split('/') if p.strip()]
                # For H2 sections: section_type = section_name
                # For H3+ sections: section_type = parent H2 (at index 1)
                if header_level == 2:
                    h2_section_type = section_name  # H2 sections are their own type
                elif header_level >= 3 and len(path_parts) >= 2:
                    h2_section_type = path_parts[1]  # H3+ inherits from H2 parent

            # Detect structured fields in content for rich filtering
            has_context = '**Context**' in content or '- **Context**:' in content
            has_solution = '**Solution**' in content or '- **Solution**:' in content
            has_rationale = '**Rationale**' in content or '- **Rationale**:' in content
            has_alternatives = '**Alternatives**' in content or '- **Alternatives**:' in content
            has_approach = '**Approach**' in content or '- **Approach**:' in content
            has_benefits = '**Benefits**' in content or '- **Benefits**:' in content
            has_drawbacks = '**Drawbacks**' in content or '- **Drawbacks**:' in content

            # Warn about large chunks (exceeds model token limit)
            char_count = len(content)
            if char_count > MAX_CHUNK_SIZE:
                large_chunks.append({
                    'path': raw_header_path,
                    'size': char_count,
                    'file': str(file_path)
                })

            # Build payload with rich metadata
            payload = {
                'source': 'context',
                'phase': phase,
                # layer determined by collection name (_impl or _pattern)
                'section_type': h2_section_type or section_name,  # H2 parent (e.g., "Decisions")
                'section_name': section_name,  # H3 title (e.g., "Database as Inert...")
                'header_path': raw_header_path,  # Keep raw for debugging
                'section_level': header_level,
                'category': category,
                'subtype': subtype,
                'timestamp': frontmatter.get('timestamp'),
                'session_id': frontmatter.get('session_id'),  # Link to originating conversation
                'content': content,
                'file_path': str(file_path),
                # Structured field flags for advanced filtering
                'has_context': has_context,
                'has_solution': has_solution,
                'has_rationale': has_rationale,
                'has_alternatives': has_alternatives,
                'has_approach': has_approach,
                'has_benefits': has_benefits,
                'has_drawbacks': has_drawbacks,
                # Metadata for migrations and monitoring
                'schema_version': 'v1.0',
                'word_count': len(content.split()),
                'char_count': len(content),
            }

            batch_points.append({
                'id': str(uuid4()),  # UUID to avoid collision with sequential IDs
                'vector': {config.default_vector_name: embedding.tolist()},  # Named vector
                'payload': payload
            })

        # Batch upsert for performance (10x faster than individual upserts)
        if batch_points:
            try:
                self.client.upsert(
                    collection_name=collection_name,
                    points=batch_points
                )
                logger.info(f"Indexed {len(batch_points)} sections from {file_path.name}")

                # Warn about large chunks
                if large_chunks:
                    for chunk in large_chunks:
                        logger.warning(
                            f"Large chunk ({chunk['size']} chars) may exceed {config.default_model} token limit: "
                            f"{chunk['path']} in {Path(chunk['file']).name}"
                        )
            except Exception as e:
                logger.error(f"Error batch indexing {file_path}: {e}")

    def parse_conversation_section(self, section_name: str) -> dict:
        """Parse TRACE H2 headers into structured metadata

        Enables rich filtering of conversation chunks by type, role, and file path.

        Args:
            section_name: H2 header like "Message 1: USER" or "Code Patch 1: src/cli.py"

        Returns:
            Dict with chunk_type, role (for messages), or file_path (for patches)

        Examples:
            "Message 1: USER" → {'chunk_type': 'message', 'role': 'user'}
            "Message 2: ASSISTANT" → {'chunk_type': 'message', 'role': 'assistant'}
            "Message 2 Extended Thinking" → {'chunk_type': 'thinking', 'role': 'assistant'}
            "Message 2 Tools" → {'chunk_type': 'tools', 'role': 'assistant'}
            "Code Patch 1: src/cli.py" → {'chunk_type': 'patch', 'file_path': 'src/cli.py'}
        """
        metadata = {}

        if section_name.startswith('Message'):
            # Check for specialized message sections (thinking, tools)
            if 'Extended Thinking' in section_name:
                metadata['chunk_type'] = 'thinking'
                metadata['role'] = 'assistant'  # Thinking is always from assistant
            elif ' Tools' in section_name:
                metadata['chunk_type'] = 'tools'
                metadata['role'] = 'assistant'  # Tools are always called by assistant
            else:
                # Regular message
                metadata['chunk_type'] = 'message'
                if 'USER' in section_name:
                    metadata['role'] = 'user'
                elif 'ASSISTANT' in section_name:
                    metadata['role'] = 'assistant'

        elif section_name.startswith('Code Patch'):
            metadata['chunk_type'] = 'patch'
            # Extract "Code Patch 1: src/cli.py" → "src/cli.py"
            match = re.match(r'Code Patch \d+:\s*(.+)', section_name)
            if match:
                metadata['file_path'] = match.group(1).strip()

        return metadata

    def ingest_conversation_chunked(self, markdown_path: Path, session_id: str, metadata: dict,
                                   collection_name: str = "institutional_memory"):
        """Ingest conversation with H2-level chunking using LlamaIndex"""

        # Lazy load model if not already loaded
        if self.model is None:
            logger.info(f"Loading embedding model: {config.default_model}")
            self.model = SentenceTransformer(config.default_model, trust_remote_code=True)

        try:
            with open(markdown_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            logger.error(f"Error reading {markdown_path}: {e}")
            return

        # Parse with LlamaIndex
        llama_doc = LlamaDocument(
            text=content,
            metadata={'session_id': session_id}
        )

        nodes = self.parser.get_nodes_from_documents([llama_doc])

        if not nodes:
            logger.warning(f"No nodes parsed from conversation {session_id}")
            return

        # Index each H2 section (batch upsert for performance)
        # OPTIMIZATION: Batch encode all sections at once (2x faster!)
        # Extract all text first
        texts = [node.get_content() for node in nodes]

        # Batch encode (2x faster than encoding one at a time)
        embeddings = self.model.encode(texts)

        # Build points with pre-computed embeddings
        batch_points = []
        for node, embedding in zip(nodes, embeddings):
            # Extract clean section name from content (first line)
            content = node.get_content()
            first_line = content.split('\n')[0] if content else ''

            # Extract section name from markdown header (e.g., "## User Messages" -> "User Messages")
            import re
            header_match = re.match(r'^#{1,6}\s+(.+)$', first_line)
            section_name = header_match.group(1).strip() if header_match else ''

            # Parse section name into structured metadata (chunk_type, role, file_path)
            parsed_meta = self.parse_conversation_section(section_name)

            raw_header_path = node.metadata.get('header_path', '')

            payload = {
                'source': 'conversation',
                'session_id': session_id,
                'section_type': section_name,  # Clean: "Message 1: USER", "Code Patch 1: src/cli.py"
                'header_path': raw_header_path,  # Raw: "/Conversation: .../"
                'section_level': node.metadata.get('header_level'),
                'content': node.get_content(),
                'start_time': metadata.get('start_time'),
                'duration_minutes': metadata.get('duration_minutes'),
                'message_count': metadata.get('message_count'),
                'has_changelog': metadata.get('has_changelog', False),
                'changelog_path': metadata.get('changelog_path'),
                # Rich metadata from parsing (enables filtering)
                **parsed_meta  # Adds: chunk_type, role (for messages), file_path (for patches)
            }

            batch_points.append({
                'id': str(uuid4()),  # UUID to avoid collision with sequential IDs
                'vector': {config.default_vector_name: embedding.tolist()},  # Named vector
                'payload': payload
            })

        # Batch upsert for performance (10x faster than individual upserts)
        if batch_points:
            try:
                self.client.upsert(
                    collection_name=collection_name,
                    points=batch_points
                )
                logger.info(f"Indexed {len(batch_points)} sections from conversation {session_id[:12]}")
                return len(batch_points)  # Return chunk count for registry tracking
            except Exception as e:
                logger.error(f"Error batch indexing conversation: {e}")
                return 0
        return 0

    def get_collection_status(self):
        """Show detailed status of all collections.

        Displays comprehensive information about all configured search collections,
        including document counts, model configurations, and sample file paths from
        each collection. Useful for verifying ingestion success and monitoring
        collection health.

        Returns:
            None. Prints formatted status information to stdout including:
                - Collection name and document count
                - Embedding model name and dimensions
                - Sample file paths from the collection (up to 3)

        Notes:
            - Iterates through all configs in modular_search.configs
            - Marks collections as not found if they don't exist
            - Truncates long file paths to 80 characters for readability
        """
        logger.info("Collection Status:")
        logger.info("-" * 70)
        
        for name, config in self.modular_search.configs.items():
            try:
                info = self.client.get_collection(config.collection_name)
                logger.info(f"{name}: {info.points_count} docs in '{config.collection_name}'")
                logger.info(f"   Model: {config.model_name} ({config.dimensions}D)")
                
                # Sample a few points to show file paths
                try:
                    points, _ = self.client.scroll(
                        collection_name=config.collection_name,
                        limit=3,
                        with_payload=True,
                        with_vectors=False
                    )
                    if points:
                        logger.info("   Sample files:")
                        for point in points:
                            if 'file_path' in point.payload:
                                file_path = point.payload['file_path']
                                # Show relative path for readability
                                rel_path = file_path
                                logger.info(f"     - {rel_path[:80]}{'...' if len(rel_path) > 80 else ''}")
                except KeyboardInterrupt:
                    raise  # Allow user to cancel
                except (ConnectionError, TimeoutError) as e:
                    logger.debug(f"Failed to get sample files: {e}")
                except Exception as e:
                    logger.debug(f"Error getting sample files: {e}")
                
            except KeyboardInterrupt:
                raise  # Allow user to cancel
            except (ConnectionError, TimeoutError) as e:
                logger.debug(f"Collection '{config.collection_name}' not accessible: {e}")
                logger.error(f"{name}: Collection '{config.collection_name}' not found")
            except Exception as e:
                logger.debug(f"Error getting collection info: {e}")
                logger.error(f"{name}: Collection '{config.collection_name}' not found")
            logger.info("")

    def find_duplicates(self, config_name: str):
        """Find potential duplicate documents in collection"""
        if config_name not in self.modular_search.configs:
            logger.error(f"Configuration '{config_name}' not found")
            return
        
        config = self.modular_search.configs[config_name]
        
        logger.info(f"Checking for duplicates in {config.collection_name}...")
        
        file_paths = {}
        hash_groups = {}
        
        try:
            offset = None
            while True:
                points, next_offset = self.client.scroll(
                    collection_name=config.collection_name,
                    limit=100,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False
                )
                
                for point in points:
                    payload = point.payload
                    
                    # Check file path duplicates
                    if 'file_path' in payload:
                        file_path = payload['file_path']
                        if file_path in file_paths:
                            file_paths[file_path].append(point.id)
                        else:
                            file_paths[file_path] = [point.id]
                    
                    # Check content hash duplicates
                    if 'file_hash' in payload:
                        file_hash = payload['file_hash']
                        if file_hash in hash_groups:
                            hash_groups[file_hash].append(point.id)
                        else:
                            hash_groups[file_hash] = [point.id]
                
                if next_offset is None:
                    break
                offset = next_offset
            
            # Report duplicates
            path_duplicates = {path: ids for path, ids in file_paths.items() if len(ids) > 1}
            hash_duplicates = {hash_val: ids for hash_val, ids in hash_groups.items() if len(ids) > 1}
            
            if path_duplicates:
                logger.warning(f"Found {len(path_duplicates)} file path duplicates:")
                for path, ids in path_duplicates.items():
                    logger.warning(f"   {path}: {ids}")
            
            if hash_duplicates:
                logger.warning(f"Found {len(hash_duplicates)} content hash duplicates:")
                for hash_val, ids in hash_duplicates.items():
                    logger.warning(f"   {hash_val}: {ids}")
            
            if not path_duplicates and not hash_duplicates:
                logger.info("No duplicates found!")
                
        except Exception as e:
            logger.error(f"Error checking duplicates: {e}")

def main():
    parser = argparse.ArgumentParser(description="Enhanced Modular Ingestion with Deduplication")
    parser.add_argument("config", nargs="?", help="Configuration name (e.g., e5_large)")
    parser.add_argument("--source-dir", default=None, help="Source directory for documents")
    parser.add_argument("--batch-size", type=int, default=100, help="Batch size for processing")
    parser.add_argument("--sample-size", type=int, help="Limit to N documents for testing")
    parser.add_argument("--recreate", action="store_true", help="Recreate collection from scratch")
    parser.add_argument("--status", action="store_true", help="Show collection status")
    parser.add_argument("--incremental", action="store_true", default=True, help="Skip existing documents")
    parser.add_argument("--force-reindex", action="store_true", help="Force complete reindexing")
    parser.add_argument("--find-duplicates", help="Find duplicates in specified collection")

    args = parser.parse_args()

    ingest = EnhancedModularIngest()

    if args.status:
        ingest.get_collection_status()
        return

    if args.find_duplicates:
        ingest.find_duplicates(args.find_duplicates)
        return
    
    if not args.config:
        logger.error("Please specify a configuration name")
        ingest.modular_search.list_available_configs()
        return
    
    ingest.ingest_documents(
        config_name=args.config,
        source_dir=args.source_dir,
        batch_size=args.batch_size,
        sample_size=args.sample_size,
        incremental=not args.force_reindex,
        force_reindex=args.force_reindex
    )

if __name__ == "__main__":
    main()