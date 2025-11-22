#!/usr/bin/env python3
"""
IMEM Introspection - Self-Documenting System Capabilities

Enables AI agents to discover indexed metadata fields programmatically.
Zero documentation drift - schema reflects live data structure.

SQLite-first: All queries use SQLite directly.
Traversal: Metadata predicates ARE the graph. Query them to traverse.
"""

import json
from typing import Dict, Any, Optional, Set
from pathlib import Path

from ..config import config
from ..registry import SimpleRegistry
from ..storage import SQLiteVectorStore


def introspect(
    fields_only: bool = False,
    source: str = 'all',
    sample_size: int = 100,
    enumerate_entities: bool = False,
    store: Optional[SQLiteVectorStore] = None
) -> Dict[str, Any]:
    """Main introspection entry point

    Args:
        fields_only: Return only metadata schema
        source: 'context' | 'conversations' | 'all'
        sample_size: Number of chunks to sample
        enumerate_entities: Include project ontology (types, entities, sessions, files)
        store: SQLiteVectorStore (created from registry if not provided)

    Returns:
        Schema of indexed metadata fields with examples
    """
    registry = SimpleRegistry()
    project_root = registry.get_project_root()

    if not registry.is_registered(project_root):
        return {"error": "Project not registered. Run 'imem init' first."}

    if store is None:
        store = SQLiteVectorStore(project_root=project_root)

    result = {
        "metadata_fields": {}
    }

    # Discover metadata from SQLite
    result['metadata_fields'] = discover_schema(store, sample_size, source)

    # Add traversal hints (these are just SQL patterns, not APIs)
    if not fields_only:
        result['traversal'] = {
            'note': 'Metadata predicates ARE the graph. Query SQLite directly.',
            'patterns': {
                'same_document': 'SELECT * FROM chunks WHERE file_path = ?',
                'same_conversation': 'SELECT * FROM chunks WHERE session_id = ?',
                'temporal_after': 'SELECT * FROM chunks WHERE timestamp > ? ORDER BY timestamp',
                'by_phase': 'SELECT * FROM chunks WHERE phase = ?',
                'by_section_type': 'SELECT * FROM chunks WHERE section_type = ?'
            }
        }

    # Add entity enumeration (project ontology)
    if enumerate_entities:
        result['ontology'] = discover_ontology(store, sample_size)

    return result


def discover_schema(
    store: SQLiteVectorStore,
    sample_size: int = 100,
    source: str = 'all'
) -> Dict[str, Any]:
    """Discover metadata schema by sampling SQLite

    Args:
        store: SQLiteVectorStore instance
        sample_size: Number of chunks to sample
        source: 'context' | 'conversations' | 'all'

    Returns:
        Field schema with types, values, examples
    """
    fields = {}

    # Build query
    query = """
        SELECT id, content, file_path, phase, section_type,
               section_name, timestamp, session_id, metadata
        FROM chunks
    """
    params = []

    if source == 'context':
        query += " WHERE json_extract(metadata, '$.source') = 'context'"
    elif source == 'conversations':
        query += " WHERE json_extract(metadata, '$.source') = 'conversation'"

    query += f" LIMIT {sample_size}"

    try:
        conn = store.store.conn
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()

        for row in rows:
            payload = {
                'file_path': row['file_path'],
                'phase': row['phase'],
                'section_type': row['section_type'],
                'section_name': row['section_name'],
                'timestamp': row['timestamp'],
                'session_id': row['session_id'],
            }

            if row['metadata']:
                try:
                    meta = json.loads(row['metadata'])
                    payload.update(meta)
                except json.JSONDecodeError:
                    pass

            _aggregate_fields(fields, payload)

    except Exception as e:
        return {"error": f"Schema discovery failed: {e}"}

    return _format_field_schema(fields)


def _aggregate_fields(fields: Dict, payload: Dict[str, Any]) -> None:
    """Aggregate field info from a single payload"""
    for key, value in payload.items():
        if key not in fields:
            fields[key] = {
                'type': type(value).__name__ if value is not None else 'NoneType',
                'values': set(),
                'examples': [],
                'nullable': False
            }

        if value is None:
            fields[key]['nullable'] = True

        if isinstance(value, bool):
            fields[key]['values'].add(value)
        elif isinstance(value, str) and len(value) < 50:
            fields[key]['values'].add(value)

        if len(fields[key]['examples']) < 3 and value is not None:
            if isinstance(value, str) and len(value) > 200:
                fields[key]['examples'].append(value[:200] + "...")
            else:
                fields[key]['examples'].append(value)


