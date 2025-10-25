---
type: "design"
timestamp: "2025-10-08T10:40:00-0700"
---

# Changelog Template Creation and LlamaIndex Alignment

## Question
> "How should the final template look? Perhaps it needs 1-3 documents? One template and one or two accommodating documents?"

## Key Insights

### Template Package Structure
Created 4-document package for `.develop/.changes/` ground truth changelogs:
1. **00_TEMPLATE.md** - Full template with HTML comments for AI agent guidance + LlamaIndex section
2. **00_TEMPLATE-CLEAN.md** - Pure markdown without comments + LlamaIndex section
3. **01_FIELD_GUIDE.md** - Progressive disclosure reference showing 2-6 field variations
4. **02_EXAMPLE_SPECTRUM.md** - 9 real examples spanning 44-171 lines

### Language-Agnostic Overviews
Critical design decision: Overviews must avoid code-specific terminology
- ❌ "Fixed React hooks violation in useAnimatedText"
- ✅ "Fixed framework execution order violation in animation function"

**Why:** Knowledge transfers across projects, languages, and technology stacks.

### Code Signatures Not Full Implementations
Middle ground between semantic description and complete code:
- Show key patterns, configurations, integration points
- Omit error handling, edge cases
- 10-20 lines vs 100+ lines of complete implementation
- Enough to understand approach, not enough to copy-paste blindly

**Purpose:** RAG retrieval needs concepts and patterns, not full source (that's in the actual files).

### Progressive Disclosure in Practice
Field counts vary naturally within same changelog:
- Simple items: 2-3 fields (Context, Solution)
- Standard items: 3-4 fields (add Alternatives)
- Complex items: 5-6 fields (add Rationale, Trade-offs, Implications)

**Demonstrated across 9 examples:** 44 lines (minimal) to 171 lines (complex) - no gaps in spectrum.

### LlamaIndex MarkdownNodeParser Alignment
Template optimized for hierarchical parsing:
- **h1** (# Title) → Document root node
- **h2** (## Decisions, ## Implementation) → Section parent nodes
- **h3** (### Decision Title) → Individual searchable items

**Node granularity decision:** One node per h3 with all fields combined (not per-field nodes)
**Rationale:** When searching "decisions about X," need complete decision context, not isolated "Solution" field

**Metadata enrichment strategy:**
- MarkdownNodeParser extracts: `header_path`, `node_type`, `parent_node_id`
- Custom additions at index time: `section_type`, `category`, `subtype`, `timestamp`
- Section IDs auto-generated from headers (no manual management)

### HTML Comments Strategy
**Decision:** Keep HTML comments in AI-facing template (00_TEMPLATE.md), remove from clean version (00_TEMPLATE-CLEAN.md)

**Rationale:**
- AI agents benefit from guidance comments
- Comments won't be indexed as content during vector embedding
- Two versions serve different purposes (generation vs indexing)

## Explored Ideas

### Template Granularity Options
**Explored:**
1. Single monolithic template (too rigid)
2. Separate templates per complexity level (too many files)
3. One adaptive template + guidance docs (chosen)

**Why chosen:** Template adapts to work, examples show spectrum, field guide clarifies variation.

### Node Parsing Granularity
**Explored:**
1. One node per h3 (complete decisions, constraints, etc.)
2. One node per field (Context, Solution as separate nodes)
3. Custom split patterns

**Why option 1:** Search queries like "decisions about rate limiting" need full decision context, not isolated fields. Can always extract field-level structure in metadata without splitting nodes.

### Code Snippet Handling
**Explored:**
1. Code Signatures as h4 subsections (creates more nodes)
2. Code Signatures as bold headers in h3 section (single node)
3. Custom code extraction at index time

**Why option 2 (for now):** Code signatures meant to be read together. Future enhancement could add cross-project code snippet detection while maintaining header context.

### Section ID Management
**Explored:**
1. Manual IDs in frontmatter
2. Manual IDs in headers: `### Decision {#DEC-ID}`
3. Auto-generate from header text at parse time

**Why option 3:** Keeps template clean, no manual ID management burden, consistent slug generation from headers.

## Outcomes

### Final Template Package
Located: `/home/axp/projects/mcp-servers/imem/changelogs/03_final-template/`

**Features:**
- Language-agnostic overviews (transferable knowledge)
- Code signatures not implementations (patterns over details)
- Progressive disclosure (2-6 fields naturally)
- LlamaIndex optimized (h1/h2/h3 hierarchy)
- 9 real examples (44-171 lines, full spectrum)

### Query Patterns Enabled
**Section-level retrieval:**
```python
filter={'section_type': 'decision'}      # All decisions
filter={'category': 'implementation'}     # All implementation work
```

**Specific item retrieval:**
```python
filter={'section_id': 'use-official-rate-limiting'}  # Exact decision
```

**Context reconstruction:**
```python
node → parent (Decisions section) → root (Full changelog)
```

### Node Density Examples
**Minimal changelog (44 lines):** ~6 nodes
- Precise, surgical retrieval
- 1 root + 3 sections + 1 decision + 1 code signature

**Complex changelog (171 lines):** ~25 nodes
- Granular search, full context reconstruction
- 1 root + 5 sections + 4 decisions + constraints + patterns + implementation

### Integration with IMEM System
This template package becomes the foundation for:
1. **ChangelogAgent** - Uses template to generate `.develop/.changes/` ground truth
2. **PULSE** - Reads these changelogs to maintain `.document/` stable docs
3. **IMEM** - Indexes with LlamaIndex MarkdownNodeParser for section-level search
4. **AI Agents** - Read to understand current state (static docs + recent changelogs)

**Position in architecture:** Template powers the ground truth layer (`.develop/.changes/`) of the three-tier memory system (`.design/` → `.develop/` → `.document/`).

## References

### Design Documents
- `/home/axp/projects/mcp-servers/imem/.design/template-llama-index/.snapshot/02_evals/` - 9 refined examples
- `/home/axp/projects/mcp-servers/imem/changelogs/.design/template-design/05_llamaindex-integration-guide.md` - LlamaIndex strategy
- `/home/axp/projects/aura-retrieval-qdrant/aura/projects/imem-suite/main/.design/.modules/complete-system/` - IMEM architecture

### Key Decisions From Conversation
1. Remove 40% fluff from changelogs (business impact, future ideas, redundant sections)
2. Code Signatures pattern (show shape not implementation)
3. Language-agnostic Overview principle
4. Progressive disclosure (field variation within sections)
5. LlamaIndex node granularity (h3 = one node with all fields)
6. Section ID auto-generation (no manual management)
7. HTML comments acceptable in AI-facing template

### Example Reduction
Original changelogs averaged 200-220 lines with 40-70% noise.
Refined examples: 44-171 lines with 0% fluff, pure technical value.

Average reduction: 40% smaller while preserving all insights.

### Type Taxonomy
Dot notation with bounded categories, freeform subtypes:
- `implementation.security-guardrails`
- `bug-fix.timeout-handling`
- `refactor.api-simplification`

Parser auto-extracts `category` and `subtype` for flexible querying.

## Next Steps

1. **ChangelogAgent implementation** - Use template package to generate changelogs via `/log:develop`
2. **LlamaIndex parser integration** - Implement MarkdownNodeParser in IMEM ingestion
3. **Section-type detection** - Add logic to identify decision/constraint/failure/pattern from parent headers
4. **Test with real changelogs** - Validate parsing and search quality
5. **Future enhancement** - Code snippet detection across entire document space with contextualization
