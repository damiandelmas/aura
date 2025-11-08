# discover-lineage

## OVERVIEW

Reconstructs how an artifact evolved by combining multiple information sources into a chronological narrative. Searches current codebase for the artifact, retrieves its modification history from version control, locates related design documents that influenced its creation, and synthesizes these fragments into a timeline showing initial decisions, implementation changes, and proposed versus realized features. This archaeological approach reveals not just what exists now, but why it was created, what alternatives were considered, and how it changed over time—essential for understanding architectural decisions and avoiding repeated mistakes.

---

## SPECIFICATION

**Purpose:** Reconstruct artifact evolution through multi-source archaeology

**Input:** Pattern or file path (e.g., "MarkdownNodeParser", "template")

**Output:** Chronological timeline with:
- Initial commit + date
- Evolution through commits
- Design decisions from documents
- Current state vs proposed features
- Key decision points with rationale

**Process:**
```
1. Find artifacts (Grep for pattern across codebase)
2. Read current implementation (Read tool)
3. Get git history (Bash: git log --oneline --follow -- <path>)
4. Get detailed timestamps (Bash: git log --format="%H %ai %s" -- <path>)
5. Read historical content (Bash: git show <hash>:<path>)
6. Find related design docs (Grep for pattern in design directories)
7. Read design documents (Read tool)
8. Synthesize chronological timeline
```

**Tool Composition:**
```
Grep → Read → Bash(git log) → Bash(git show) → Grep → Read → Synthesis
```

---

## ACTUAL CONVERSATION EXECUTION

### Request 1: MarkdownNodeParser Lineage

**User asked:**
> "Can you try to uncover he geneology /lineage of that current implementation against docuemnts, git history etc?"

**What I did:**

```
1. Used TodoWrite to track 5 tasks:
   - Read current MarkdownNodeParser implementation
   - Check git history for ingest.py
   - Review design documents mentioning the parser
   - Trace evolution through conversation logs
   - Synthesize genealogy/lineage report

2. Read current implementation:
   Read(/home/axp/projects/fleet/hangar/code/aura/main/imem/src/imem/ingest.py)
   Found: Line 60: self.parser = MarkdownNodeParser()

3. Got git history:
   Bash: cd /home/axp/projects/fleet/hangar/code/aura/main && git log --oneline --all -- imem/src/imem/ingest.py | head -20

   Results:
   c7dcb71 H2 filter fix + template update
   0585e6c empty section filtering
   ... (8 commits total from Oct 24 - Nov 1)

4. Got detailed timestamps:
   Bash: git log --all --format="%H %ai %s" -- imem/src/imem/ingest.py

   Timeline established:
   - Oct 24 (9268206): Initial implementation
   - Oct 25 (5fa703b): Retrieval working
   - Oct 29 (0585e6c, c7dcb71): Refinements
   - Oct 30 (3481866, 1e6db55): Architecture migration
   - Nov 1 (f642e70): Layer separation

5. Read historical content:
   Bash: git show 9268206:imem/src/imem/ingest.py | head -100
   Confirmed MarkdownNodeParser existed from first commit

6. Found design documents:
   Grep pattern="MarkdownNodeParser" output_mode="files_with_matches"

   Found:
   - brain/.claude/.convs/251103-1639.md
   - fleet/hangar/code/aura/main/.claude/.convs/251104-1850.md
   - imem/src/imem/ingest.py
   - imem/tests/validate_indexing.py

7. Read design documents:
   Read(.context/develop/.changes/251024-0137_two-tier-llamaindex-conversation-indexing.md)

   Key findings:
   - Oct 24: Decision to use section-level chunking instead of summary-level
   - "Use LlamaIndex MarkdownNodeParser" chosen for battle-tested parsing
   - Rationale: "No LLM costs, better precision"

8. Read conversation discussing future:
   Read(fleet/hangar/code/aura/main/.claude/.convs/251104-1850.md)

   Found: Nov 3-4 conversation proposed SchemaAwareNodeParser
   Status: Discussed but NOT implemented

9. Synthesized timeline report showing:
   - Oct 24, 2025: Initial Implementation (commit 9268206)
   - Design decision: Choose section-level chunking over summary-level
   - Implementation: Imported MarkdownNodeParser from LlamaIndex
   - Key choice: Use LlamaIndex native parser rather than custom
   - Rationale: "No LLM costs, better precision"
   - Evolution through 8 commits
   - Nov 3-4: Architectural vision for custom parser (unimplemented)
   - Current: Using vanilla LlamaIndex with post-processing
```

