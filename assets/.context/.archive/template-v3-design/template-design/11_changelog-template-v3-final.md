# IMEM Changelog Template v3.0 - Context-Engineered for AI Retrieval

## Design Philosophy

Inspired by context engineering principles: **"Context is King. Structure enables retrieval. Simplicity beats complexity."**

This template is optimized for:
1. **AI Agent Creation** - Claude writes these perfectly every time
2. **Section-Level Chunking** - LlamaIndex parses effortlessly
3. **Vector Retrieval** - Qdrant finds exactly what's needed
4. **Human Readability** - Developers can read as natural documents

---

## Core Template Principles

### 1. Information Density
- Use keywords from actual work (file paths, technical terms, tool names)
- Avoid generic descriptions - be specific and concrete
- Include context that can't be derived from code alone

### 2. Hierarchical Structure
- `##` headers define semantic section types (auto-parsed)
- `###` headers create retrievable sub-items
- Consistent field structure within sections enables extraction

### 3. Validation Through Template
- Template structure IS the validation
- If Claude follows template, parsing always succeeds
- No separate validation needed - structure guarantees correctness

### 4. Progressive Disclosure
- Start with high-level overview
- Progress to specific decisions and constraints
- End with actionable replication guide

---

## The Template

```markdown
---
schema_version: "v3_section_chunking"
timestamp: "$(TZ=America/Los_Angeles date '+%Y-%m-%dT%H:%M:%S%z')"
type: "implementation"  # implementation | analysis | architecture | bug-fix
status: "completed"     # completed | partial | draft | reverted
scope: "feature"        # feature | refactor | bug-fix | integration | architecture
chu_keywords: "[6-9 dense technical terms from actual work]"
---

# [Session Title - Auto-Generated from Conversation]

## Request
> "[Exact user request that triggered this work]"

[Optional: Brief additional context if request alone isn't clear]

## Overview
[2-3 paragraph narrative covering:
- What problem was solved
- Key breakthroughs achieved
- Overall approach taken
- Final outcome]

## Decisions
[Strategic choices made during implementation]

### [Decision Title - Specific and Concrete]
- **Context**: Why this decision was needed
- **Solution**: What we chose to do
- **Alternatives**: What else we considered (and why rejected)
- **Trade-offs**: What we accepted/gave up
- **Rationale**: Why this approach works
- **Implications**: Future considerations or when to revisit

### [Another Decision]
[Repeat same structure]

## Constraints
[Discovered limitations, blockers, and workarounds]

### [Constraint Title - Specific Technical Limitation]
- **What**: The limitation discovered
- **Discovery**: How/when we found it (context)
- **Why Non-Obvious**: Why this wasn't documented/expected
- **Workaround**: How we handle it
- **Impact**: What this affects going forward
- **Testing**: How we validated the workaround

### [Another Constraint]
[Repeat same structure]

## Implementation
[Technical details, architecture, code examples]

### [Component/Feature Name]
[Explanation of approach and architecture]

```language
[Relevant code snippets - actual working code]
```

[Additional technical context]

### [Another Component]
[Repeat pattern as needed]

## Audit
[Comprehensive record of all file operations and changes]

### Created/Modified
- `path/to/file.ts` - Purpose and functionality
- `path/to/another.js` - What it does

### Configuration
- `config.json` - Settings changed
- `.env` - Variables added

### Operations
- Build/test results
- Deployment steps taken
- Validation performed

**Files Referenced**: [Any files read or consulted during work]
**Tools Used**: [Claude Code features, CLI commands, MCP tools]

## Patterns
[Reusable insights, lessons learned, anti-patterns discovered]

### [Pattern Title - Reusable Solution]
- **When**: Situation/trigger where this applies
- **Approach**: The solution/technique
- **Why**: Business/technical rationale
- **Benefit**: What you gain by using this
- **Anti-pattern**: What NOT to do (common mistakes)
- **Occurrences**: Where else we've seen/used this

### [Another Pattern]
[Repeat same structure]

## Replication
[Step-by-step guide for applying these learnings to similar work]

1. [First step with specific context]
2. [Second step with important considerations]
3. [Continue with concrete, actionable steps...]

**Notes**: [Important considerations, gotchas, or prerequisites]
**Duration**: [Approximate time spent on this work]
**Success Metrics**: [What validated this worked correctly]
```

---

## Section Type Semantics (Auto-Extracted)

