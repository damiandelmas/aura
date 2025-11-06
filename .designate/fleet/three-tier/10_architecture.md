---
session_id: c5383e9c-9894-4584-9edd-1cf8aaebaca1
---

# Three-Tier Architecture (Clarified)

```
┌─ TIER 0: THE THING ITSELF ────────────────────┐
│ • URL content (docs.anthropic.com/hooks)      │
│ • File contents (/path/to/design-log.md)      │
│ • Repo code (github.com/user/repo)            │
│ • Implementation-specific, just EXISTS         │
└────────────────────────────────────────────────┘
            ↓
┌─ TIER 1: OBJECTIVE GATEWAY ───────────────────┐
│ GLOBAL REGISTRY (external to all projects)    │
│                                                │
│ • Universal wrapper around Tier 0             │
│ • Language-agnostic facts ABOUT the thing     │
│ • ONE entry serves INFINITE intentions        │
│                                                │
│ Fields:                                        │
│   source: pointer to Tier 0                    │
│   description: what it is                      │
│   authority: 1-10 (1=canonical, 10=speculative)│
│   tags: [official | hypothesis | tested]       │
│   creator: who made it                         │
│   created: when it was made                    │
│   type: [docs | code | design | research]      │
└────────────────────────────────────────────────┘
            ↓
┌─ TIER 2: SUBJECTIVE GATEWAY(S) ───────────────┐
│ PER-PROJECT REGISTRIES (project-x/.brain/)    │
│                                                │
│ • Intention-specific wrapper                   │
│ • Points to Tier 1 objective entry             │
│ • Accumulates intellectual capital             │
│                                                │
│ Fields:                                        │
│   objective_ref: link to Tier 1 entry          │
│   added: when YOU found it (transaction time)  │
│   purpose: WHY you care (this project context) │
│   attention: computed usage density            │
│   accessed: usage count & patterns             │
│   notes: project-specific learnings            │
│   status: [active | archived | evaluated]      │
└────────────────────────────────────────────────┘
```

---

## Concrete Example: Anthropic Hooks Docs

### Tier 0 (The Thing)

```
https://docs.anthropic.com/en/docs/claude-code/hooks
[actual HTML/content lives here, we fetch on demand]
```

### Tier 1 (Objective - ONE global entry)

**Anthropic Claude Code Hooks Documentation**

- **source:** `https://docs.anthropic.com/en/docs/claude-code/hooks`
- **description:** Official lifecycle hooks for intercepting Claude Code events (SessionStart, PreToolUse, PostToolUse, Stop). Enables blocking, validation, context injection, and audit trails.
- **authority:** 1
- **tags:** official, documentation
- **creator:** Anthropic
- **created:** 2024-10
- **type:** documentation

Lives in: `GLOBAL_REGISTRY/anthropic-hooks.md`

### Tier 2 (Subjective - MULTIPLE project entries)

#### project-barbar/.brain/wrappers/anthropic-hooks.md:

- **objective_ref:** anthropic-hooks-official
- **added:** 2025-01-15
- **purpose:** Implement security validation blocking dangerous bash commands
- **attention:** 0.85  # computed from usage
- **accessed:** 12 times
- **last_query:** "PreToolUse exit code 2 security"
- **project_schema_tags:** [security, bash-validation, production]
- **notes:** |
  ```
  Used PreToolUse hook to block rm -rf, curl to internal IPs.
  Exit code 2 blocks execution. Critical for prod safety.
  ```
- **status:** implemented

#### project-npta/.brain/wrappers/anthropic-hooks.md:

- **objective_ref:** anthropic-hooks-official
- **added:** 2025-01-20
- **purpose:** Audit trail for AI-generated training content
- **attention:** 0.3
- **accessed:** 3 times
- **last_query:** "PostToolUse logging compliance"
- **project_schema_tags:** [compliance, audit, logging]
- **notes:** |
  ```
  Using PostToolUse to log all AI generations for review.
  Compliance requirement for training content.
  ```
- **status:** researching

#### project-orca/.brain/wrappers/anthropic-hooks.md:

