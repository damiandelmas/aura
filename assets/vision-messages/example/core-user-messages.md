# Core Architectural Messages

Architectural implications of user decisions. Facts only, no narrative.

---

## Zero Cost Constraint - LLM Extraction Only
**Timestamp:** 2025-10-11 17:00
**Message:**
> "we are never paying for it. we are only using claude -p. its with the membership. please DO NOT use regex to do anything."

**Architectural impact:**
- All brother spawns use `claude -p` (included in membership, zero marginal cost)
- Extraction workflows spawn analysis brothers (LLM intelligence, not regex patterns)
- Intelligence-first: Brothers make decisions, not scripted parsing

**What this enables:**
- Unlimited brother spawns without cost constraints
- Context-aware analysis (LLM understands nuance vs pattern matching)

**What NOT to build:**
- Regex-based extraction patterns
- Scripted parsers for conversation/changelog analysis
- Cost optimization around LLM calls (they're free with membership)

---

## Two-Tier Architecture - Static + Live
**Timestamp:** 2025-10-11 17:00
**Message:**
> "we do want static and live. this is correct. please give concise, spartan shape of the architecture."

**Architectural impact:**
- Static tier: Historical session discovery via TRACE
- Live tier: Real-time monitoring via conversation_watcher.py
- Independent systems with different data sources (TRACE vs active JSONL writes)

**Codebase structure:**
```
aura-v2/src/orchestrator/
   conversation_registry.py   # Static - wraps TRACE
   conversation_watcher.py    # Live - monitors active session

aura-v2/src/aura/services/trace/
   conversation_finder.py     # Session discovery
   conversation_query.py      # Agent formatting
   conversation_retrieval.py  # JSONL parsing
```

**What this enables:**
- Post-hoc workflows (registry queries TRACE)
- In-conversation monitoring (watcher detects writes)

**What NOT to build:**
- Unified discovery system (tiers serve different use cases)
- Watcher using registry data (independent detection methods)

---

## TRACE Pre-Existence - Don't Rebuild
**Timestamp:** 2025-10-11 16:30
**Message:**
> (User requested review of conversation_finder.py, conversation_query.py, conversation_retrieval.py)

**Architectural impact:**
- TRACE already exists: session discovery, JSONL parsing, agent formatting
- Registry must be thin wrapper (~50 lines), not reimplementation
- Filesystem (TRACE) is source of truth, not registry.json

**Codebase structure:**
```
# Existing (DO NOT REBUILD):
aura-v2/src/aura/services/trace/
   conversation_finder.py     # Session discovery
   conversation_query.py      # Agent formatting
   conversation_retrieval.py  # JSONL parsing

# New (THIN WRAPPER):
aura-v2/src/orchestrator/
   conversation_registry.py   # Wraps TRACE methods
```

**What NOT to build:**
- New JSONL parser (use conversation_retrieval.py)
- New session discovery (use conversation_finder.py)
- registry.json as primary data store (TRACE is source of truth)

---

## Agnostic Naming Convention
**Timestamp:** 2025-10-11 16:45
**Message:**
> "lets keep the names agonstic for now. conversation_watcher.py is fine. just like converation_registry et etc"

**Architectural impact:**
- Module names reflect function: conversation_registry, conversation_watcher
- NOT branded names: aui_watcher, omega_registry
- System can evolve without renaming coupling

**What this enables:**
- Modules reusable in different contexts
- Clear function from name alone

---

## SessionStart Hook Validation
**Timestamp:** 2025-10-11 17:30
**Message:**
> "hooks do exist '/home/axp/projects/shared/KNOWLEDGE/claude-docs/anthropic-docs-urls.md'"

**Architectural impact:**
- Claude Code SessionStart hook exists (official feature)
- Hook receives JSON via stdin with session metadata
- Can inject context and trigger brother spawns at conversation start

**Hook pattern:**
```bash
# .claude/hooks/session-start.sh or ~/.claude/hooks/session-start.sh
read json_input
session_id=$(extract_from_json)
trigger_registration(session_id)
```

**What this enables:**
- Automatic session registration (no manual lookup)
- Context injection at conversation start
- Brother spawning for initial context loading

**What NOT to build:**
- JSONL parsing workarounds (hook provides session metadata natively)
- Process wrappers to intercept Claude Code (hook system exists)

---

## Phase 4 Task 0 - Missing Workflow Implementation
**Timestamp:** 2025-10-11 17:45
**Message:**
> (User agreed with updated roadmap identifying missing workflow implementation)

**Architectural impact:**
- run_log_develop_workflow() DOES NOT EXIST (must build before other Phase 4 tasks)
- Task 0 prerequisite: 50-line glue function
- ORCA CLI depends on this function

**Codebase structure:**
```
# MISSING (MUST BUILD FIRST):
aura-v2/src/orchestrator/workflows/
   log_develop.py   # run_log_develop_workflow() - ~50 lines

# DEPENDS ON TASK 0:
aura-v2/src/cli/orca.py
   workflow_log_develop()  # Calls run_log_develop_workflow()
```

**What NOT to build:**
- Tasks 1-4 before Task 0 (dependency violation)
- Complex orchestration before simple spawn (foundation first)

---

## Design Lineage - Validated Architecture
**Timestamp:** 2025-10-11
**Source files:**
- .context/design/.modules/complete-system/02_research/VALIDATED_ARCHITECTURE_SYNTHESIS.md
- .context/design/.modules/complete-system/03_claude-code_control-points/CONTROL_POINTS_REVISED.md
- .context/design/.modules/complete-system/03_claude-code_control-points/DESIGN_DECISIONS_REVISED.md
- .context/design/.modules/complete-system/03_claude-code_control-points/INTEGRATION_PATTERNS_REVISED.md

**Architectural impact:**
- Brother spawning architecture validated by parallel research agents
- ClaudeAgent wrapper is production-ready (VALIDATED_ARCHITECTURE_SYNTHESIS.md:284-413)
- Progressive phases validated: Direct spawn → Swarms → Intelligence

**Reference code:**
```pseudocode
class ClaudeAgent:
  function spawn(task, context):
    process = run_command("claude -p")
    write_stdin(task_prompt + context)
    return capture_output()
```

**What to keep:**
- ClaudeAgent wrapper pattern (copy from VALIDATED_ARCHITECTURE_SYNTHESIS.md:284-413)
- Phased approach (proven strategy)
- Integration patterns (changelog extraction, parallel research)

**What to adapt:**
- Session discovery: Use TRACE (not rebuild)
- Registry: Thin wrapper (not full system)
- Identifiers: Use session_id directly (not bookmark encoding)

---

## TRACE mtime Detection - Definitive Not Guessing
**Timestamp:** 2025-10-11 18:00
**Message:**
> "why would we need the user to confirm.. .we should have a definitive way that links THIS conversation to its SESSIONID are you serious?"

**Architectural impact:**
- TRACE find_recent(1) is DEFINITIVE (slash command writes to .jsonl → updates mtime → find_recent(1) returns THIS conversation)
- User confirmation is wrong approach (adds friction, implies uncertainty when none exists)
- Detection must be automatic and reliable

**Detection pattern:**
```pseudocode
function detect_current_session():
  # Slash command invocation writes to .jsonl, updating mtime
  recent = trace.find_recent(1)
  return recent[0].session_id  # THIS conversation, definitively
```

**What this enables:**
- Zero-friction `/log:develop` (no prompts)
- Reliable detection (based on file write, not guessing)

**What NOT to build:**
- Confirmation prompts ("Use session abc123? [Y/n]")
- Interactive session selection (system knows definitively)

---

## One Command Requirement - No Multi-Step Workflows
**Timestamp:** 2025-10-11 18:00
**Message:**
> "but we should be able to do this all in one command no? sint there a way to do this from all the fucing codebases we studied..."

**Architectural impact:**
- `/log:develop` must be ONE command (not multi-step)
- Smart detection: Explicit parameter → TRACE find_recent(1) → No fallback needed
- No mode selection flags required

**Detection pattern:**
```pseudocode
function detect_session(bookmark=null):
  if bookmark: return resolve_bookmark(bookmark)

  # Primary path: TRACE detection
  recent = trace.find_recent(1)
  return recent[0].session_id
```

**What this enables:**
- Single command works everywhere (`/log:develop`)
- Automatic detection is primary (explicit is override)

**What NOT to build:**
- Mode selection flags (`--current` vs `--bookmark`)
- Multi-command workflows (list → select → execute)

---

## Modular Template System - Stage Later Not Now
**Timestamp:** 2025-10-11 18:30
**Message:**
> "● 🎯 Modular Architecture Analysis Complete [...] thoughts?"

**Architectural impact:**
- Template modularity is Stage 2/3, NOT Stage 1
- Stage 1: Hardcode v3_adaptive template (prove workflow works)
- Stage 2: Add template swapping (TemplateConfig class)
- Stage 3: Add phase-specific templates (design/designate/develop/document)

**Progressive implementation:**
```pseudocode
# Stage 1 (NOW):
function run_log_develop_workflow():
  template_path = "assets/changelogs/templates/v3_adaptive.md"
  spawn_brother(template_path, session_id)

# Stage 2 (LATER):
function run_log_develop_workflow(template_name=null):
  template_path = template_loader.resolve(template_name or "v3_adaptive")
  spawn_brother(template_path, session_id)

# Stage 3 (FUTURE):
function run_changelog_workflow(phase):
  template_path = template_loader.resolve_for_phase(phase)
  spawn_brother(template_path, session_id)
```

**What NOT to build:**
- Template config system in Phase 4 (defer to Phase 5)
- Phase-specific workflows before single workflow proven

---

## Four-Phase Changelog System
**Timestamp:** 2025-10-11 18:00
**Message:**
> "[Review] 251011-0145_four-phase-changelog-architecture.md [...] lets not use CHU anywhere. its stupid"

**Architectural impact:**
- Four distinct lifecycle phases: design → designate → develop → document
- `phase:` frontmatter field enables precise RAG filtering
- `designate` = ground truth (THE plan, THE schema)

**Directory structure:**
```
.context/
├── design/.changes/          # Exploration (questions, alternatives)
├── designate/                # Ground Truth (THE plan, THE data)
├── develop/.changes/         # Implementation (code changes)
└── document/                 # Stable Reference (how-to guides)
```

**RAG filtering pattern:**
```pseudocode
function search_ground_truth(query):
  return qdrant.search(query, filter={'phase': 'designate'})

function search_design_decisions(query):
  return qdrant.search(query, filter={'phase': 'design'})

function search_implementation(query):
  return qdrant.search(query, filter={'phase': 'develop'})
```

**What this enables:**
- RAG precision (find authoritative specs vs discussions vs implementations)
- Phase-specific templates (different structures per phase)

**What NOT to build:**
- CHU naming/branding (explicitly rejected)
- Single unified template for all phases (loses phase-specific precision)

---

## Progressive Disclosure - Template Adapts to Work
**Timestamp:** 2025-10-11 18:00
**Message:**
> [Review of 02_EXAMPLE_SPECTRUM.md showing 44-171 line range with natural variation]

**Architectural impact:**
- v3_adaptive template uses optional sections (not all required)
- Changelog length matches work complexity: 44 lines (simple) to 171 lines (complex)
- Field counts vary: 2 fields (simple decision) to 6 fields (complex decision)
- Code signatures show patterns only (~10 lines max, not full implementations)

**Template philosophy:**
- Use sections that add value, skip what doesn't
- Natural variation expected (length, field counts, section presence)
- Template guides without constraining

**What this enables:**
- Changelogs match actual work (no artificial padding)
- Flexible structure (2-6 fields per decision based on complexity)

**What NOT to build:**
- Rigid section requirements (all sections always present)
- Fixed field counts (every decision same structure)
- Minimum length requirements
- Complete code dumps (show patterns only)
