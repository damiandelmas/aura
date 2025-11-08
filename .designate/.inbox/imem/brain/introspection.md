# IMEM Introspection: Self-Documenting Systems

**Feature Status:** Designed, not implemented

---

## The Problem

AI agents want to use IMEM but don't know:
- What metadata fields exist and their valid values
- What primitives are available for discovery
- How to construct valid compose queries
- What query patterns work for different use cases

**Current state:** Agents guess schema, read stale documentation, or trial-and-error query construction.

---

## The Solution: `imem introspect`

System exposes capabilities programmatically. AI agents discover metadata structure, compose patterns, and example queries from live data.

```bash
imem introspect
```

Returns complete schema discovery:
```json
{
  "template_metadata": {
    "section_type": {...},
    "has_rationale": {...},
    "structural_completeness": {...},
    ...
  },
  "document_properties": {
    "category": {...},
    "session_id": {...}, 
    "timestamp": {...},
    "temporal_position": {...},
    ...
  },
  "computed_scores": {
    "confidence_score": {...},
    "authority_score": {...},
    "completeness_score": {...},
    ...
  },
  "primitives": {
    "siblings": {"description": "...", "filters": [...]},
    "genealogy": {"description": "...", "filters": [...]},
    "temporal": {"description": "...", "filters": [...]}
  },
  "compose_patterns": {
    "trace_lineage": {...},
    "validate_claims": {...},
    "find_related": {...},
    ...
  }
}
```

**Extended capabilities:**
```bash
imem introspect --examples      # Query pattern library
imem introspect --fields        # Just metadata schema  
imem introspect --live-sample   # Sample actual chunk structure
```

---

## The Vision

**AI Agent Workflow:**
1. **Discover:** `introspect` → understand capabilities
2. **Compose:** Build queries from schema patterns
3. **Execute:** Run validated compose queries
4. **Learn:** Save successful patterns for reuse
5. **Share:** Query patterns become part of introspection library

**Query Pattern Evolution:**
- Successful queries get saved as named patterns
- Patterns accumulate usage statistics
- High-value patterns surface in introspection
- Brother agents inherit proven query strategies

**Self-Improving System:**
```pseudocode
agent_discovers_schema()
agent_constructs_query_from_schema()
agent_executes_successful_query()
system_learns_pattern(query, success_metrics)
future_agents_inherit_pattern()
```

---

## Implementation Approach

**Live Schema Discovery:**
```pseudocode
sample_collection_chunks(limit=100)
aggregate_metadata_fields(chunks)
discover_field_types_and_ranges()
expose_primitive_capabilities()
return_comprehensive_schema()
```

**Pattern Library Management:**
```pseudocode
save_successful_queries(query, metrics)
rank_patterns_by_effectiveness()
expose_top_patterns_in_introspection()
enable_pattern_search_and_discovery()
```

**Zero Documentation Drift:**
- Schema reflects live data structure
- Examples from actual successful queries
- Field values from current chunk contents
- Always synchronized with system reality

---

## The Value

**For AI Agents:**
- Complete capability discovery without documentation
- Proven query patterns from successful usage
- Programmatic query construction from schema
- Learning from brother agent successes

**For System Evolution:**
- Self-documenting metadata capabilities
- Query pattern accumulation and improvement
- Zero-maintenance schema introspection
- Emergent best practices from usage

**For Brother Agents:**
- Immediate productive system usage
- Inherited successful query strategies
- No ramp-up time for system discovery
- Collaborative pattern development

---

## Related Concepts

See: [../vision/imem.md](../vision/imem.md) - Self-describing systems principle
See: [../business-logic/AI-FIRST-USER.md](../business-logic/AI-FIRST-USER.md) - Brother agent collaboration