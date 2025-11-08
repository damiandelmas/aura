# discover-lineage (iteration 1)

## OVERVIEW

Reconstructs artifact evolution through systematic multi-source archaeology. Locates the artifact in current codebase, extracts its complete modification history from version control, identifies related design documents that influenced decisions, and synthesizes these sources into a chronological narrative. Distinguishes what was implemented from what was only proposed, reveals the rationale behind choices, and surfaces alternatives that were considered then rejected. The output is a timeline showing genesis → evolution → current state → unrealized proposals, with all claims cited to source.

---

## OPTIMAL WORKFLOW

### Input
Artifact identifier: pattern (e.g., "MarkdownNodeParser") OR file path

---

### Step 1: Find Artifact
```bash
Grep(pattern=<artifact>, output_mode="files_with_matches")
```

**Purpose:** Locate where it exists now
**Search scope:** Entire codebase (no path restrictions)
**Finds:** Implementation files, tests, configs, related code

**Why broad search:** You don't know where it lives yet. Cast wide net.

---

### Step 2: Read Current State
```bash
Read(<discovered_path>)
```

**Purpose:** Understand what exists now
**Establishes:** Baseline for comparison
**Look for:** Current implementation, imports, dependencies, usage patterns

---

### Step 3: Extract Commit History
```bash
git log --all --follow --format="%H %ai %s" -- <path>
```

**Purpose:** Get complete timeline of changes
**Output:** Hash, timestamp, commit message for each change

**Critical flags:**
- `--all` - Search all branches (not just current)
- `--follow` - Track file across renames
- `--format="%H %ai %s"` - Hash, ISO timestamp, subject

**Shows:** WHAT changed, WHEN, commit message

---

### Step 4: Read Key Historical Versions
```bash
# First commit (genesis)
git show <first_commit_hash>:<path>

# Significant changes (major refactors, migrations)
git show <significant_commit_hash>:<path>
```

**Purpose:** See how it looked at critical moments
**Strategy:** Don't read every commit - only genesis + major changes
**Reveals:** Initial design, how it evolved over time

---

### Step 5: Find Design Documents
```bash
# Design explorations
Grep(pattern=<artifact>, path=".context/design", output_mode="files_with_matches")

# Authoritative specifications
Grep(pattern=<artifact>, path=".designate", output_mode="files_with_matches")

# Conversations/proposals
Grep(pattern=<artifact>, path=".claude/.convs", output_mode="files_with_matches")
```

**Purpose:** Locate WHY decisions were made
**Three sources:**
- `.context/design` - Exploration, alternatives considered
- `.designate` - Authoritative specs, the plan
- `.claude/.convs` - Proposals, discussions, rejected ideas

**Why three greps:** Different document types live in different locations

---

### Step 6: Read Design Context
```bash
Read(<design_doc_path>)
Read(<designate_spec_path>)
Read(<conversation_path>)
```

**Purpose:** Extract rationale, alternatives, proposals
**Look for:**
- Decision sections (why this approach)
- Alternatives (what was rejected and why)
- Rationale (technical reasoning)
- Proposals (discussed but not implemented)

**Key insight:** Design docs answer "why", git answers "what"

---

### Step 7: Synthesize Timeline

**Combine three sources:**
1. Git commits → WHAT changed, WHEN
2. Design docs → WHY it changed, RATIONALE
3. Conversations → WHAT WAS PROPOSED but not realized

**Ordering:** Chronological by date (not discovery order)

**Distinguish:**
- **Implemented:** Exists in git history + current code
- **Proposed:** Discussed in docs/conversations but NOT in git

**Output structure:**
```markdown
## <Artifact> Lineage

### Genesis (YYYY-MM-DD)
**Commit:** <hash>
**Design Doc:** <path>
**Decision:** [from design doc - what was chosen]
**Rationale:** [why this approach vs alternatives]
**Alternatives Considered:** [what was rejected]

### Evolution
**YYYY-MM-DD** (<hash>): [change description]
- **Reason:** [from commit message or design doc]
- **Source:** <design_doc_path or commit_message>

**YYYY-MM-DD** (<hash>): [another change]
- **Reason:** [why]
- **Source:** <source>

### Proposed but Unrealized
**YYYY-MM-DD**: [feature/change proposed]
- **Source:** <conversation_path>
- **Status:** Discussed but not implemented
- **Context:** [why it was considered]

### Current State
**Implementation:** [brief description]
**Key Decisions:** [summary of major choices]
**Design Philosophy:** [extracted from docs]
```

---

## TOOL SEQUENCE

```
Grep (find artifact everywhere)
  ↓
Read (current implementation)
  ↓
git log --all --follow (complete history)
  ↓
git show <hash> (historical snapshots)
  ↓
Grep (.context/design, .designate, .claude/.convs)
  ↓
Read (design docs + conversations)
  ↓
Synthesis (chronological timeline)
```

**Total operations:**
- 2 Grep (find artifact, find docs)
- 2+ Read (current + design docs)
- 2-3 git (log + show snapshots)
- 1 synthesis

---

## ESSENTIAL PRINCIPLES

### 1. Multi-Source by Default
Never rely on git alone. Design docs provide the "why."

**Git shows:** WHAT changed
**Design docs show:** WHY it changed
**Conversations show:** WHAT was considered but not done

### 2. Broad Then Narrow
**First Grep:** No path restrictions (find everything)
**Second Grep:** Specific paths (design/designate/convs)

