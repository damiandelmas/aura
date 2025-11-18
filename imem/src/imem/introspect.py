#!/usr/bin/env python3
"""
IMEM Introspection - Self-Documenting System Capabilities

Enables AI agents to discover IMEM capabilities programmatically:
- Metadata field schema (live from collections)
- Discovery primitives (siblings, genealogy, temporal, cross_phase)
- Compose query patterns (proven examples)

Design: Zero documentation drift - schema reflects live data structure.
"""

import json
from typing import Dict, Any, Optional, Set
from pathlib import Path
from qdrant_client import QdrantClient
from .config import config
from .registry import SimpleRegistry


def introspect(
    show_examples: bool = False,
    fields_only: bool = False,
    source: str = 'all',
    sample_size: int = 100,
    enumerate_entities: bool = False
) -> Dict[str, Any]:
    """Main introspection entry point

    Args:
        show_examples: Include compose pattern library
        fields_only: Return only metadata schema (skip primitives/patterns)
        source: 'context' | 'conversations' | 'all'
        sample_size: Number of points to sample per collection
        enumerate_entities: Include project ontology (types, entities, sessions, files)

    Returns:
        Comprehensive JSON schema of IMEM capabilities
    """
    client = QdrantClient(host=config.qdrant_host, port=config.qdrant_port)
    registry = SimpleRegistry()
    project_root = registry.get_project_root()

    if not registry.is_registered(project_root):
        return {"error": "Project not registered. Run 'imem init' first."}

    result = {
        "collections": {},
        "metadata_fields": {}
    }

    # Discover collections
    project_info = registry.get_project_info(project_root)
    collections = project_info.get('collections', {})

    context_collection = None
    conv_collection = None

    if source in ['all', 'context'] and 'context' in collections:
        context_base = collections['context']
        context_collection = f"{context_base}_impl"

        result['collections']['context'] = {
            'implementation': context_collection,
            'pattern': f"{context_base}_pattern"
        }

        # Discover context metadata
        if client.collection_exists(context_collection):
            result['metadata_fields']['context'] = discover_schema(
                client,
                context_collection,
                sample_size
            )

    if source in ['all', 'conversations'] and 'conversation' in collections:
        conv_collection = collections['conversation']
        result['collections']['conversation'] = conv_collection

        # Discover conversation metadata
        if client.collection_exists(conv_collection):
            result['metadata_fields']['conversations'] = discover_schema(
                client,
                conv_collection,
                sample_size
            )

    # Add primitives info (unless fields_only)
    if not fields_only:
        result['primitives'] = get_primitives_info()

    # Add compose patterns (if requested)
    if show_examples:
        result['compose_patterns'] = get_compose_patterns()

    # Add entity enumeration (project ontology)
    if enumerate_entities:
        result['ontology'] = discover_ontology(
            client,
            context_collection,
            conv_collection,
            sample_size
        )

    return result


def discover_schema(
    client: QdrantClient,
    collection_name: str,
    sample_size: int = 100
) -> Dict[str, Any]:
    """Discover metadata schema by sampling collection

    Args:
        client: Qdrant client
        collection_name: Collection to sample
        sample_size: Number of points to sample

    Returns:
        Field schema with types, values, examples
    """
    fields = {}
    offset = None
    sampled = 0

    # Sample points from collection
    while sampled < sample_size:
        try:
            points, next_offset = client.scroll(
                collection_name=collection_name,
                limit=min(100, sample_size - sampled),
                offset=offset,
                with_payload=True,
                with_vectors=False
            )

            if not points:
                break

            for point in points:
                _aggregate_fields(fields, point.payload)
                sampled += 1

            if next_offset is None or sampled >= sample_size:
                break

            offset = next_offset

        except Exception as e:
            # Collection might be empty or inaccessible
            break

    # Format fields into schema
    return _format_field_schema(fields)


