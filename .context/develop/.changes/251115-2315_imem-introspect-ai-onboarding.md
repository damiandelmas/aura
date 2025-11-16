---
schema_version: "v3_adaptive"
type: "implementation.introspection"
status: "completed"
keywords: "imem introspect ai-onboarding schema-discovery ontology-enumeration self-documenting"
timestamp: "2025-11-15T23:15:00-0700"
session_id: "08a69e59-12d9-4984-ad66-f06aec5b4af1"
---

# IMEM Introspect: AI Self-Onboarding System

## Request
> "plan to enable introspect? we should be able to enable an AI to excavate the codebase purely from imem introspect first and then imem compose correct?"

User requested programmatic capability discovery enabling AI agents to onboard without documentation.

## Overview

Implemented `imem introspect` command exposing system capabilities as JSON schema. AI agents discover metadata fields, filterable values, discovery primitives, and proven query patterns through live collection sampling. Enables zero-documentation onboarding where agents learn project structure, construct valid queries, and retrieve targeted knowledge autonomously. Tested end-to-end with brother agent successfully onboarding and executing compose queries.

## Decisions

### Live Sampling Over Static Schema
- **Context**: Need to expose metadata structure to AI agents
- **Solution**: Sample collection points, aggregate field types and values, return discovered schema
- **Rationale**: Zero documentation drift - schema reflects actual data structure
- **Benefit**: Always accurate, adapts as collections evolve

### Ontology Enumeration for Project Context
- **Context**: AI needs to know what exists (sessions, files, types, phases)
- **Solution**: Added `--entities` flag enumerating types, subtypes, phases, section_types, sessions, files
- **Rationale**: Enables AI to construct meaningful filters without trial-and-error
- **Benefit**: AI discovers "this project has 7 sessions about architecture, imem, trace"

### Compose Patterns as Examples
- **Context**: AI needs to learn query construction
- **Solution**: Hardcoded 6 proven patterns (trace_decision_lineage, temporal_evolution, etc.)
- **Rationale**: Show working queries, not just schema
- **Benefit**: AI learns by example, can adapt patterns to new queries

## Implementation

### Architecture
1. `imem introspect` → Sample collections (default 100 points)
2. Aggregate metadata fields (type, values, examples)
3. Enumerate ontology (types, phases, sessions, files)
4. Return primitives + patterns + schema as JSON
5. AI parses, constructs `imem compose` queries

### Code Signatures

**Schema Discovery** (`imem/src/imem/introspect.py`)
```python
def discover_schema(client, collection_name, sample_size=100):
    # Sample points from collection
    points, _ = client.scroll(collection_name, limit=sample_size)

    # Aggregate field metadata
    for point in points:
        for key, value in point.payload.items():
            fields[key]['type'] = type(value).__name__
            if isinstance(value, str) and len(value) < 50:
                fields[key]['values'].add(value)  # Enum values

    return format_field_schema(fields)
```

**Ontology Enumeration** (`imem/src/imem/introspect.py`)
```python
def discover_ontology(client, context_collection, conv_collection, sample_size=500):
    ontology = {
        'taxonomy': {'types': set(), 'phases': set(), 'section_types': set()},
        'inventory': {'sessions': set(), 'files': set()}
    }

    # Extract from sampled payloads
    for point in points:
        if 'category' in point.payload:
            ontology['taxonomy']['types'].add(point.payload['category'])
        if 'session_id' in point.payload:
            ontology['inventory']['sessions'].add(point.payload['session_id'])

    return ontology
```

**CLI Integration** (`imem/src/imem/cli.py`)
```python
@imem.command()
@click.option('--entities', is_flag=True, help='Enumerate project ontology')
@click.option('--examples', is_flag=True, help='Include compose pattern library')
def introspect(entities, examples):
    result = introspect_fn(enumerate_entities=entities, show_examples=examples)
    click.echo(json.dumps(result, indent=2))
```

## Patterns

### Self-Documenting Systems via Live Introspection
- **Pattern**: Expose capabilities programmatically by sampling live data, not maintaining static docs
- **Approach**: Query collections → aggregate metadata → return schema
- **Benefit**: Zero documentation drift, always synchronized with reality
- **When**: Any system where AI agents need capability discovery

### Ontology Before Query
- **Pattern**: Provide inventory (what exists) before primitives (how to query)
- **Sequence**: 1) Discover sessions/files, 2) Learn filters, 3) See query examples
- **Benefit**: AI builds mental model before attempting queries
- **When**: Complex query systems with many filters and options

## Audit

### Created
- `imem/src/imem/introspect.py` - Schema discovery, ontology enumeration, pattern library

### Modified
- `imem/src/imem/cli.py` - Added `introspect` command with --entities, --examples flags

### Verified
- AI onboarding simulation: Discovered 7 sessions, 6 files, 4 primitives
- Brother agent (c4fbb265): Successfully onboarded, executed 4 compose queries
- All primitives functional (siblings, genealogy, temporal, cross_phase)
