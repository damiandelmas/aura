# IMEM Architecture

**FlexGraph methodology applied to coding agent memory**

---

## Domain

IMEM is a memory system for AI coding agents working on software projects.

**Content:** Software development changelogs
- Design decisions (what we chose, why)
- Implementation details (what we built, how)
- Constraints (limitations, trade-offs)
- Failures (what didn't work, lessons learned)
- Patterns (reusable learnings)

**Created by:** AI agents during development
**Used by:** AI agents for context retrieval

---

## Four-Phase Lifecycle

```
design → designate → develop → document
```

**design**: Abstract decisions, architectural choices, trade-off analysis
**designate**: Planning, task breakdown, implementation approach
**develop**: Implementation changelogs, code decisions, technical details
**document**: Documentation, guides, architecture explanations

**Genealogy:** Each phase links back via session_id
- Conversation (raw thinking) → design → develop → document
- Full reasoning chain from idea to implementation

---

## Template Structure

### Decisions Section
```markdown
### Decision Name
- Context: Why this decision arose
- Solution: What was chosen
- Rationale: Why this solution (optional)
- Alternatives: What was rejected (optional)
```

### Constraints Section
```markdown
### Constraint Name
- Description: What the limitation is
- Impact: How it affects system
- Mitigation: How we work around it (optional)
```

### Failures Section
```markdown
### Failure Name
- Attempted: What we tried
- Why Failed: Root cause
- Lesson: What we learned
```

### Patterns Section
```markdown
### Pattern Name
- Pattern: The reusable approach
- When: Scenarios where it applies
- Approach: How to apply it
```

**Result:** 100% metadata compliance (section_type, has_rationale, has_alternatives known deterministically)

---

## How FlexGraph Pillars Apply to IMEM

### 1. Entity Resolution

**Technical terms drift across changelogs:**
- "jwt" → "JWT" → "jwt-tokens" → "auth.jwt"
- "redis" → "Redis" → "redis-cache"
- "variant-system" → "variant system" → "prompt variants"

**IMEM Solution:**
- Weekly LLM batch clusters technical terms
- Canonical map: `"auth.jwt": ["jwt", "JWT", "jwt-tokens"]`
- Queries expand: Search "jwt" finds all variants

See: [entity-resolution.md](./entity-resolution.md)

---

### 2. Schema Introspection

**Brother agent problem:** New Claude session doesn't know what metadata exists

**IMEM Solution:**
- `imem schema` returns available fields programmatically
- `imem schema --examples` shows copyable compose queries
- AI agents discover capabilities without reading docs

**Enables:**
- Zero-friction onboarding for future sessions
- Brother agents query "what can I filter on?"

See: [schema-introspection.md](./schema-introspection.md)

---

### 3. Knowledge Graph

**Current state:** 60-80% there (implicit graph via metadata)
- session_id → genealogy edges (ephemeral)
- file_path → sibling edges (ephemeral)
- timestamp + semantic → temporal edges (ephemeral)

**IMEM Proposal:** Make explicit in SQLite
```sql
-- Persistent edges
edges(from_id, to_id, edge_type, weight)

-- Edge types
- sibling: Same changelog file
- genealogy: Same session_id (conversation → design → develop)
- temporal: Semantic similarity + timestamp ordering
- cross_phase: Related content across phases
```

**Enables:**
- PageRank → Find authoritative decisions
- Centrality → Find bridge concepts
- Fast traversal without recomputation

See: [knowledge-graph.md](./knowledge-graph.md)

---

### 4. BRAIN Persistence

**Three metadata layers:**

**Layer 1: Static** (Qdrant, never changes)
- timestamp, type, phase, session_id, content

**Layer 2: Learned** (SQLite, changes continuously)
- reference_count (incremented on every query)
- last_accessed (updated real-time)
- pagerank_score (recomputed nightly)
- superseded_by (detected weekly via LLM)

**Layer 3: Composed** (ephemeral, assembled at query time)
- Temporal position (current vs superseded)
- Confidence scores
- Contextualized views

**IMEM Use Case:**
- Track which decisions are most referenced (authority)
- Detect when decisions are superseded (soft deprecation)
- Show confidence based on age + reference count

See: [brain-persistence.md](./brain-persistence.md)
See: [adaptive-updates.md](./adaptive-updates.md)

---

### 5. Graph-Informed Templates

**Template structure affects AI comprehension**

**IMEM Templates:**

**story.j2** (Narrative reconstruction)
- Used when: High genealogy + cross-phase links
- Structure: Conversation → Design → Failures → Implementation → Patterns

**evolution.j2** (Timeline)
- Used when: Strong temporal chain (3+ related chunks over time)
- Structure: Chronological progression showing refinements

**anti-pattern.j2** (Failure compilation)
- Used when: Multiple Failures sections + single Decision
- Structure: What failed → What worked → Lessons

**authority.j2** (Canonical reference)
- Used when: High PageRank + many siblings
- Structure: Authoritative decision + related context

**Adaptive selection:**
```python
# Graph reveals: High centrality + temporal chain
→ Select evolution.j2 template
→ Structure shows progression over time
```

See: [graph-templates.md](./graph-templates.md)

---

### 6. Adaptive Learning

**Update frequencies stratified by cost/value:**

**Real-time (every query):**
- reference_count++ (~1ms)
- Track which decisions are queried most

**Nightly batch:**
- Recompute PageRank (~5min for 10K chunks)
- Update age_months
- Recalculate centrality scores

**Weekly batch:**
- Entity resolution (cluster technical terms) - $0.01
- Supersession detection (semantic comparison) - $0.05
- Pattern mining (discover reusable patterns) - $0.10

**IMEM Use Case:**
- Popular decisions surface via reference_count
- Authoritative decisions found via PageRank
- Entity map keeps term variants synchronized

See: [adaptive-updates.md](./adaptive-updates.md)

---

## Architecture Stack

```
┌─────────────────────────────────────────────────┐
│ Qdrant (Immutable Source)                      │
│ - Changelogs as written (design/develop/doc)   │
│ - Vector embeddings (E5-Large-v2)              │
│ - Metadata: session_id, phase, section_type    │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│ SQLite graph.db (BRAIN + Knowledge Graph)      │
│                                                 │
│ nodes: Static metadata from Qdrant             │
│ edges: sibling, genealogy, temporal, cross_phase│
│ brain_stats: reference_count, last_accessed    │
│ brain_metrics: pagerank_score, superseded_by   │
│ entity_map: canonical → variants               │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│ Discovery Primitives (Python)                  │
│                                                 │
│ get_siblings(id, section_types, limit)         │
│ get_genealogy(id) → conversation chain         │
│ get_temporal(id, direction)                    │
│ cross_phase(id, target_phase)                  │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│ Compose Orchestrator                           │
│                                                 │
│ imem compose '{                                 │
│   "search": {...},                              │
│   "discovery": {siblings, genealogy, temporal}, │
│   "graph": {algorithm, top},                    │
│   "output": {template}                          │
│ }'                                              │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│ Graph-Informed Templates                       │
│ story.j2 | evolution.j2 | anti-pattern.j2      │
└─────────────────────────────────────────────────┘
```

---

## Use Cases

### Explain Decision
**Query:** "Why did we choose JWT authentication?"

**Composition:**
```json
{
  "search": {"text": "JWT auth", "phase": "develop", "limit": 1},
  "discovery": {
    "genealogy": true,
    "siblings": {"section_types": ["Decisions", "Failures", "Patterns"]},
    "cross_phase": "design"
  },
  "output": {"template": "story"}
}
```

**Returns:**
- Origin conversation (brainstorming, debugging)
- Design decisions (abstract choices)
- Failed approaches (what didn't work)
- Working solution (implementation)
- Extracted patterns (reusable learnings)

---

### Trace Evolution
**Query:** "How did caching strategy evolve?"

**Composition:**
```json
{
  "search": {"text": "caching", "phase": "develop"},
  "discovery": {
    "temporal": {"direction": "both"},
    "siblings": {"section_types": ["Patterns"], "order_by": "timestamp"}
  },
  "output": {"template": "evolution"}
}
```

**Returns:**
- Earlier attempts (temporal: before)
- Current implementation
- Later refinements (temporal: after)
- Patterns extracted over time

---

### Find Anti-Patterns
**Query:** "What approaches didn't work for authentication?"

**Composition:**
```json
{
  "search": {"text": "authentication"},
  "discovery": {
    "siblings": {"section_types": ["Failures"]}
  },
  "output": {"template": "anti-pattern"}
}
```

**Returns:**
- All Failures sections across related changelogs
- What was attempted, why it failed, lessons learned

---

## Observable Usage → Presets

**After 30 uses of "explain decision" composition:**

Captured as `/explain-decision` slash command:
```markdown
# .claude/commands/explain-decision.md

Find a decision and reconstruct complete context.

Usage: /explain-decision <query>

Internally expands to:
imem compose '{"search": {...}, "discovery": {"genealogy": true, "siblings": {...}}}'
```

**Self-improving:** Preset library grows from proven patterns, not designer predictions.

---

## Status

**Phase 1-5:** Template-as-schema validated ✅
- AI agents write changelogs
- Guaranteed metadata
- Four-phase lifecycle working

**Phase 6-7:** Compositional primitives (in development)
- Discovery primitives built
- Compose orchestrator working
- Templates basic (need graph-informed selection)

**V2 (Planned):**
- SQLite knowledge graph (make implicit graph explicit)
- BRAIN persistence (reference counts, PageRank)
- Entity resolution (technical term clustering)
- Schema introspection (imem schema command)

---

## Related Documents

**Methodology:**
- [../methodology/flexgraph.md](../methodology/flexgraph.md) - General FlexGraph methodology

**Architecture (Six Pillars):**
- [entity-resolution.md](./entity-resolution.md)
- [schema-introspection.md](./schema-introspection.md)
- [knowledge-graph.md](./knowledge-graph.md)
- [brain-persistence.md](./brain-persistence.md)
- [graph-templates.md](./graph-templates.md)
- [adaptive-updates.md](./adaptive-updates.md)

**Implementation:**
- [../.modules/flex-graph/02_current/](../.modules/flex-graph/02_current/) - Detailed specs

**Business Logic:**
- [../business-logic/AI-FIRST-USER.md](../business-logic/AI-FIRST-USER.md)
- [../business-logic/IMMUTABLE-SOURCE.md](../business-logic/IMMUTABLE-SOURCE.md)
- [../business-logic/COMPOSITIONAL-PRIMITIVES.md](../business-logic/COMPOSITIONAL-PRIMITIVES.md)
- [../business-logic/USAGE-DRIVEN.md](../business-logic/USAGE-DRIVEN.md)

---

**IMEM = FlexGraph applied to coding agents. Template-as-schema → 6 pillars → self-improvement.**
