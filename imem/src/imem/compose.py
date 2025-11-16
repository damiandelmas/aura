"""
Compose orchestrator for IMEM FlexGraph
Single entry point for search + discovery + graph + rendering
"""

import asyncio
from typing import Dict, List, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from sentence_transformers import SentenceTransformer

from .config import config
from .primitives import get_siblings, get_genealogy, get_temporal, cross_phase_search


async def compose(collection_name: str, config_dict: dict,
                  client: Optional[QdrantClient] = None,
                  encoder: Optional[SentenceTransformer] = None) -> dict:
    """
    Single entry point. Executes full pipeline.

    Config format:
    {
        "search": {...},          # Required
        "discovery": {...},       # Optional
        "graph": {...},           # Optional (not yet implemented)
        "output": {...}           # Optional
        "cross_project": bool     # Optional - query pattern collections across projects
    }

    Returns: {"results": [...]} or {"rendered": "..."}
    """
    # Initialize clients if not provided
    if client is None:
        client = QdrantClient(host=config.qdrant_host, port=config.qdrant_port)

    if encoder is None:
        encoder = SentenceTransformer(config.default_model, trust_remote_code=True)

    # BRAIN Query Routing: Determine which collection(s) to query
    if config_dict.get('cross_project'):
        # Cross-project: Query pattern collection
        # TODO: Support querying multiple pattern collections across projects
        query_collection = f"{collection_name}_pattern"
    else:
        # Same-project: Query impl collection (default for context docs)
        # Conversations use single collection (no _impl suffix)
        impl_collection = f"{collection_name}_impl"
        if client.collection_exists(impl_collection):
            query_collection = impl_collection
        else:
            # Fallback: Use base collection name (for conversations)
            query_collection = collection_name

    # Stage 1: Search (always happens - async for parallel queries)
    results = await _execute_search(query_collection, config_dict['search'], client, encoder)

    # Stage 2: Discovery (if requested - async for parallel enrichment)
    if config_dict.get('discovery'):
        results = await _enrich_with_discovery(
            query_collection,
            results,
            config_dict['discovery'],
            client,
            encoder
        )

    # Stage 2.5: Metadata enrichment (add temporal position and confidence signals)
    results = _enrich_metadata(results)

    # Stage 3: Graph (if requested - sync, NetworkX has no async)
    if config_dict.get('graph'):
        results = _apply_graph_operations(
            query_collection,
            results,
            config_dict['graph'],
            client,
            encoder
        )

    # Stage 4: Render (if template specified)
    if config_dict.get('output', {}).get('template'):
        return {"rendered": _render_template(results, config_dict['output']['template'])}

    return {"results": results}


async def _execute_search(collection_name: str, search_config: dict,
                          client: QdrantClient,
                          encoder: SentenceTransformer) -> List[Dict[str, Any]]:
    """Execute search stage with parallel query execution"""

    if 'queries' in search_config:
        # Multi-query: execute in parallel
        tasks = [
            asyncio.to_thread(
                _single_search,
                collection_name,
                query_cfg.get('text', ''),
                query_cfg.get('filters', {}),
                query_cfg.get('limit', 10),
                client,
                encoder
            )
            for query_cfg in search_config['queries']
        ]

        # Execute all queries in parallel
        results_list = await asyncio.gather(*tasks)

        # Deduplicate across queries
        all_results = []
        seen_ids = set()
        for results in results_list:
            for result in results:
                if result['id'] not in seen_ids:
                    all_results.append(result)
                    seen_ids.add(result['id'])

        return all_results
    else:
        # Single query - wrap in thread
        return await asyncio.to_thread(
            _single_search,
            collection_name,
            search_config.get('text', ''),
            search_config.get('filters', {}),
            search_config.get('limit', 10),
            client,
            encoder
        )


def _single_search(collection_name: str, query_text: str, filters: dict, limit: int,
                   client: QdrantClient, encoder: SentenceTransformer) -> List[Dict[str, Any]]:
    """Execute single semantic search"""

    # Encode query
    query_vector = encoder.encode(query_text).tolist()

    # Build Qdrant filter
    query_filter = None
    if filters:
        must_conditions = []
        for key, value in filters.items():
            must_conditions.append(
                FieldCondition(key=key, match=MatchValue(value=value))
            )
        query_filter = Filter(must=must_conditions)

    # Execute search
    try:
        search_results = client.query_points(
            collection_name=collection_name,
            query=query_vector,
            using=config.default_vector_name,
            query_filter=query_filter,
            limit=limit,
            with_payload=True,
            with_vectors=False
        ).points
    except Exception:
        # Fallback without named vector
        search_results = client.query_points(
            collection_name=collection_name,
            query=query_vector,
            query_filter=query_filter,
            limit=limit,
            with_payload=True,
            with_vectors=False
        ).points

    # Convert to standard format
    results = [
        {
            'id': str(point.id),
            'score': point.score,
            'payload': point.payload
        }
        for point in search_results
    ]

    return results