def _aggregate_fields(fields: Dict, payload: Dict[str, Any]) -> None:
    """Aggregate field info from a single payload

    Args:
        fields: Accumulator dict for field metadata
        payload: Single point's payload to process
    """
    for key, value in payload.items():
        if key not in fields:
            fields[key] = {
                'type': type(value).__name__,
                'values': set(),
                'examples': [],
                'nullable': False
            }

        # Track if field is nullable
        if value is None:
            fields[key]['nullable'] = True

        # Collect enum values (for short strings/bools)
        if isinstance(value, bool):
            fields[key]['values'].add(value)
        elif isinstance(value, str) and len(value) < 50:
            fields[key]['values'].add(value)

        # Collect examples
        if len(fields[key]['examples']) < 3 and value is not None:
            if isinstance(value, str) and len(value) > 200:
                # Truncate long strings
                fields[key]['examples'].append(value[:200] + "...")
            else:
                fields[key]['examples'].append(value)


def _format_field_schema(fields: Dict) -> Dict[str, Any]:
    """Format aggregated fields into clean schema

    Args:
        fields: Raw aggregated field data

    Returns:
        Formatted schema dict
    """
    schema = {}

    for key, info in fields.items():
        field_schema = {
            'type': info['type'],
            'filterable': True  # All payload fields are filterable in Qdrant
        }

        # Add nullable flag if needed
        if info['nullable']:
            field_schema['nullable'] = True

        # Add enum values if meaningful
        if len(info['values']) > 0 and len(info['values']) < 20:
            # Convert set to sorted list
            field_schema['values'] = sorted(list(info['values']), key=str)

        # Add examples
        if info['examples']:
            field_schema['examples'] = info['examples']

        # Add descriptions for known fields
        field_schema['description'] = _get_field_description(key)

        schema[key] = field_schema

    return schema


def _get_field_description(field_name: str) -> str:
    """Get human-readable description for known fields

    Args:
        field_name: Field name

    Returns:
        Description string
    """
    descriptions = {
        # Context fields
        'source': 'Document source type',
        'phase': 'Lifecycle phase (develop/design/document/designate)',
        'section_type': 'H2 parent section category',
        'section_name': 'H3 section title',
        'header_path': 'Full header hierarchy path',
        'section_level': 'Header depth level',
        'category': 'Document type category',
        'subtype': 'Document type subtype',
        'timestamp': 'Document timestamp (ISO format)',
        'session_id': 'Originating conversation UUID',
        'file_path': 'Relative file path from project root',
        'content': 'Full section text content',

        # Structured flags
        'has_context': 'Section contains Context subsection',
        'has_solution': 'Section contains Solution subsection',
        'has_rationale': 'Section contains Rationale subsection',
        'has_alternatives': 'Section contains Alternatives subsection',
        'has_approach': 'Section contains Approach subsection',
        'has_benefits': 'Section contains Benefits subsection',
        'has_drawbacks': 'Section contains Drawbacks subsection',

        # Conversation fields
        'chunk_type': 'Conversation chunk category (message/thinking/tools/patch)',
        'role': 'Message author role (user/assistant)',
        'start_time': 'Conversation start timestamp',
        'duration_minutes': 'Conversation duration in minutes',
        'message_count': 'Total messages in conversation',
        'has_changelog': 'Conversation has generated changelog',
        'changelog_path': 'Path to generated changelog file',

        # Metadata
        'schema_version': 'Document schema version',
        'word_count': 'Section word count',
        'char_count': 'Section character count',
    }

    return descriptions.get(field_name, f'Field: {field_name}')


