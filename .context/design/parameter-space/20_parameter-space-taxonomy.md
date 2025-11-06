---
session_id: "034ba596-240e-4bc3-b71a-2194dafd9656"
---

# Parameter Space Taxonomy

**Per-chunk metadata dimensions in IMEM vector store**

**Context:** Current implementation. Template structure (H2/H3) provides type system. Frontmatter provides semantic context.

**CORE dimensions:** Proposed enhancement. Would make typing explicit and universal. See [00_NAMESPACE.md](../00_NAMESPACE.md).

**Both approaches:** Rich metadata at index, enabling type-safe semantic search.

**References:** [document-properties.md](../architecture-i2/database/document-properties.md), [type-system.md](../architecture-i2/database/type-system.md)

---

## Identity & Source

**Immutable identifiers:**

- `id` — UUID
- `file_path` — Absolute path to source file
- `source` — "context" | "conversation"

---

## Vector Space

**Semantic representation:**

- `embedding` — 768-dim vector (nomic-embed-text-v1.5)
- `score` — float (0-1, similarity from search query)
- `content` — Full chunk text with structured fields

---

## Type System (Template Structure)

**Detected from H2/H3 markdown hierarchy:**

- `section_type` — H2 parent: "Decision" | "Pattern" | "Failure" | "Constraint" | "Implementation" | "Request" | "Overview" | "Audit"
- `section_name` — H3 title (for collection types) or H2 title (for singleton types)
- `section_level` — int (2=H2, 3=H3)
- `header_path` — Full breadcrumb: "/Title/Section/Subsection/"

**The template IS the type system.** Each H2 declares a type with required/optional fields.

---

## Document Properties (Frontmatter)

**Inherited by all chunks from document frontmatter:**

- `schema_version` — "v3_adaptive" | etc.
- `type` — Freeform "category.subtype" (resolved at write-time)
- `category` — Resolved from type field
- `subtype` — Resolved from type field
- `keywords` — Space-separated natural language terms
- `status` — "completed" | "in-progress" | "archived" | "reverted"
- `timestamp` — ISO8601 creation time
- `session_id` — UUID linking to originating conversation

**Dual metadata:** Template provides structural types, frontmatter provides semantic context.

---

## Phase & Layer (Develop Logs Only)

**Content classification:**

- `phase` — "develop" | "design" | "document" | "designate"
- `layer` — "implementation" | "pattern" (develop phase only)

---

## Structural Completeness Flags

**Template fields detected (presence, not quality):**

Type-specific required fields:
- Decision: `has_context`, `has_solution`
- Pattern: `has_pattern`, `has_when`, `has_approach`, `has_benefit`
- Failure: `has_attempted`, `has_why_failed`, `has_lesson`
- Constraint: `has_what`, `has_discovery`, `has_workaround`, `has_impact`

Optional fields (when present):
- `has_rationale`, `has_alternatives`, `has_trade_offs`, `has_implications`

**Note:** These indicate field presence, not validation of content quality.

---

## Quantitative Metrics

**Computed from content:**

- `word_count` — int
- `char_count` — int

---

## Conversation-Specific (source="conversation" only)

**Additional parameters for conversation chunks:**

- `start_time` — ISO8601
- `duration_minutes` — int
- `message_count` — int
- `has_changelog` — bool
- `changelog_path` — string (if changelog was generated)
- `chunk_type` — "message" | "patch"
- `role` — "USER" | "ASSISTANT" (messages only)

---

## Graph Traversal Predicates (Speculative)

**Indexed metadata that could enable implicit graph edges via FlexGraph:**

- **Genealogical:** `session_id` → Link chunks to conversation origin
- **Temporal:** `timestamp` + semantic similarity → Evolution/supersession chains
- **Type-based:** `section_type` + `category` → Domain clustering
- **File-based:** `file_path` → Co-location relationships

**Status:** Predicates indexed, graph materialization methodology in development. FlexGraph approach: materialize k-subgraph from query results, compute O(k²) edges on-demand rather than precompute O(n²).

---

## Total Dimensions

**~30-35 distinct parameters per chunk** (varies by source type and template instantiation).

**Enables:**
- Type-safe semantic search (`section_type` filtering + vector similarity)
- Genealogical traversal (changelog ↔ conversation via `session_id`)
- Temporal ordering (evolution chains via `timestamp`)
- Progressive type instantiation (not every chunk has every field)
