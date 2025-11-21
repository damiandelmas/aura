---
session_id: 7b8d151d-3cfd-482f-a4e6-d9da4516bac5
---

# Extraction Strategy: Qdrant Isolation

**Goal:** Understand current coupling, separate concerns to enable protocol-based architecture

---

## Conceptual Approach

### Phase 1: Extract & Isolate
- Identify Qdrant-coupled code (likely `ingest.py`, `search.py`, `enhanced.py`)
- Move to `legacy/v2/` or similar isolation directory
- Document what this code does (features, capabilities, patterns)
- Mark broken dependencies with clear TODOs
- Preserve as reference implementation

### Phase 2: SQL-First Primary Path
- Establish SQLite as working baseline
- Ensure VectorStore protocol usage (not concrete implementations)
- Separate core logic from backend choice
- Vectors become optional modality

### Phase 3: Study Legacy as Specification
- Analyze what capabilities exist in isolated code
- Examples might include:
  - Field detection patterns
  - Scoring formulas
  - Collection routing
  - Search composition
- Decide what to preserve, what to rebuild, what to defer

### Phase 4: Clean Re-integration (If Needed)
- If Qdrant remains useful, implement as protocol-compliant backend
- Reference legacy patterns without copying coupling
- Make it one option, not the only path

---

## Why Extraction (Not Deletion or Refactor)

**Extraction Preserves:**
- Working code as specification
- Proven patterns and logic
- Ability to compare v2 vs v3 results
- Reference for "what did we build before?"

**Extraction Enables:**
- Clean protocol-based architecture
- Independent testing of SQL path
- Walking skeleton approach (one feature at a time)
- No feature degradation (v2 shows what must work)

**Extraction Prevents:**
- Mixed concerns (old + new tangled)
- Lost tribal knowledge
- Regression ("v2 could do X, v3 can't")
- Big-bang rewrite risk

---

## Architectural Principle

**v2 = What** (features, capabilities, proven patterns)
**v3 = How** (clean architecture, protocol abstraction, domain separation)

Integration combines proven features with clean structure.

---

## Current vs Intended State

**Likely Current Pattern:**
```
Indexing/compilation code → possibly hardcoded to specific backend
                         → may have parallel paths (SQL + vector service)
                         = Could be tangled, assess actual state
```

**Intended Pattern:**
```
Indexing/compilation code → VectorStore protocol only
                         ↓
Runtime/config chooses backend implementation
                         ↓
Core logic backend-agnostic
```

**Key Difference:** Core should depend on abstraction, not concrete backends.

---

## What Makes a "Good Extraction"

**Identify files for isolation:**
- Files directly coupled to specific backend (find through import analysis)
- Likely candidates based on naming/purpose
- Assess actual coupling, don't assume

**Document in isolation directory README:**
- What features the code provides
- What patterns are worth preserving
- Why it's being isolated (coupling, not protocol-based)
- How to use as reference (specification, not active dependency)

**Handle broken imports:**
- Mark clearly where coupling exists
- Add TODO markers pointing to protocol-based approach
- Don't fix everything at once—isolate first, refactor later

**Keep one path working:**
- Ensure at least one end-to-end workflow functions
- Proves architecture is viable
- Provides comparison baseline

---

## Success Criteria

**After extraction:**
- Legacy code in `legacy/v2/`, documented, runnable
- Active code has NO imports from `legacy/v2/`
- One command path works (SQLite metadata indexing/querying)
- Clear TODO markers where v2 coupling existed
- Can study v2 without it affecting v3 development

---

**Next:** Use explore agent to audit current state vs intended architecture.
