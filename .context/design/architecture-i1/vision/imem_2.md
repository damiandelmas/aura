# IMEM: Extremely Concise Overview

## What it is

First implementation of FlexGraph methodology. Structured knowledge retrieval for AI-generated development changelogs.

## How it works

- **AI agents write template-compliant docs** → guaranteed metadata (100% reliability)
- **LlamaIndex chunks at H2/H3-level** → ENTIRE changelog structure (Overview, Decisions, Patterns, Failures, Implementation, Constraints, Audit) = separate vectors, programmatically retrievable by `section_type`
- **4 compositional primitives** (siblings, genealogy, temporal, cross_phase) compose flexibly at query-time
- **Query-time graphs built from metadata predicates** → graph topology determines template structure
- **Templates convey relationships via structure** (timeline/authority/anti-pattern), not ranking

## Key philosophy

- **Decisions valid until explicitly superseded** (not age-based)
- **Silence = affirmation** (5-week-old = yesterday's if not overturned)
- **Structure aids AI comprehension** (not just similarity ranking)

## Status

- ~75% complete (primitives, compose orchestrator, dual-layer all working)
- **Missing:** BRAIN persistence (SQLite for supersession tracking, observable usage, entity resolution)

## Why different from research systems

- **Controls document creation** → metadata synergy (research accepts any input)
- **Query-time ephemeral graphs** (research stores persistent entity graphs)
- **Validity-until-overturned** (research uses recency bias + frequency)
- **Graph reveals structure** (research ranks by authority)

## Bottom line

AI writes compliant logs → guaranteed edges → compositional retrieval → graph-informed structure → AI comprehension.
