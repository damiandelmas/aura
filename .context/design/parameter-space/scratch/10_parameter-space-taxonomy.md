# Parameter Space Taxonomy

## Foundation Layer (Immutable, Indexed)

**What's created and queryable:**

### Identity
- `id`, `source`, `phase`, `layer`, `file_path`

### Type System (Template)
- `section_type`, `section_name`, `section_level`, `schema_version`

### Document Context (Frontmatter)
- `category`, `subtype`, `timestamp`, `session_id`, `keywords`, `status`

### Vector Space
- `embedding`, `content`

---

## Traversal Predicates (Implicit Edges)

**Indexed metadata that enables graph navigation:**

### Sibling Traversal
- `file_path` → chunks from same document

### Genealogical Traversal
- `session_id` → conversation origin

### Temporal Traversal
- `timestamp` + `semantic_similarity` → evolution chains

### Type Traversal
- `section_type` + `category`/`subtype` → domain clustering

**These ARE the graph. Query them to traverse.**

---

## Structural Signals (Detected, Not Validated)

**Fields that exist but don't indicate truth:**

- `has_context`, `has_solution`, `has_rationale`, `has_alternatives`
- `word_count`, `char_count`

**What they mean:** AI filled template fields. Not validation signals.

---

## Runtime Computed (Ephemeral Graph Metrics)

**Derived from k-result subgraph:**

### Topology Metrics
- `pagerank`, `betweenness`, `degree_centrality`
- `continuation_count` (outgoing temporal edges)
- `isolation_score` (sparse connectivity)

### Validation Signals
- `user_authority` (genealogy → user message similarity)
- `implementation_exists` (siblings contain code)
- `supersession_probability` (forward temporal edges)

### Confidence Composite
- Weighted combination of validation signals

---

## Assembly Directives (What to Gather + How to Present)

**Query-specific context gathering:**

### For "Current State"
- Decision + Latest temporal + Implementation code + No supersessions

### For "Decision Origin"
- Decision + User messages (genealogy) + Alternatives (siblings) + Rationale

### For "Evolution Trace"
- Temporal chain + User feedback at each step + Failed attempts

### For "Full Story"
- User request → Failures → Final decision → Implementation → Validation

---

## The Flow

```
Template + Frontmatter
    ↓
Indexed metadata (Foundation)
    ↓
Semantic search → k results
    ↓
Query metadata predicates (Traverse implicit graph)
    ↓
Materialize subgraph (k nodes, k² edges)
    ↓
Compute topology metrics (Runtime)
    ↓
Gather related chunks per assembly directive
    ↓
Render in template (Graph-aware serving)
```

**Foundation → Traversal → Computation → Assembly**

*Everything exploits what's already there.*