| Section Header | `section_type` | Purpose | Queryable For |
|----------------|----------------|---------|---------------|
| `## Request` | `request` | Original problem statement | Understanding initial ask |
| `## Overview` | `overview` | High-level narrative | Quick context |
| `## Decisions` | `decision` | Strategic choices | Why we chose X over Y |
| `## Constraints` | `constraint` | Discovered limitations | Blockers and workarounds |
| `## Implementation` | `implementation` | Technical details | How it was built |
| `## Audit` | `audit` | File operations | What changed |
| `## Patterns` | `pattern` | Reusable insights | Lessons learned |
| `## Replication` | `replication` | How-to guide | Applying to similar work |

---

## Field Structure Within Sections

Each section type has consistent field structure that enables extraction:

### Decision Fields (Always Present)
```yaml
- Context: [Why needed]
- Solution: [What chosen]
- Alternatives: [Options considered]
- Trade-offs: [What given up]
- Rationale: [Why this works]
- Implications: [Future considerations]
```

### Constraint Fields (Always Present)
```yaml
- What: [The limitation]
- Discovery: [How/when found]
- Why Non-Obvious: [Why unexpected]
- Workaround: [How handled]
- Impact: [What affected]
- Testing: [Validation]
```

### Pattern Fields (Always Present)
```yaml
- When: [Trigger/situation]
- Approach: [The solution]
- Why: [Rationale]
- Benefit: [Value gained]
- Anti-pattern: [What NOT to do]
- Occurrences: [Where seen]
```

---

## LlamaIndex Parsing Benefits

### Automatic Metadata Extraction
```python
# LlamaIndex automatically provides:
node = {
  'text': "## Decisions\n\n### Use File-Based Retrieval...",
  'metadata': {
    'header_path': "Decisions > Use File-Based Retrieval",
    'node_type': 'h3',
    'parent_node_id': 'decisions_section',
    'prev_node_id': None,
    'next_node_id': 'decision_2_id'
  }
}

# We enhance with:
enhanced_metadata = {
  'section_type': 'decision',  # extracted from header
  'fields': {  # extracted from bold markers
    'Context': '...',
    'Solution': '...',
    'Alternatives': '...'
  }
}
```

### Hierarchical Relationships (Built-In)
- Parent-child: `## Decisions` → `### Decision 1`
- Siblings: `### Decision 1` ↔ `### Decision 2`
- Document root: All sections link back to parent changelog

### Context Reconstruction
```python
# Get single decision
result = search("bash output handling", type="decision")

# Expand context on demand
full_section = get_parent(result.node_id)  # All decisions
full_document = get_root(result.node_id)   # Entire changelog
```

---

## Information Density Guidelines

### ✅ Dense, Specific, Concrete
```markdown
## Constraints

### Bash Tool 30K Character Output Limit
- **What**: Bash tool truncates at 30,000 characters hard limit
- **Discovery**: Attempted retrieval of 3,143 line conversation (712KB), output truncated with "...+2943 lines" message
- **Why Non-Obvious**: Claude Code documentation doesn't mention this limit, only discovered through testing with large files
- **Workaround**: Use file-based retrieval pattern: write to temp file via bash, then use Read tool to load full content
- **Impact**: All operations expecting large output (>30K chars) must use intermediate file pattern
- **Testing**: Verified with 700KB+ files, Read tool handles without truncation
```

### ❌ Generic, Vague, Unusable
```markdown
## Constraints

### Output Limitation
- **What**: Tool has limits
- **Discovery**: Found during testing
- **Workaround**: Use different approach
- **Impact**: Affects some operations
```

The first example is **information-dense** - AI can retrieve and understand exact context, reproduce the workaround, and avoid the same issue.

---

## Anti-Patterns to Avoid

### ❌ Don't Skip Section Types
```markdown
# BAD - Missing Constraints section
## Decisions
[decisions]

## Implementation
[implementation]

# GOOD - All relevant section types present
## Decisions
[decisions]

## Constraints
[constraints discovered during implementation]

## Implementation
[implementation]
```

### ❌ Don't Use Vague Descriptions
```markdown
# BAD - Generic, unhelpful
### Port Configuration
- **Context**: Needed to configure port
- **Solution**: Changed the port

# GOOD - Specific, actionable
### Port 6334 Standardization for Qdrant
- **Context**: Port 6333 conflicted with internal MongoDB instance on dev machines
- **Solution**: Changed docker-compose.yml to use port 6334 for Qdrant
- **Alternatives**: Use dynamic port allocation (rejected - hard to remember), Use non-standard port 9333 (rejected - outside common ranges)
- **Trade-offs**: All existing projects need update, documentation references need changing
- **Rationale**: 6334 is adjacent to 6333 (Qdrant default), easy to remember, no known conflicts
```

