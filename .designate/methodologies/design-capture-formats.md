# Design Capture Format Catalog

**Comprehensive reference of 10 distinct design document methodologies used in AURA.**

Last Updated: 2025-11-07

---

## Overview

This catalog documents the different formats/methodologies for capturing design thinking, architectural decisions, user intent, and system evolution. Each format serves a different cognitive state and information density requirement.

**Format Categories:**
- **Preservation** (1-2): Raw voice, zero interpretation
- **Scientific** (3, 5): Hypothesis-driven, structured
- **Visual** (4): Diagram-first explanation
- **Conceptual** (6): Idea-driven design
- **Exploration** (7-8): Question-driven analysis
- **Exhaustive** (9): Full context decisions
- **Synthesis** (10): Meta-analysis

---

## FORMAT 1: Quote + Why Pattern

**Purpose:** Distill architectural principles from user messages while preserving authentic voice.

**Ethic:** Maximum density. User's exact words paired with architectural reasoning. Zero interpretation layer.

**Structure:**
```markdown
## Principle Title
**Quote:** "exact user message with typos preserved"
**Why:** Architectural reasoning in one sentence
```

**Key Characteristics:**
- Two-part structure enforces discipline
- Preserves typos for authenticity
- Why statements are architectural, not explanatory
- No interpretation between voice and principle
- Principle per paragraph (ultra-dense)

**Location:** `.claude/.vision/core-user-messages.md`

**Examples:**

### Example 1: Composition Pattern
```markdown
## Composition via markdown slash commands not code wrappers
**Quote:** "the composition will come through composable/iterable markdown files first. IE you use imem well, we capture that 'compsoiton' / 'module' as a slash commmand combination of flags and now its reusable. Rather than locking it in code as a flag or API wrapper."
**Why:** Git-tracked markdown compositions enable iteration without code changes
```

### Example 2: Communication Style
```markdown
## Response style: Spartan technical precision for AI coding
**Quote:** "think about our roles. i only do ai coding. restate concise, no code ideas. technically precise. spratn. extremely concise. think"
**Why:** Dense architectural communication optimized for AI-directed implementation
```

### Example 3: Zero-Loss Memory
```markdown
## Zero-loss memory via flippable chunks (impl/pattern)
**Quote:** "this enables no loss in degredation of memroy — being able to serve unfitted (pattern insight — intellectual capital) whenever superceded whil;e also being able to retrieve full resolution chunk (impl chunk) upon command."
**Why:** Supersession promotes abstraction without deleting implementation - reversible via metadata
```

---

## FORMAT 2: Timestamp + User Message

**Purpose:** Chronological preservation of raw user utterances. Archaeological record.

**Ethic:** Pure preservation. Zero AI interpretation. Raw user voice = ground truth.

**Structure:**
```markdown
## YYMMDD-HHMM
> "exact user message"
```

**Key Characteristics:**
- Timestamp as section header (chronological index)
- Blockquote format preserves source distinction
- Zero commentary, zero interpretation
- Typos preserved (authentic capture)
- Dense messages (multi-idea statements)

**Location:** `.claude/.vision/user-messages.md`

**Examples:**

### Entry 1
```markdown
## 251027-1149
> One thing — the composition will come through composable/iterable markdown files first. IE you use imem well, we capture that 'compsoiton' / 'module' as a slash commmand combination of flags and now its reusable. Rather than locking it in code as a flag or API wrapper.
```

### Entry 2
```markdown
## 251027-1556
> restate questions, no code. im a system architect, not a developer.
```

### Entry 3
```markdown
## 251027-1600
> think about our roles. i only do ai coding. restate concise, no code ideas. technically precise. spratn. extremely concise. think
```

---

## FORMAT 3: Hypothesis + Components + Architecture

**Purpose:** Document methodologies with scientific rigor. Theory before practice.

**Ethic:** Scientific structure. Testable hypothesis → components → architecture → implementations.

**Structure:**
```markdown
## Hypothesis
[Single sentence hypothesis]

## Components
### 1. Component Name
[Description + examples]

### 2. Component Name
[Description]

## Architecture
### Index Time
[Flow diagram]

### Serve Time
[Flow diagram]

## Implementations
**Current:** [What works today]
**Future:** [Planned enhancements]
```

**Key Characteristics:**
- Top-level hypothesis (single sentence)
- Components with concrete examples (YAML, code)
- Architecture shows dataflow (arrows)
- Current vs Future implementations
- Visual flow diagrams (ASCII)
- Scientific rigor (testable)

**Location:** `.designate/methodologies/`

