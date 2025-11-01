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

## The Concept

System exposes capabilities programmatically. AI agents query for schema instead of reading docs.

**Query flow:**
```
Agent asks: "What can I filter on?"
    ↓
System introspects: Live data → Schema
    ↓
Returns: Properties, primitives, composition patterns
```

**Property:** Zero documentation drift (schema from reality, not docs).

---

## The Value

- **Self-describing** (schema from live data)
- **Brother agent discovery** (future sessions learn capabilities)
- **Zero drift** (docs can't go stale)
- **Programmatic** (AI constructs queries from schema)

---

## Related Concepts

See: [../vision/imem.md](../vision/imem.md) - Principle #2: Self-Describing Systems
See: [../business-logic/AI-FIRST-USER.md](../business-logic/AI-FIRST-USER.md) - Schema introspection