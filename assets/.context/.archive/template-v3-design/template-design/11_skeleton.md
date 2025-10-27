# IMEM Changelog Template v3.0 - Modular & Agile

## Design Principle

**"Use what you need. Skip what you don't."**

The template provides structure, not prescription. Sections appear only when they add value.

---

## Minimal Template (5-30 min work)

```markdown
---
schema_version: "v3_section_chunking"
timestamp: "$(TZ=America/Los_Angeles date '+%Y-%m-%dT%H:%M:%S%z')"
type: "bug-fix"
status: "completed"
scope: "bug-fix"
chu_keywords: "[3-5 keywords]"
---

# [Title]

## Request
> "[quote]"

## Overview
[1-2 paragraphs: what was done, why, outcome]

## Implementation
[What changed - keep brief]

## Audit
- `file` - changes

**Duration**: [time]
```

**Use for:** Bug fixes, typos, simple config changes, documentation updates

---

## Standard Template (30min - 2hr work)

```markdown
---
schema_version: "v3_section_chunking"
timestamp: "$(TZ=America/Los_Angeles date '+%Y-%m-%dT%H:%M:%S%z')"
type: "implementation"
status: "completed"
scope: "feature"
chu_keywords: "[6-9 keywords]"
---

# [Title]

## Request
> "[quote]"

## Overview
[2-3 paragraphs]

## Decisions

### [Decision Title]
- **Context**:
- **Solution**:
- **Alternatives**:
- **Rationale**:

## Implementation

### [Component]
```language
[code]
```

## Audit
- `files` - changes

**Duration**: [time]
**Success Metrics**: [results]
```

**Use for:** Most feature work, integrations, refactors with choices

---

## Full Template (Complex work with learning)

```markdown
---
schema_version: "v3_section_chunking"
timestamp: "$(TZ=America/Los_Angeles date '+%Y-%m-%dT%H:%M:%S%z')"
type: "implementation"
status: "completed"
scope: "feature"
chu_keywords: "[6-9 keywords]"
---

# [Title]

## Request
> "[quote]"

## Overview
[Full narrative]

## Decisions

### [Decision Title]
- **Context**:
- **Solution**:
- **Alternatives**:
- **Trade-offs**:
- **Rationale**:
- **Implications**:

## Constraints

### [Constraint Title]
- **What**:
- **Discovery**:
- **Why Non-Obvious**:
- **Workaround**:
- **Impact**:
- **Testing**:

## Implementation

### [Component]
```language
[code]
```

## Audit

### Created/Modified
- `file` - description

### Configuration
- `file` - changes

**Files Referenced**:
**Tools Used**:

## Patterns

### [Pattern Title]
- **When**:
- **Approach**:
- **Why**:
- **Benefit**:
- **Anti-pattern**:
- **Occurrences**:

## Replication

1. [step]
2. [step]

**Notes**:
**Duration**:
**Success Metrics**:
```

**Use for:** Major features, architectural work, constraint discovery, novel patterns

---

## Section Inclusion Rules

### ✅ Always Include
- Frontmatter
- Title
- Request
- Overview

### ⚡ Include When Relevant

| Section | Include When... |
|---------|----------------|
| **Decisions** | Strategic choices were made with alternatives |
| **Constraints** | Limitations/blockers were discovered |
| **Implementation** | Technical details worth documenting |
| **Audit** | Files were created/modified |
| **Patterns** | Reusable insights emerged |
| **Replication** | Steps are worth documenting for future |

---

## Field Flexibility

You don't need all fields in every section. Use what applies:

### Decisions
- **Context**: Always
- **Solution**: Always
- **Alternatives**: If options were considered
- **Trade-offs**: If something was sacrificed
- **Rationale**: If not obvious
- **Implications**: If future impact

### Constraints
- **What**: Always
- **Discovery**: Always
- **Why Non-Obvious**: If unexpected
- **Workaround**: If found
- **Impact**: Always
- **Testing**: If validated

### Patterns
- **When**: Always
- **Approach**: Always
- **Why**: If not obvious
- **Benefit**: Always
- **Anti-pattern**: If relevant
- **Occurrences**: If seen before

---

## Selection Guide

```
Is it < 30 min work?
├─ Yes → Minimal template
│         (Request, Overview, Implementation, Audit)
└─ No
   │
   Did you make strategic decisions?
   ├─ Yes → Standard or Full
   │        (Add Decisions section)
   └─ No → Minimal
   │
   Did you discover constraints/blockers?
   ├─ Yes → Full template
   │        (Add Constraints section)
   └─ Continue
   │
   Did reusable patterns emerge?
   ├─ Yes → Full template
   │        (Add Patterns section)
   └─ Standard template
```

---

## Real Examples

### Minimal Example
```markdown
# Fix Qdrant Connection Timeout

## Request
> "Qdrant client times out after 5 seconds"

## Overview
Increased default timeout from 5s to 30s to handle large embedding operations.

## Implementation
Changed `QdrantClient(timeout=30)` in `src/database/client.py`

## Audit
- `src/database/client.py` - Increased timeout parameter

**Duration**: 10 minutes
```

---