**Example:**
See: `/home/axp/projects/fleet/hangar/code/aura/main/.designate/methodologies/flexschema/overview.md`

**Sample:**
```markdown
## Hypothesis

Pre-defined domain schemas with universal CORE coordinates enable bootstrap and cross-domain pattern transfer.

## Components

### 1. Schema Library
Registry of domain-specific schemas (software, legal, business, research).

Each domain defines types with CORE coordinate signatures:
```yaml
# software_development
Decision: {what: 0.8, why: 0.7, valence: good, epistemic: known}

# legal
Precedent: {what: 0.85, why: 0.75, who: 0.7, temporal: past}
```
```

---

## FORMAT 4: Visual Diagrams + Layer Architecture

**Purpose:** Explain innovations through geometric relationships. Visual-first.

**Ethic:** Show before tell. ASCII diagrams reveal structure. Innovation explained through layers.

**Structure:**
```markdown
[Title]

The missing piece between X and Y:

[ASCII diagram showing layers with arrows]

---
The Specific Innovation

[Component breakdown]

---
Where It Sits in the Stack

[Box diagram with connecting arrows]
```

**Key Characteristics:**
- Visual diagrams first (geometry reveals meaning)
- Layer architecture with ASCII boxes
- "What it does" for each component
- Innovation explicitly isolated
- Stack positioning (context)
- Progression narrative (missing layer → filled)

**Location:** `.designate/.inbox/imem/brain/statements/`

**Example:**
See: `/home/axp/projects/fleet/hangar/code/aura/main/.designate/.inbox/imem/brain/statements/temporal_statement-4.md`

**Sample:**
```markdown
Layer 4: BRAIN Temporal Intelligence (Change Detection)

The missing piece between storage and serving:

Layer 1 (Storage): Chunks with dual content + serving_mode flag
                            ↓
                    [MISSING LAYER]
                            ↓
Layer 3 (Serving): Serve based on flag

You just built the missing layer:

Layer 1 (Storage): Chunks with dual content
                            ↓
Layer 4 (BRAIN): Git-based change detection
    - Detects: Which chunks changed
    - Analyzes: Narrative distance
    - Decides: Supersession tier
    - Marks: Updates metadata
                            ↓
Layer 3 (Serving): Serve based on updated flags
```

---

## FORMAT 5: Vision Alignment Statements

**Purpose:** Map high-level vision to implementation mechanics. Theory meets practice.

**Ethic:** Alignment document. Two perspectives on same system. Economic + architectural reasoning.

**Structure:**
```markdown
# Title

## Mapping the Alignment

### Perspective A
[Flow]

### Perspective B
[Flow]

## Key Accordances

### 1. Principle Name
- Perspective A: [insight]
- Perspective B: [insight]
- Shared insight: [synthesis]

## The Shape Match

[Meta-pattern revelation]

### [System] describes
- **Aspect 1:** [description]
- **Aspect 2:** [description]

### Perspective
[Same system, different angles explanation]
```

**Key Characteristics:**
- Mapping structure (two perspectives aligned)
- Numbered accordances (parallel principles)
- Economic + architectural reasoning
- "Shape Match" reveals meta-pattern
- Perspective section (different angles)
- Dense insight extraction

**Location:** `.designate/.inbox/fleet/vision/`

**Example:**
See: `/home/axp/projects/fleet/hangar/code/aura/main/.designate/.inbox/fleet/vision/statement-2.md`

---

## FORMAT 6: Concept + Properties Pattern

**Purpose:** Lead with the idea, follow with mechanics, end with value. Technical specs.

**Ethic:** Concept-driven. Idea before implementation. Properties explicitly called out.

**Structure:**
```markdown
# Title: Concept Name

**[Pithy summary statement]**

## The Concept

[Workflow/flow diagrams]

## Serving Logic / Properties

**[System] intelligence:**

[Logic description]

**Property:** [Key characteristic]

## Storage Topology

[Diagram or description]

## The Value

**Enables [N] use cases:**

1. [Use case]
2. [Use case]

## Related Concepts

See: [link] - [description]
```

**Key Characteristics:**
- Opening tagline (concept summary)
- "The Concept" first (idea before implementation)
- Workflow diagrams
- Properties called out explicitly
- "The Value" section (why this matters)
- Related concepts with descriptions
- Planned vs current distinction

**Location:** `.designate/.inbox/imem/`

**Example:**
See: `/home/axp/projects/fleet/hangar/code/aura/main/.designate/.inbox/imem/flippable-chunks/flippable-chunks.md`

