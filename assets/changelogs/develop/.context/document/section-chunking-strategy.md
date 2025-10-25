# Section-Level Chunking Strategy

## Problem

**Document-level chunking:**
- Search returns entire 150-line changelog
- AI must scan full document for relevant constraint
- Too much noise, not enough precision

**Solution:** Section-level chunking with LlamaIndex MarkdownNodeParser

## Architecture

```
Single Changelog (150 lines)
        ↓
LlamaIndex MarkdownNodeParser
        ↓
┌─────────────────────────────────┐
│ H2: Decisions                   │ → Parent node
│   ├── H3: Decision 1            │ → Child node (vector 1)
│   └── H3: Decision 2            │ → Child node (vector 2)
│                                 │
│ H2: Constraints                 │ → Parent node
│   ├── H3: Constraint 1          │ → Child node (vector 3)
│   └── H3: Constraint 2          │ → Child node (vector 4)
│                                 │
│ H2: Implementation              │ → Parent node
│   ├── H3: Architecture          │ → Child node (vector 5)
│   └── H3: Code Signatures       │ → Child node (vector 6)
└─────────────────────────────────┘
        ↓
E5-Large-v2 embeddings (1024D)
        ↓
Qdrant (6 vectors, not 1)
```

**Result:** Search finds specific section, not entire document.

## Node Structure

### Hierarchy Requirements

**Must follow:**
- H1: Document title
- H2: Section type (Decisions, Constraints, etc.)
- H3: Individual items

**Why:** LlamaIndex expects this hierarchy for proper parent-child relationships.

### Node Metadata

**Auto-extracted by MarkdownNodeParser:**
```python
{
  "header_path": "Decisions > Use Port 6334",
  "node_type": "h3",
  "parent_node_id": "decisions_section_abc123",
  "prev_node_id": "decision_1_def456",
  "next_node_id": "decision_3_ghi789"
}
```

**Added at index time:**
```python
{
  "section_type": "decision",        # From H2 parent
  "section_id": "use-port-6334",     # From H3 header
  "file_path": "vercel-deployment.md",
  "timestamp": "2025-09-27T...",
  "category": "implementation",       # From frontmatter type
  "subtype": "deployment"
}
```

## Section Type Detection

### Automatic Mapping

```python
H2_TO_SECTION_TYPE = {
  "Request": "request",
  "Overview": "overview",
  "Decisions": "decision",
  "Constraints": "constraint",
  "Failures": "failure",
  "Implementation": "implementation",
  "Patterns": "pattern",
  "Audit": "audit"
}

def extract_section_type(header_path: str) -> str:
    root = header_path.split(' > ')[0]
    return H2_TO_SECTION_TYPE.get(root, 'general')
```

**No manual IDs needed.** Structure provides metadata.

## Storage Pattern

### Vector Storage

```python
# One vector per H3 item
{
  "id": "uuid-abc-123",
  "vector": [0.123, -0.456, ...],  # 1024 dimensions
  "payload": {
    # Node content
    "content": "### Use Port 6334\n- **Context**: ...\n- **Solution**: ...",

    # LlamaIndex metadata
    "header_path": "Decisions > Use Port 6334",
    "node_type": "h3",
    "parent_node_id": "decisions_section",

    # Custom metadata
    "section_type": "decision",
    "section_id": "use-port-6334",
    "file_path": "250927-vercel.md",
    "timestamp": "2025-09-27T22:17:00-0700"
  }
}
```

### Example: 150-Line Changelog

**Without section chunking:**
- 1 vector (entire document)
- Vague search results

**With section chunking:**
- ~15-20 vectors (one per H3)
- Surgical retrieval

## Query Patterns

### 1. Section Type Filtering

```python
# All constraints across all changelogs
qdrant.search(
  query_vector=query_embedding,
  filter={'section_type': 'constraint'}
)
```

**Returns:** Only constraint nodes, not full documents.

### 2. Category Filtering

```python
# All implementation work
filter={'category': 'implementation'}

# All security implementations
filter={
  'category': 'implementation',
  'subtype': 'security'
}
```

### 3. Context Reconstruction

```python
# Found specific decision, need full context
decision_node = search_result[0]

# Get parent section (all decisions)
parent = get_node(decision_node.parent_node_id)

# Get all siblings
siblings = [get_node(id) for id in parent.child_node_ids]

# Get full changelog
root = get_node(parent.parent_node_id)
```

**Surgical retrieval + context expansion when needed.**

## Benefits

| Capability | Document-Level | Section-Level |
|------------|---------------|---------------|
| Find all constraints | Search + read 20 docs | Filter section_type='constraint' → 5 exact sections |
| Find decision rationale | Grep through docs | Filter section_type='decision' → Instant |
| Pattern recognition | Manual | Auto-detected from section_type='pattern' |
| Context retrieval | All or nothing | Surgical + expandable |

## Storage Impact

**Before (document-level):**
- 100 changelogs = 100 vectors

**After (section-level):**
- 100 changelogs × 15 sections avg = 1,500 vectors

**Performance:**
- 15x more vectors
- Qdrant handles easily (tested to millions)
- Results are MORE relevant (precision)
- Net impact: Faster answers despite more vectors

## Production RAG Pattern

This matches how production systems work:

**LlamaIndex approach:**
1. Parse documents into nodes (sections)
2. Store each node separately with metadata
3. Search at node level (surgical)
4. Reconstruct context via relationships (expandable)

**Notion AI:** Every block is separately embedded
**GitHub Copilot:** Code chunked by function/class
**ChatGPT:** Documents chunked at paragraph level

**Our implementation:** Changelogs chunked at H3 item level

## Validation

**Strategy is valid when:**
- H1 > H2 > H3 hierarchy maintained
- Each H3 becomes one searchable node
- Metadata flows from structure
- Parent-child relationships preserved
- Context can be reconstructed
- Query filters work by section_type

**Tested with:** LlamaIndex MarkdownNodeParser on 9 real examples
