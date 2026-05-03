---
name: flex:context:aura
description: Read Aura context docs from the aura-context docpac cell.
allowed-tools:
  - mcp__flex__flex_search
user-invocable: true
argument-hint: "topic/section, e.g. seat ledger or Overview recent 5"
---

# flex:context:aura

Use this to read current Aura context documents from the `aura-context` Flex cell.

This skill is self-contained. It may be invoked directly without loading the base `flex` skill.

Single endpoint: `mcp__flex__flex_search`. Use `cell="aura-context"`.

Every query must be valid SQL or a preset such as `@orient`. Plain text is not accepted; wrap natural language in `keyword()` or `vec_ops()`.

# RETRIEVAL

Pipeline: SQL -> vec_ops -> SQL. Phase 1 narrows with SQL. Phase 2 scores with embeddings. Phase 3 composes with SQL.

Primary surface: `sections`.

Common columns:

- `id`
- `content`
- `source_id`
- `title`
- `source_path`
- `file_date`
- `doc_type`
- `temporal`
- `section_title`
- `position`
- `centrality`
- `is_hub`
- `community_id`

Start with `@orient` unless this cell has already been oriented in the current turn:

```text
cell = "aura-context"
query = "@orient"
```

## RECIPES

Structural corpus shape:

```sql
SELECT doc_type, COUNT(DISTINCT source_id) AS docs, COUNT(*) AS sections
FROM sections
GROUP BY doc_type
ORDER BY docs DESC
```

Recent sections:

```sql
SELECT
  source_id,
  title,
  source_path,
  file_date,
  doc_type,
  section_title,
  substr(content, 1, 1800) AS content
FROM sections
WHERE section_title = 'Overview'
ORDER BY file_date DESC
LIMIT 10
```

Semantic search:

```sql
SELECT
  v.score,
  s.source_id,
  s.title,
  s.source_path,
  s.file_date,
  s.doc_type,
  s.section_title,
  substr(s.content, 1, 1800) AS content
FROM vec_ops(
  'similar:aura runtime seats delivery ledger orchestration diverse pool:100',
  'SELECT id FROM sections'
) v
JOIN sections s ON s.id = v.id
ORDER BY v.score DESC
LIMIT 10
```

Exact term search:

```sql
SELECT
  k.rank,
  k.snippet,
  s.source_id,
  s.title,
  s.source_path,
  s.file_date,
  s.doc_type,
  s.section_title,
  substr(s.content, 1, 1200) AS content
FROM keyword('TERM') k
JOIN sections s ON s.id = k.id
ORDER BY k.rank DESC
LIMIT 10
```

Hub navigation:

```sql
SELECT
  source_id,
  title,
  source_path,
  file_date,
  doc_type,
  section_title,
  centrality,
  substr(content, 1, 1400) AS content
FROM sections
WHERE is_hub = 1
ORDER BY centrality DESC
LIMIT 10
```

Full document drilldown:

```sql
SELECT section_title, substr(content, 1, 2200) AS content
FROM sections
WHERE source_id = 'SOURCE_ID'
ORDER BY position
LIMIT 30
```

# METHODOLOGY

Known path/name -> structural SQL on `source_path`, `title`, or `source_id`.

Known exact term -> `keyword('term')`.

Conceptual/fuzzy -> `vec_ops('similar:...')`.

Use `substr(content, 1, N)` and `LIMIT` to avoid oversized results.

Answer from retrieved evidence. Mention source paths, titles, or source IDs when useful. If evidence is thin, say what was found and what remains uncertain.
