# Core Architectural Messages

Architectural principles from user decisions. Quote + Why only.

---

## Zero cost constraint - claude -p only
**Quote:** "we are never paying for it. we are only using claude -p. its with the membership. please DO NOT use regex to do anything."
**Why:** Unlimited brother spawns with membership - use LLM intelligence not patterns

## Static + live two-tier architecture
**Quote:** "we do want static and live. this is correct. please give concise, spartan shape of the architecture."
**Why:** Different use cases require different detection methods (historical vs real-time)

## TRACE is source of truth - don't rebuild
**Quote:** "(User requested review of conversation_finder.py, conversation_query.py, conversation_retrieval.py)"
**Why:** Session discovery and JSONL parsing already exist in one place

## Agnostic naming convention
**Quote:** "lets keep the names agonstic for now. conversation_watcher.py is fine. just like converation_registry et etc"
**Why:** Module names reflect function without branded coupling

## SessionStart hooks enable automatic detection
**Quote:** "hooks do exist '/home/axp/projects/shared/KNOWLEDGE/claude-docs/anthropic-docs-urls.md'"
**Why:** Official feature provides session metadata without workarounds

## Stage 1 simplicity - prove workflow first
**Quote:** "(User agreed with updated roadmap identifying missing workflow implementation)"
**Why:** 50-line foundation before complex orchestration

## Brother spawning architecture validated
**Quote:** "(Design lineage: VALIDATED_ARCHITECTURE_SYNTHESIS.md, CONTROL_POINTS_REVISED.md, DESIGN_DECISIONS_REVISED.md, INTEGRATION_PATTERNS_REVISED.md)"
**Why:** Parallel research agents validated ClaudeAgent wrapper as production-ready

## TRACE mtime detection is definitive
**Quote:** "why would we need the user to confirm.. .we should have a definitive way that links THIS conversation to its SESSIONID are you serious?"
**Why:** Slash command writes update mtime - no guessing needed

## One command workflow - no multi-step
**Quote:** "but we should be able to do this all in one command no? sint there a way to do this from all the fucing codebases we studied..."
**Why:** Single command with smart detection - explicit parameter or auto-detect

## Template modularity is Stage 2+
**Quote:** "● 🎯 Modular Architecture Analysis Complete [...] thoughts?"
**Why:** Hardcode template in Stage 1, add swapping later

## Four-phase documentation lifecycle
**Quote:** "[Review] 251011-0145_four-phase-changelog-architecture.md [...] lets not use CHU anywhere. its stupid"
**Why:** Phase filtering enables precise RAG retrieval (design vs designate vs develop vs document)

## Progressive disclosure - template adapts to work
**Quote:** "[Review of 02_EXAMPLE_SPECTRUM.md showing 44-171 line range with natural variation]"
**Why:** Optional sections match complexity - no artificial padding

## Global editable installation
**Quote:** "lets do option 2 — then any change we make i nthe porject we can just glovbal update and itworks evrywhere?"
**Why:** Code changes immediately reflected everywhere without reinstall

## Minimal .context/ structure
**Quote:** "we dont need either of these yet. /// lets leave document folder empty for now."
**Why:** Start with 8 essential dirs - add structure when needed

## Runbook slash commands inject docs
**Quote:** "i think we need a /salsh command for each of them that has their runbook."
**Why:** Context injection at point of use - not CLAUDE.md bloat

## develop/.changes are user-validated ground truth
**Quote:** "develop/.changes are ground truth changelogs: these document ACTUAL FACT changes [...] they emerge from a conversation between USER and AI AGENT, and are created by the user using a slash command. they are, therefore, validated by the user."
**Why:** User validation through slash commands makes these authoritative

## Concise spartan documentation only
**Quote:** "ensure they are concise, spartan, and are only the length necessary to complete that package of knowledge. have knowledge transfer to future brother in arms as the omega point."
**Why:** Dense knowledge transfer without superfluidity - respect future readers

## AI triggers over dumb automation
**Quote:** "we could differentiate between what is actually 'dumb automation' — THAT both pulse and prune and triggered at point of design or develop document creation, and their ecosystem of responsibiltiies / swarm. but triggering that may be better to be done from AI."
**Why:** Intelligent guidance at trigger points vs watchdog processes

## PULSE manages documents not general tasks
**Quote:** "'sync' << was 'pulse' after rename. we named back to pulse. i think pulse should just be a thing that is managing documents. so it is more of an action than a management system."
**Why:** PULSE pressed by agents for document maintenance - not agent manager

## Log commands differentiate by phase
**Quote:** "we want to utilize the USERs insight whenever possible. would be useful to have a log:design and a log:develop to immediately validate the document into either category."
**Why:** User validates phase at creation time via slash command choice
