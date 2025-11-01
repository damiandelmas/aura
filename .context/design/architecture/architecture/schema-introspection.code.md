# Schema Introspection: Self-Documenting Systems

**Feature Status:** Designed, not implemented

---

## The Brother Agent Problem

Your brother (future Claude session) WANTS to use imem but doesn't know:
- What metadata fields exist to filter on
- What compose primitives are available
- What the query schema is

**Problem:** Every new AI session has to guess or read docs/code

---

## The Solution: `imem schema`

Make the system introspectable. AI agents query the system directly for capabilities.

```bash
imem schema --format json
```

Returns:
```json
{
  "properties": {
    "keywords": {"type": "list[string]", "indexed": true, "filterable": true},
    "type": {"type": "string", "pattern": "category.subtype"},
    "section_type": {"type": "string", "values": ["Decisions", "Failures", "Patterns"]},
    "has_rationale": {"type": "bool", "filterable": true}
  },
  "primitives": {
    "siblings": {
      "description": "Chunks from same document",
      "filters": ["section_types", "has_rationale", "order_by", "limit"]
    },
    "temporal": {
      "description": "Evolution chain via timestamp + semantic similarity",
      "filters": ["direction", "limit"]
    },
    "genealogy": {
      "description": "Origin conversation via session_id",
      "filters": []
    }
  },
  "compose_schema": {
    "search": {"text": "string", "filters": "object"},
    "discovery": {"siblings": "object|bool", "temporal": "object|bool"},
    "output": {"template": "string"}
  }
}
```

---

## Example Queries

```bash
imem schema --examples
```

Returns copyable compose queries:
```json
{
  "find_failures": {
    "search": {"text": "auth", "filters": {"section_type": "Failures"}},
    "discovery": {"siblings": {"section_types": ["Decisions"], "limit": 3}}
  },
  "trace_evolution": {
    "search": {"text": "streaming", "filters": {"type": "implementation.*"}},
    "discovery": {"temporal": {"direction": "both"}}
  },
  "get_patterns": {
    "search": {"filters": {"section_type": "Patterns", "has_rationale": true}}
  }
}
```

---

## Implementation Approach

### Schema Discovery Function

```python
# imem/src/imem/schema.py
def get_collection_schema(collection_name: str, client: QdrantClient):
    """Return queryable metadata fields from collection"""

    # Get collection info
    collection = client.get_collection(collection_name)

    # Sample points to discover payload structure
    points = client.scroll(collection_name, limit=10)

    # Aggregate all payload keys
    schema = {
        "properties": {},
        "indexed_fields": [],
        "primitives": PRIMITIVES_CONFIG,
        "compose_schema": COMPOSE_SCHEMA
    }

    # Discover from actual data
    for point in points:
        for key, value in point.payload.items():
            if key not in schema["properties"]:
                schema["properties"][key] = {
                    "type": type(value).__name__,
                    "example": value
                }

    return schema
```

### CLI Command

```python
# imem/src/imem/cli.py
@imem.command()
@click.option('--examples', is_flag=True)
def schema(examples):
    """Show available metadata fields and compose schema"""

    registry = SimpleRegistry()
    collection = registry.get_collection_by_type(Path.cwd(), 'context')

    schema = get_collection_schema(collection, client)

    if examples:
        print_examples()
    else:
        print(json.dumps(schema, indent=2))
```

---

## The Value

**Before:** AI agents guess/read docs
**After:** AI agents query the system directly for capabilities

**Implementation:** ~2-3 hours
**Impact:** Every brother agent (including future-you) can discover and use ALL metadata without documentation

**The insight:** Make the tool INSPECTABLE to AI, not just usable.

---

## Related Concepts

See: [VISION.md](./VISION.md) - Principle #2: Self-Describing Systems
