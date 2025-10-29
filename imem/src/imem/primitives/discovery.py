"""
Discovery primitives for IMEM FlexGraph
Pure functions for relationship discovery via metadata queries
"""

from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchAny
from sentence_transformers import SentenceTransformer

from ..config import config


def get_siblings(collection_name: str, chunk_id: str,
                 section_types: Optional[List[str]] = None,
                 order_by: str = 'section_level',
                 limit: Optional[int] = None,
                 has_rationale: Optional[bool] = None,
                 has_alternatives: Optional[bool] = None,
                 client: Optional[QdrantClient] = None,
                 encoder: Optional[SentenceTransformer] = None) -> List[Dict[str, Any]]:
    """
    Get sibling chunks (same file_path) with filtering and ordering

    Args:
        collection_name: Qdrant collection name
        chunk_id: Target chunk ID
        section_types: Filter by section types (e.g., ["Patterns", "Failures"])
        order_by: Order results by 'section_level', 'timestamp', or None
        limit: Limit number of results returned
        has_rationale: Filter by has_rationale metadata
        has_alternatives: Filter by has_alternatives metadata
        client: Optional Qdrant client (creates new if None)
        encoder: Optional encoder (not used but kept for consistency)

    Returns:
        List of sibling chunks with payload
    """
    if client is None:
        client = QdrantClient(host=config.qdrant_host, port=config.qdrant_port)

    # Retrieve target chunk
    target = client.retrieve(collection_name=collection_name, ids=[chunk_id])
    if not target:
        return []

    target_payload = target[0].payload
    file_path = target_payload.get('file_path')

    if not file_path:
        return []

    # Build filter conditions
    must_conditions = [
        FieldCondition(key='file_path', match=MatchValue(value=file_path))
    ]

    # Add section_type filter if specified
    if section_types:
        must_conditions.append(
            FieldCondition(key='section_type', match=MatchAny(any=section_types))
        )

    # Add quality filters if specified
    if has_rationale is not None:
        must_conditions.append(
            FieldCondition(key='has_rationale', match=MatchValue(value=has_rationale))
        )

    if has_alternatives is not None:
        must_conditions.append(
            FieldCondition(key='has_alternatives', match=MatchValue(value=has_alternatives))
        )

    scroll_filter = Filter(must=must_conditions)

    # Scroll with filter
    results, _ = client.scroll(
        collection_name=collection_name,
        scroll_filter=scroll_filter,
        limit=limit or 100,
        with_payload=True,
        with_vectors=False
    )

    # Exclude target chunk itself
    siblings = [
        {
            'id': str(point.id),
            'payload': point.payload,
            'score': 0.9  # Sibling weight from architecture
        }
        for point in results
        if str(point.id) != chunk_id
    ]

    # Order results
    if order_by == 'timestamp':
        siblings.sort(key=lambda s: s['payload'].get('timestamp') or '', reverse=True)
    elif order_by == 'section_level':
        siblings.sort(key=lambda s: s['payload'].get('section_level') or 999)

    # Apply limit if specified
    if limit:
        siblings = siblings[:limit]

    return siblings


def get_genealogy(collection_name: str, chunk_id: str,
                  order_by: str = 'timestamp',
                  limit: Optional[int] = None,
                  client: Optional[QdrantClient] = None,
                  encoder: Optional[SentenceTransformer] = None) -> List[Dict[str, Any]]:
    """
    Get genealogy chunks (same session_id, from conversations)

    Args:
        collection_name: Qdrant collection name
        chunk_id: Target chunk ID
        order_by: Order results by 'timestamp' (default) or None
        limit: Limit number of results returned
        client: Optional Qdrant client
        encoder: Optional encoder (not used)

    Returns:
        List of conversation chunks from same session
    """
    if client is None:
        client = QdrantClient(host=config.qdrant_host, port=config.qdrant_port)

    # Retrieve target chunk
    target = client.retrieve(collection_name=collection_name, ids=[chunk_id])
    if not target:
        return []

    target_payload = target[0].payload
    session_id = target_payload.get('session_id')

    if not session_id:
        return []

    # Find all chunks with same session_id from conversations
    scroll_filter = Filter(
        must=[
            FieldCondition(key='session_id', match=MatchValue(value=session_id)),
            FieldCondition(key='source', match=MatchValue(value='conversation'))
        ]
    )

    results, _ = client.scroll(
        collection_name=collection_name,
        scroll_filter=scroll_filter,
        limit=limit or 200,
        with_payload=True,
        with_vectors=False
    )

    genealogy = [
        {
            'id': str(point.id),
            'payload': point.payload,
            'score': 0.85  # Genealogy weight from architecture
        }
        for point in results
    ]

    # Order results
    if order_by == 'timestamp':
        genealogy.sort(key=lambda g: g['payload'].get('timestamp') or '')

    # Apply limit if specified
    if limit:
        genealogy = genealogy[:limit]

    return genealogy


