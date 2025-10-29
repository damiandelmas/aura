# Soft-Graph Innovation Package

**Session:** a86bc733-c4e3-4d88-b17f-2f9e330ca11a
**Date:** 2025-10-27
**Purpose:** Capture architectural innovations from session

---

## Overview

This package documents 4 key innovations that enable AURA to transcend traditional knowledge graph architectures:

1. **Soft-Graph: Runtime Discovery** - Zero-maintenance knowledge graphs
2. **Query-Adaptive Bundling** - Dynamic context assembly per query intent
3. **Batch Primitive** - Parallelization infrastructure for CLI operations
4. **Template Schema** - Creation-time enforcement for deterministic metadata

---

## Document Structure

Each innovation is documented at 3 resolution levels:

- **L1 (Vision):** Geometric, systemic, pattern-level thinking
- **L2a (Architecture Pattern):** Language-agnostic, mid-resolution design
- **L2b (Implementation):** Specific, code-ready specifications

**Naming convention:** `innovation-name.key-insight.L{1|2a|2b}-{vision|architecture|implementation}.md`

---

## Innovation 1: Soft-Graph Runtime Discovery

**The Core Insight:** Metadata as latent edges. Relationships materialized at query time, not stored.

**Files:**
- `soft-graph.runtime-discovery.L1-vision.md`
- `soft-graph.runtime-discovery.L2a-architecture.md`
- `soft-graph.runtime-discovery.L2b-implementation.md`

**Key Concepts:**
- O(0) precomputation vs O(n²) for traditional knowledge graphs
- Edges discovered via metadata predicates (file_path, session_id, timestamp)
- Graph constructed from top-k query results (k << n)
- Ephemeral graphs used for ranking, then discarded
- Zero maintenance overhead

**Why It Matters:**
Traditional knowledge graphs require expensive precomputation and storage.
Soft-graphs build only what's needed, when it's needed, from query results.

**Implementation:** ~300 lines
- `imem/src/imem/relationships.py` - get_siblings, get_temporal_chain, get_session_chain
- `imem/src/imem/graph_ops.py` - build_graph, apply_algorithm, export_graph

---

## Innovation 2: Query-Adaptive Bundling

**The Core Insight:** Graph structure adapts to query intent, not vice versa.

**Files:**
- `query-adaptive-bundling.dynamic-context.L1-vision.md`
- `query-adaptive-bundling.dynamic-context.L2a-architecture.md`
- `query-adaptive-bundling.dynamic-context.L2b-implementation.md`

**Key Concepts:**
- Same chunks, different bundling strategies per query
- Authority bundling (PageRank) - Find most-referenced
- Context bundling (siblings + session) - Complete genealogy
- Bridge bundling (centrality) - Connecting concepts
- Timeline bundling (temporal) - Evolution tracking

**Why It Matters:**
Knowledge graphs serve predefined relationships (fixed edge schema).
AURA serves query-adaptive relationships (runtime bundling strategies).

**Implementation:** ~400 lines
- `imem/src/imem/bundling/authority.py` - PageRank-based bundling
- `imem/src/imem/bundling/context.py` - Complete context assembly
- `imem/src/imem/bundling/bridges.py` - Centrality-based bridge discovery
- `imem/src/imem/bundling/timeline.py` - Temporal evolution tracking

---

## Innovation 3: Batch Primitive

**The Core Insight:** batch is infrastructure, not domain logic.

**Files:**
- `batch-primitive.parallelization-infrastructure.L1-vision.md`
- `batch-primitive.parallelization-infrastructure.L2a-architecture.md`
- `batch-primitive.parallelization-infrastructure.L2b-implementation.md`

**Key Concepts:**
- Generic parallelization for ANY CLI primitives
- Two formats: "queries" (sugar) and "parallel" (generic)
- Single bash call reduces latency (3 ops @ 100ms = 110ms vs 300ms)
- Observable, atomic, discoverable
- Extensible via operation registry

**Why It Matters:**
Enables efficient composition for Claude Code orchestration.
Not just multi-query, but parallelization infrastructure for all primitives.

**Implementation:** ~250 lines
- `imem/src/imem/batch.py` - batch_execute, execute_queries_format, execute_parallel_format
- Operation registry for extensibility
- ThreadPoolExecutor for parallelization

---

## Innovation 4: Template Schema

**The Core Insight:** Quality at creation, not extraction.

**Files:**
- `template-schema.creation-time-enforcement.L1-vision.md`
- `template-schema.creation-time-enforcement.L2a-architecture.md`
- `template-schema.creation-time-enforcement.L2b-implementation.md`

**Key Concepts:**
- Enforce template compliance at ingestion (reject invalid docs)
- Deterministic metadata extraction (regex, not LLM)
- Two-tier enforcement (required + optional fields)
- 100% metadata reliability vs ~70-85% for post-hoc extraction
- Enables reliable soft-graph relationship discovery

**Why It Matters:**
Post-hoc extraction is probabilistic. Template enforcement is deterministic.
Guaranteed metadata enables guaranteed queries.

