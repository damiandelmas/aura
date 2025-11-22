# IMEM Runbook - SQLite-First

**SQLite is THE store.** No Qdrant, no external services, no version switching.

## Quick Start

```bash
cd /path/to/your/project
imem init                              # Register project
imem index develop                     # Index .context/develop/*.md
imem query --phase develop --limit 5   # Query by phase
```

---

## Commands

| Command | Purpose |
|---------|---------|
| `imem init` | Register current directory as IMEM project |
| `imem index <phase>` | Index phase: `develop`, `design`, `designate`, `document`, or `context` (all) |
| `imem query` | Fast metadata search |
| `imem compose '{...}'` | Processor pipeline with JSON config |
| `imem stats` | Show chunk counts, phase breakdown |
| `imem introspect` | Discover indexed fields and traversal patterns |

---

## Indexing

### Index by Phase
```bash
imem index develop      # .context/develop/*.md
imem index design       # .context/design/*.md
imem index designate    # .context/designate/*.md
imem index context      # All phases
```

### Options
```bash
imem index develop --force          # Clear existing, reindex
imem index develop --limit 10       # Index first 10 files only
```

---

## Querying

### By Phase
```bash
imem query --phase develop --limit 10
imem query --phase design --limit 5
```

### By Text
```bash
imem query --text "SQLite" --limit 5
imem query --text "authentication" --phase develop
```

### By Section Type
```bash
imem query --section-type "Decisions" --limit 5
imem query --section-type "Implementation" --phase develop
```

### Combined Filters
```bash
imem query --text "routing" --phase develop --section-type "Decisions" --limit 3
```

---

## Compose (Advanced)

For processor pipeline queries with JSON config:

### Basic Search
```bash
imem compose '{"search": {"text": "SQLite", "filters": {"phase": "develop"}, "limit": 5}}'
```

### Filter Only (No Text)
```bash
imem compose '{"search": {"text": "", "filters": {"phase": "design"}, "limit": 10}}'
```

**Output:** JSON with results array and metadata.

---

## Introspection

### See What's Indexed
```bash
imem stats
# Total chunks: 1060
# By phase: designate: 786, develop: 186, design: 88
```

### Discover Fields
```bash
imem introspect
# Indexed fields: file_path, phase, section_type, section_name, timestamp, session_id
# Traversal patterns: same_document, same_conversation, temporal_after, by_phase
```

### JSON Output
```bash
imem introspect --format json
```

### With Ontology (What Values Exist)
```bash
imem introspect --ontology
```

---

## Traversal (Direct SQL)

**Metadata predicates ARE the graph.** Query SQLite directly for relationship queries:

```sql
-- Same document (siblings)
SELECT * FROM chunks WHERE file_path = '/path/to/file.md'

-- Same conversation (genealogy)
SELECT * FROM chunks WHERE session_id = 'uuid-here'

-- Temporal (after timestamp)
SELECT * FROM chunks WHERE timestamp > '2025-11-21' ORDER BY timestamp

-- By phase
SELECT * FROM chunks WHERE phase = 'develop'

-- By section type
SELECT * FROM chunks WHERE section_type = 'Decisions'
```

**Access DB directly:**
```bash
sqlite3 ~/.imem/namespaces/$(git branch --show-current)/projects/*/metadata.db
```

---

## Data Location

```
~/.imem/namespaces/{git-branch}/
├── projects/{hash}/
│   └── metadata.db      # All chunks
└── registry.json        # Project mappings
```

**Namespace = git branch name.** Each branch gets isolated storage.

---

## Quality Hierarchy

| Source | Quality | Use For |
|--------|---------|---------|
| `section_type='Decisions'` | Best | Why decisions were made |
| `section_type='Implementation'` | Good | How things work |
| `section_type='Patterns'` | Good | Reusable approaches |
| `phase='develop'` | Good | What was built |
| `phase='design'` | Good | What was planned |

---

## Examples

### Find All Decisions
```bash
imem query --section-type "Decisions" --limit 20
```

### Find SQLite-Related Content in Develop
```bash
imem query --text "SQLite" --phase develop --limit 10
```

### Get Stats After Indexing
```bash
imem index context --force
imem stats
```

### Export Query Results
```bash
imem compose '{"search": {"text": "auth", "limit": 10}}' > results.json
```

---

## Troubleshooting

### "Not in a registered project"
```bash
imem init   # Register current directory
```

### Empty Results
```bash
imem stats  # Check if anything indexed
imem index develop --force  # Reindex
```

### Wrong Namespace
```bash
git branch --show-current  # Check branch
# Namespace auto-detects from git branch
```