**Sample:**
```markdown
# Flippable Chunks: Dual-Face Architecture

**Same chunk, two faces.**

## The Concept

Pattern layer created via separate .pattern.md files, not dual storage.

**Pattern extraction workflow:**
```
Write changelog (.md)
    ↓
Single LLM pass (10% cost)
    ↓
Generate .pattern.md (language-agnostic)
    ↓
Both indexed with layer='implementation' or 'pattern'
```

## The Value

**Enables two use cases:**
1. **Decaying memories** - Serve abstractions for old decisions
2. **Cross-project knowledge** - Query patterns without code pollution
```

---

## FORMAT 7: Question + Key Insights Pattern

**Purpose:** Question-driven exploration. Transparent reasoning path from question to decision.

**Ethic:** Discovery process matters. Uncertainty documented. Alternatives visible.

**Structure:**
```markdown
## Question
> "user question"

## Key Insights

### Insight Title
- **Problem:** [description]
- **Discovery:** [what we learned]
- **Solution:** [approach]

### [More insights]

## Explored Ideas

### Option A (Rejected)
[Description + why rejected]

### Option B (Accepted)
[Description + why accepted]

## Outcomes

[Decision + frontmatter examples]
```

**Key Characteristics:**
- User question as primary anchor (quoted)
- Key Insights section (problem/discovery/solution)
- Numbered phases or options
- Code examples (YAML, frontmatter)
- Explored Ideas (rejected vs accepted)
- Transparent reasoning

**Location:** `assets/.context/design/`

**Example:**
See: `/home/axp/projects/fleet/hangar/code/aura/main/assets/.context/design/251011-0145_four-phase-changelog-architecture.md`

---

## FORMAT 8: Central Question + Problem Analysis

**Purpose:** Deep problem decomposition. Educational rigor. Why it's hard → solution.

**Ethic:** Teach the reasoning. Problem breakdown before solution. Multiple evidence types.

**Structure:**
```markdown
# Title

## The Central Question

**[Question]**

The answer: **[Direct answer]**

[Context paragraph]

## The Problem with [X]

### Why [X] Is Hard

#### 1. [Sub-problem]
[Explanation + examples]

#### 2. [Sub-problem]
[Explanation + code/data]

## The Problem with [Y]

[Similar breakdown]

## Our Solution: [Approach]

[Synthesis]
```

**Key Characteristics:**
- Bold central question (clarity)
- Answer given immediately
- Problem decomposition (numbered)
- Concrete examples (JSON, diffs, dialogue)
- "Missing" sections (gap identification)
- Educational tone
- Multiple evidence types
- Statistics (40-60% tool noise)

**Location:** `.context/design/.changes/`

**Example:**
See: `/home/axp/projects/fleet/hangar/code/aura/main/.context/design/.changes/251018-1919_design-rationale-precision-and-completeness.md`

---

## FORMAT 9: Extended Quote + Context + Options + Properties

**Purpose:** Maximum context preservation. Every decision fully justified, all alternatives documented.

**Ethic:** Exhaustive decision record. Quote → Why → Context → Options → Properties. Nothing lost.

**Structure:**
```markdown
## Decision Title
**Quote:** "exact user quote"
**Why:** One-line architectural reasoning

**Context:** [Extended paragraph explaining alternatives and framing]

**Options Considered:**
- A: [Option] - [trade-off]
- B: [Option] - [trade-off]

**Key Properties:**
- [Property 1]
- [Property 2]
- [Property N]
```

**Key Characteristics:**
- Full user quote (typos included)
- Why statement (architectural)
- Context paragraph (alternative framing)
- Options A/B with trade-offs
- Key Properties (bulleted guarantees)
- Anti-patterns called out
- HTML comments for meta-commentary
- Maximum information density

**Location:** `.context/design/.changes/`

**Examples:**

### Example 1: Flippable Chunks
```markdown
## Flippable Chunks for Zero-Loss Memory
**Quote:** "this enables no loss in degredation of memroy — being able to serve unfitted (pattern insight — intellectual capital) whenever superceded whil;e also being able to retrieve full resolution chunk (impl chunk) upon command."
**Why:** Supersession promotes abstraction without deletion—metadata flip enables O(1) serving decision

**Context:** When implementation superseded (JWT → OAuth2), system serves pattern abstraction by default (Stateless Auth Pattern), but original implementation remains indexed and retrievable via --full-resolution flag.

**Key Properties:**
- No deletion (both chunks indexed permanently)
- No re-indexing (supersession = metadata field update)
- Runtime flip (chunk.serving_mode = 'pattern' or 'impl')
- Reversible (force flag retrieves original)
- Archaeological precision available on demand
```

