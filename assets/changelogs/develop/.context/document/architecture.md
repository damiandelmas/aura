# Changelog Template Architecture

## Purpose

Transform development sessions into searchable institutional memory optimized for RAG retrieval with section-level precision.

## Core Design

### Three-Tier System

```
examples/    → Real changelogs (ground truth, 44-171 lines)
template/    → Template + field guide + spectrum
document/    → Architecture and methodology
```

### Template Philosophy

**v3_adaptive** - Single template with progressive disclosure:
- Sections appear only when valuable
- Fields vary naturally (2-6 per item)
- Structure adapts to work complexity

## Hierarchical Structure

```
H1: Changelog Title
├── H2: Request
├── H2: Overview (language-agnostic narrative)
├── H2: Decisions
│   ├── H3: Decision 1
│   └── H3: Decision 2
├── H2: Constraints
│   └── H3: Constraint 1
├── H2: Failures
│   └── H3: Failed Approach 1
├── H2: Implementation
│   ├── H3: Architecture
│   └── H3: Code Signatures
├── H2: Patterns
│   └── H3: Pattern 1
└── H2: Audit
```

## Section Types

| Section | Purpose | Always/Optional | Fields |
|---------|---------|----------------|--------|
| Request | Original user quote | Always | 1 |
| Overview | Language-agnostic story | Always | Narrative |
| Decisions | Strategic choices | Optional | 2-6 |
| Constraints | Discovered limitations | Optional | 4-6 |
| Failures | Failed approaches | Optional | 3-7 |
| Implementation | Technical details | Optional | Variable |
| Patterns | Reusable insights | Optional | 4-7 |
| Audit | File operations | Always | Lists |

## Key Principles

### 1. Language-Agnostic Overview
```
❌ "Fixed React hooks violation in useAnimatedText"
✅ "Fixed framework execution order violation in animation function"
```

Concepts transfer across stacks. Syntax does not.

### 2. Code Signatures
```
❌ 100 lines of complete implementation
✅ 10 lines showing key pattern/configuration
```

Show shape, not exhaustive detail. Full code lives in actual files.

### 3. Progressive Disclosure
```
Simple work:  Request + Overview + 1 Decision (2 fields) + Audit = 44 lines
Complex work: All sections + multiple items + 5-6 fields = 171 lines
```

Template adapts to complexity naturally.

### 4. Field Flexibility

Within same changelog:
- Decision 1: 2 fields (simple)
- Decision 2: 5 fields (complex)
- Decision 3: 3 fields (standard)

Use fields that add value. Skip redundancy.

## RAG Optimization

### LlamaIndex Integration

**Node Structure:**
- H1 → Document root node
- H2 → Section parent nodes
- H3 → Individual item nodes (searchable units)

**Each H3 becomes one vector:**
```python
Node {
  text: "### Use Port 6334\n- **Context**: ...\n- **Solution**: ...",
  metadata: {
    section_type: "decision",
    header_path: "Decisions > Use Port 6334",
    parent_node_id: "decisions_section",
    file_path: "250927-vercel-deployment.md"
  }
}
```

### Metadata Auto-Detection

**From structure (no duplication):**
- Section type from H2 parent: `## Decisions` → `section_type: "decision"`
- Section ID from H3 header: `### Use Port 6334` → `section_id: "use-port-6334"`
- Category/subtype from frontmatter: `type: "implementation.security"` → splits into `category` + `subtype`

**From frontmatter:**
- `timestamp`, `status`, `keywords`

### Query Patterns Enabled

```python
# All decisions across corpus
filter={'section_type': 'decision'}

# All implementation work
filter={'category': 'implementation'}

# Specific decision
filter={'section_id': 'use-port-6334'}

# Context reconstruction
node → parent (Decisions section) → root (Full changelog)
```

## Complexity Spectrum

| Lines | Type | Sections | Use When |
|-------|------|----------|----------|
| 44 | Minimal | D, I, A | Bug fixes, config changes |
| 58-77 | Simple | D, I, P, A | Small features, UI work |
| 114-128 | Standard | D, C, I, A | Typical features |
| 150-171 | Complex | D, C, F, I, P, A | Major features, refactors |

**Legend:** D=Decisions, C=Constraints, F=Failures, I=Implementation, P=Patterns, A=Audit

## Storage Integration

### IMEM Directory Structure
```
.develop/.changes/     → Changelogs using this template
.develop/.modules/     → Proven patterns (100% real)
.document/            → Current stable documentation
```

### Vector Database
- Collection: One per project (git repo boundary)
- Vectors: One per H3 item (section-level granularity)
- Model: E5-Large-v2 (1024 dimensions)
- Metadata: Rich filtering + context reconstruction

## Validation

**Template is valid when:**
- H1 > H2 > H3 hierarchy maintained
- Request + Overview + Audit always present
- Optional sections used only when valuable
- Fields vary naturally (2-6 per item)
- Overview is language-agnostic
- Code signatures show patterns, not full implementations

**Validated against:** 9 real examples (44-171 lines)

## Philosophy

**Code is ephemeral. Patterns are eternal.**

Changelogs capture what survives rewrites:
- WHY decisions were made (not HOW they were coded)
- WHAT constraints exist (not implementation details)
- WHICH approaches failed (not complete error traces)
- WHEN to apply patterns (not exhaustive tutorials)

Future AI agents can read code. They need the context code cannot provide.
