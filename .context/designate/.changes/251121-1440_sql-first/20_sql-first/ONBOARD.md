# ONBOARD: SQLite-First Architecture

## Overview

Phase 1-3 complete (~19 hours). Core architecture shipped: SQLite-first storage, processor chains, domain separation, 72% CLI reduction. Phases 4-6 (~10 hours) complete the vision: split VectorStore protocol, add semantic relationship layer, integrate git validation. All patterns validated against production systems (Vespa, Graphiti, AgentDB).

---

## Documentation

### Vision & Architecture
- **00_overview.md** - What shipped (Phases 1-3), what's missing (Phases 4-6), gap analysis
- **01_architecture.md** - Domain structure, storage topology, protocol design (includes Phase 4 fix)

### Implementation
- **02_plan.md** - Phases 4-6 implementation guide with concrete code examples

### Reference
- **03_optional_enhancements.md** - HNSW backend, enhanced entity consolidation (post-Phase 6)
- **04_patterns_applied.md** - Patterns from 5-system review (Vespa, Graphiti, AgentDB)

---

## Phase Status

### ✅ Phase 1-3: Foundation (Complete)
- SQLite-first storage with VectorStore abstraction
- Processor chain pattern (declarative pipelines)
- Domain separation (cli/, compile/, manage/, compose/)
- Two-layer resolution (COMPILE + MANAGE)
- CLI composition root (1772 → 501 LOC)

**Changelogs:** 251117-1900, 251117-2015, 251117-2045, 251117-2117, 251117-2119, 251117-2121

### ⏳ Phase 4: Protocol Separation (~4h)
Split VectorStore → VectorSearch + GraphStore, extract Qdrant to vector-only, implement discovery processors, add relationships table

### ⏳ Phase 5: Semantic Layer (~3h)
Build manage/analyzer.py for semantic detection, add `imem analyze` command, implement get_implementations()

### ⏳ Phase 6: Git Integration (~3h)
Parse commits → chunks, temporal validation (manage/temporal.py), mark superseded decisions

---

## Quick Start

**Read 00_overview.md** for current state and gap analysis

**Read 02_plan.md** for Phase 4-6 implementation details with code examples

**Check 01_architecture.md** for protocol split design and domain structure