**Implementation:** ~300 lines
- `imem/src/imem/templates/schema.py` - TEMPLATE_SCHEMA definition
- `imem/src/imem/templates/validator.py` - TemplateValidator class
- `imem/src/imem/templates/extractor.py` - MetadataExtractor class

---

## How These Innovations Work Together

```
Template Enforcement (Innovation 4)
    ↓ (guarantees metadata)
Soft-Graph Discovery (Innovation 1)
    ↓ (builds runtime graphs)
Query-Adaptive Bundling (Innovation 2)
    ↓ (assembles context per intent)
Batch Primitive (Innovation 3)
    ↓ (parallelizes efficiently)
Claude Code Orchestration
```

Foundation → Discovery → Bundling → Infrastructure → Intelligence

Each innovation enables the next.

---

## Architectural Uniqueness

### vs Traditional Knowledge Graphs

| Aspect | Knowledge Graphs | AURA Soft-Graph |
|--------|------------------|-----------------|
| Edge storage | Precomputed (O(n²)) | On-demand (O(k²)) |
| Maintenance | Rebuild on change | Zero (lazy construction) |
| Bundling | Fixed schema | Query-adaptive |
| Metadata | Post-hoc (LLM) | Creation-time (deterministic) |
| Parallelization | N/A | Infrastructure primitive |

### vs RAG Systems

| Aspect | RAG | AURA |
|--------|-----|------|
| Context | Top-k chunks | Query-adaptive bundled context |
| Relationships | Implicit | Explicit (via soft-graph) |
| Metadata | Best-effort | Guaranteed (template-enforced) |
| Graph ops | None | PageRank, centrality, temporal |

---

## Implementation Priority

1. **Template Schema** (Foundation)
   - ~300 lines
   - 1-2 days
   - Enables all other innovations

2. **Soft-Graph Discovery** (Core)
   - ~300 lines
   - 2 days
   - siblings, temporal, session primitives + graph ops

3. **Batch Primitive** (Infrastructure)
   - ~250 lines
   - 1.5 days
   - Parallelization for efficient orchestration

4. **Query-Adaptive Bundling** (Intelligence)
   - ~400 lines
   - 2 days
   - Bundling strategies for different intents

**Total:** ~1250 lines, 6-7 days

---

## Key Architectural Principles

1. **Zero Precomputation:** Build only what's needed at query time
2. **Deterministic Metadata:** Enforce at creation, not extract post-hoc
3. **Query-Adaptive Structure:** Graph adapts to intent, not vice versa
4. **Infrastructure as Primitive:** Parallelization orthogonal to domain logic
5. **Observation-Driven Evolution:** Mine usage patterns, codify successful compositions

---

## Usage Patterns

### Authority Discovery
```bash
imem batch '{
  "queries": [
    {"text": "auth patterns", "filters": {"decisions": true}},
    {"text": "auth patterns", "filters": {"patterns": true}}
  ],
  "combine": true,
  "graph": {"algorithm": "pagerank", "top": 5}
}'
```

### Complete Context
```bash
decision=$(imem develop search "JWT auth" --decisions --limit 1)
siblings=$(imem siblings $decision)
conversation=$(imem session $decision)
# Claude assembles complete context
```

### Bridge Concepts
```bash
results=$(imem develop search "chunking + indexing" --limit 20)
graph=$(imem graph build $results)
bridges=$(imem graph apply $graph centrality)
```

### Evolution Timeline
```bash
original=$(imem develop search "JSONB decision" --decisions --limit 1)
evolution=$(imem temporal $original --direction forward)
# Returns chronological chain
```

---

## Cross-Reference

### Related Sessions
- Previous session: `ca22384b-3a6d-4821-8b70-2aa1a89ea4ba` (see `README.md`)
  - Flippable chunks, cross-project transfer, dual-layer architecture

### Main Architecture Docs
- `../02_current/251025-1202_architecture.md` - Five-layer architecture
- `../02_current/251025-1203_roadmap.md` - Implementation roadmap
- `../02_current/251025-1201_vision.md` - Knowledge genealogy vision
- `../02_current/251025-1200_discovery.md` - Competitive positioning

### Session Transcript
- `.claude/.convs/a86bc733-c4e3-4d88-b17f-2f9e330ca11a.md`

---

## The Bottom Line

These innovations collectively enable AURA to transcend traditional knowledge graphs:

**Not:** "RAG with knowledge graphs"
**But:** "Knowledge graphs as query-time views over metadata-enriched chunks with runtime relationship discovery, query-adaptive bundling, and deterministic schema enforcement"

**Foundation:** Template-enforced metadata
**Core:** Soft-graph runtime discovery
**Intelligence:** Query-adaptive bundling
**Infrastructure:** Batch parallelization

**Result:** Zero-maintenance institutional memory with graph-level reasoning power.

---

**4 innovations × 3 resolution levels = 12 documents**

Total architectural capture from session focused on:
- Runtime relationship discovery (zero maintenance)
- Query-adaptive context assembly (transcends fixed schemas)
- Parallelization infrastructure (efficient orchestration)
- Deterministic metadata guarantees (reliable queries)

**This is the architectural foundation for soft-graph knowledge navigation.**