- **objective_ref:** anthropic-hooks-official
- **added:** 2025-01-18
- **purpose:** Workflow orchestration event triggers
- **attention:** 0.6
- **accessed:** 7 times
- **last_query:** "SessionStart initialization patterns"
- **project_schema_tags:** [orchestration, workflow, initialization]
- **notes:** |
  ```
  SessionStart hook loads BASE library patterns.
  PreToolUse validates workflow composition.
  ```
- **status:** active

---

## Example 2: Your Design Log

### Tier 0

```
/home/axp/projects/fleet/hangar/code/aura/main/.context/design/
architecture-i2/vision/typed-vector-document-store.md
[actual markdown content]
```

### Tier 1 (Objective)

**AURA Typed Vector Document Store Design**

- **source:** `file:///home/axp/projects/fleet/.../typed-vector-document-store.md`
- **description:** Schema-enforced vector database with semantic type system. Template sections become queryable types (Decision, Pattern, Failure). LlamaIndex chunks preserve structure. Metadata index IS graph.
- **authority:** 7  # internal design doc
- **tags:** hypothesis, design-document
- **creator:** axp
- **created:** 2025-01-10
- **type:** design-document

Lives in: `GLOBAL_REGISTRY/aura-typed-vector-design.md`

### Tier 2 (Subjective - barbar project)

- **objective_ref:** aura-typed-vector-design
- **added:** 2025-01-22
- **purpose:** Apply typed markdown parsing to barbar decision/pattern logs
- **attention:** 0.9
- **accessed:** 15 times
- **project_schema_tags:** [architecture, decision-logs, markdown-as-schema]
- **notes:** |
  ```
  Schema pattern directly applicable. Want section_type='Decision'
  queries for barbar arch decisions. Need to extend LlamaIndex parser.
  ```
- **evaluation:** "Core insight: H2 headers = semantic types"
- **status:** implementing

---

## The Profound Insight

### EVERYTHING is Intellectual Capital

No difference between:
- Anthropic docs (authority=1, official)
- Community guide (authority=5, tested)
- Your design log (authority=7, hypothesis)
- Code repo (authority=4, community)

**ALL** are sources of intelligence. The **WRAPPING** determines treatment:

#### Official doc
```
authority: 1
tags: official, canonical
→ High confidence in queries
→ Serve as authoritative answer
```

#### Design hypothesis
```
authority: 7
tags: hypothesis, speculative
→ Lower confidence weight
→ Present as "proposed approach"
→ Flag for validation
```

#### Tested implementation
```
authority: 6
tags: tested, production
→ Medium-high confidence
→ "Proven in barbar production"
```

---

## Intellectual Capital Accumulation

### Traditional Approach (Lost Context)

```
Developer: [googles anthropic hooks]
Developer: [reads docs, implements]
Developer: [6 months later, forgets why they used PreToolUse]
New developer: [googles same docs, rediscovers]
```

### This Architecture (Compound Learning)

```
project-barbar accesses anthropic-hooks:
  ↓
Creates Tier 2 wrapper:
  purpose: "security validation"
  attention: +0.1 per access
  notes: accumulate learnings
  ↓
6 months later:
  Query: "why do we use PreToolUse?"
  Returns: project-barbar wrapper with full context
  ↓
project-npta researches hooks:
  Query: "how did other projects use hooks?"
  Discovers: barbar used for security (notes + attention density)
  Learns from barbar's accumulated capital
```

### The Flow

#### 1. Discovery (Tier 1 creation):
```
Find: https://docs.anthropic.com/hooks
↓
Create objective entry in GLOBAL_REGISTRY:
  - authority: 1 (official)
  - tags: official, documentation
  - description: summary for vector search
```

#### 2. Usage (Tier 2 creation):
```
project-barbar accesses for security purpose:
↓
Create subjective wrapper in project-barbar/.brain/:
  - objective_ref: anthropic-hooks-official
  - purpose: "block dangerous bash"
  - attention: 0.0 (initial)
```

#### 3. Accumulation (Tier 2 updates):
```
Each access from project-barbar:
  - attention += usage_weight
  - accessed++
  - notes accumulate
  - "barbar's understanding of hooks" grows
```