def _format_field_schema(fields: Dict) -> Dict[str, Any]:
    """Format aggregated fields into clean schema"""
    schema = {}

    for key, info in fields.items():
        field_schema = {
            'type': info['type'],
            'filterable': True
        }

        if info['nullable']:
            field_schema['nullable'] = True

        if len(info['values']) > 0 and len(info['values']) < 20:
            field_schema['values'] = sorted(list(info['values']), key=str)

        if info['examples']:
            field_schema['examples'] = info['examples']

        field_schema['description'] = _get_field_description(key)
        schema[key] = field_schema

    return schema


def _get_field_description(field_name: str) -> str:
    """Get human-readable description for known fields"""
    descriptions = {
        # Identity
        'source': 'Document source type (context/conversation)',
        'file_path': 'Source file path - use for same-document queries',
        'session_id': 'Conversation UUID - use for genealogy queries',

        # Temporal
        'timestamp': 'ISO timestamp - use for temporal ordering',

        # Type system
        'phase': 'Lifecycle phase (develop/design/document/designate)',
        'section_type': 'H2 parent section category',
        'section_name': 'H3 section title',
        'header_path': 'Full header hierarchy path',
        'section_level': 'Header depth level',
        'category': 'Document type category',
        'subtype': 'Document type subtype',

        # Conversation
        'chunk_type': 'Conversation chunk category (message/thinking/tools/patch)',
        'role': 'Message author role (user/assistant)',
        'message_count': 'Total messages in conversation',

        # Structural signals (template compliance, not truth)
        'has_context': 'Section contains Context field (template compliance)',
        'has_solution': 'Section contains Solution field (template compliance)',
        'has_rationale': 'Section contains Rationale field (template compliance)',
        'has_alternatives': 'Section contains Alternatives field (template compliance)',

        # Stats
        'word_count': 'Section word count',
        'char_count': 'Section character count',
    }
    return descriptions.get(field_name, f'Field: {field_name}')


def discover_ontology(
    store: SQLiteVectorStore,
    sample_size: int = 500
) -> Dict[str, Any]:
    """Discover project ontology - what's actually indexed"""
    ontology = {
        "taxonomy": {
            "phases": set(),
            "section_types": set(),
            "categories": set()
        },
        "inventory": {
            "sessions": set(),
            "files": set()
        }
    }

    query = f"""
        SELECT phase, section_type, session_id, file_path, metadata
        FROM chunks
        LIMIT {sample_size}
    """

    try:
        conn = store.store.conn
        cursor = conn.execute(query)
        rows = cursor.fetchall()

        for row in rows:
            if row['phase']:
                ontology["taxonomy"]["phases"].add(row['phase'])

            section = row['section_type']
            if section and not section.startswith('Message ') and not section.startswith('Code Patch '):
                ontology["taxonomy"]["section_types"].add(section)

            if row['session_id']:
                ontology["inventory"]["sessions"].add(row['session_id'])

            if row['file_path']:
                ontology["inventory"]["files"].add(row['file_path'])

            if row['metadata']:
                try:
                    meta = json.loads(row['metadata'])
                    if meta.get('category'):
                        ontology["taxonomy"]["categories"].add(meta['category'])
                except json.JSONDecodeError:
                    pass

    except Exception as e:
        return {"error": f"Ontology discovery failed: {e}"}

    result = {
        "taxonomy": {k: sorted(list(v)) for k, v in ontology["taxonomy"].items()},
        "inventory": {
            "session_count": len(ontology["inventory"]["sessions"]),
            "file_count": len(ontology["inventory"]["files"])
        }
    }

    return result


def get_coverage_stats(store: Optional[SQLiteVectorStore] = None) -> Dict[str, Any]:
    """Get coverage statistics from SQLite"""
    registry = SimpleRegistry()
    project_root = registry.get_project_root()

    if not registry.is_registered(project_root):
        return {"error": "Project not registered"}

    if store is None:
        store = SQLiteVectorStore(project_root=project_root)

    try:
        stats = store.get_stats()

        phases_query = """
            SELECT phase, COUNT(*) as count
            FROM chunks
            WHERE phase IS NOT NULL
            GROUP BY phase
        """
        conn = store.store.conn
        cursor = conn.execute(phases_query)
        phase_counts = {row['phase']: row['count'] for row in cursor.fetchall()}

        return {
            "total_chunks": stats.get('total_chunks', 0),
            "by_phase": phase_counts
        }

    except Exception as e:
        return {"error": f"Stats query failed: {e}"}