def get_primitives_info() -> Dict[str, Any]:
    """Return discovery primitives capabilities

    Returns:
        Primitive definitions with descriptions and parameters
    """
    return {
        'siblings': {
            'description': 'Find chunks from same file (document siblings)',
            'use_case': 'Retrieve related sections from same document',
            'filters': {
                'section_types': {
                    'type': 'list[str]',
                    'description': 'Filter to specific section types'
                },
                'has_rationale': {
                    'type': 'bool',
                    'description': 'Only sections with rationale'
                },
                'has_alternatives': {
                    'type': 'bool',
                    'description': 'Only sections with alternatives'
                }
            },
            'ordering': ['section_level', 'timestamp'],
            'default_weight': 0.9,
            'example': {
                'discovery': {
                    'siblings': {
                        'section_types': ['Patterns', 'Failures'],
                        'order_by': 'section_level',
                        'limit': 10
                    }
                }
            }
        },
        'genealogy': {
            'description': 'Find chunks from same conversation (lineage)',
            'use_case': 'Trace decision evolution through conversation',
            'filters': {
                'session_id': {
                    'type': 'str',
                    'description': 'Conversation UUID'
                }
            },
            'ordering': ['timestamp'],
            'default_weight': 0.85,
            'example': {
                'discovery': {
                    'genealogy': {
                        'order_by': 'timestamp',
                        'limit': 200
                    }
                }
            }
        },
        'temporal': {
            'description': 'Find semantically similar chunks chronologically',
            'use_case': 'Track concept evolution over time',
            'parameters': {
                'direction': {
                    'type': 'str',
                    'values': ['after', 'before'],
                    'description': 'Temporal direction from anchor'
                }
            },
            'threshold': 0.85,
            'example': {
                'discovery': {
                    'temporal': {
                        'direction': 'after'
                    }
                }
            }
        },
        'cross_phase': {
            'description': 'Find similar content in different lifecycle phase',
            'use_case': 'Link design decisions to implementation',
            'parameters': {
                'phase': {
                    'type': 'str',
                    'values': ['develop', 'design', 'document'],
                    'description': 'Target phase to search'
                }
            },
            'threshold': 0.7,
            'example': {
                'discovery': {
                    'cross_phase': {
                        'phase': 'design'
                    }
                }
            }
        }
    }


def discover_ontology(
    client: QdrantClient,
    context_collection: Optional[str],
    conversation_collection: Optional[str],
    sample_size: int = 500
) -> Dict[str, Any]:
    """Discover project ontology - types, entities, taxonomy

    Args:
        client: Qdrant client
        context_collection: Context collection name
        conversation_collection: Conversation collection name
        sample_size: Number of points to sample (more = better coverage)

    Returns:
        Project ontology with types, section taxonomy, entities, inventories
    """
    ontology = {
        "taxonomy": {
            "types": set(),
            "subtypes": set(),
            "phases": set(),
            "section_types": set(),
            "categories": set()
        },
        "inventory": {
            "sessions": set(),
            "files": set()
        }
    }

    # Sample context collection
    if context_collection and client.collection_exists(context_collection):
        _sample_for_ontology(client, context_collection, ontology, sample_size)

    # Sample conversation collection
    if conversation_collection and client.collection_exists(conversation_collection):
        _sample_for_ontology(client, conversation_collection, ontology, sample_size)

    # Convert sets to sorted lists for JSON
    result = {
        "taxonomy": {
            "types": sorted(list(ontology["taxonomy"]["types"])),
            "subtypes": sorted(list(ontology["taxonomy"]["subtypes"])),
            "phases": sorted(list(ontology["taxonomy"]["phases"])),
            "section_types": sorted(list(ontology["taxonomy"]["section_types"])),
            "categories": sorted(list(ontology["taxonomy"]["categories"]))
        },
        "inventory": {
            "sessions": sorted(list(ontology["inventory"]["sessions"])),
            "files": sorted(list(ontology["inventory"]["files"]))
        }
    }

    # Add counts for AI understanding
    result["statistics"] = {
        "total_types": len(result["taxonomy"]["types"]),
        "total_phases": len(result["taxonomy"]["phases"]),
        "total_section_types": len(result["taxonomy"]["section_types"]),
        "total_sessions": len(result["inventory"]["sessions"]),
        "total_files": len(result["inventory"]["files"])
    }

    return result