#### 4. Schema Emergence:
```
project-barbar's Tier 2 wrappers → attention density map:
  - anthropic-hooks: 0.85 (critical)
  - jwt-guide: 0.6 (important)
  - redis-docs: 0.3 (referenced)
↓
Schema emerges weighted by attention:
  - section_types prioritize security/validation concepts
  - Entity resolution: auth → [jwt, hooks, validation]
```

#### 5. Cross-Project Intelligence:
```
Query: "How do projects use anthropic hooks?"
↓
Find objective entry: anthropic-hooks-official
↓
Find all Tier 2 wrappers:
  - barbar: security, attention=0.85
  - npta: audit, attention=0.3
  - orca: orchestration, attention=0.6
↓
See: Different projects, different purposes, different learnings
```

---

## Query Patterns

### Objective Queries (Tier 1)

**"Show all official documentation about hooks"**
```
→ Filter: authority <= 3 AND tags CONTAINS 'official'
→ Semantic search: "hooks"
→ Returns: objective entries (global view)
```

### Subjective Queries (Tier 2)

**Context: project-barbar**

**"What did we learn about security validation?"**
```
→ Filter: project='barbar' AND purpose CONTAINS 'security'
→ Returns: project-barbar's Tier 2 wrappers
→ Each points to objective entry + accumulated notes
```

### Cross-Project Learning

**"Which projects studied anthropic hooks and why?"**
```
→ Find Tier 1: anthropic-hooks-official
→ Find all Tier 2 wrappers referencing it
→ Group by project:
    barbar: security validation (12 accesses, 0.85 attention)
    npta: compliance audit (3 accesses, 0.3 attention)
    orca: workflow init (7 accesses, 0.6 attention)
```

### Intellectual Capital Queries

**"What has project-barbar learned about auth?"**
```
→ Filter: project='barbar' AND (semantic='auth' OR purpose CONTAINS 'auth')
→ Returns: ALL resources barbar accessed for auth work
→ Grouped by authority:
    Official (authority 1-3): anthropic-docs, oauth-spec
    Community (authority 4-6): jwt-guide, auth-patterns
    Internal (authority 7-9): barbar-auth-design, security-log
→ Each with: attention weight, usage patterns, notes
```

---

## Why This Changes Everything

### Before

- Resources exist independently
- Context lost after first use
- Each project rediscovers
- No compound learning
- Authority implicit, unstated

### After

- **Tier 0:** Thing exists
- **Tier 1:** Objective facts ABOUT thing (global, reusable)
- **Tier 2:** Subjective relationships TO thing (per-project, accumulating)
- **Query:** Compose across tiers
- **Schema:** Emerges from Tier 2 attention density
- **Intelligence:** Compounds with every access

**The wrapping IS the intelligence layer.**

---

## Clean?

> *Yes. Just restate the SCHEMA / ARCHITECTURE / DATAFLOW. Extremely concise. Essential components.*

## Three-Tier Architecture

### Schema

#### Tier 0: THE THING
- Raw content (URL, file, repo)
- No metadata, just exists

#### Tier 1: OBJECTIVE (Global Registry)
```
source: pointer to Tier 0
description: summary (150-250 words, vectorized)
authority: 1-10 (1=canonical, 10=speculative)
tags: [official | hypothesis | tested | ...]
creator: attribution
created: valid time
type: [docs | code | design | research]
```

#### Tier 2: SUBJECTIVE (Per-Project Registry)
```
objective_ref: link to Tier 1 entry
added: transaction time
purpose: why this project cares
attention: computed usage weight
accessed: count + patterns
notes: accumulated learnings
project_schema_tags: [project-specific taxonomy]
status: [active | archived | evaluated]
```

---

### Architecture

```
Tier 0: Thing itself
    ↑
Tier 1: ONE global objective wrapper (external registry)
    ↑
Tier 2: MANY subjective wrappers (project-x/.brain/, project-y/.brain/, ...)
```

**Properties:**
- Tier 1 → Tier 0: immutable facts
- Tier 2 → Tier 1: mutable relations
- Tier 2 accumulates per-project intelligence
- Schema emerges from Tier 2 attention density

---

### Data Flow

