# SQLite-First Refactor: Start Here

**Status:** Phase 3 in progress (75% complete)

---

## For New Agents

Read these files in order:

1. **STATUS.md** - What's built, what works, what doesn't
2. **HANDOFF.md** - Your next steps (4 tasks, 3-4 hours to complete)
3. **02_plan.md** - Technical reference for Phase 3 details

---

## Quick Context

**Completed:**
- ✅ Phase 1: Storage abstraction (VectorStore protocol + SQLite/Qdrant backends)
- ✅ Phase 2: Processor chain (Chain + async helpers + multi-phase ranking)

**In progress:**
- ⏳ Phase 3: Domain separation (80% done - need CLI composition root + resolution tables)

**Next:** See **HANDOFF.md** for 4 specific tasks to complete Phase 3.

---

## Architecture Overview

**Storage:**
- SQLite = primary (metadata + content, always indexed)
- Qdrant = optional (vectors + ID reference only)
- Backends swappable via VectorStore protocol

**Pipeline:**
- Processor chain pattern (declarative, testable)
- Bounded concurrency (prevents SQLite crashes)
- Multi-phase ranking (25x performance boost)

**Resolution (Two Layers):**
- COMPILE: Structure normalization (phase/section_type variations → canonical)
- MANAGE: Entity normalization (project-scoped, "jwt"/"JWT" → canonical)

**Target:**
- CLI < 600 LOC (currently 1772 LOC)
- Domain separation: compile/ manage/ storage/ compose/
- Shared DB/embedder initialization

See **01_architecture.md** for full details.
