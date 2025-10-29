# Template Schema: Creation-Time Enforcement

**Session:** a86bc733-c4e3-4d88-b17f-2f9e330ca11a
**Level:** Vision (L1)
**Date:** 2025-10-27

## The Paradigm Shift

Post-hoc systems (MindsDB, Azure, Microsoft GraphRAG):
- Ingest any markdown
- Extract metadata via LLM
- Probabilistic, best-effort
- No guarantees

AURA:
- Enforce template at creation time
- Guaranteed metadata
- Deterministic, reliable
- Queryable structure

## The Core Insight

Knowledge quality is determined at creation, not extraction.

If documents follow template → metadata is guaranteed
If documents don't follow template → reject at ingestion

No LLM guessing. No probabilistic extraction. Schema enforcement.

## The Template as Schema

Example template:
```markdown
## Decisions
### Use JWT Authentication
- **Context**: Session auth doesn't scale
- **Solution**: Migrate to stateless JWT
- **Rationale**: Enables load balancing
```

Schema enforcement:
- H2 (##) = Section type (Decisions/Constraints/Patterns)
- H3 (###) = Section name
- Bold fields (**Context**, **Solution**) = Required metadata

Ingestion validates:
- ✓ H2 present → section_type extracted
- ✓ H3 present → section_name extracted
- ✓ **Context** + **Solution** present → has_context, has_solution = true

Missing required fields → ingestion fails.

## The Unique Advantage

Post-hoc extraction:
```
Input: Any markdown
Process: LLM extraction
Output: Probabilistic metadata
Reliability: ~70-85%
```

Template enforcement:
```
Input: Template-compliant markdown
Process: Pattern matching
Output: Guaranteed metadata
Reliability: 100% (or reject)
```

## Why This Matters

Soft-graph discovery requires reliable metadata:
- siblings requires file_path (guaranteed)
- session requires session_id (guaranteed)
- temporal requires timestamp (guaranteed)

Post-hoc systems can't guarantee metadata presence.
AURA can → enables deterministic relationship discovery.

## The Trade-off

Flexibility vs Reliability

Post-hoc: Accepts any input, extracts what it can
AURA: Rejects invalid input, guarantees structure

For institutional memory: Reliability > Flexibility

Documents created by AI agents (Claude Code) → template compliance automatic
Documents created by humans → validation ensures quality

## The Architectural Choice

Could have:
- Accepted any markdown + LLM extraction
- Best-effort metadata
- Probabilistic queries

Why template enforcement wins:
- Deterministic metadata → reliable queries
- Validation feedback → quality improvement
- Git-native → diffs show structure changes
- Agent-friendly → AI generates compliant docs

## The Pattern

Template = schema as markdown structure

Not JSON schema. Not database DDL. Markdown patterns.

Human-readable. Git-diffable. Agent-generatable.

## Two-Tier Enforcement

Required fields: MUST be present (Context, Solution)
Optional fields: CAN be missing (Rationale, Alternatives)

Schema defines structure, not presence for optional fields.

Benefits:
- Lower barrier (minimal decisions: just Context + Solution)
- Progressive elaboration (add details later)
- Still deterministic (can query for optional field presence)

## The Innovation

Not "better metadata extraction" but "metadata guarantees via creation-time schema enforcement."

Shift quality left: Validate at creation, not extraction.
Reliable metadata enables reliable queries.

Foundation for everything else (soft-graph, bundling, etc.)
