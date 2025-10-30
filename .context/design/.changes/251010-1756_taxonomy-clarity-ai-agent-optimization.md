---
type: "architectural"
timestamp: "2025-10-10T17:56:00-0700"
---

# Taxonomy Clarity - AI Agent Development Optimization

## Question
> "we have A LOT of naming conflicts. even review the entire codebase. currently its 'imem' but it should be called aura no? also we have 'search' as a folder. we chose that so it wouldnt conflcit with 'imem' lol. yes i understand this is quite pedantic, but having clear, crystal and intuitive taxonomy makes AI driven development 100X faster when you have it delinated and directed."

## Context

Legacy monolithic `imem` package had namespace collisions:
- Package name: `imem/` (should be `aura/`)
- Search module: `src/search/` (confusingly named to avoid collision)
- CLI structure unclear (who uses what?)

**Core insight**: Clear taxonomy is CRITICAL for brother agents. When spawning 10 brothers in parallel via `claude -p`, each must instantly know:
- What to import (`aura.services.imem` not `imem.search`)
- What to call (`trace --session` not `imem trace`)
- Where to write (`.context/develop/.changes/` not `.memory/`)

## Key Insights

### 1. The 100X Multiplier
Clear naming enables:
- **Brothers spawn faster** (no guessing imports)
- **Parallel execution** (no namespace conflicts)
- **Self-documenting code** (name reveals purpose)
- **Onboarding speed** (new brothers understand immediately)

**Example**:
```python
# ❌ Confusing (brother has to guess)
from imem.search import search
from imem import trace

# ✅ Crystal clear (brother knows instantly)
from aura.services.imem import search
from aura.services.trace import ConversationRetrieval
```

### 2. Component Roles (Clarified from Architecture Docs)

**TRACE** = Tool (library + CLI)
- Brothers call: `trace --session abc123 --patches` (via Bash)
- Retrieves conversation memory
- Read-only (archaeology, not maintenance)

**IMEM** = Tool (library + CLI)
- Brothers call: `imem search "query"` (via Bash)
- Vector search for context
- Read-mostly (search, occasional update)