### Example 2: Markdown Slash Commands
```markdown
## Markdown Slash Commands Over Code Wrappers
**Quote:** "the composition will come through composable/iterable markdown files first. IE you use imem well, we capture that 'compsoiton' / 'module' as a slash commmand combination of flags and now its reusable."
**Why:** Git-tracked markdown compositions enable iteration without code changes

**Context:** Alternative to building explain/trace/patterns as code functions. Instead, observe Claude composing CLI primitives, capture proven patterns as markdown slash commands. Enables iteration without code deployment.

**Options Considered:**
- A: Build wrapper functions in Python (explain(), trace()) - rigid, requires code changes
- B: Capture patterns as markdown slash commands - flexible, Git-tracked, user-editable
```

**Full File:**
See: `/home/axp/projects/fleet/hangar/code/aura/main/.context/design/.changes/251027-1715_aura-innovation-refinement.md`

---

## FORMAT 10: Meta-Analysis Pattern

**Purpose:** Archaeological synthesis of system evolution. Timeline + evidence + current state.

**Ethic:** Documentation archaeology. Reconstruct journey from artifacts. Phases → gaps → status.

**Structure:**
```markdown
---
[Rich frontmatter: schema_version, type, status, scope, keywords, timestamp]
---

# Title

## Original Request
> "user quote"

## Implementation Overview

[Meta-description of the work]

**Key Discovery**: [Synthesis insight]

## Meta-Analysis: [System] Evolution Timeline

### Phase 1: [Period]
**Goal**: [Objective]

**Key Achievements**:
- [Achievement with evidence]
- [Achievement with metrics]

**Evidence Files**:
- [path] - [description]

### Phase 2: [Period]
[Similar structure]

## Current State

[Status assessment]

## Gaps & Future Work

[Actionable findings]
```

**Key Characteristics:**
- Rich frontmatter metadata
- Original request quoted (anchor)
- Implementation overview (meta-description)
- Key Discovery (synthesis)
- Phased timeline structure
- Goal → Achievements → Evidence
- Code examples with WRONG/CORRECT annotations
- Metrics included (95% → 100%)
- Evidence files listed
- Multi-file synthesis capability

**Location:** `.context/design/.changes/`

**Example:**
See: `/home/axp/projects/fleet/hangar/code/aura/main/.context/design/.changes/251007-2235_trace-journey-complete-review.md`

---

## Format Comparison Matrix

### Information Architecture Spectrum

**Minimal → Maximal:**
1. Timestamp + Message (pure chronology)
2. Quote + Why (principle extraction)
3. Concept + Properties (idea-driven)
4. Hypothesis + Components (scientific)
5. Vision Alignment (perspective mapping)
6. Question + Insights (exploration)
7. Central Question + Problem (deep analysis)
8. Extended Context (exhaustive)
9. Meta-Analysis (archaeological synthesis)

### Density Spectrum

**Ultra-Dense:**
- FORMAT 1: Quote + Why
- FORMAT 2: Timestamp + Message
- FORMAT 6: Concept + Properties

**Balanced:**
- FORMAT 3: Hypothesis + Components
- FORMAT 5: Vision Alignment
- FORMAT 7: Question + Insights

**Verbose (Context-Rich):**
- FORMAT 8: Central Question + Problem
- FORMAT 9: Extended Quote + Context
- FORMAT 10: Meta-Analysis

### Structural Approaches

**Chronological:** FORMAT 2
**Principle-Driven:** FORMAT 1, FORMAT 5
**Question-Driven:** FORMAT 7, FORMAT 8
**Hypothesis-Driven:** FORMAT 3
**Visual-First:** FORMAT 4
**Concept-Driven:** FORMAT 6
**Decision-Driven:** FORMAT 9
**Synthesis-Driven:** FORMAT 10

### Unique Characteristics

| Format | Unique Feature |
|--------|---------------|
| FORMAT 1 | Preserves typos for authenticity |
| FORMAT 2 | Zero interpretation layer |
| FORMAT 3 | YAML coordinate examples |
| FORMAT 4 | ASCII diagrams with layers |
| FORMAT 5 | Economic + architectural reasoning |
| FORMAT 6 | "The Value" section |
| FORMAT 7 | Rejected vs Accepted options |
| FORMAT 8 | Percentage statistics (40-60% noise) |
| FORMAT 9 | Anti-patterns explicitly called out |
| FORMAT 10 | WRONG/CORRECT code annotations |

### Use Case Guidance

**When to use FORMAT 1 (Quote + Why):**
- Capturing architectural principles from conversations
- Distilling user messages into design rules
- Creating communication style guides
- Building principle libraries

