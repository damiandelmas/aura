---
type: "design"
timestamp: "2025-10-18T17:01:00-07:00"
session_id: "d203b22e-efef-4467-ad79-14a073d2daf5"
---

# AURA Portability + Unified `aura init` Command

## Question

> "Can you review these insights so we can potentially make trace easier to use? I think the main problem the agent had was that it was using trace from imem-suite rather than installing aura for its own codebase and using it from there? IE we need to make ALL of aura able to be installed for any project and make the paths relative? But I'll let you look into this. I trust your judgment."

## Key Insights

### Problem: Brother Agents Can't Use TRACE
- **Root Cause**: TRACE installed only in project-local venv (`/main/aura-v2/venv/`)
- Brothers spawn in different contexts → can't find `trace` command
- Hardcoded paths assume `/main/` project structure
- `ModuleNotFoundError: No module named 'aura'` when brothers try to use it

### Solution: Global Installation via pipx
- `pipx install /path/to/aura-v2` creates isolated venv but exposes CLIs globally
- Makes `trace`, `imem`, `orca` available system-wide in `~/.local/bin/`
- Brothers can now use all three CLIs without path issues
- **Verified working**: Brother successfully ran `trace --recent 1` after permissions added

### Unix Philosophy Insight
- Keep CLIs **standalone and focused** (trace, imem, orca each do one thing)
- Bundle together in single package (`aura`) for distribution
- Add **one unified initialization command** (`aura init`) to scaffold projects

## Explored Ideas

### Three-Tier Installation Strategy
1. **Global User Install** (✅ Chosen - via pipx)
   - Works everywhere, all projects + brothers
   - Con: Version conflicts if projects need different AURA versions

2. **Project-Local + PATH Export** (Current before fix)
   - Version isolated per project
   - Con: Brothers still can't import Python modules

3. **Standalone Binary** (Future consideration)
   - PyInstaller/Nuitka compilation
   - Works anywhere, no Python needed
   - Con: Build complexity, platform-specific

### Unified CLI Approaches Considered

**Option A: Delegate subcommands** (e.g., `aura trace`, `aura imem`)
- Con: Breaks Unix philosophy - `trace` should be standalone

**Option B: Keep CLIs independent + add `aura init`** (✅ Chosen)
- `trace`, `imem`, `orca` remain focused, standalone tools
- `aura init` provides single entry point for project setup
- Clean, composable, Unix-style

### What `aura init` Should Initialize

**TRACE Setup:**
- `.claude/.trace/registry.json` (session bookmark storage)
- `.claude/hooks/session-start.sh` (auto-registration)
- `.claude/settings.json` (hook configuration)

**IMEM Setup:**
- Ensure Qdrant service running (`imem service start`)
- Create `.context/` directory structure:
  - `design/.changes/` + `design/.modules/`
  - `designate/`
  - `develop/.changes/` + `develop/.modules/`
  - `document/` (no subdirs initially)
- Run `imem init` to index project

**ORCA Setup:**
- Registry already created by TRACE
- `agents.yaml` bundled with package
- No per-project setup needed

## Outcomes

### Implemented: Global Installation
```bash
pipx install /path/to/aura-v2
# Result: trace, imem, orca now globally available
```

**Permissions Added:**
- `Bash(trace:*)`, `Bash(imem:*)`, `Bash(orca:*)` to `~/.claude/settings.json`
- Brothers can now use all AURA tools without approval

**Verified Working:**
- Test brother successfully ran `trace --recent 1`
- Returned conversation data from `/tmp` directory
- Proves portability is solved

### Next: Build Unified `aura init` Command

**Scope:**
- Create `aura-v2/src/aura/cli/aura.py` with single `init` subcommand
- Add `aura=aura.cli.aura:aura` to `setup.py` console_scripts
- Implement initialization logic for all three subsystems

**User Experience:**
```bash
cd /new/project
git init
aura init

# Output:
✅ TRACE: Registry + SessionStart hook configured
✅ IMEM: Qdrant running, project indexed
✅ ORCA: Ready to spawn brothers
✅ Project fully initialized!
```

## Design Decisions

### Decision: Use pipx over pip --user
**Rationale:**
- Debian/Ubuntu block `pip --user` with externally-managed-environment error
- pipx creates isolated venv per tool but exposes CLIs globally
- Better isolation, same global availability
- Recommended tool for Python CLI applications

### Decision: Keep CLIs Standalone (Unix Philosophy)
**Rationale:**
- Each tool has focused purpose: trace (archaeology), imem (search), orca (orchestration)
- Can be used independently or together
- Easier to understand, maintain, and extend
- Follows established Unix tradition

### Decision: Single Initialization Command
**Rationale:**
- Users shouldn't need to understand TRACE vs IMEM vs ORCA internals
- One command (`aura init`) handles all setup complexity
- Reduces friction for new projects
- Clear, simple user experience

## References

**Related Documents:**
- `.context/design/.modules/AURA_PORTABILITY_PROPOSAL.md` (created this session)
- `.context/design/.modules/conversation-archaeology-methodology.md` (identified the problem)

**Key Architecture Principles:**
- TRACE-first: Source of truth for conversations (`~/.claude/projects/`)
- Path relativity: Dynamic root detection via `.git` walking
- Brother isolation: Use `CLAUDE_IS_BROTHER` env var to prevent pollution
- Unix philosophy: Small, focused tools that compose well

**Implementation Notes:**
- Package name is already clean: `aura` (not `aura-retrieval-qdrant`)
- Version 2.0.0 in setup.py
- Entry points defined for all 3 CLIs
- Dependencies include ML libs (~2GB on first install via sentence-transformers)
