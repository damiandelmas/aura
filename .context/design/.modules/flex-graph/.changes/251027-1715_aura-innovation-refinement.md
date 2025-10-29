---
session_id: "eee3b7a5-3870-4b50-984c-19eb2e2fa729"
timestamp: "2025-10-27T17:15:00-0700"
---

# Architectural Decisions: AURA Innovation Refinement

Decisions from conversation 251027-1715 capturing flippable chunks, cross-project transfer, and runtime composition architecture.

---

## Markdown Slash Commands Over Code Wrappers
**Quote:** "the composition will come through composable/iterable markdown files first. IE you use imem well, we capture that 'compsoiton' / 'module' as a slash commmand combination of flags and now its reusable. Rather than locking it in code as a flag or API wrapper."
**Why:** Git-tracked markdown compositions enable iteration without code changes—patterns emerge from usage, codified only when proven

**Context:** Alternative to building explain/trace/patterns as code functions. Instead, observe Claude composing CLI primitives, capture proven patterns as markdown slash commands. Enables iteration without code deployment—slash command files are just markdown in .claude/commands/.

**Options Considered:**
- A: Build wrapper functions in Python (explain(), trace(), patterns()) - rigid, requires code changes
- B: Capture patterns as markdown slash commands - flexible, Git-tracked, user-editable

---

## Slash Commands as Modular MCP
**Quote:** "we already know u can wrap endponts in slash comand with expalntion. its bascially just MCP on the fly via PROMPT+RUNBOOK/BASH/IMEM <<< this is MCP (more or less) but modular and iteratble."
**Why:** Avoid MCP protocol overhead while maintaining composability—prompt+CLI composition achieves same result with less infrastructure

<!-- Straightforward, no expansion needed -->

---

## JSON Inline Arguments (Not Files)
**Quote:** "we warent imem imem query config.json we are doing imem query {{JSON THAT U WRITE lol}}"
**Why:** Claude constructs JSON dynamically per context—no file management, just inline composition adapted to query

<!-- Straightforward, no expansion needed -->

---

## Flippable Chunks for Zero-Loss Memory
**Quote:** "this enables no loss in degredation of memroy — being able to serve unfitted (pattern insight — intellectual capital) whenever superceded whil;e also being able to retrieve full resolution chunk (impl chunk) upon command. we would have a board of chunks that can be flipped from impl to pattern at runtime (their supercession stored via simple amapping rather than deleting, removin etc or even re-indexing)."
**Why:** Supersession promotes abstraction without deletion—metadata flip enables O(1) serving decision (pattern vs implementation)

**Context:** When implementation superseded (JWT → OAuth2), system serves pattern abstraction by default (Stateless Auth Pattern), but original implementation remains indexed and retrievable via --full-resolution flag. Double-sided chunk architecture—every decision has impl and pattern variants, serving decided at query time.

**Key Properties:**
- No deletion (both chunks indexed permanently)
- No re-indexing (supersession = metadata field update)
- Runtime flip (chunk.serving_mode = 'pattern' or 'impl')
- Reversible (force flag retrieves original implementation)
- Archaeological precision available on demand

---

## Cross-Project Pattern Transfer Without Contamination
**Quote:** "this enables cross project memory. i can ask it to retriev how we solved problem A from typescript codebase while working on Problem Aa in python codebase without being worried about it 'fitting' to typsecipe or even wrose. a similar python codebase as the one im working on that solved Problem Aaa"
**Why:** Pattern layer isolation prevents framework leakage—principles transfer, code doesn't, intellectual capital compounds across stacks

**Context:** Query patterns across projects returns language-agnostic abstractions only. TypeScript JWT implementation → Stateless Auth Pattern (no TypeScript/JWT mentions). Python project queries pattern layer, applies principle with Python tools. Authority accumulation: pattern in N projects = validated approach.

**Anti-Contamination Guarantee:**
- Cross-project queries: Pattern layer only (--pattern-only flag)
- Single-project queries: Implementation + pattern (default)
- Framework leakage impossible (pattern extraction strips tech details)
- Intellectual capital transfer without code pollution

---

## Primitives Over Wrappers (explain/trace/patterns Deferred)
**Quote Context:** Discussing whether to build explain() functions vs CLI primitives
**Why:** Observe composition patterns first, codify only if validated (>10 uses)—premature abstraction costs more than runtime composition

**Questions Resolved:** When to build convenience wrappers? Answer: After >10 observed uses of same composition pattern. Let Claude compose primitives, observe via usage.log, generate shortcuts only when pattern proven.

---

## CLI → JSON → Python → MCP Progression
**Quote:** "think about our roles. i only do ai coding. restate concise, no code ideas. technically precise. spratn. extremely concise."
**Why:** Each layer serves different user—CLI for testing, JSON for batching, Python for programmatic, MCP for AI integration

**Context:** Implementation progression over time. Start with CLI primitives (testing/validation). Add JSON batch (parallelization). Optional Python API wrapper (programmatic access). Eventually MCP tools (Claude Code integration). Each layer built only when proven need exists.

**Phase Plan:**
- Phase 6: CLI primitives (immediate)
- Phase 8: JSON batch support (validated)
- Future: Python API (if programmatic use emerges)
- Future: MCP tools (proper protocol integration)

---

## Three-Level Resolution Documentation
**Quote Context:** Creating innovation docs with vision/pattern/implementation levels
**Why:** Geometric → language-agnostic → code-ready progression enables different readers (architects, developers, implementers)

<!-- Straightforward, no expansion needed -->

---

## System Architect Communication Style
**Quote:** "restate questions, no code. im a system architect, not a developer."
**Why:** Focus on architecture and systems design—implementation details separate, dense technical precision for AI-directed coding

<!-- Straightforward, no expansion needed -->

---

## Document Organization: 02_current vs 03_additional
**Quote Context:** Reviewing existing architecture docs vs today's innovations
**Why:** Foundation docs (Oct 25) remain valid—innovations (Oct 27) complement without replacement, separate genealogy preservation

<!-- Straightforward, no expansion needed -->

---

## Template Enforcement Remains the Moat
**Quote Context:** Throughout conversation validating flippable chunks and cross-project patterns
**Why:** Creation-time schema enables everything downstream—flippable chunks, pattern transfer, deterministic queries all depend on guaranteed metadata

<!-- Straightforward, no expansion needed -->

---

## Soft-Graph Runtime Construction Validated
**Quote Context:** Reviewing O(k²) vs O(n²) complexity analysis
**Why:** Query-time graph construction from top-k results enables zero maintenance and query-adaptive ranking—1000× efficiency over precomputed graphs

<!-- Straightforward, no expansion needed -->

---

## Pattern Authority via Accumulation
**Quote Context:** Discussing cross-project pattern queries
**Why:** Pattern appearing in N projects = validated approach—authority compounds through reuse, PageRank on pattern layer surfaces most proven solutions

<!-- Straightforward, no expansion needed -->

---

## Vision Files for Anti-Drift
**Quote Context:** Capturing session principles in .claude/.vision/
**Why:** User constraints and architectural decisions preserved across conversations—prevent "Brother, we already talked about this" moments

<!-- Straightforward, no expansion needed -->
