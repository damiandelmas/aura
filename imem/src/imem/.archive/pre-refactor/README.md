# Pre-Refactor Archive

Legacy files from before SQLite-first architecture refactor (Phases 1-3).

**Archive Date:** 2025-11-17
**Refactor Commits:** 2208be8 (Phase 1), 539f2b3 (Phase 2), b0c096e (Phase 3)

---

## Archived Files (Partial Cleanup)

### ✅ Archived in This Session

- **cli.py** (1772 LOC) - Monolithic CLI
  - **Replaced by:** `cli_new.py` + `cli/main.py` + `cli/commands.py`
  - **Reduction:** 72% (1772 → 506 LOC)
  - **Reason:** No longer imported by any active code

- **cli.py.backup** - Duplicate of cli.py
  - **Action:** Deleted (not archived)
  - **Reason:** Exact copy, no unique content

- **compose.py** (679 LOC) - Hardcoded retrieval pipeline
  - **Replaced by:** `compose/orchestrator.py` (196 LOC)
  - **Pattern:** Processor chain (declarative vs procedural)
  - **Reason:** Only imported by cli.py (also archived)

### ⏳ Kept (Still Used by Active Code)

- **search.py** (587 LOC)
  - **Used by:** `ingest.py`, `__init__.py` exports
  - **Plan:** Archive after `ingest.py` refactored into `compile/indexer.py`

- **enhanced.py** (445 LOC)
  - **Used by:** `__init__.py` exports
  - **Plan:** Archive after package API cleanup

---

## Replacement Mapping

| Old File | New Location | LOC Change | Pattern |
|----------|--------------|------------|---------|
| cli.py | cli_new.py + cli/main.py + cli/commands.py | 1772 → 506 (-72%) | Composition root |
| compose.py | compose/orchestrator.py | 679 → 196 (-71%) | Processor chain |
| search.py | compose/processors/search.py | 587 → 100 (-83%) | VectorStore protocol |
| enhanced.py | storage/qdrant_backend.py | 445 → 431 (-3%) | Backend abstraction |

**Total Reduction:** ~3,000 LOC → ~1,233 LOC (59% reduction in refactored modules)

---

## Architecture Evolution

### Before (Monolithic)
```
cli.py (1772 LOC)
├── Direct imports: ingest, search, enhanced, compose
├── Per-command initialization (DB, embedder)
└── Business logic mixed with CLI routing

compose.py (679 LOC)
├── Hardcoded pipeline stages
├── Procedural control flow
└── Coupled to Qdrant implementation
```

### After (Domain-Separated)
```
cli_new.py (27 LOC) + cli/ (477 LOC)
├── Composition root (shared resources)
├── Controller delegation (compile, manage, compose)
└── Thin command wrappers

compose/orchestrator.py (196 LOC)
├── Config-driven chain builder
├── Processor abstraction (reorderable stages)
└── Backend polymorphism via VectorStore protocol
```

---

## Restoration Instructions

### Restore Individual Files

```bash
# From git history (before archival)
git show ef0fed3~1:src/imem/cli.py > cli.py
git show ef0fed3~1:src/imem/compose.py > compose.py
```

### Restore from Archive

```bash
cp .archive/pre-refactor/cli.py cli.py
cp .archive/pre-refactor/compose.py compose.py
```

### Test Against Legacy Implementation

```bash
# Checkout pre-refactor commit
git checkout 2208be8~1

# Run old CLI
python -m imem.cli index develop --limit 5

# Compare with new CLI
git checkout sql-first
python src/imem/cli_new.py index develop --limit 5
```

---

## Phase 3 Refactor Summary

**Commits:**
- `2208be8` - Phase 1: Storage abstraction (VectorStore protocol)
- `539f2b3` - Phase 2: Processor chain (declarative pipelines)
- `4884372` - Phase 3.0: Domain extraction (compile, manage)
- `b0c096e` - Phase 3.1: CLI composition root
- `ef0fed3` - Phase 3.2: Critical bug fixes

**Time Investment:** ~12 hours total

**Key Patterns Applied:**
- Composition root (dependency injection)
- Processor chain (strategy pattern)
- Protocol abstraction (polymorphism)
- Two-layer resolution (COMPILE + MANAGE)

**Result:** Production-ready architecture with 10 passing integration tests.

---

## Future Cleanup

**Next files to archive (after refactoring):**

1. **search.py** → After `ingest.py` uses `compose/processors/search.py`
2. **enhanced.py** → After package exports removed
3. **ingest.py** → After logic moved to `compile/indexer.py`

**Estimated:** 2-3 hours to complete full cleanup
