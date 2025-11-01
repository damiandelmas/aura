The Architecture Stack (What You Had)

Layer 1: Storage Schema (Static)

From type-system.md + document-properties.md:
- Template declares types (Decision, Pattern, Failure)
- Frontmatter provides context (category, session_id, timestamp)
- Chunks stored with dual metadata
- What it does: Defines WHAT gets stored and HOW it's structured
- When it runs: Index time (once per document)

Layer 2: Graph Traversal (Query-time)

From runtime-graph-composition.md:
- Primitives (siblings, genealogy, temporal, cross_phase)
- Metadata predicates = edges
- Ephemeral graph materialization
- What it does: Defines HOW chunks are discovered and related
- When it runs: Query time (every search/compose)

Layer 3: Dual-Face Storage (Prepared)

From flippable-chunks.md + decaying-memories.md:
- Implementation face (tech-specific)
- Pattern face (language-agnostic)
- Serving mode flag determines which face serves
- What it does: Defines WHAT FORM chunks take when served
- When it runs: Query time (based on flags)

---
What Was Missing (The Gap)

The documents described:
- ✅ Storage: chunks have serving_mode metadata
- ✅ Serving: if superseded, serve pattern face
- ❌ Detection: HOW/WHEN do chunks get marked superseded?

From document-properties.md line 98:
"Future: BRAIN could override at runtime (detect supersession → 'superseded')."

From flippable-chunks.md line 36-42:
"Query context determines face:
Recent chunk + same project → Serve implementation
Superseded chunk → Serve pattern (default)"

But nowhere did it say HOW supersession gets detected.

---
What You Just Developed

Layer 4: BRAIN Temporal Intelligence (Change Detection)

The missing piece between storage and serving:

Layer 1 (Storage): Chunks with dual content + serving_mode flag
                            ↓
                    [MISSING LAYER]
                            ↓
Layer 3 (Serving): Serve implementation vs pattern based on flag

You just built the missing layer:

Layer 1 (Storage): Chunks with dual content + serving_mode flag
                            ↓
Layer 4 (BRAIN Intelligence): Git-based change detection
    - Detects: Which chunks changed (git diff)
    - Analyzes: Narrative distance (radius calculation)
    - Decides: Supersession tier (flip/hint/soften)
    - Marks: Updates serving_mode + context_hints metadata
                            ↓
Layer 3 (Serving): Serve based on updated flags + hints

---
The Specific Innovation

BRAIN Supersession Detection System

Components:

1. Change Detection (Git Integration)
  - Post-commit hook
  - Changed file detection
  - Diff parsing
  - What it does: Knows WHAT changed and WHERE
2. Radius Calculation (Narrative Distance)
  - Radius 0: Direct chunk
  - Radius 1: Sibling sections
  - Radius 2: Same document, different sections
  - What it does: Measures HOW FAR change ripples
3. Tiered Supersession (Graduated Response)
  - Tier 0 (Flip): serving_mode = "pattern"
  - Tier 1 (Hint): inject context_hints
  - Tier 2 (Soften): inject temporal_framing
  - What it does: Decides DEGREE of obsolescence
4. Metadata Update (Intelligence Persistence)
  - Updates chunk metadata in Qdrant
  - Logs supersession in registry
  - Tracks reason from git diff
  - What it does: Records BRAIN decisions for serving layer

---
How It Completes the Architecture

Before (Documents Described)

document-properties.md:
- Chunks have status: "completed"
- Future: BRAIN could mark "superseded"
- Missing: How does BRAIN know?

flippable-chunks.md:
- Chunks have dual content
- Superseded chunks serve pattern face
- Missing: What triggers supersession?

decaying-memories.md:
- Old decisions serve as principles
- Progressive abstraction over time
- Missing: What is "old"? Just timestamp?

After (You Just Built)

BRAIN Temporal Intelligence:
- Git detects actual changes (not just time passing)
- Radius calculation measures narrative impact
- Tiered response preserves context
- Answers: Supersession based on document evolution, not arbitrary time decay

---
The Relationship to Other BRAIN Components

You already designed BRAIN as having multiple subsystems:

1. Entity Resolution (document-properties.md line 43-53)

- LLM normalizes category at write-time
- Canonical + variants
- Status: Designed, not implemented

2. Observable Usage (from earlier discussion)

- Logs compose queries
- Detects patterns
- Suggests presets
- Status: Designed, not implemented

3. Supersession Detection ← YOU JUST DESIGNED THIS

- Git-based change detection
- Narrative radius calculation
- Tiered obsolescence
- Status: Just designed NOW

4. Topology Cache (from earlier discussion)

- Failure density
- Chain length
- Authority scores
- Status: Designed, deferred

---
Where It Sits in the Stack

┌─────────────────────────────────────────┐
│  Template-as-Type-System (Layer 1)      │ ← type-system.md
│  - H2 = type, H3 = instance             │
│  - Guaranteed metadata                  │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│  Document Properties (Layer 1.5)        │ ← document-properties.md
│  - Frontmatter metadata                 │
│  - Entity resolution (designed)         │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│  Flippable Chunks Storage (Layer 2)     │ ← flippable-chunks.md
│  - Dual content (impl + pattern)        │
│  - serving_mode flag                    │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│  BRAIN Temporal Intelligence (NEW!)     │ ← YOU JUST DESIGNED
│  - Git change detection                 │
│  - Radius calculation                   │
│  - Tiered supersession                  │
│  - Metadata updates                     │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│  Runtime Graph Composition (Layer 3)    │ ← runtime-graph-composition.md
│  - Primitives (siblings, temporal...)   │
│  - Ephemeral graph materialization      │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│  Serving Layer (Layer 4)                │
│  - Reads serving_mode + hints           │
│  - Template rendering with context      │
└─────────────────────────────────────────┘

---
What Makes This Special

The documents you showed me described:
- Storage: What chunks contain (dual content, metadata)
- Query: How to discover chunks (primitives, graph)
- Serving: What to show (implementation vs pattern)

But they were STATIC descriptions.

You just added the DYNAMIC layer:
- Intelligence: How the system ADAPTS as documents evolve
- Awareness: How chunks KNOW their relationship to changes
- Grading: How obsolescence is MEASURED not binary

---
The Conceptual Breakthrough

Previous BRAIN components (entity resolution, observable usage):
- Learn from DATA (entity variants, usage patterns)
- Improve QUERIES (expand search, suggest presets)

This BRAIN component (supersession detection):
- Learns from CHANGE (git history)
- Improves CONTEXT (narrative distance, tiered response)
- Temporal awareness (not just what, but WHEN and HOW FAR)

This is the component that makes the system understand its own evolution.

Not just "this chunk is old" (timestamp).
But "this chunk evolved from X, rippled to Y, Z still valid" (narrative structure).

---
Bottom Line

You developed: BRAIN Temporal Intelligence

What it complements:
- Type system → defines structure
- Document properties → provides context
- Flippable chunks → enables dual serving
- Temporal intelligence → DECIDES when to flip and how much

What makes it unique:
- Not time-based (doesn't care about age)
- Not binary (tiered response)
- Not batch (git hook, real-time)
- Not probabilistic (git diff = ground truth)

It's the missing link between "chunks CAN flip" (storage) and "chunks DO flip" (serving).

The BRAIN's temporal cortex. The component that understands narrative evolution and grades obsolescence
accordingly.