def _sample_for_ontology(
    client: QdrantClient,
    collection_name: str,
    ontology: Dict,
    sample_size: int
) -> None:
    """Sample collection and extract ontology data

    Args:
        client: Qdrant client
        collection_name: Collection to sample
        ontology: Accumulator dict
        sample_size: Points to sample
    """
    offset = None
    sampled = 0

    while sampled < sample_size:
        try:
            points, next_offset = client.scroll(
                collection_name=collection_name,
                limit=min(100, sample_size - sampled),
                offset=offset,
                with_payload=True,
                with_vectors=False
            )

            if not points:
                break

            for point in points:
                payload = point.payload

                # Extract taxonomy
                if 'category' in payload and payload['category']:
                    ontology["taxonomy"]["types"].add(payload['category'])

                if 'subtype' in payload and payload['subtype']:
                    ontology["taxonomy"]["subtypes"].add(payload['subtype'])

                if 'phase' in payload and payload['phase']:
                    ontology["taxonomy"]["phases"].add(payload['phase'])

                if 'section_type' in payload and payload['section_type']:
                    # Clean section_type (remove "Message N: " prefixes for conversations)
                    section = payload['section_type']
                    if not section.startswith('Message ') and not section.startswith('Code Patch '):
                        ontology["taxonomy"]["section_types"].add(section)

                # Extract inventory
                if 'session_id' in payload and payload['session_id']:
                    ontology["inventory"]["sessions"].add(payload['session_id'])

                if 'file_path' in payload and payload['file_path']:
                    ontology["inventory"]["files"].add(payload['file_path'])

                sampled += 1

            if next_offset is None or sampled >= sample_size:
                break

            offset = next_offset

        except Exception:
            break


def get_system_and_landscape(
    include_examples: bool = False,
    client: Optional[QdrantClient] = None,
    registry: Optional[SimpleRegistry] = None
) -> Dict[str, Any]:
    """Get system capabilities and project landscape for AI onboarding

    Args:
        include_examples: Include compose pattern library
        client: Qdrant client (created if not provided)
        registry: Project registry (created if not provided)

    Returns:
        System shape + project landscape + quick start examples
    """
    if client is None:
        client = QdrantClient(host=config.qdrant_host, port=config.qdrant_port)
    if registry is None:
        registry = SimpleRegistry()

    project_root = registry.get_project_root()

    if not registry.is_registered(project_root):
        return {"error": "Project not registered. Run 'imem init' first."}

    project_info = registry.get_project_info(project_root)
    collections = project_info.get('collections', {})

    # Get coverage stats
    stats = _get_coverage_stats_internal(client, collections)

    # Get top concepts
    top_concepts = _get_top_concepts(client, collections)

    # Build output
    result = {
        "system": {
            "primitives": ["siblings", "genealogy", "temporal", "cross_phase"],
            "compose_syntax": "imem compose '{\"search\": {...}, \"discovery\": {...}}'"
        },
        "landscape": {
            "coverage": stats,
            "top_concepts": top_concepts[:10],  # Top 10 most mentioned
            "interpretation": "Section titles show architectural vocabulary and exploration areas"
        },
        "quick_start": [
            "imem compose '{\"search\": {\"text\": \"authentication\", \"limit\": 5}}'",
            "imem compose '{\"source\": \"conversations\", \"search\": {\"text\": \"bug\", \"limit\": 3}, \"discovery\": {\"genealogy\": true}}'",
            "imem introspect --map  # See full concept topology"
        ]
    }

    # Preset/pattern system removed - premature to codify before validation through usage
    # See: Template removal (251117 changelog) for rationale

    return result


def get_concept_topology(
    client: Optional[QdrantClient] = None,
    registry: Optional[SimpleRegistry] = None,
    sample_size: int = 500
) -> Dict[str, Any]:
    """Get complete concept topology - all section titles as knowledge graph

    Args:
        client: Qdrant client (created if not provided)
        registry: Project registry (created if not provided)
        sample_size: Number of points to sample

    Returns:
        Full concept network with frequencies and phase coverage
    """
    if client is None:
        client = QdrantClient(host=config.qdrant_host, port=config.qdrant_port)
    if registry is None:
        registry = SimpleRegistry()

    project_root = registry.get_project_root()

    if not registry.is_registered(project_root):
        return {"error": "Project not registered. Run 'imem init' first."}

    project_info = registry.get_project_info(project_root)
    collections = project_info.get('collections', {})

    # Gather all concepts with frequencies
    concepts = {}

    # Sample context collections
    if 'context' in collections:
        context_base = collections['context']
        for suffix in ['_impl', '_pattern']:
            coll_name = f"{context_base}{suffix}"
            if client.collection_exists(coll_name):
                _sample_for_concepts(client, coll_name, concepts, sample_size)

    # Sample conversation collection
    if 'conversation' in collections:
        conv_coll = collections['conversation']
        if client.collection_exists(conv_coll):
            _sample_for_concepts(client, conv_coll, concepts, sample_size)

    # Format output
    all_concepts = []
    for title, data in sorted(concepts.items(), key=lambda x: x[1]['frequency'], reverse=True):
        all_concepts.append({
            "title": title,
            "frequency": data['frequency'],
            "phases": sorted(list(data['phases'])) if data['phases'] else []
        })

    return {
        "concept_network": {
            "all_concepts": all_concepts,
            "total_unique": len(all_concepts),
            "high_frequency": [c for c in all_concepts if c['frequency'] >= 5],
            "interpretation": "Section titles across all documents - architectural vocabulary and concept coverage"
        }
    }