async def _enrich_with_discovery(collection_name: str, results: List[Dict[str, Any]],
                                  discovery_config: dict,
                                  client: QdrantClient,
                                  encoder: SentenceTransformer) -> List[Dict[str, Any]]:
    """Execute discovery stage with parallel enrichment per result"""

    async def enrich_single_result(result):
        """Enrich a single result with all requested discovery operations"""
        chunk_id = result['id']
        tasks = []
        keys = []

        # Handle siblings config (bool or dict)
        if discovery_config.get('siblings'):
            sibling_config = discovery_config['siblings']

            if isinstance(sibling_config, bool):
                # Legacy: Just true/false
                tasks.append(asyncio.to_thread(get_siblings, collection_name, chunk_id,
                                             client=client, encoder=encoder))
            else:
                # New: Dict with parameters
                tasks.append(asyncio.to_thread(
                    get_siblings,
                    collection_name,
                    chunk_id,
                    section_types=sibling_config.get('section_types'),
                    order_by=sibling_config.get('order_by', 'section_level'),
                    limit=sibling_config.get('limit'),
                    has_rationale=sibling_config.get('has_rationale'),
                    has_alternatives=sibling_config.get('has_alternatives'),
                    client=client,
                    encoder=encoder
                ))
            keys.append('siblings')

        # Handle genealogy config (bool or dict)
        if discovery_config.get('genealogy'):
            genealogy_config = discovery_config['genealogy']

            if isinstance(genealogy_config, bool):
                # Legacy: Just true/false
                tasks.append(asyncio.to_thread(get_genealogy, collection_name, chunk_id,
                                              client=client, encoder=encoder))
            else:
                # New: Dict with parameters
                tasks.append(asyncio.to_thread(
                    get_genealogy,
                    collection_name,
                    chunk_id,
                    order_by=genealogy_config.get('order_by', 'timestamp'),
                    limit=genealogy_config.get('limit'),
                    client=client,
                    encoder=encoder
                ))
            keys.append('genealogy')

        # Handle temporal config (bool or dict)
        if discovery_config.get('temporal'):
            temporal_config = discovery_config['temporal']

            if isinstance(temporal_config, bool):
                direction = 'after'
            else:
                direction = temporal_config.get('direction', 'after')

            tasks.append(asyncio.to_thread(get_temporal, collection_name, chunk_id, direction, client, encoder))
            keys.append('temporal')

        # Handle cross_phase config (string or dict)
        if discovery_config.get('cross_phase'):
            cross_phase_config = discovery_config['cross_phase']

            if isinstance(cross_phase_config, str):
                # Legacy: Just phase name
                target_phase = cross_phase_config
            else:
                # New: Dict with parameters
                target_phase = cross_phase_config.get('phase', cross_phase_config)

            tasks.append(asyncio.to_thread(cross_phase_search, collection_name, chunk_id, target_phase, client, encoder))
            keys.append('cross_phase')

        # Execute all discovery operations for this result in parallel
        if tasks:
            values = await asyncio.gather(*tasks)
            for key, value in zip(keys, values):
                result[key] = value

        return result

    # Enrich all results in parallel
    enriched_results = await asyncio.gather(*[enrich_single_result(r) for r in results])

    return enriched_results


def _enrich_metadata(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Add temporal position and confidence signals to results"""

    for result in results:
        # Detect temporal position
        result['temporal_position'] = _detect_temporal_position(result)

        # Calculate confidence signals
        result['confidence'] = {
            'has_rationale': result['payload'].get('has_rationale', False),
            'has_alternatives': result['payload'].get('has_alternatives', False),
            'semantic_score': result.get('score', 0),
            'continuation_count': _count_continuations(result)
        }

    return results


def _detect_temporal_position(result: Dict[str, Any]) -> str:
    """Detect if this is current thrust, superseded, or failed branch"""

    # Check if in Failures section
    if result['payload'].get('section_type') == 'Failures':
        return 'failed_branch'

    # Check temporal continuations
    temporal = result.get('temporal', [])
    if not temporal:
        return 'current_thrust'  # No temporal = likely current

    # Count how many temporal chunks are AFTER this one
    result_timestamp = result['payload'].get('timestamp') or ''
    later_chunks = [t for t in temporal if (t['payload'].get('timestamp') or '') > result_timestamp]

    if len(later_chunks) > 2:
        return 'superseded'  # Many later chunks = old direction
    elif len(later_chunks) > 0:
        return 'evolved'  # Some later = evolved from this
    else:
        return 'current_thrust'  # No later = current direction


def _count_continuations(result: Dict[str, Any]) -> int:
    """Count temporal chunks that continue this direction"""
    temporal = result.get('temporal', [])
    if not temporal:
        return 0

    result_timestamp = result['payload'].get('timestamp') or ''
    return len([t for t in temporal if (t['payload'].get('timestamp') or '') > result_timestamp])


def _apply_graph_operations(collection_name: str, results: List[Dict[str, Any]],
                             graph_config: dict,
                             client: QdrantClient,
                             encoder: SentenceTransformer) -> List[Dict[str, Any]]:
    """
    Execute graph stage (placeholder - will implement if Phase 6 testing shows need)

    For now, implement simple authority ranking via reference counting
    """

    # Authority = count of siblings + genealogy references
    # This is the test to see if we need full graph operations

    for result in results:
        authority_score = 0

        # Count references (siblings + genealogy)
        if 'siblings' in result:
            authority_score += len(result['siblings'])

        if 'genealogy' in result:
            authority_score += len(result['genealogy'])

        result['authority_score'] = authority_score

    # Sort by authority if requested
    if graph_config.get('algorithm') == 'authority':
        results.sort(key=lambda r: r.get('authority_score', 0), reverse=True)

        # Keep top N if specified
        if graph_config.get('top'):
            results = results[:graph_config['top']]

    return results


def _render_template(results: List[Dict[str, Any]], template_name: str) -> str:
    """Render with Jinja2 template"""

    # Import here to avoid circular dependency
    from pathlib import Path
    from jinja2 import Environment, FileSystemLoader

    # Template directory: imem/templates/ (not imem/src/templates/)
    # Path(__file__) = imem/src/imem/compose.py
    # Go up 3 levels: compose.py -> imem -> src -> imem -> templates
    template_dir = Path(__file__).parent.parent.parent / 'templates'

    # Create Jinja2 environment
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        trim_blocks=True,
        lstrip_blocks=True
    )

    # Render template
    template = env.get_template(f"{template_name}.j2")
    return template.render(results=results)