**When to use FORMAT 2 (Timestamp + Message):**
- Raw conversation preservation
- Archaeological records
- Input for later analysis (e.g., FORMAT 1)
- Audit trails

**When to use FORMAT 3 (Hypothesis + Components):**
- Documenting new methodologies
- Scientific approach documentation
- System architecture with testable claims
- Component-based designs

**When to use FORMAT 4 (Visual Diagrams):**
- Explaining layer architectures
- Showing missing pieces in systems
- Stack positioning
- Visual learners / geometric thinkers

**When to use FORMAT 5 (Vision Alignment):**
- Mapping different perspectives
- Economic justification documents
- Theory-practice bridges
- Cross-reference documents

**When to use FORMAT 6 (Concept + Properties):**
- Technical specifications
- Feature design documents
- Property-based reasoning
- Value proposition documents

**When to use FORMAT 7 (Question + Insights):**
- Exploratory design work
- User-question-driven research
- Option evaluation
- Discovery process documentation

**When to use FORMAT 8 (Central Question + Problem):**
- Deep problem analysis
- Educational documentation
- Design rationale (why not just what)
- Problem decomposition

**When to use FORMAT 9 (Extended Context):**
- Critical architectural decisions
- High-stakes choices
- Cross-project patterns
- Exhaustive decision records

**When to use FORMAT 10 (Meta-Analysis):**
- System evolution documentation
- Phase assessments
- Gap analysis
- Archaeological synthesis of multiple documents

---

## Meta-Principles Across All Formats

### 1. No Code Emphasis
All formats emphasize **design thinking, not implementation code**. When code appears, it's:
- Illustrative examples (FORMAT 8)
- Configuration/structure (FORMAT 3, 6)
- Pattern pseudocode (FORMAT 9)

### 2. User Voice Preservation
Formats prioritizing authentic voice:
- FORMAT 1: Quote + Why (architectural distillation)
- FORMAT 2: Timestamp + Message (raw preservation)
- FORMAT 9: Extended Context (full quotes with context)

**Philosophy:** User's words = ground truth. Typos preserved for authenticity.

### 3. Progressive Disclosure
Different formats serve different detail needs:
- **Quick reference:** FORMAT 1, 2
- **Conceptual understanding:** FORMAT 3, 5, 6
- **Deep dive:** FORMAT 8, 9, 10

### 4. Visual Communication
ASCII diagrams appear in:
- FORMAT 3: Flow diagrams (arrows)
- FORMAT 4: Layer architecture (boxes + arrows)
- FORMAT 6: Workflow diagrams

**Philosophy:** Geometry reveals structure. Show, don't just tell.

### 5. Uncertainty Handling

**No Uncertainty:**
- FORMAT 1, 2 (ground truth preservation)

**Explicit Options:**
- FORMAT 7, 9 (alternatives documented)

**Gap Identification:**
- FORMAT 8, 10 (missing pieces called out)

### 6. Evidence-Based
Formats emphasizing proof:
- FORMAT 3: Testable hypothesis
- FORMAT 8: Statistics and examples
- FORMAT 10: Evidence files listed

---

## File Location Patterns

### `.claude/.vision/`
- Core architectural principles (FORMAT 1)
- Raw user messages (FORMAT 2)
- Ground truth preservation

### `.designate/methodologies/`
- System methodologies (FORMAT 3)
- Scientific documentation
- Reusable frameworks

### `.designate/.inbox/{component}/`
- Vision statements (FORMAT 5)
- Technical specs (FORMAT 6)
- Layer architectures (FORMAT 4)

### `.context/design/.changes/`
- Exploration documents (FORMAT 7)
- Design rationale (FORMAT 8)
- Decision records (FORMAT 9)
- Meta-analysis (FORMAT 10)

### `assets/.context/design/`
- Historical design docs
- Template examples
- Reference material

---

## Evolution & Iteration

These formats evolved organically from different needs:

**Oct 2025:** Scientific formats emerged (FORMAT 3: FlexSchema)
**Oct 2025:** Visual layer thinking (FORMAT 4: Statement architecture)
**Oct 2025:** Question-driven exploration (FORMAT 7, 8)
**Oct 2025:** Exhaustive decision capture (FORMAT 9)
**Oct-Nov 2025:** User voice preservation (FORMAT 1, 2)

**Trend:** Movement from single "design template" → multiple methodologies serving different cognitive states.

**Future:** Potential for hybrid formats combining strengths of multiple approaches.

---

**This catalog is a living document. Formats may evolve, merge, or spawn new variants as design capture needs change.**