### Standard Example
```markdown
# Add Semantic Search Reranking

## Request
> "Search results not relevant enough, need better ranking"

## Overview
Implemented cross-encoder reranking after initial vector search.
Uses sentence-transformers/ms-marco-MiniLM-L-6-v2 to rescore top 20
results, returning top 5 with highest relevance.

## Decisions

### Cross-Encoder After Vector Search
- **Context**: Vector similarity alone gives false positives
- **Solution**: Two-stage retrieval: vector search → cross-encoder rerank
- **Alternatives**: Better embedding model (rejected - diminishing returns),
  Keyword + vector hybrid (rejected - complexity)
- **Rationale**: Cross-encoders excel at relevance scoring

## Implementation

### Reranking Pipeline
```python
def search_with_rerank(query: str) -> List[Result]:
    # Stage 1: Vector similarity
    candidates = qdrant.search(query, limit=20)

    # Stage 2: Cross-encoder reranking
    scores = cross_encoder.predict([(query, c.text) for c in candidates])
    reranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)

    return [c for c, _ in reranked[:5]]
```

## Audit
- `src/search/reranker.py` - Cross-encoder reranking logic
- `requirements.txt` - Added sentence-transformers

**Duration**: 2 hours
**Success Metrics**: Relevance improved from 60% to 85% in test queries
```

---

### Full Example
```markdown
# Implement Section-Level Chunking with LlamaIndex

## Request
> "Search returns entire changelogs. Need section-level precision."

## Overview
Implemented section-level chunking using LlamaIndex MarkdownNodeParser.
Changelogs now parsed into sections (Decisions, Constraints, Patterns)
with each stored as separate vector. Enables surgical retrieval while
maintaining ability to reconstruct full context via parent/sibling links.

## Decisions

### LlamaIndex Parser vs Custom Parser
- **Context**: Need reliable markdown parsing with hierarchy
- **Solution**: Use LlamaIndex MarkdownNodeParser
- **Alternatives**: Roll custom parser (rejected - reinventing wheel)
- **Trade-offs**: New dependency vs proven solution
- **Rationale**: Markdown parsing has edge cases, use battle-tested lib
- **Implications**: Easier to maintain, integrates with LlamaIndex ecosystem

### Section Type Detection from Headers
- **Context**: Need to classify sections automatically
- **Solution**: Map `## Decisions` → `section_type="decision"` at parse time
- **Alternatives**: Explicit IDs in frontmatter (rejected - duplication)
- **Rationale**: Structure itself provides metadata

## Constraints

### LlamaIndex Requires H1/H2/H3 Hierarchy
- **What**: Parser expects H1 title, H2 sections, H3 items
- **Discovery**: Initial template used H2 title, broke parent-child links
- **Why Non-Obvious**: Not mentioned in docs, found through testing
- **Workaround**: Updated template to use correct header levels
- **Impact**: All existing changelogs need migration
- **Testing**: Verified with 10 sample changelogs, hierarchy correct

## Implementation

### Section Parser Integration
```python
from llama_index import MarkdownNodeParser

parser = MarkdownNodeParser()
nodes = parser.get_nodes_from_document(changelog_content)

for node in nodes:
    section_type = extract_type(node.metadata['header_path'])

    qdrant.upsert({
        'vector': e5_encoder.encode(node.text),
        'payload': {
            'content': node.text,
            'section_type': section_type,
            'parent_id': node.parent_node_id,
            'file_path': changelog_path
        }
    })
```

## Audit

### Created
- `src/parsing/section_parser.py` - LlamaIndex integration
- `src/models/section.py` - Section metadata models

### Modified
- `src/ingestion/ingest.py` - Updated to use section parser
- `docs/11_changelog-template-v3-final.md` - Fixed header hierarchy

### Configuration
- `requirements.txt` - Added llama-index-core==0.10.0

**Files Referenced**: docs/05_llamaindex-integration-guide.md
**Tools Used**: Read, Write, Grep, Bash

## Patterns

### Structure-as-Metadata Pattern
- **When**: AI generates docs from templates you control
- **Approach**: Encode metadata in structure rather than explicit fields
- **Why**: Eliminates duplication, enforces consistency
- **Benefit**: Parsing becomes trivial, zero errors
- **Anti-pattern**: Duplicating structure info in frontmatter and body
- **Occurrences**: This project (changelogs), similar pattern in PRP templates

## Replication

1. Install LlamaIndex: `pip install llama-index-core`
2. Create MarkdownNodeParser instance
3. Pass changelog content to `get_nodes_from_document()`
4. Iterate nodes, extract section_type from header_path
5. Encode each node text with existing E5 encoder
6. Store in Qdrant with enhanced metadata (section_type, parent_id)
7. Update search to filter by section_type
8. Add context reconstruction by following parent_id links

**Notes**: Ensure changelogs use H1 title, H2 sections, H3 items hierarchy
**Duration**: 4 hours (research + implementation + testing)
**Success Metrics**: Section-level search works, returns specific sections not full docs
```

---

## Key Principles

1. **Start minimal, expand as needed**
   - Begin with Request + Overview + Implementation
   - Add sections only when they provide value

2. **Fields are guidelines, not rules**
   - Use all 6 decision fields for complex choices
   - Use 3 decision fields for simple choices
   - Both are valid

3. **Complexity follows work, not template**
   - Simple work = simple changelog
   - Complex work = detailed changelog
   - Template adapts to reality

4. **Information density over completeness**
   - Better to have 3 well-documented decisions
   - Than 10 poorly documented ones

---

## TL;DR

**Three templates, one structure:**
- **Minimal**: Core sections only (< 30 min work)
- **Standard**: Add Decisions (30min - 2hr work)
- **Full**: Add Constraints + Patterns (complex work)

**All share same structure. All parse the same way. Different depth.**

Lean when simple. Complete when complex.
