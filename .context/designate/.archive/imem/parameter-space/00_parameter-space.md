# Complete Parameter Space

## Per-Chunk Vector + Base Metadata

- **id**: UUID
- **score**: float (0-1, semantic similarity from search)
- **embedding**: 768-dim vector (nomic-embed-text-v1.5)

## Template Metadata (Structure/Type System)

- **section_type**: string — H2 parent: "Decisions", "Patterns", "Failures", etc.
- **section_name**: string — H3 title: "Use JWT Auth", "Retry Pattern", etc.
- **section_level**: int — 2=H2, 3=H3
- **header_path**: string — Full breadcrumb: "/Title/Section/Subsection/"
- **content**: string — Full chunk text with structured fields

## Frontmatter (Document Properties)

- **category**: string — "implementation", "architecture", "bug-fix", etc.
- **subtype**: string — "security-guardrails", "cli-cleanup", etc.
- **timestamp**: ISO8601 — "2025-10-28T23:00:00-0700"
- **session_id**: UUID — Link to originating conversation
- **schema_version**: string — "v1.0", "v3_adaptive", etc.

## Source Context

- **source**: string — "context" or "conversation"
- **phase**: string — "develop", "design", "document", "designate"
- **layer**: string — "implementation" or "pattern" (develop only)
- **file_path**: string — Absolute path to source file

## Structural Completeness Flags

- **has_context**: bool
- **has_solution**: bool
- **has_rationale**: bool
- **has_alternatives**: bool
- **has_approach**: bool
- **has_benefits**: bool
- **has_drawbacks**: bool

## Quantitative Metrics

- **word_count**: int
- **char_count**: int

## Conversation-Specific (source="conversation" only)

- **start_time**: ISO8601
- **duration_minutes**: int
- **message_count**: int
- **has_changelog**: bool
- **changelog_path**: string
- **chunk_type**: string — "message" or "patch"
- **role**: string — "USER" or "ASSISTANT" (messages only)

## Runtime Computed (from compose enrichment)

- **temporal_position**: string — "current_thrust", "superseded", "evolved", "failed_branch"
- **confidence**: object
  - **has_rationale**: bool
  - **has_alternatives**: bool
  - **semantic_score**: float
  - **continuation_count**: int — How many temporal chunks follow this

## Discovery Enrichment (from primitives)

- **siblings**: List[Chunk] — Related sections from same document
- **genealogy**: List[Chunk] — Conversation chunks via session_id
- **temporal**: List[Chunk] — Semantically similar chunks before/after
- **authority_score**: int — (stub) len(siblings) + len(genealogy)

---

**Total**: ~35 distinct parameters per chunk when fully enriched.