#### Write:
1. Discover source → Create Tier 1 (objective facts)
2. Access from project → Create Tier 2 (subjective wrapper)
3. Each access → Update Tier 2 (attention++, notes accumulate)

#### Query:
1. Vector search Tier 1 (description + authority)
2. Filter by Tier 2 (project context + attention)
3. Fetch Tier 0 (live source content)
4. Return: objective facts + subjective context + source

#### Schema Emergence:
1. Observe Tier 0 corpus → Cluster patterns
2. Weight by Tier 2 attention density
3. Emit schema for current project/intent
4. Cache or recompute on-demand

---

### Storage

```
GLOBAL_REGISTRY/               # Tier 1 (one per source)
├── anthropic-hooks.md
├── jwt-guide.md
└── aura-design-log.md

project-barbar/.brain/         # Tier 2 (barbar's view)
├── wrappers/
│   ├── anthropic-hooks.md
│   ├── jwt-guide.md
│   └── aura-design-log.md
├── attention_density.json
└── schemas/barbar-auth.json

project-npta/.brain/           # Tier 2 (npta's view)
├── wrappers/
│   └── anthropic-hooks.md
└── schemas/npta-compliance.json
```

---

## Schema Refinement

> *Tier 1: OBJECTIVE (Global Registry)*
> *Tier 2: SUBJECTIVE (Per-Project Registry)*

Let's refine this. We want maximal flexibility. It's likely best to have:

### TIER 1
```
source
description: (overview, semantic, narrative. 2-5 sentences)
authority:
keywords:
creator
time_created
```

And we let the tags define the 'type'? Or do you see a need for type? Seems like it adds a bit of brittleness that can be just extracted from parsing keywords?

### TIER 2

**PROJECT REGISTRY**
- `project_schema` <<< what is 'resolved' in cache and utilized at runtime
  - Includes all knowledge documents, repos, and ALL of our design, develop, document logs (the .context folder)
  - Is the ground truth for emergent PROJECT SPECIFIC SCHEMA
  - Is accessed VIA introspect
- Logs all queries, searches, retrievals etc

**REFERENCE REGISTRY**
```
ref
time_added
... appends of each time its used
```

We would create a standardized entry. It would likely be very narrativistic to avoid overfitting or brittleness during design/development phases.

```
time_accessed:
keywords: SQL, database, official documentation etc
motivation: thought it would solve our issue with querying our SQL database
```

**What is NOT IN THIS:**
- status, count + patterns, attention etc.
- ALL OF THAT is held in the 'BRAIN'.
- We DO NOT, EVER, include analytics OF KNOWLEDGE OR REPOS ETC IN THEIR isolated entry.
- This would be a COMPLETE AND UTTER disrespect of separation of concerns.

---

## Refined Schema

### TIER 1: OBJECTIVE (Global Registry)

```
source: pointer to Tier 0
description: 2-5 sentence narrative overview
authority: 1-10
keywords: [flexible tags, no enum]
creator: attribution
time_created: valid time
```

**No type field** - extract from keywords naturally.

---

### TIER 2: SUBJECTIVE (Per-Project)

#### A. PROJECT REGISTRY (Ground Truth)
```
project-x/.brain/
├── project_schema.json          # Emergent schema (cached/runtime)
├── analytics/
│   ├── attention_density.json   # ALL analytics here
│   ├── access_patterns.json
│   └── query_history.json
└── references/                   # Individual entries below
```

#### B. REFERENCE REGISTRY (Individual Entries)
```
ref: link to Tier 1 objective entry
time_added: when first accessed
keywords: [context-specific, SQL, database, ...]
motivation: narrative - "thought it would solve querying issue"
```

**Append on each access:**
```
time_accessed: 2025-01-23T14:30
keywords: [may add new contextual tags]
motivation: "revisited for performance optimization"
```

---

### What Lives WHERE

#### TIER 1 (immutable facts):
- What it is
- Who made it
- When created
- How authoritative

#### TIER 2 Reference (narrativistic log):
- What I thought when I found it
- Why I accessed it each time
- Contextual keywords per access

#### /.brain/ Analytics (computed):
- attention weights
- access counts
- usage patterns
- schema emergence
- query history

