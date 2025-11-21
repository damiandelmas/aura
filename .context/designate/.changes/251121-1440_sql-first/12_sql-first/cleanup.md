Perfect! Here's the cleanup plan:

---

## **Files to Archive (Move to `.archive/`)**

### **Legacy Files (No Longer Used):**

```bash
mkdir -p src/imem/.archive/pre-refactor

# 1. OLD CLI (replaced by cli_new.py + cli/)
src/imem/cli.py                  → .archive/pre-refactor/cli.py
src/imem/cli.py.backup           → DELETE (duplicate)

# 2. OLD COMPOSE (replaced by compose/orchestrator.py)
src/imem/compose.py              → .archive/pre-refactor/compose.py

# 3. OLD SEARCH (functionality now in processors/)
src/imem/search.py               → .archive/pre-refactor/search.py

# 4. OLD ENHANCED (replaced by storage/qdrant_backend.py)
src/imem/enhanced.py             → .archive/pre-refactor/enhanced.py
```

---

### **Files to KEEP (Still Used):**

```bash
# Entry point
src/imem/cli_new.py              ✅ New CLI entry point

# CLI composition root
src/imem/cli/                    ✅ New structure
├── __init__.py
├── main.py                      ✅ IMEMCLI composition root
└── commands.py                  ✅ Command definitions

# Core infrastructure (still used)
src/imem/config.py               ✅ Configuration
src/imem/registry.py             ✅ Project registry (should move to manage/ later)
src/imem/qdrant_service.py       ✅ Docker service management (wrapped by service/)

# Legacy ingestion (used by compile/indexer.py)
src/imem/ingest.py               ✅ KEEP - Still imports EnhancedModularIngest
src/imem/introspect.py           ✅ KEEP - Used by manage/ domain

# Parse utilities
src/imem/parse/                  ✅ KEEP - Used by indexing
```

---

### **Refactored Structure:**

**New (after cleanup):**
```
src/imem/
├── cli_new.py                   # Entry point
├── cli/                         # Composition root + commands
├── core/                        # Chain, processors
├── compile/                     # Indexer, resolver
├── manage/                      # Introspection, entity resolver
├── service/                     # Qdrant lifecycle
├── storage/                     # VectorStore backends
├── compose/                     # Orchestrator, processors
│
├── config.py                    # Config (keep)
├── registry.py                  # Registry (keep for now)
├── qdrant_service.py            # Service (keep, wrapped)
├── ingest.py                    # Legacy ingestion (keep, used)
├── introspect.py                # Introspection (keep, used)
├── parse/                       # Parse utilities (keep)
│
└── .archive/pre-refactor/       # Legacy files
    ├── cli.py                   # Old 1772 LOC monolith
    ├── compose.py               # Old hardcoded pipeline
    ├── search.py                # Old search module
    └── enhanced.py              # Old Qdrant wrapper
```

---

## **Archive Script:**

```bash
#!/bin/bash
# Archive legacy files from SQLite-first refactor

cd src/imem

# Create archive directory
mkdir -p .archive/pre-refactor

# Move legacy files
echo "📦 Archiving legacy files..."

mv cli.py .archive/pre-refactor/cli.py
rm cli.py.backup  # Duplicate of cli.py
mv compose.py .archive/pre-refactor/compose.py
mv search.py .archive/pre-refactor/search.py
mv enhanced.py .archive/pre-refactor/enhanced.py

# Create README in archive
cat > .archive/pre-refactor/README.md <<'EOF'
# Pre-Refactor Archive

Legacy files from before SQLite-first architecture refactor (Phase 1-3).

## Archived Files

- **cli.py** (1772 LOC) - Monolithic CLI, replaced by cli_new.py + cli/
- **compose.py** (679 LOC) - Hardcoded pipeline, replaced by compose/orchestrator.py
- **search.py** (587 LOC) - Search logic, replaced by compose/processors/search.py
- **enhanced.py** (445 LOC) - Qdrant wrapper, replaced by storage/qdrant_backend.py

## Replacement Mapping

| Old File | New Location | Notes |
|----------|--------------|-------|
| cli.py | cli_new.py + cli/main.py + cli/commands.py | 72% LOC reduction |
| compose.py | compose/orchestrator.py | Processor chain pattern |
| search.py | compose/processors/search.py | Backend-agnostic |
| enhanced.py | storage/qdrant_backend.py | VectorStore protocol |

## Restoration

If needed, restore via:
```bash
git show phase-2-domain-extraction:src/imem/cli.py > cli.py
```

Archive created: $(date)
Refactor tags: phase-1-storage-abstraction, phase-2-processor-chain, phase-3-domain-separation
EOF

echo "✅ Archive complete"
ls -lh .archive/pre-refactor/
```

---

## **Execute Cleanup?**

Want me to:
1. **Run the archive script now?** (moves 4 files to `.archive/`)
2. **Show you the diff first?** (verify nothing breaks)
3. **Skip cleanup for now?** (keep everything until fully tested)

**My recommendation:** Run it now. Those files aren't used by anything, and we have git history + tags to restore if needed.

What do you prefer?