### 3. Chronological Synthesis
Order by actual date, not discovery order.
Timeline flows: earliest → latest

### 4. Distinguish Proposed from Realized
Mark clearly:
- ✅ Implemented (in git + current code)
- 📝 Proposed (in docs/convs, not in git)

### 5. Cite All Sources
Every claim links to:
- Commit hash (for implementations)
- Design doc path (for rationale)
- Conversation file (for proposals)

### 6. Focus on Critical Moments
Don't read every commit - only:
- Genesis (first implementation)
- Major changes (refactors, migrations)
- Current state

---

## SUCCESS CRITERIA

✅ **Complete timeline:** initial → evolution → current → proposed
✅ **"Why" answered:** Not just "what changed" but rationale
✅ **All sources cited:** Commits, design docs, conversations
✅ **Proposed vs realized:** Clear distinction
✅ **Chronological accuracy:** Events in date order
✅ **Key decisions surfaced:** Major choices highlighted
✅ **Alternatives documented:** What was rejected and why

---

## EXAMPLE EXECUTION

**Query:** "What's the lineage of MarkdownNodeParser?"

### Execution

**1. Find it:**
```
Grep(pattern="MarkdownNodeParser", output_mode="files_with_matches")
→ Found: imem/src/imem/ingest.py, imem/tests/validate_indexing.py
```

**2. Read current:**
```
Read(imem/src/imem/ingest.py)
→ Line 60: self.parser = MarkdownNodeParser()
→ Usage: Standard LlamaIndex parser, no customization
```

**3. Get history:**
```
git log --all --follow --format="%H %ai %s" -- imem/src/imem/ingest.py
→ 9268206 2025-10-24 init
→ 5fa703b 2025-10-25 Retrieval working
→ c7dcb71 2025-10-29 H2 filter fix + template update
→ ... (8 commits total)
```

**4. Read genesis:**
```
git show 9268206:imem/src/imem/ingest.py
→ MarkdownNodeParser present from first commit
→ Imported from llama_index.core.node_parser
```

**5. Find design docs:**
```
Grep(pattern="MarkdownNodeParser", path=".context/design")
→ .context/develop/.changes/251024-0137_two-tier-llamaindex-conversation-indexing.md

Grep(pattern="MarkdownNodeParser", path=".claude/.convs")
→ .claude/.convs/251104-1850.md
```

**6. Read design context:**
```
Read(.context/develop/.changes/251024-0137_two-tier-llamaindex-conversation-indexing.md)
→ Decision: "Use section-level chunking instead of summary-level"
→ Rationale: "No LLM costs, better precision"
→ Alternative: "Generate summaries with Haiku 4.5 ($0.001/conversation)"
→ Why rejected: "Section-level chunking cheaper, more precise"

Read(.claude/.convs/251104-1850.md)
→ Proposal: SchemaAwareNodeParser (custom parser)
→ Status: Discussed Nov 3-4, NOT implemented
→ Would add: Schema evolution observer, type resolution
```

**7. Synthesize:**
```markdown
## MarkdownNodeParser Lineage

### Genesis (2025-10-24)
**Commit:** 9268206
**Design Doc:** .context/develop/.changes/251024-0137_two-tier-llamaindex-conversation-indexing.md
**Decision:** Use LlamaIndex MarkdownNodeParser for section-level chunking
**Rationale:**
- No LLM costs (vs Haiku 4.5 summary generation)
- Better precision (section-level vs summary-level)
- Battle-tested parser (vs custom implementation)
**Alternatives Considered:**
- Generate summaries with Haiku 4.5 - Rejected (cost + lower precision)
- Custom parser - Rejected (reinventing wheel)

### Evolution
**2025-10-25** (5fa703b): Retrieval working
- Basic functionality validated

**2025-10-29** (c7dcb71): H2 filter fix + template update
- Refined section detection
- Overview language-agnostic for impl changelogs

**2025-11-01** (f642e70): Layer separation
- Impl/pattern layer split introduced

### Proposed but Unrealized
**2025-11-03/04**: SchemaAwareNodeParser
- **Source:** .claude/.convs/251104-1850.md
- **Status:** Discussed but not implemented
- **Proposal:** Custom parser extending MarkdownNodeParser with:
  - Schema evolution observer
  - Cross-domain type resolution
  - Automatic metadata enrichment
- **Context:** Would enable typed vector store vision

### Current State
**Implementation:** Using vanilla LlamaIndex MarkdownNodeParser
**Approach:** Post-parse metadata enrichment (not custom parser)
**Design Philosophy:** Pragmatic - use battle-tested tools, add metadata as needed
**Status:** Stable, works well for current use cases
```

---

## KEY INSIGHT

Multi-source synthesis reveals the **decision archaeology**:
- **Git:** WHAT exists (code, commits)
- **Design docs:** WHY it exists (rationale, alternatives)
- **Conversations:** WHAT was imagined (proposals, visions)

Together: Complete story from idea → decision → implementation → current reality

---

## PRACTICAL VALUE

**Avoids:**
- Repeating rejected approaches
- Implementing already-discussed-and-abandoned ideas
- Missing context on "why we did it this way"

**Enables:**
- Understanding decisions without tribal knowledge
- Evaluating whether to revisit old proposals
- Learning from past trade-off analysis

**Use cases:**
- Onboarding new team members
- Evaluating migration decisions
- Understanding design philosophy
- Deciding whether to implement old proposals