### ❌ Don't Duplicate Code in Changelog
```markdown
# BAD - Entire file contents pasted
## Implementation
### Database Schema
[Paste 500 lines of schema code]

# GOOD - Key patterns with reference
## Implementation
### Database Schema
Created type-safe Pydantic models for all entities:

```python
class MemoryDocument(BaseModel):
    content: str
    metadata: DocumentMetadata
    embedding: List[float]

    class Config:
        # CRITICAL: Qdrant requires dict serialization
        arbitrary_types_allowed = True
```

Key patterns:
- Pydantic v2 models for type safety
- Nested metadata structure for rich filtering
- 1024-dim embeddings for E5-Large-v2

**Files**: `src/models/document.py` (full implementation)
```

---

## Why This Template Works for AI Retrieval

### 1. Semantic Headers → Automatic Typing
`## Decisions` = all children are type `decision`
`## Constraints` = all children are type `constraint`

No explicit IDs needed - structure provides typing.

### 2. Consistent Fields → Reliable Extraction
Every decision has same 6 fields.
Every constraint has same 6 fields.
Parser knows exactly what to expect.

### 3. Information Density → Better Embeddings
Specific technical terms → better vector similarity.
Concrete examples → better semantic matching.
Real file paths → exact context retrieval.

### 4. Progressive Disclosure → Context Reconstruction
- Search returns specific section (surgical precision)
- Can retrieve parent section (more context)
- Can retrieve full document (complete narrative)
- Can traverse siblings (related items)

### 5. Template Enforcement → Zero Parsing Failures
Claude receives template in system prompt.
Claude follows template structure perfectly.
Parser has guaranteed structure to work with.
No fuzzy parsing, no error handling needed.

---

## Comparison to Generic Documentation

### Typical Project Documentation
```markdown
# Project Overview
This is a vector database system for institutional memory...

## Features
- Search functionality
- Vector embeddings
- Document storage

## Usage
Install and run the system...
```

**Problem**: Generic, no specific context, hard to retrieve meaningful information.

### IMEM Changelog (This Template)
```markdown
## Constraints

### Qdrant Collection Creation Requires Explicit Vector Size
- **What**: create_collection() fails with cryptic error if vector size not specified in init
- **Discovery**: 2025-09-15, attempted auto-detection of size from first insert, Qdrant returned "Vector dimension mismatch"
- **Why Non-Obvious**: Other vector DBs (Pinecone, Weaviate) auto-detect from first insert, expected same behavior
- **Workaround**: Always specify vectors_config with explicit size=1024 for E5-Large-v2 at collection creation
- **Impact**: Collection creation code must know embedding model dimensions upfront
- **Testing**: Verified with E5-Large-v2 (1024), tested error with wrong size (384)
```

**Benefit**: Specific, actionable, searchable, prevents repeating same mistake.

---

## Success Criteria for Template Usage

### For Claude (Writing Changelogs)
- [ ] Template structure is clear and unambiguous
- [ ] All section types are present when relevant
- [ ] Information is dense and specific (file paths, error messages, numbers)
- [ ] Fields within sections are consistently filled
- [ ] Code examples are minimal but representative
- [ ] No placeholder or generic content

### For LlamaIndex (Parsing)
- [ ] Clear hierarchical structure (`##` and `###` headers)
- [ ] Consistent section naming for type extraction
- [ ] Parent-child relationships obvious from nesting
- [ ] No ambiguous structure (missing headers, weird nesting)

### For Qdrant (Storage & Retrieval)
- [ ] Rich metadata from section type and fields
- [ ] Semantic content for good embeddings
- [ ] Technical keywords for filtering
- [ ] Enough context in each section to stand alone

### For Humans (Readability)
- [ ] Reads like a narrative, not a form
- [ ] Progressive disclosure (overview → details)
- [ ] Scannable structure with clear headers
- [ ] Code examples are helpful, not overwhelming

---

## Template Evolution

### Current Version: v3_section_chunking
- Optimized for section-level retrieval
- LlamaIndex-compatible structure
- Information-dense field formatting
- Semantic section types

### Migration from v2
- Add explicit `## Constraints` section
- Add explicit `## Patterns` section
- Ensure consistent field structure within sections
- Add `schema_version` to frontmatter

### Future Considerations
- Could add `## Failures` section for explicitly documented failures
- Could add `## Dependencies` section for cross-changelog references
- Could add `## Timeline` section for multi-session work
- Template should remain lean - only add if clear retrieval benefit

---

## TL;DR

**This template is designed for machines to parse and humans to read.**

✅ **Semantic structure** = automatic section typing
✅ **Consistent fields** = reliable extraction
✅ **Information density** = better retrieval
✅ **Hierarchical organization** = context reconstruction
✅ **Template enforcement** = zero parsing failures

**Result**: Perfect chunking, surgical retrieval, human readability.