def get_temporal(collection_name: str, chunk_id: str,
                 direction: str = 'after',
                 client: Optional[QdrantClient] = None,
                 encoder: Optional[SentenceTransformer] = None) -> List[Dict[str, Any]]:
    """
    Get temporally related chunks (semantically similar + chronological)

    Args:
        collection_name: Qdrant collection name
        chunk_id: Target chunk ID
        direction: 'after' (later) or 'before' (earlier)
        client: Optional Qdrant client
        encoder: Optional encoder

    Returns:
        List of temporal chunks ranked by semantic similarity
    """
    if client is None:
        client = QdrantClient(host=config.qdrant_host, port=config.qdrant_port)

    if encoder is None:
        encoder = SentenceTransformer(config.default_model)

    # Retrieve target chunk with vector
    target = client.retrieve(collection_name=collection_name, ids=[chunk_id], with_vectors=True)
    if not target:
        return []

    target_payload = target[0].payload
    target_vector = target[0].vector

    # Get timestamp from payload (could be in various fields)
    timestamp = target_payload.get('timestamp') or target_payload.get('created')

    # Note: Qdrant Range filters require numeric values, but timestamps are ISO strings
    # For MVP, rely on semantic similarity only and post-filter by timestamp
    # Future: Store Unix timestamps as numeric field for efficient filtering

    # Semantic search with high threshold (temporal = semantic similarity + chronology)
    try:
        results = client.query_points(
            collection_name=collection_name,
            query=target_vector.get(config.default_vector_name) if isinstance(target_vector, dict) else target_vector,
            using=config.default_vector_name,
            limit=50,
            score_threshold=0.85,  # High similarity threshold from architecture
            with_payload=True,
            with_vectors=False
        ).points
    except Exception:
        # Fallback without named vector
        results = client.query_points(
            collection_name=collection_name,
            query=target_vector,
            limit=50,
            score_threshold=0.85,
            with_payload=True,
            with_vectors=False
        ).points

    # Post-filter by timestamp direction if timestamp exists
    temporal = []
    for point in results:
        if str(point.id) == chunk_id:
            continue

        # If we have timestamps, filter by direction
        if timestamp:
            point_timestamp = point.payload.get('timestamp') or point.payload.get('created')
            if point_timestamp:
                if direction == 'after' and point_timestamp <= timestamp:
                    continue
                if direction == 'before' and point_timestamp >= timestamp:
                    continue

        temporal.append({
            'id': str(point.id),
            'payload': point.payload,
            'score': point.score
        })

    return temporal


def cross_phase_search(collection_name: str, chunk_id: str,
                       target_phase: str,
                       client: Optional[QdrantClient] = None,
                       encoder: Optional[SentenceTransformer] = None) -> List[Dict[str, Any]]:
    """
    Search for related content in different phase (e.g., design -> develop)

    Args:
        collection_name: Qdrant collection name
        chunk_id: Target chunk ID
        target_phase: Phase to search in (design, develop, document)
        client: Optional Qdrant client
        encoder: Optional encoder

    Returns:
        List of cross-phase chunks ranked by semantic similarity
    """
    if client is None:
        client = QdrantClient(host=config.qdrant_host, port=config.qdrant_port)

    if encoder is None:
        encoder = SentenceTransformer(config.default_model)

    # Retrieve target chunk with vector
    target = client.retrieve(collection_name=collection_name, ids=[chunk_id], with_vectors=True)
    if not target:
        return []

    target_vector = target[0].vector

    # Build phase filter
    phase_filter = Filter(
        must=[
            FieldCondition(key='phase', match=MatchValue(value=target_phase))
        ]
    )

    # Semantic search in target phase
    try:
        results = client.query_points(
            collection_name=collection_name,
            query=target_vector.get(config.default_vector_name) if isinstance(target_vector, dict) else target_vector,
            using=config.default_vector_name,
            query_filter=phase_filter,
            limit=20,
            score_threshold=0.7,  # Lower threshold for cross-phase from architecture
            with_payload=True,
            with_vectors=False
        ).points
    except Exception:
        # Fallback without named vector
        results = client.query_points(
            collection_name=collection_name,
            query=target_vector,
            query_filter=phase_filter,
            limit=20,
            score_threshold=0.7,
            with_payload=True,
            with_vectors=False
        ).points

    cross_phase = [
        {
            'id': str(point.id),
            'payload': point.payload,
            'score': point.score
        }
        for point in results
        if str(point.id) != chunk_id
    ]

    return cross_phase