**pulse** = Library (used by PULSE brother)
- PULSE brother uses Read/Write/Edit tools + pulse library logic
- Updates `.context/document/` files
- **No CLI needed** (brothers don't need it)

**PRUNE** = Pure brother logic
- Uses Read/Edit tools directly
- Updates metadata chains
- **No library or CLI needed**

**ORCA** = Orchestrator
- Spawns brothers via `claude -p`
- Coordinates workflows (Swarms)
- **Needs CLI** for manual triggers: `orca design`, `orca develop`, `orca pulse`

### 3. The ORCA CLI Insight

ORCA needs a CLI for:
```bash
# Manual brother spawning (testing, debugging)
orca design --session abc123      # Spawn DesignAgent
orca develop --session abc123     # Spawn ChangelogAgent
orca pulse --changelog <file>     # Spawn PULSE brother
orca prune --session abc123       # Spawn PRUNE brother

# Workflow management
orca status                       # Show running workflows
orca logs <workflow-id>           # View logs
```

**Why separate from slash commands?**
- Slash (`/log:develop`) = Convenience (auto-extracts session, blocks conversation)
- ORCA CLI (`orca develop`) = Explicit control (background, manual testing)

### 4. Async Flow Pattern (from INTEGRATION_PATTERNS.md)

```
User: /log:develop "auth decision"
    ↓
I extract bookmark from context
    ↓
I spawn: subprocess.Popen(["orca", "develop", "--session", "abc123"])
    ↓
I return IMMEDIATELY:
  "✅ ChangelogAgent spawned (background)
   📋 Session: abc123def456

   Or run manually:
     orca develop --session abc123def456"
    ↓
[Brother runs in background]
    ↓
[User and I continue conversation]
```

**Key**: User isn't blocked, gets manual command for debugging.

## Explored Ideas

### Naming Options

**Package Level**:
- `imem/` → `aura/` ✅ (aligns with project name)

**Module Level**:
- `src/search/` → `src/services/imem/` ✅ (clear purpose)
- `src/trace/` → `src/services/trace/` ✅ (consistency)
- `src/pulse/` → `src/pulse/` ✅ (library, not service)

**CLI Files**:
- `cli/imem_cli.py` → `cli/imem.py` ✅ (folder name says "CLI")
- `cli/trace_cli.py` → `cli/trace.py` ✅ (cleaner)
- `cli/orchestrator/` → `cli/orca.py` ✅ (agent orchestration)

### CLI Structure Options

**Option A: 4 CLIs**
```bash
aura init              # Meta operations
trace --session        # Conversation archaeology
imem search            # Vector search
pulse process          # Manual maintenance
```
❌ Rejected: pulse doesn't need CLI (PULSE brother uses Read/Write directly)

**Option B: 3 CLIs + ORCA** (CHOSEN)
```bash
aura init              # Meta operations
trace --session        # Conversation archaeology
imem search            # Vector search
orca develop           # Agent orchestration
```
✅ Accepted: Clean separation, clear roles

## Outcomes

### Proposed Clean Taxonomy

```
aura/                          # Package root (renamed from imem/)
├── cli/                       # CLI layer (4 independent CLIs)
│   ├── aura.py               # Meta (init, status, service mgmt)
│   ├── orca.py               # Agent orchestration ✨ NEW
│   ├── trace.py              # Conversation archaeology
│   └── imem.py               # Vector search
│
├── services/                  # Reusable libraries (used by brothers)
│   ├── trace/                # Conversation service
│   │   ├── conversation_finder.py
│   │   └── conversation_retrieval.py
│   ├── imem/                 # Search service (renamed from search/)
│   │   ├── modular_search.py
│   │   └── modular_ingest.py
│   └── qdrant/               # Backend service management
│
├── orca/                      # Agent orchestration ✨ RENAMED (was orchestrator/)
│   ├── claude_agent.py       # Swarms wrapper for claude -p
│   ├── spawn_brother.py      # Brother spawning utilities
│   ├── run_workflow.py       # CLI entry point
│   └── workflows/
│       ├── log_develop.py    # SequentialWorkflow
│       └── parallel_research.py
│
├── pulse/                     # pulse library (for PULSE brother)
│   └── pulse.py              # Document maintenance logic
│
└── core/                      # Shared utilities
    ├── paths.py              # ✅ Centralized path detection
    ├── registry.py           # Project registry
    └── service.py            # Qdrant service management
```

### Import Clarity

**Before (confusing)**:
```python
from imem.search.modular_search import search
from imem.trace.conversation_finder import ConversationFinder
from imem.core.registry import ProjectRegistry
```

**After (crystal clear)**:
```python
from aura.services.imem import search
from aura.services.trace import ConversationFinder
from aura.core.registry import ProjectRegistry
```

**Brother agents see**:
- `aura.services.imem` → "This is the vector search service"
- `aura.services.trace` → "This is the conversation archaeology service"
- `aura.orca` → "This is the agent orchestration system"

### CLI Clarity

**Before**:
```bash
imem init              # ❓ Is this search or meta?
imem search            # ✅ Clear
imem trace             # ❓ Why is trace inside imem?
```

**After**:
```bash
aura init              # ✅ Clear: meta operations
imem search            # ✅ Clear: vector search
trace --session        # ✅ Clear: standalone archaeology
orca develop           # ✅ Clear: agent orchestration
```

## Technical Implementation

### Rename Checklist (Ready to Execute)

**1. Package rename**:
```bash
mv imem/ aura/
```

**2. Module reorganization**:
```bash
mv aura/src/search/ aura/src/services/imem/
mv aura/src/trace/ aura/src/services/trace/
mkdir aura/src/orca/  # (rename from orchestrator/ when created)
```

**3. CLI file cleanup**:
```bash
# In aura/cli/
mv imem_cli.py imem.py
mv trace_cli.py trace.py
# Create orca.py (new)
```

**4. Update imports**:
- Find/replace: `from imem.` → `from aura.`
- Find/replace: `from .search.` → `from .services.imem.`
- Find/replace: `from .trace.` → `from .services.trace.`

**5. Update setup.py entry points**:
```python
console_scripts = [
    'aura=aura.cli.aura:main',
    'trace=aura.cli.trace:main',
    'imem=aura.cli.imem:main',
    'orca=aura.cli.orca:main',  # ✨ NEW
]
```

## Knowledge Capture

### Pattern: Taxonomy for Multi-Agent Systems

**Principle**: Every name should answer:
1. **What** is it? (tool, service, orchestrator)
2. **Who** uses it? (human, brother, both)
3. **Where** does it live? (CLI, library, service)

**Example**:
```
aura.services.imem.search()     # Service function
↓
imem search "query"             # CLI wrapper (for humans + brothers)
↓
Brother calls via Bash tool     # Brother usage pattern
```

**Anti-pattern**:
```
imem.search.search()            # ❌ Redundant, confusing
search.search()                 # ❌ What is 'search'? Package? Module?
```

### Pattern: CLI vs Library Separation

**CLI needed when**:
- Humans need quick access (`trace --session abc123`)
- Brothers need tool interface (Bash calls)
- Debugging/testing required

**Library only when**:
- Only brothers use it (PULSE uses pulse library)
- Pure Python integration (no CLI needed)

**PRUNE example**:
- ❌ No CLI (brothers use Read/Edit directly)
- ❌ No library (logic is simple, inline in brother)
- ✅ Just brother intelligence

### Brother Perspective

When brother spawns via `claude -p`, it sees:
```python
# Available CLIs (via Bash tool)
trace --session abc123 --patches
imem search "authentication patterns"
orca develop --session abc123

# Available libraries (via Python import)
from aura.services.trace import ConversationRetrieval
from aura.services.imem import EnhancedSearch
from aura.pulse.pulse import DocumentPulse
from aura.core.paths import ProjectPaths

# Where to write
.context/design/changes/      # Design exploration
.context/develop/changes/     # Validated changelogs
.context/document/            # Maintained docs
```

**No ambiguity. 100% clear.**

## References

- `E_01_SYSTEM_ARCHITECTURE.md` - Component structure (lines 163-189)
- `E_02_AGENT_PROTOCOLS.md` - Brother spawning patterns
- `INTEGRATION_PATTERNS_REVISED.md` - Async flow (lines 134-176)

## Success Metrics

- ✅ **Zero namespace collisions** in proposed structure
- ✅ **Self-documenting names** (aura.services.imem vs imem.search)
- ✅ **Clear CLI boundaries** (4 independent CLIs with distinct purposes)
- ✅ **Brother-ready** (spawning brothers can import without confusion)

## Duration
~30 minutes (taxonomy analysis, architecture alignment, rename planning)

## Impact

**For developers**:
- Faster onboarding (names reveal purpose)
- Easier debugging (clear component boundaries)
- Predictable structure (services/, cli/, orca/)

**For brother agents**:
- **100x faster development** (no namespace guessing)
- Parallel execution safe (clear module boundaries)
- Self-documenting (import path reveals role)

**For system evolution**:
- Easy to add new services (`aura.services.new_service/`)
- Easy to add new CLIs (`aura.cli.new_cli.py`)
- Easy to add new workflows (`aura.orca.workflows/new_workflow.py`)

## Next Steps

1. ✅ Taxonomy designed (this document)
2. ⏳ Execute rename (systematic, test after each step)
3. ⏳ Update all imports (23+ files)
4. ⏳ Test CLIs work (aura, trace, imem)
5. ⏳ Create ORCA CLI stub (for future brother orchestration)