def get_coverage_stats(
    client: Optional[QdrantClient] = None,
    registry: Optional[SimpleRegistry] = None
) -> Dict[str, Any]:
    """Get just coverage statistics

    Args:
        client: Qdrant client (created if not provided)
        registry: Project registry (created if not provided)

    Returns:
        Coverage statistics only
    """
    if client is None:
        client = QdrantClient(host=config.qdrant_host, port=config.qdrant_port)
    if registry is None:
        registry = SimpleRegistry()

    project_root = registry.get_project_root()

    if not registry.is_registered(project_root):
        return {"error": "Project not registered. Run 'imem init' first."}

    project_info = registry.get_project_info(project_root)
    collections = project_info.get('collections', {})

    return _get_coverage_stats_internal(client, collections)


def _get_coverage_stats_internal(client: QdrantClient, collections: Dict) -> Dict[str, Any]:
    """Internal helper to get coverage stats

    Args:
        client: Qdrant client
        collections: Collection info from registry

    Returns:
        Coverage statistics
    """
    stats = {}

    # Context docs
    if 'context' in collections:
        context_base = collections['context']
        impl_coll = f"{context_base}_impl"
        pattern_coll = f"{context_base}_pattern"

        impl_count = 0
        pattern_count = 0
        phases = set()

        if client.collection_exists(impl_coll):
            try:
                info = client.get_collection(impl_coll)
                impl_count = info.points_count or 0
                # Sample to get phases
                points, _ = client.scroll(impl_coll, limit=100, with_payload=True, with_vectors=False)
                for p in points:
                    if 'phase' in p.payload and p.payload['phase']:
                        phases.add(p.payload['phase'])
            except:
                pass

        if client.collection_exists(pattern_coll):
            try:
                info = client.get_collection(pattern_coll)
                pattern_count = info.points_count or 0
            except:
                pass

        stats['context_docs'] = {
            "implementation_chunks": impl_count,
            "pattern_chunks": pattern_count,
            "total_chunks": impl_count + pattern_count,
            "phases_indexed": sorted(list(phases))
        }

    # Conversations
    if 'conversation' in collections:
        conv_coll = collections['conversation']

        if client.collection_exists(conv_coll):
            try:
                info = client.get_collection(conv_coll)
                chunk_count = info.points_count or 0

                # Count unique sessions
                sessions = set()
                offset = None
                sampled = 0
                while sampled < 1000:  # Sample up to 1000 points
                    points, next_offset = client.scroll(
                        conv_coll,
                        limit=100,
                        offset=offset,
                        with_payload=True,
                        with_vectors=False
                    )
                    if not points:
                        break

                    for p in points:
                        if 'session_id' in p.payload and p.payload['session_id']:
                            sessions.add(p.payload['session_id'])
                        sampled += 1

                    if next_offset is None or sampled >= 1000:
                        break
                    offset = next_offset

                stats['conversations'] = {
                    "total_chunks": chunk_count,
                    "indexed_sessions": len(sessions),
                    "average_chunks_per_session": round(chunk_count / len(sessions), 1) if sessions else 0
                }
            except:
                stats['conversations'] = {"error": "Could not access conversation collection"}

    return stats


def _get_top_concepts(client: QdrantClient, collections: Dict, limit: int = 20) -> list:
    """Get top mentioned concepts from section titles

    Args:
        client: Qdrant client
        collections: Collection info
        limit: Number of top concepts to return

    Returns:
        List of top concepts with mention counts
    """
    concepts = {}

    # Sample context
    if 'context' in collections:
        context_base = collections['context']
        impl_coll = f"{context_base}_impl"
        if client.collection_exists(impl_coll):
            _sample_for_concepts(client, impl_coll, concepts, sample_size=200)

    # Sort by frequency
    sorted_concepts = sorted(concepts.items(), key=lambda x: x[1]['frequency'], reverse=True)

    return [
        {"name": name, "mentions": data['frequency']}
        for name, data in sorted_concepts[:limit]
    ]


