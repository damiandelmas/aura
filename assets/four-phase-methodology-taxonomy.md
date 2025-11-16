---
type: "reference.taxonomy"
phase: "document"
status: "stable"
created: "2025-11-07"
scope: "cross-project methodology"
---

# Complete Taxonomy: Four-Phase Knowledge Lifecycle

**Methodology:** design → designate → develop → document

**Source Projects:**
- `/home/axp/projects/fleet/hangar/code/aura/main`
- `/home/axp/projects/fleet/hangar/code/orca`
- `/home/axp/projects/jesse-benson/projects/npta_ava/ava_chatbot/worktrees/main`

**Discovery Date:** November 7, 2025
**Document Types Found:** 24 distinct formats

---

## Table of Contents

1. [Methodology Overview](#methodology-overview)
2. [Phase: Design](#phase-design)
3. [Phase: Designate](#phase-designate)
4. [Phase: Develop](#phase-develop)
5. [Phase: Document](#phase-document)
6. [Cross-Phase Types](#cross-phase-types)
7. [Comparison Matrices](#comparison-matrices)
8. [Directory Structures](#directory-structures)
9. [Key Insights](#key-insights)

---

## Methodology Overview

### The Four Phases

```
design → designate → develop → document
```

**Design (Exploration → Decision)**
- Question-driven exploration
- Multiple approaches evaluated
- Trade-offs analyzed
- Decision made with rationale
- Output: Design changelogs
- **"What should we do?"**

**Designate (Plan Staging)**
- Clearest articulation of plan/vision
- Staging area for implementation plans
- Refined designs ready for development
- Can include: vision, architectural plans, parameter space, namespace
- Output: Plans, schemas, roadmaps, refined specifications
- **"Here's the plan, clearly stated."**

**Develop (Implementation)**
- Code written based on designate artifacts
- Tests passing
- Technical decisions documented
- Output: Implementation changelogs
- **"Here's what we built and how."**

**Document (Stable Reference)**
- Living documentation
- Architecture explanations
- User guides, API docs
- Output: README, reference docs
- **"Here's how it all works."**

### The Critical Insight: Designate

Designate fills the gap between rough design exploration and concrete implementation:

```
Before: design → ??? → develop
        (rough exploration)    (code)

After:  design → designate → develop
        (exploration) (clear plan) (implementation)
```

**Designate is where:**
- Design work gets refined into clear, actionable plans
- Vision statements get articulated precisely
- Architectural plans get staged for implementation
- Parameter spaces and namespaces get defined
- Plans are ready to hand off to developers
- On same conceptual plane as design, but more refined and clear

---

## PHASE: DESIGN

### Type 1: Vision Document

**Phase:** Design
**Format:** Question-driven exploration
**Structural Pattern:** Challenge → Hypothesis → Exploration
**Density:** Medium (conceptual)
**Ethic:** Expansive thinking

**Characteristics:**
- Philosophical framing
- Multiple perspectives
- Open-ended questions
- Blue-sky thinking
- No constraints initially

**Example Locations:**
```
fleet/hangar/code/aura/main/.context/design/.modules/AUI/00_vision-trace-talk.md
fleet/hangar/code/orca/.context/.vision/orca.md
fleet/hangar/code/orca/.context/.vision/atom/01-atomic-principle.md
```

**Unique Features:**
- Defines "North Star" direction
- Establishes core principles
- Often contains user quotes/directives
- Sets constraints as "non-negotiables"

**Template Structure:**
```markdown
## Vision
[Core concept and goal]

## Principles
[Non-negotiable truths]

## Questions
[Open explorations]

## Constraints
[What we won't compromise]
```

---

### Type 2: Architectural Proposal

**Phase:** Design
**Format:** Layered architecture description
**Structural Pattern:** Current State → Proposed → Benefits → Risks
**Density:** High (technical depth)
**Ethic:** Comprehensive planning

**Characteristics:**
- Detailed component diagrams
- Data flow descriptions
- API specifications
- Integration points
- Phase-based implementation roadmap

**Example Locations:**
```
fleet/hangar/code/aura/main/.context/design/.modules/AUI/01_backend-curation-engine.md
jesse-benson/projects/npta_ava/ava_chatbot/worktrees/main/.context/design/shopify-integration/001/01-overall-plan.md
```

**Unique Features:**
- Contains code signatures
- CLI interface proposals
- Data structure definitions
- Migration strategies

**Template Structure:**
```markdown
## Current State
[What exists now]

## Proposed Architecture
### Components
### Data Flow
### APIs

## Benefits
[Why this approach]

## Risks & Mitigation
[What could go wrong]

## Implementation Phases
[Roadmap]
```

---

### Type 3: Research Document

**Phase:** Design
**Format:** Investigative analysis
**Structural Pattern:** Topic → Findings → Implications → Questions
**Density:** Medium-High
**Ethic:** Evidence-based exploration

**Characteristics:**
- External research synthesis
- Technology comparisons
- Tool evaluations
- Best practice analysis

**Example Locations:**
```
fleet/hangar/code/aura/main/.context/design/.modules/AUI/.archive/conversation-manager/research/vector-memory.md
fleet/hangar/code/aura/main/.context/design/.modules/research/memory-research.md
```

**Template Structure:**
```markdown
## Topic
[Research question]

## Findings
### Technology A
### Technology B
### Comparison

## Implications
[What this means for our project]

## Open Questions
[What we still need to explore]
```

---

### Type 4: Geometry/Essence Documents

**Phase:** Design
**Format:** Conceptual framework
**Structural Pattern:** Core Truth → Shape → Boundaries
**Density:** Low (abstract)
**Ethic:** Fundamental clarity

**Characteristics:**
- Minimal text
- Core principles only
- Philosophy statements
- Immutable truths

**Example Locations:**
```
fleet/hangar/code/orca/.context/design/geometry/01_3D-geometry/geometry.md
fleet/hangar/code/orca/.context/.vision/essence/shape.md
```

**Unique Features:**
- Very short (< 200 lines)
- No implementation details
- Defines "what it is, not how"

**Template Structure:**
```markdown
# [Concept Name]

## Essence
[Core truth in 1-3 sentences]

## Shape
[Fundamental properties]

## Boundaries
[What it is NOT]
```

---

### Type 5: Timestamped Exploration

**Phase:** Design
**Format:** Chronological investigation
**Structural Pattern:** Sequential discoveries with timestamps
**Density:** Variable
**Ethic:** Process documentation

**Characteristics:**
- Filename contains timestamp (`YYMMDD-HHMM`)
- Captures evolution of thinking
- Multiple iterations numbered
- Raw exploration notes

**Example Locations:**
```
fleet/hangar/code/orca/.context/design/geometry/00_vision/251022-1932.md
fleet/hangar/code/orca/.context/design/251023-1306.md
```

**Naming Convention:**
```
YYMMDD-HHMM_description.md
251022-1932_initial-exploration.md
```

---

### Type 6: Audit Document

**Phase:** Design
**Format:** Systematic assessment
**Structural Pattern:** Current State → Problems → Breaking Points → Recommendations
**Density:** Very High
**Ethic:** Exhaustive analysis

**Characteristics:**
- Comprehensive system review
- Dependency mapping
- Breaking point identification
- Code flow tracing
- Matrix summaries

**Example Locations:**
```
fleet/hangar/code/aura/main/.context/design/.modules/index-cli-refactor/00_audit/IMEM_AUDIT.md
fleet/hangar/code/aura/main/.context/design/.modules/index-cli-refactor/00_audit/IMEM_BREAKING_POINTS.md
```

**Unique Features:**
- Contains call-path diagrams
- Line number references
- Breaking point matrices
- Migration strategies

**Template Structure:**
```markdown
## System Overview
[High-level architecture]

## Current State Analysis
### Component A
### Component B

## Problems Identified
[Issues with severity]

## Breaking Points
[Critical failure scenarios]

## Dependency Map
[Component relationships]

## Recommendations
[Migration path]
```

---

## PHASE: DESIGNATE

### Type 7: Handoff Document

**Phase:** Designate
**Format:** Session transition specification
**Structural Pattern:** What We Accomplished → What's Ready → What To Do Next
**Density:** High
**Ethic:** Complete knowledge transfer

**Characteristics:**
- Session metadata (from/to/date)
- Accomplishments summary
- Ready artifacts checklist
- Detailed next steps
- Troubleshooting guide
- Success metrics

**Example Locations:**
```
fleet/hangar/code/orca/.context/designate/workflow-orca/HANDOFF-251023.md
jesse-benson/projects/npta_ava/ava_chatbot/worktrees/main/.context/design/HANDOFF-UPDATED.md
```

**Unique Features:**
- Explicit "next AI instance" framing
- Pre-written commands to execute
- Known issues section
- File location references

**Template Structure:**
```markdown
---
from: [Session ID or date]
to: [Next session or AI instance]
date: [YYYY-MM-DD]
---

## What We Accomplished
[Completed work]

## What's Ready
- [ ] Artifact 1
- [ ] Artifact 2

## What To Do Next
### Step 1
[Detailed instructions]

### Step 2
[Commands to run]

## Known Issues
[Troubleshooting]

## Success Metrics
[How to verify completion]
```

---

### Type 8: Implementation Plan (Multi-Phase)

**Phase:** Designate
**Format:** Phased roadmap
**Structural Pattern:** Phase 1 → Phase 2 → Phase N (with dependencies)
**Density:** High
**Ethic:** Incremental delivery

**Characteristics:**
- Numbered phases
- Duration estimates
- Business impact per phase
- Deliverables checklist
- Success metrics
- Migration strategy

**Example Locations:**
```
jesse-benson/projects/npta_ava/ava_chatbot/worktrees/main/.context/design/session-dynamic-static/000/250920-1555/250919-1820_session-memory/02-current-plan.md
jesse-benson/projects/npta_ava/ava_chatbot/worktrees/main/.context/design/shopify-integration/003/02-current-sprint-implementation.md
```

**Template Structure:**
```markdown
## Phase 1: [Name]
**Duration:** [Estimate]
**Business Impact:** [Value delivered]

### Deliverables
- [ ] Item 1
- [ ] Item 2

### Dependencies
[What must be completed first]

### Success Metrics
[How to measure completion]

## Phase 2: [Name]
...
```

---

### Type 9: Workflow Specification

**Phase:** Designate
**Format:** Operational procedure
**Structural Pattern:** Template → Method → Task → Execution
**Density:** Medium
**Ethic:** Executable clarity

**Characteristics:**
- ORCA-style composition
- `{{pattern}}` interpolation syntax
- Step-by-step instructions
- Resource constraints
- Input/Output specifications

**Example Locations:**
```
fleet/hangar/code/orca/.context/designate/workflow-orca/251023-1512.md
fleet/hangar/code/orca/.context/designate/namespace/namespace-workflow.md
```

**Unique Features:**
- Uses `{{variable}}` syntax for interpolation
- Composable workflow primitives
- Resource constraint declarations

**Template Structure:**
```markdown
## Workflow: [Name]

### Inputs
- {{input_1}}: Description
- {{input_2}}: Description

### Resources
- Tool A
- Tool B

### Steps
1. [Step with {{interpolation}}]
2. [Step description]

### Outputs
- {{output_1}}: Description

### Constraints
[Resource limits, time bounds]
```

---

### Type 10: Taxonomy Document

**Phase:** Designate
**Format:** Classification system
**Structural Pattern:** Categories → Definitions → Examples → Relationships
**Density:** Medium
**Ethic:** Systematic organization

**Characteristics:**
- Type definitions
- Category hierarchies
- Canonical mappings
- Variation lists

**Example Locations:**
```
fleet/hangar/code/orca/.context/designate/namespace/namespace-taxonomy.md
```

**Template Structure:**
```markdown
## Taxonomy: [Domain]

### Category A
**Definition:** [What it is]
**Characteristics:** [Distinguishing features]
**Examples:** [Instances]

### Category B
**Definition:** [What it is]
**Characteristics:** [Distinguishing features]
**Examples:** [Instances]

## Relationships
[How categories relate]

## Canonical Mappings
[Official term → variations]
```

---

### Type 11: Statement Documents

**Phase:** Designate
**Format:** Formal declaration
**Structural Pattern:** Statement → Rationale → Implications
**Density:** Low-Medium
**Ethic:** Definitive clarity

**Characteristics:**
- Numbered statements
- Clear assertions
- Supporting rationale
- System-level implications

**Example Locations:**
```
fleet/hangar/code/aura/main/.designate/.inbox/fleet/vision/statements/statement-1.md
fleet/hangar/code/aura/main/.designate/.inbox/imem/brain/statements/temporal_statement-4.md
```

**Template Structure:**
```markdown
# Statement N: [Title]

## Statement
[Clear, unambiguous assertion]

## Rationale
[Why this is true/necessary]

## Implications
[What this means for the system]

## Examples
[Concrete cases]
```

---

## PHASE: DEVELOP

### Type 12: Changelog (Standard)

**Phase:** Develop
**Format:** Session chronicle
**Structural Pattern:** YAML Frontmatter → Request → Overview → Decisions → Implementation → Audit
**Density:** Very High
**Ethic:** Complete documentation

**Characteristics:**
- Strict YAML schema (`v3_adaptive`)
- Session ID tracking
- Type classification
- Status tracking
- Keywords for searchability
- Structured sections:
  - Request (what was asked)
  - Overview (what was done)
  - Decisions (with alternatives)
  - Failures (what didn't work)
  - Implementation (architecture + code)
  - Patterns (reusable insights)
  - Audit (files changed)

**Example Locations:**
```
fleet/hangar/code/aura/main/.context/develop/.changes/251010-2053_aura-v2-cli-installation-fix.md
jesse-benson/projects/npta_ava/ava_chatbot/worktrees/main/.context/develop/.changes/250826-2034_product-link-debugging-session.md
```

**Unique Features:**
- `schema_version` field
- `type` field (bug-fix, feature, refactor)
- `status` field (completed, in-progress)
- Searchable by multiple dimensions

**Template Structure:**
```yaml
---
schema_version: "v3_adaptive"
type: "feature.new-capability"
status: "completed"
session_id: "abc123..."
keywords: "space-separated search terms"
timestamp: "YYYY-MM-DDTHH:MM:SS-0700"
---

## Request
[What was asked for]

## Overview
[What was accomplished]

## Key Decisions

### Decision 1: [Title]
**Context:** [Why this decision was needed]
**Options Considered:**
1. Option A (rejected - reason)
2. Option B ✓ (chosen - reason)

**Decision:** [What was chosen]
**Rationale:** [Why]

## Implementation

### Architecture
[High-level structure]

### Components Built
[What was created]

### Code Highlights
```language
[Key code snippets]
```

## Failures & Learnings
[What didn't work and why]

## Patterns Emerged
[Reusable insights]

## Audit
**Files Modified:**
- path/to/file.ext (description)

**Files Created:**
- path/to/new-file.ext (purpose)
```

---

### Type 13: Pattern Changelog

**Phase:** Develop
**Format:** Architectural pattern extraction
**Structural Pattern:** Problem Statement → Pattern N → Principles → Architecture → Failures → Extension Points
**Density:** Extreme (most dense format)
**Ethic:** Reusable knowledge extraction

**Characteristics:**
- Filename ends with `.pattern.md`
- Contains 3-7 distinct patterns
- Each pattern has:
  - Pattern name
  - Context (when to use)
  - Solution structure (with code/pseudocode)
  - Decision rationale
  - Trade-offs
  - Key principles
- Reusable design principles section
- Common failure modes
- Extension points for future use

**Example Locations:**
```
fleet/hangar/code/aura/main/.context/develop/.changes/251029-0013_flexgraph-phase-6-5-primitives-enrichment.pattern.md
fleet/hangar/code/aura/main/.context/develop/.changes/251025-1058_memory-system-architecture.pattern.md
```

**Unique Features:**
- Type: `"pattern.compositional-memory-enrichment"`
- Focuses on "how" not "what"
- Transferable across projects
- Contains anti-patterns

**Template Structure:**
```yaml
---
schema_version: "v3_adaptive"
type: "pattern.[category]"
status: "stable"
keywords: "pattern reusable architecture"
---

## Problem Statement
[What architectural challenge this addresses]

## Pattern 1: [Name]

### Context
[When to use this pattern]

### Solution Structure
```pseudocode
[Architectural approach]
```

### Key Decisions
- Decision A (rationale)
- Decision B (rationale)

### Trade-offs
**Benefits:**
- Benefit 1
- Benefit 2

**Costs:**
- Cost 1
- Cost 2

### Principles
[Design principles underlying this pattern]

## Pattern 2: [Name]
[Same structure]

## Reusable Principles
[Cross-cutting design principles]

## Common Failure Modes
[Anti-patterns to avoid]

## Extension Points
[How to adapt this pattern for future use]
```

---

### Type 14: Standalone Notes

**Phase:** Develop
**Format:** Quick capture
**Structural Pattern:** Unstructured observations
**Density:** Low
**Ethic:** Rapid capture

**Characteristics:**
- No strict template
- Quick observations
- Reminders for later
- Integration points

**Example Locations:**
```
fleet/hangar/code/aura/main/.context/develop/model-ab-testing.md
fleet/hangar/code/aura/main/.context/develop/251031-1730_note.md
```

**Usage:**
- Quick thoughts during development
- Integration notes
- Reminders for later sessions
- Ideas to explore

---

## PHASE: DOCUMENT

### Type 15: Architecture Document

**Phase:** Document
**Format:** System reference
**Structural Pattern:** Overview → Components → Data Flow → APIs → Deployment
**Density:** High
**Ethic:** Comprehensive reference

**Characteristics:**
- Stable documentation
- Component descriptions
- Integration guides
- Deployment instructions
- Versioned (`-i1`, `-i2`, `-i3`)

**Example Locations:**
```
fleet/hangar/code/aura/main/.context/document/architecture_aura.md
fleet/hangar/code/aura/main/.context/document/architecture_trace-i2.md
```

**Unique Features:**
- Iteration suffixes (`-i1`, `-i2`)
- Stable over time
- AI agent reference material

**Template Structure:**
```markdown
# [System Name] Architecture

## Overview
[High-level description]

## Core Components

### Component A
**Purpose:** [What it does]
**Responsibilities:** [Key functions]
**Interfaces:** [How to interact]

### Component B
[Same structure]

## Data Flow
[How information moves through system]

## APIs
[Interface specifications]

## Integration Points
[How to integrate with other systems]

## Deployment
[How to deploy and configure]
```

---

### Type 16: Runbook

**Phase:** Document
**Format:** Operational guide
**Structural Pattern:** Setup → Usage → Troubleshooting → Examples
**Density:** Medium
**Ethic:** Operational clarity

**Characteristics:**
- Command-line examples
- Configuration guides
- Common workflows
- Error resolution

**Example Locations:**
```
fleet/hangar/code/aura/main/.context/document/runbooks/imem.md
fleet/hangar/code/aura/main/.context/document/runbooks/trace.md
```

**Template Structure:**
```markdown
# [Tool/System] Runbook

## Setup
```bash
# Installation commands
```

## Common Operations

### Operation 1
**Purpose:** [What this does]
**Command:**
```bash
tool command --flag
```

### Operation 2
[Same structure]

## Troubleshooting

### Error: "Message"
**Cause:** [Why this happens]
**Solution:** [How to fix]

## Examples
[Real-world usage scenarios]
```

---

### Type 17: Decision Framework

**Phase:** Document
**Format:** Structured guidance system
**Structural Pattern:** Principles → Decision Trees → Guidelines → Patterns
**Density:** High
**Ethic:** Systematic decision-making

**Characteristics:**
- YAML frontmatter with schema
- Core architectural principles
- Decision trees (ASCII diagrams)
- System boundary definitions
- Search terms for reference
- Audience specification (often "ai-coding-agents")

**Example Locations:**
```
jesse-benson/projects/npta_ava/ava_chatbot/worktrees/main/.context/document/01-architectural-decision-framework.md
```

**Unique Features:**
- Decision tree diagrams
- "When to apply" guidelines
- Search term indexing
- AI agent optimization

**Template Structure:**
```yaml
---
type: "framework.decision-making"
audience: "ai-coding-agents"
search_terms: "architecture decisions patterns"
---

# [System] Decision Framework

## Core Principles
1. Principle A
2. Principle B

## Decision Tree

```
Question A?
├─ Yes → Path A
│         └─ Question B?
│             ├─ Yes → Outcome 1
│             └─ No → Outcome 2
└─ No → Path B
```

## Guidelines

### When to [Action]
- Condition 1
- Condition 2

### When NOT to [Action]
- Anti-condition 1

## System Boundaries
[What is in/out of scope]
```

---

### Type 18: System Mental Model

**Phase:** Document
**Format:** Conceptual map
**Structural Pattern:** Concepts → Relationships → Workflows
**Density:** Medium
**Ethic:** Understanding over instruction

**Characteristics:**
- Conceptual relationships
- System thinking aids
- Pattern languages
- Workflow narratives

**Example Locations:**
```
jesse-benson/projects/npta_ava/ava_chatbot/worktrees/main/.context/document/03-system-mental-model.md
```

**Template Structure:**
```markdown
# [System] Mental Model

## Core Concepts

### Concept A
[Definition and role in system]

### Concept B
[Definition and role in system]

## Relationships
[How concepts interact]

## Workflow Narratives

### User Flow: [Scenario]
1. [Step with conceptual explanation]
2. [Step with conceptual explanation]

## Pattern Language
[Recurring patterns and their meanings]
```

---

### Type 19: Business Context

**Phase:** Document
**Format:** Domain knowledge
**Structural Pattern:** Context → Constraints → Objectives → Success Metrics
**Density:** Medium
**Ethic:** Domain alignment

**Characteristics:**
- User flows
- Business rules
- Domain terminology
- Conversion metrics

**Example Locations:**
```
jesse-benson/projects/npta_ava/ava_chatbot/worktrees/main/.context/document/02-business-context-user-flows.md
```

**Template Structure:**
```markdown
# Business Context: [Domain]

## Domain Overview
[What this business does]

## User Flows

### Flow: [Primary Action]
**Goal:** [User intent]
**Steps:**
1. [User action]
2. [System response]

**Success Metrics:** [How to measure]

## Business Rules
[Domain constraints and policies]

## Terminology
[Domain-specific terms and definitions]

## Conversion Metrics
[Key performance indicators]
```

---

## CROSS-PHASE TYPES

### Type 20: Conversation Chronicle (.convs)

**Phase:** Cross-phase (captured during any phase)
**Format:** Raw conversation export
**Structural Pattern:** Markdown transcript of Claude Code session
**Density:** Very High
**Ethic:** Complete capture

**Characteristics:**
- Stored in `.claude/.convs/`
- Organized by date folders
- Contains full dialogue
- Tool usage captured
- Code artifacts embedded

**Example Locations:**
```
fleet/hangar/code/aura/main/.claude/.convs/251104-1850.md
fleet/hangar/code/aura/main/.claude/.convs/251024/251027-1554.md
```

**Unique Features:**
- Primary source material
- Can be mined for insights
- Temporal record
- Session ID linked

**Usage:**
- Archive of all AI-human interactions
- Source material for changelog creation
- Historical reference
- Pattern discovery

---

### Type 21: Signoff Log

**Phase:** Cross-phase (end of session)
**Format:** Session reference list
**Structural Pattern:** Session IDs with minimal context
**Density:** Very Low
**Ethic:** Session tracking

**Characteristics:**
- Stored in `.claude/.signoff/`
- Lists session IDs
- Brief descriptors
- Link to conversation archives

**Example Locations:**
```
fleet/hangar/code/aura/main/.claude/.signoff/log-1.md
fleet/hangar/code/aura/main/.claude/.signoff/log-3.md
```

**Template Structure:**
```markdown
# Signoff Log

## 2025-11-07
- `abc123...` - Description of work
- `def456...` - Description of work

## 2025-11-06
- `ghi789...` - Description of work
```

---

### Type 22: Timeline/Dashboard

**Phase:** Cross-phase (ongoing tracking)
**Format:** Chronological event log
**Structural Pattern:** Date → Time → Event → Details
**Density:** Medium
**Ethic:** Historical tracking

**Characteristics:**
- Reverse chronological
- Business events
- User quotes
- Links to detailed docs

**Example Locations:**
```
jesse-benson/projects/npta_ava/ava_chatbot/worktrees/main/.context/dashboard/timeline.md
jesse-benson/projects/npta_ava/ava_chatbot/worktrees/main/.context/dashboard/timeline/20250812T112515-PST.md
```

**Template Structure:**
```markdown
# Timeline

## 2025-11-07

### 14:30 PST
**Event:** [What happened]
**Context:** [Why it matters]
**Reference:** [Link to detailed doc]

### 09:15 PST
**Event:** [What happened]
**User Quote:** "[Direct quote from user]"

## 2025-11-06
[Earlier events]
```

---

### Type 23: Vision Statement (.vision)

**Phase:** Cross-phase (persistent reference)
**Format:** Foundational document
**Structural Pattern:** Core concept → Principles → Constraints
**Density:** Medium
**Ethic:** Immutable truth

**Characteristics:**
- Stored in `.context/.vision/` or `.claude/.vision/`
- System-level truth
- Rarely changes
- Referenced frequently

**Example Locations:**
```
fleet/hangar/code/aura/main/.context/.vision/aiUX.md
fleet/hangar/code/orca/.context/.vision/orca-actual-orchestration-vision.md
```

**Template Structure:**
```markdown
# [System] Vision

## Core Concept
[Fundamental purpose in 2-3 sentences]

## Guiding Principles
1. Principle A (immutable)
2. Principle B (immutable)

## Constraints
[Non-negotiables]

## North Star
[Long-term destination]
```

---

### Type 24: CLAUDE.md (Agent Instructions)

**Phase:** Cross-phase (persistent reference)
**Format:** AI collaboration framework
**Structural Pattern:** Role → Primitives → Principles → Project Context
**Density:** High
**Ethic:** Partnership contract

**Characteristics:**
- Root of project directory
- Defines AI role
- Core primitives (universal rules)
- Guiding principles
- Project-specific context

**Example Locations:**
```
fleet/hangar/code/aura/main/CLAUDE.md
jesse-benson/projects/npta_ava/ava_chatbot/worktrees/main/CLAUDE.md
```

**Unique Features:**
- Hierarchy of directives
- Constructive challenge mandate
- System designed for AI efficiency
- Quality of outcome prioritization

**Template Structure:**
```markdown
# Claude Workflow

## PART 1: FRAMEWORK

### 1.1. Your Role: Collaborative Partner
[Role definition]

### 1.2. Core Primitives (Universal Rules)
**Primitive #1:** [Unbreakable rule]
**Primitive #2:** [Unbreakable rule]

### 1.3. Guiding Principles
**Principle #1:** [Operating principle]
**Principle #2:** [Operating principle]

## PART 2: THE [PROJECT] PROJECT

### 2.1. Core Concept
[What this project is]

### 2.2. Project Primitives
**Principle #1:** [Project-specific rule]
**Principle #2:** [Project-specific rule]
```

---

## COMPARISON MATRICES

### Density Spectrum

```
Extreme   ████████████ Pattern Changelog
Very High ██████████   Standard Changelog, Conversation Chronicle, Audit
High      ████████     Architectural Proposal, Handoff, Implementation Plan, Architecture Doc, Decision Framework
Medium    ██████       Vision Document, Research, Taxonomy, Workflow Spec, Runbook, Mental Model, Business Context, Timeline
Low       ████         Geometry/Essence, Statement, Standalone Notes, Signoff Log
Minimal   ██           (none - all formats provide value-dense content)
```

### Structural Approaches

| Type | Structure |
|------|-----------|
| Vision Document | Question-driven |
| Architectural Proposal | Layered (current → proposed) |
| Research Document | Topic → Findings → Implications |
| Geometry/Essence | Core Truth → Shape → Boundaries |
| Timestamped Exploration | Chronological sequence |
| Audit Document | Current → Problems → Recommendations |
| Handoff Document | Accomplished → Ready → Next Steps |
| Implementation Plan | Phased roadmap |
| Workflow Specification | Template → Method → Execution |
| Taxonomy Document | Categories → Definitions → Relationships |
| Statement Documents | Statement → Rationale → Implications |
| Standard Changelog | Request → Implementation → Audit |
| Pattern Changelog | Problem → Pattern N → Principles |
| Architecture Document | Overview → Components → APIs |
| Runbook | Setup → Usage → Troubleshooting |
| Decision Framework | Principles → Decision Trees → Guidelines |
| Mental Model | Concepts → Relationships → Workflows |
| Business Context | Context → Constraints → Metrics |

### Unique Characteristics Table

| Type | Unique Identifier | When to Use |
|------|------------------|-------------|
| Vision Document | Philosophical framing, North Star | Project inception, strategic pivots |
| Architectural Proposal | Component diagrams, data flow | Major system design |
| Research Document | External synthesis | Technology evaluation |
| Geometry/Essence | < 200 lines, abstract | Core principles definition |
| Timestamped Exploration | `YYMMDD-HHMM` filename | Iterative exploration |
| Audit Document | Breaking points matrix | System assessment |
| Handoff Document | From/To, next commands | Session transitions |
| Implementation Plan | Numbered phases | Multi-phase projects |
| Workflow Specification | `{{pattern}}` syntax | ORCA-style workflows |
| Taxonomy Document | Category hierarchies | Classification systems |
| Statement Documents | Numbered assertions | Formal declarations |
| Standard Changelog | YAML frontmatter, sections | Every development session |
| Pattern Changelog | `.pattern.md` suffix | Pattern extraction |
| Standalone Notes | Unstructured | Quick capture |
| Architecture Document | Versioned (`-i1`, `-i2`) | Stable system reference |
| Runbook | Command examples | Operations guide |
| Decision Framework | Decision trees | Structured guidance |
| Mental Model | Conceptual relationships | Understanding aids |
| Business Context | Domain terminology | Business alignment |
| Conversation Chronicle | `.convs/` location | Raw capture |
| Signoff Log | Session ID list | Session tracking |
| Timeline/Dashboard | Reverse chronological | Event tracking |
| Vision Statement | `.vision/` location | Foundational truth |
| CLAUDE.md | Root directory, primitives | AI partnership |

---

## DIRECTORY STRUCTURES

### Aura Project Structure

```
/home/axp/projects/fleet/hangar/code/aura/main/

.context/
  .vision/              → Vision statements (Type 23)
  design/
    .modules/           → Design explorations (Types 1-6)
      AUI/
      index-cli-refactor/
        00_audit/       → Audit documents (Type 6)
    .wishlist/          → Future features
  develop/
    .changes/           → Changelogs (Types 12-13)
      *.md              → Standard changelogs
      *.pattern.md      → Pattern changelogs
  document/
    .iterations-test/   → Versioned architectures
    runbooks/           → Operational guides (Type 16)
      imem.md
      trace.md
    architecture_*.md   → Architecture docs (Type 15)

.claude/
  .convs/              → Conversation chronicles (Type 20)
    251024/
      251027-1554.md
  .signoff/            → Session logs (Type 21)
    log-1.md
  .vision/             → Project vision (Type 23)
  agents/              → Subagent definitions

.designate/
  .inbox/              → Pending specifications
    imem/
      vision/          → Component visions (Type 1)
      brain/           → Subsystem specs
        statements/    → Statement documents (Type 11)
      database/        → Data models
  methodologies/       → Methodology docs
    flexschema/
    flexgraph/
  skills/              → Skill definitions
    catalog-types.md
    discover-taxonomy.md

CLAUDE.md              → AI partnership contract (Type 24)
```

### Orca Project Structure

```
/home/axp/projects/fleet/hangar/code/orca/

.context/
  .vision/             → Vision statements (Type 23)
    atom/              → Core principles (Type 4)
      01-atomic-principle.md
    end-state/         → Target architecture
    essence/           → Geometry docs (Type 4)
      shape.md
    brainstorm-v1-v2/  → Evolution
  design/
    geometry/          → Conceptual frameworks (Type 4)
      01_3D-geometry/
        geometry.md
      00_vision/       → Timestamped explorations (Type 5)
        251022-1932.md
    barbar-orchestration/ → Specific designs
    251023-1306.md     → Timestamped exploration (Type 5)
  designate/
    workflow-orca/     → ORCA workflows (Type 9)
      251023-1512.md
      HANDOFF-251023.md → Handoff doc (Type 7)
    namespace/         → Taxonomy (Type 10)
      namespace-taxonomy.md
      namespace-workflow.md
  develop/             → (Minimal - mostly patterns)
  document/            → (API docs)
```

### AVA Chatbot Structure

```
/home/axp/projects/jesse-benson/projects/npta_ava/ava_chatbot/worktrees/main/

.context/
  dashboard/
    timeline.md        → Timeline (Type 22)
    timeline/
      20250812T112515-PST.md
  design/
    .staging/          → Work in progress
    .modules/          → Subsystem designs (Types 1-3)
    shopify-integration/
      001/
        01-overall-plan.md → Architectural proposal (Type 2)
      003/
        02-current-sprint-implementation.md → Implementation plan (Type 8)
    session-dynamic-static/
      000/
        250920-1555/
          250919-1820_session-memory/
            02-current-plan.md → Implementation plan (Type 8)
    bugs/              → Bug investigations
    HANDOFF-UPDATED.md → Handoff document (Type 7)
  develop/
    .changes/          → Changelogs (Types 12-13)
      250826-2034_product-link-debugging-session.md
  document/
    01-architectural-decision-framework.md → Decision framework (Type 17)
    02-business-context-user-flows.md → Business context (Type 19)
    03-system-mental-model.md → Mental model (Type 18)

CLAUDE.md              → AI partnership contract (Type 24)
```

---

## KEY INSIGHTS

### 1. Phase Progression Flow

Documents naturally flow through phases:

```
Exploratory (design)
    ↓
Prescriptive (designate)
    ↓
Descriptive (develop)
    ↓
Normative (document)
```

**Example journey:**
1. Design: Vision doc explores "what if we had conversational memory?"
2. Designate: Implementation plan specifies 3 phases for building it
3. Develop: Changelogs document what was built in each phase
4. Document: Architecture doc becomes stable reference

### 2. Density Gradient

Information density correlates with purpose:

- **Extreme density**: Pattern changelogs (extract reusable knowledge)
- **Very high density**: Standard changelogs, audits (complete capture)
- **High density**: Proposals, plans, architecture docs (comprehensive)
- **Medium density**: Vision, research, taxonomies (balanced)
- **Low density**: Geometry, statements (clarity through brevity)

### 3. Temporal Markers

Different phases use different time markers:

- **Design**: Timestamps (`YYMMDD-HHMM`) for iteration tracking
- **Develop**: Session IDs for genealogical tracing
- **Document**: Version suffixes (`-i1`, `-i2`) for stable evolution
- **Cross-phase**: Date folders for chronological organization

### 4. Format Diversity

All 24 types use **markdown**, but with varying conventions:

- YAML frontmatter: Develop phase (changelogs)
- Minimal frontmatter: Document phase (stable docs)
- No frontmatter: Design phase (exploratory)
- Special syntax: `{{patterns}}` in designate workflows

### 5. Cross-Phase Persistence

Some documents transcend phases:

- **CLAUDE.md**: Partnership contract (always referenced)
- **.vision/**: Foundational truth (rarely changes)
- **.convs/**: Raw material (mined for insights)
- **Timeline**: Historical record (continuously updated)

### 6. Project Signatures

Each project has unique patterns:

**Aura:**
- Heavy pattern extraction (`.pattern.md` files)
- `.designate/` inbox system for specifications
- Versioned architecture documents (`-i1`, `-i2`)

**Orca:**
- Geometry/essence documents (abstract frameworks)
- Workflow specifications with `{{pattern}}` syntax
- Minimal develop phase (focus on design & designate)

**AVA:**
- Timeline dashboards (business event tracking)
- Business context documents (domain alignment)
- Decision frameworks (structured guidance)

### 7. Genealogical Linking

Documents link across phases via session IDs:

```
Conversation (raw thinking)
    ↓ session_id
design (abstract decisions)
    ↓ session_id
designate (clear plans)
    ↓ session_id
develop (implementation)
    ↓ session_id
document (knowledge synthesis)
```

**Property:** Full reasoning chain traceable from idea → documentation.

### 8. RAG Optimization

Phase-based filtering enables precise retrieval:

```python
# Find design decisions
filter={'phase': 'design'}

# Find staged plans
filter={'phase': 'designate'}

# Find implementation details
filter={'phase': 'develop'}

# Find stable reference
filter={'phase': 'document'}
```

### 9. Template Flexibility

Templates exist on a spectrum:

- **Strict**: Standard changelogs (v3_adaptive schema)
- **Structured**: Handoffs, implementation plans
- **Flexible**: Research, vision documents
- **Minimal**: Geometry, standalone notes

### 10. The Designate Gap

The discovery of "designate" phase filled critical gap:

**Before:**
```
design → ??? → develop
```
Developers had rough explorations but no clear, refined plan.

**After:**
```
design → designate → develop
```
Plans get refined and clearly stated before implementation (e.g., `courses.json`, architectural specs, namespaces).

---

## Usage Guidelines

### When to Create Each Type

**Design Phase:**
- Start with **Vision Document** (Type 1) for new projects
- Use **Architectural Proposal** (Type 2) for major system changes
- Create **Research Document** (Type 3) when evaluating technologies
- Write **Geometry/Essence** (Type 4) for core principles
- Use **Timestamped Exploration** (Type 5) for iterative thinking
- Conduct **Audit** (Type 6) before major refactors

**Designate Phase:**
- Write **Handoff Document** (Type 7) at session transitions
- Create **Implementation Plan** (Type 8) for multi-phase work
- Build **Workflow Specification** (Type 9) for ORCA-style systems
- Develop **Taxonomy** (Type 10) for classification systems
- Issue **Statement Documents** (Type 11) for formal declarations

**Develop Phase:**
- Create **Standard Changelog** (Type 12) for EVERY session
- Extract **Pattern Changelog** (Type 13) when reusable patterns emerge
- Use **Standalone Notes** (Type 14) for quick captures

**Document Phase:**
- Maintain **Architecture Document** (Type 15) as system evolves
- Write **Runbook** (Type 16) for operational procedures
- Create **Decision Framework** (Type 17) for structured guidance
- Build **Mental Model** (Type 18) for conceptual understanding
- Document **Business Context** (Type 19) for domain alignment

**Cross-Phase:**
- Archive **Conversations** (Type 20) automatically
- Maintain **Signoff Log** (Type 21) for session tracking
- Update **Timeline** (Type 22) for business events
- Establish **Vision Statement** (Type 23) at project start
- Create **CLAUDE.md** (Type 24) for AI partnership

### Choosing Between Similar Types

**Vision Document vs. Vision Statement:**
- Vision Document (Type 1): Exploratory, in design phase
- Vision Statement (Type 23): Foundational truth, persistent

**Architectural Proposal vs. Architecture Document:**
- Proposal (Type 2): Design phase, evaluating options
- Document (Type 15): Document phase, stable reference

**Implementation Plan vs. Standard Changelog:**
- Plan (Type 8): Designate phase, what WILL be done
- Changelog (Type 12): Develop phase, what WAS done

**Pattern Changelog vs. Standard Changelog:**
- Pattern (Type 13): Extract reusable patterns (`.pattern.md`)
- Standard (Type 12): Document session work

**Handoff vs. Implementation Plan:**
- Handoff (Type 7): Session transition, immediate next steps
- Plan (Type 8): Multi-phase roadmap, strategic sequence

---

## Conclusion

This taxonomy represents the complete diversity of document formats discovered across three mature projects using the four-phase knowledge lifecycle methodology. The 24 distinct types provide comprehensive coverage of:

- **Exploration** (design phase)
- **Specification** (designate phase)
- **Implementation** (develop phase)
- **Reference** (document phase)
- **Persistence** (cross-phase)

Each type serves a specific purpose, has unique characteristics, and integrates into the larger knowledge system through genealogical linking via session IDs.

The methodology's power lies in:
1. **Separation of concerns**: Lifecycle phase vs. domain category
2. **Plan clarity**: Designate phase refines rough design into clear, actionable plans
3. **Traceability**: Session IDs link idea → plan → implementation → docs
4. **RAG optimization**: Phase-based filtering for precise retrieval
5. **Flexibility**: 24 types handle diverse needs while maintaining coherence

---

**Document Status:** Stable reference
**Last Updated:** 2025-11-07
**Maintained By:** Four-phase methodology practitioners
**Next Review:** When new document types emerge