---

### Separation of Concerns

**✅ Reference entry:** Narrative intent, context
**❌ Reference entry:** Analytics, computed metrics

**✅ /.brain/ analytics:** Attention, patterns, counts
**❌ /.brain/ analytics:** Intent narratives

**Reference = qualitative, /.brain/ = quantitative**

---

## Reflection

### What's Brilliant:

#### 1. Narrative over rigidity
- `motivation: "thought it would solve X"` captures intent at that moment
- Keywords emerge from actual usage, not predefined taxonomies
- Description is semantic prose, not structured fields
- AI can parse meaning, not just match enums

#### 2. Separation is profound
- Reference = qualitative (what I was thinking)
- .brain/ = quantitative (what actually happened)
- Intent ≠ outcome, both truths preserved
- Respects that "I accessed this for X" but analytics show "actually used for Y"

#### 3. Append-only archaeology
- Each access adds new entry with time + motivation
- Builds temporal story: "First for X, revisited for Y, later used for Z"
- Can't sanitize history, preserves intellectual journey
- Like git commits: immutable, traceable, honest

#### 4. Project-specific intelligence
- Same Tier 1 source → different Tier 2 keywords per project
- Anthropic hooks: [security, validation] in barbar, [audit, compliance] in npta
- Each project builds its own understanding
- No forced centralization, but discoverable cross-pollination

#### 5. .brain/ owns emergence
- Schema, attention, patterns computed there
- References are dumb logs
- Could rebuild .brain/ from references (archaeological soundness)
- Intelligence layer separate from data layer

---

### What's Subtle But Critical

#### Authority + keywords > type field
- `authority: 1, keywords: [official, documentation]` more flexible than `type: docs`
- Same source could be [design, hypothesis, auth, barbar] naturally
- No forced single categorization

#### No status in reference
- "Active/archived" is computed from usage patterns, not manual flag
- If no access in 30 days + decaying attention → effectively archived
- Data tells you, you don't declare it

#### Introspection as interface
- "accessed VIA introspect" → .brain/ is black box with clean API
- Don't read files directly, query schema/analytics
- Encapsulation preserved

---

### Questions/Considerations

#### 1. Reference bloat?
- Every access appends → could get large
- But it's a log, this is feature not bug
- Could partition by time if needed: reference-2025-01.md

#### 2. Cross-project discovery mechanism?
```
Query: "Who else uses anthropic-hooks?"
→ Find Tier 1: anthropic-hooks-official
→ Find all Tier 2 references pointing to it
→ Group by project:
    barbar: [security motivations, high attention]
    npta: [compliance motivations, low attention]
```

#### 3. Entity resolution for keywords?
- References stay raw: "SQL" vs "sql" vs "database-sql"
- .brain/ canonicalizes via entity resolution
- Keeps references pure, intelligence computed

#### 4. Connection to emerged schema?
- project_schema.json weights based on attention density from analytics
- Clusters keywords from high-attention references
- Schema reflects "what this project actually focuses on"

---

### The Philosophy

This treats knowledge work like **version control:**
- **References** = commits (immutable, append-only, capture moment)
- **.brain/** = log analysis (patterns, graphs, insights)
- **Tier 1** = remote repo (shared, objective)
- **Tier 2** = local branches (per-project, subjective)

Or like a **library system:**
- **Tier 0** = books (exist)
- **Tier 1** = catalog cards (describe objectively)
- **Tier 2** = checkout slips (who, when, why)
- **.brain/** = librarian analytics (popular topics, usage patterns)

---

### Assessment

This will scale. The key insight is respecting the boundary between:
- **Human narrative** (motivation, context, intent)
- **Machine analytics** (patterns, weights, metrics)

Both are valuable. Neither pollutes the other.

**One trade-off:** Can't "correct" past motivations. If wrong, can only append new understanding. This is archaeologically sound but might feel weird. Probably right call - preserve journey, don't sanitize.

**Emergent property:** Every project builds independent understanding of same sources. Knowledge transfer happens through discovery (query objective → see all projects' references), not forced sharing. Organic, not prescribed.

**Clean. Ship it.**