def _sample_for_concepts(
    client: QdrantClient,
    collection_name: str,
    concepts: Dict,
    sample_size: int = 200
) -> None:
    """Sample collection for concept frequency data

    Args:
        client: Qdrant client
        collection_name: Collection to sample
        concepts: Accumulator dict {title: {frequency, phases}}
        sample_size: Points to sample
    """
    offset = None
    sampled = 0

    while sampled < sample_size:
        try:
            points, next_offset = client.scroll(
                collection_name=collection_name,
                limit=min(100, sample_size - sampled),
                offset=offset,
                with_payload=True,
                with_vectors=False
            )

            if not points:
                break

            for point in points:
                payload = point.payload

                # Extract section title
                section_title = payload.get('section_type') or payload.get('section_name')
                if not section_title:
                    continue

                # Skip conversation message headers
                if section_title.startswith('Message ') or section_title.startswith('Code Patch '):
                    continue

                # Add to concepts
                if section_title not in concepts:
                    concepts[section_title] = {'frequency': 0, 'phases': set()}

                concepts[section_title]['frequency'] += 1

                if 'phase' in payload and payload['phase']:
                    concepts[section_title]['phases'].add(payload['phase'])

                sampled += 1

            if next_offset is None or sampled >= sample_size:
                break

            offset = next_offset

        except Exception:
            break


def get_compose_patterns() -> Dict[str, Any]:
    """Return proven compose query patterns

    Returns:
        Pattern library with descriptions and example configs
    """
    return {
        'trace_decision_lineage': {
            'description': 'Follow conversation genealogy to understand decision evolution',
            'use_case': 'Understand why a technical decision was made',
            'config': {
                'source': 'context',
                'search': {
                    'text': 'JWT authentication decision',
                    'filters': {'phase': 'develop'},
                    'limit': 1
                },
                'discovery': {
                    'siblings': True,
                    'genealogy': True
                },
                'output': {
                    'template': 'genealogy'
                }
            }
        },
        'temporal_evolution': {
            'description': 'Track how a concept evolved over time',
            'use_case': 'See how implementation approach changed',
            'config': {
                'source': 'context',
                'search': {
                    'text': 'caching strategy',
                    'limit': 1
                },
                'discovery': {
                    'temporal': {
                        'direction': 'after'
                    }
                },
                'output': {
                    'template': 'timeline'
                }
            }
        },
        'cross_phase_linking': {
            'description': 'Link design documents to implementation',
            'use_case': 'Find implementation details for design decision',
            'config': {
                'source': 'context',
                'search': {
                    'text': 'API authentication',
                    'filters': {'phase': 'design'},
                    'limit': 1
                },
                'discovery': {
                    'cross_phase': {
                        'phase': 'develop'
                    }
                }
            }
        },
        'authority_ranking': {
            'description': 'Rank documents by authority score',
            'use_case': 'Find most authoritative source on topic',
            'config': {
                'source': 'context',
                'search': {
                    'text': 'security decisions',
                    'limit': 5
                },
                'discovery': {
                    'siblings': True
                },
                'graph': {
                    'algorithm': 'authority',
                    'top': 5
                }
            }
        },
        'assistant_reasoning': {
            'description': 'Get assistant thinking on a topic',
            'use_case': 'Understand AI reasoning process',
            'config': {
                'source': 'conversations',
                'search': {
                    'text': 'implementation approach',
                    'filters': {'chunk_type': 'thinking'}
                },
                'limit': 5
            }
        },
        'code_changes_by_file': {
            'description': 'Find all patches to specific file',
            'use_case': 'See evolution of a file through conversations',
            'config': {
                'source': 'conversations',
                'search': {
                    'text': 'cli.py',
                    'filters': {'chunk_type': 'patch'}
                },
                'limit': 10
            }
        }
    }