**Tools used in sequence:**
1. TodoWrite (progress tracking)
2. Read (current implementation)
3. Bash (git log --oneline)
4. Bash (git log --format with timestamps)
5. Bash (git show historical content)
6. Grep (find design docs)
7. Read (design documents)
8. Read (conversation logs)
9. Synthesis (timeline construction)
10. TodoWrite (mark complete)

---

### Request 2: Template Lineage

**User asked:**
> "Can you find information on the lineage of the template that we are utilizing to structure our input documents?"

**What I did:**

```
1. Searched for template files:
   Grep pattern="template" glob="**/*.md" output_mode="files_with_matches"
   Found 135 files

2. Found template files:
   Bash: find /home/axp/projects/fleet/hangar/code/aura/main -type f -name "*TEMPLATE*" -o -name "*template*"

   Key findings:
   - assets/context/develop/template/00_TEMPLATE.md (current v3_adaptive)
   - assets/.context/.archive/template-v3-design/template-design/11_changelog-template-v3-final.md
   - assets/context/design/00_DESIGN_TEMPLATE.md

3. Got git history:
   Bash: git log --all --oneline --follow -- assets/context/develop/template/00_TEMPLATE.md

   Results:
   c7dcb71 H2 filter fix + template update (overview is now not langauge agonistc for imlpl changelgo)
   d60f210 docs and stuff
   9268206 init

4. Read current template:
   Read(assets/context/develop/template/00_TEMPLATE.md)
   Found: v3_adaptive template, Last Updated: 2025-10-07

   Structure:
   - Frontmatter (schema_version, type, status, keywords, timestamp, session_id)
   - Request, Overview, Decisions, Constraints, Failures, Implementation, Patterns, Audit
   - Progressive disclosure design (44-171 lines based on complexity)
   - Optimized for LlamaIndex H2/H3 hierarchy

5. Read migration document:
   Read(.context/develop/.changes/251024-1247_changelog-v3-migration.md)

   Found: Oct 24 parallel migration of 23 changelogs to v3_adaptive
   - 10 parallel agents, 2-3 files each
   - Frontmatter standardization
   - Content restructuring to progressive disclosure

6. Read template design history:
   Read(assets/.context/.archive/template-v3-design/template-design/11_changelog-template-v3-final.md)

   Found: Oct 8 design
   - Created 4-document package
   - Language-agnostic overviews principle
   - Code signatures not full implementations
   - Progressive disclosure (2-6 fields)
   - H1/H2/H3 hierarchy for MarkdownNodeParser

7. Read earliest design:
   Read(.archive/251007-2052_template-llama-index/.changes/too-harsh/251004-1556_section-level-chunking-rag-architecture.md)

   Found: Oct 4 genesis
   - Section-level chunking vision
   - LlamaIndex hierarchical nodes concept
   - Decision to use LlamaIndex MarkdownNodeParser

8. Synthesized timeline:
   Oct 4, 2025 - Genesis: Section-Level Chunking Vision
   Oct 7-8, 2025 - Template Package & Progressive Disclosure
   Oct 18, 2025 - Workflow Integration
   Oct 24, 2025 - V3 Migration & Normalization
   Oct 29, 2025 - Template Refinement
   Current (Nov 7, 2025) - v3_adaptive stable
```

**Tools used:**
1. Grep (find template references)
2. Bash (find template files)
3. Bash (git log for history)
4. Read (current template)
5. Read (migration doc)
6. Read (design history)
7. Read (earliest design)
8. Synthesis (evolution timeline)

---

## OUTCOME UNDERSTANDING

**What this skill does:**
Takes a single artifact identifier (implementation name, file path, concept) and reconstructs its complete evolutionary story by:
1. Finding where it exists now (grep + read)
2. Extracting its change history (git log)
3. Reading historical versions (git show)
4. Locating design rationale (grep for related docs)
5. Synthesizing chronological narrative

**Key insight:** Multi-source synthesis reveals "why" not just "what changed"
- Git shows WHAT changed and WHEN
- Design docs show WHY it changed
- Conversations show WHAT WAS CONSIDERED but not implemented

**Success criteria:** Timeline showing initial decision → evolution → current state → proposed future, with all sources cited

**Practical value:** Understanding architectural decisions without tribal knowledge or guesswork
