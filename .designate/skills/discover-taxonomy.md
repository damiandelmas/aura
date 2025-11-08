# discover-taxonomy

## OVERVIEW

Systematically searches a corpus to find distinct structural patterns and categorizes them by their essential characteristics. Rather than assuming patterns exist, this discovers them through agent-driven exploration that examines many examples, identifies what makes each unique, extracts representative samples, and builds a classification system. The output is a taxonomy showing all distinct types found, their defining features, and concrete examples—useful when you know examples exist but don't yet know how many types there are or what distinguishes them. This transforms implicit diversity into explicit categories.

---

## SPECIFICATION

**Purpose:** Find distinct patterns in corpus and categorize by characteristics

**Input:**
- Directory paths to search
- Pattern type (document formats, code structures, config styles, etc.)

**Output:**
- Taxonomy of distinct types found
- Characteristics per type (structure, density, ethic, etc.)
- Representative examples (1-3 per type)
- Comparison matrix

**Process:**
```
1. Launch Task(Plan agent) with search strategy
   - Specify locations to search
   - Request diversity (different types, not same pattern 10x)
   - Ask for categorization by methodology/structure

2. Agent searches and categorizes
   - Finds files matching scope
   - Extracts structural characteristics
   - Identifies unique features
   - Groups by similarity

3. Launch second Task to gather samples
   - Read actual content from each type
   - Extract representative examples
   - Note structure/characteristics/density

4. Synthesize taxonomy
   - Compare types
   - Build classification matrix
   - Map use cases
   - Return categorized findings
```

**Tool Composition:**
```
Task(Plan agent: search) → Task(Plan agent: sample) → Categorization → Taxonomy
```

---

## ACTUAL CONVERSATION EXECUTION

### Request: Discover Design Document Formats

**User asked:**
> "Can you get a sample of DIFFERENT design documents. It is important that we not just get 10 of the v1 schema, and a bunch of assorted design documents (plans, architecture, etc). We actually devised a few methodologies/templates for capturing these insights. It may be difficult to find them. How do you prose that you do this?"

**What I did:**

```
1. Described search strategy to user:
   "I need to find the different design capture METHODOLOGIES you've experimented with -
    not just v1 template variants, but fundamentally different formats for capturing insights."

   Search plan:
   - .claude/.vision/ - user-messages.md, core-user-messages.md patterns
   - .context/design/.changes/ - Look for docs that DON'T follow v1_exploration
   - .designate/ - statement files, vision files with different structures
   - assets/.context/design/ or assets/.inbox/ - experimental templates
   - Files named: "statement", "vision", "principle", "hypothesis", "question", "insight"

2. Launched first Task(Plan agent) for systematic discovery:

   Prompt to agent:
   """
   I need to find samples of DIFFERENT design document methodologies/templates in the aura codebase.

   CONTEXT:
   - User has multiple design capture formats beyond the standard v1_exploration template
   - Some are short and dense
   - Some use "user message + architectural insight" patterns
   - They exist in various locations
   - May be experimental/archived formats

   TASK:
   Search the following locations and find examples of DIFFERENT design document formats:
   1. .claude/.vision/ - user-messages.md, core-user-messages.md patterns
   2. .context/design/.changes/ - Look for docs that DON'T follow v1_exploration schema
   3. .designate/ - statement files, vision files with different structures
   4. assets/.context/design/ or assets/.inbox/ - experimental templates
   5. Any files with names like "statement", "vision", "principle", "hypothesis"

   For EACH distinct format you find:
   - Identify the format/methodology (e.g., "question + insights", "quote + why")
   - Get 1-2 representative examples
   - Note the structure/sections used
   - Extract what makes it unique from other formats

   DELIVERABLE:
   A categorized list of distinct design capture methodologies with:
   - Format name
   - File path examples (1-2 per format)
   - Structure description
   - Key characteristics that make it different

   Focus on DIVERSITY of formats, not quantity of same format.
   """

3. Agent returned findings: 10 DISTINCT FORMATS FOUND

   FORMAT 1: Quote + Why Pattern
   Location: .claude/.vision/core-user-messages.md
   Structure: ## Topic\n**Quote:**\n**Why:**
   Characteristics: Ultra-dense, preserves typos, architectural distillation

   FORMAT 2: Timestamp + User Message
   Location: .claude/.vision/user-messages.md
   Structure: ## YYMMDD-HHMM\n> "quote"
   Characteristics: Chronological, zero interpretation, raw voice

   FORMAT 3: Hypothesis + Components + Architecture
   Location: .designate/methodologies/flexschema/overview.md
   Structure: ## Hypothesis\n## Components\n## Architecture
   Characteristics: Scientific, testable, flow diagrams

   FORMAT 4: Visual Diagrams + Layer Architecture
   Location: .designate/.inbox/imem/brain/statements/temporal_statement-4.md
   Structure: ASCII diagrams with boxes/arrows showing layers
   Characteristics: Visual-first, geometric explanation

   FORMAT 5: Vision Alignment Statements
   Location: .designate/.inbox/fleet/vision/statement-2.md
   Structure: ## Mapping\n## Accordances\n## Shape Match
   Characteristics: Economic+architectural reasoning, perspective mapping

   FORMAT 6: Concept + Properties Pattern
   Location: .designate/.inbox/imem/flippable-chunks/flippable-chunks.md
   Structure: ## The Concept\n## Serving Logic\n## The Value
   Characteristics: Idea-driven, properties explicit

   FORMAT 7: Question + Key Insights Pattern
   Location: assets/.context/design/251011-0145_four-phase-changelog-architecture.md
   Structure: ## Question\n## Key Insights\n## Explored Ideas
   Characteristics: Exploration-driven, rejected vs accepted

   FORMAT 8: Central Question + Problem Analysis
   Location: .context/design/.changes/251018-1919_design-rationale-precision-and-completeness.md
   Structure: ## The Central Question\n## The Problem with X\n## Why X Is Hard
   Characteristics: Deep decomposition, educational, statistics

   FORMAT 9: Extended Quote + Context + Options + Properties
   Location: .context/design/.changes/251027-1715_aura-innovation-refinement.md
   Structure: **Quote:**\n**Why:**\n**Context:**\n**Options:**\n**Properties:**
   Characteristics: Exhaustive, all alternatives documented

   FORMAT 10: Meta-Analysis Pattern
   Location: .context/design/.changes/251007-2235_trace-journey-complete-review.md
   Structure: ## Meta-Analysis: Timeline\n### Phase N\n**Evidence Files:**
   Characteristics: Archaeological synthesis, timeline+evidence

4. Launched second Task(Plan agent) to gather content samples:

   Prompt to agent:
   """
   I need to read and extract actual content samples from the 10 distinct design document formats.

   For each format, read the file and extract:
   - First 60-80 lines showing the distinctive structure
   - Enough content to show the "ethic" or communication philosophy
   - The density and information architecture
   - How it handles uncertainty, decisions, or principles

   Return actual content samples, properly formatted.
   """

5. Agent returned content samples for all 10 formats

6. Synthesized taxonomy:

   Created comparison matrices:

   Density Spectrum:
   - Ultra-Dense: FORMAT 1, 2, 6
   - Balanced: FORMAT 3, 5, 7
   - Verbose: FORMAT 8, 9, 10

   Structural Approaches:
   - Chronological: FORMAT 2
   - Principle-Driven: FORMAT 1, 5
   - Question-Driven: FORMAT 7, 8
   - Hypothesis-Driven: FORMAT 3
   - Visual-First: FORMAT 4
   - Concept-Driven: FORMAT 6
   - Decision-Driven: FORMAT 9
   - Synthesis-Driven: FORMAT 10

   Unique Characteristics:
   - Preserves typos: FORMAT 1
   - Zero interpretation: FORMAT 2
   - YAML coordinates: FORMAT 3
   - ASCII diagrams: FORMAT 4
   - Economic reasoning: FORMAT 5
   - "The Value" section: FORMAT 6
   - Rejected vs Accepted: FORMAT 7
   - Statistics (40-60%): FORMAT 8
   - Anti-patterns called out: FORMAT 9
   - WRONG/CORRECT annotations: FORMAT 10

7. Returned complete taxonomy with:
   - 10 distinct format types
   - Structure templates for each
   - 1-3 examples per format (inline or linked)
   - Comparison matrix
   - Use case guidance
   - Ethic/density/structure analysis
```

**Tools used:**
1. Task(Plan agent) - Initial discovery and categorization
2. Task(Plan agent) - Content sample gathering
3. Synthesis - Comparison matrices and taxonomy building

**Agent behavior observed:**
- Searched multiple directory paths in parallel
- Identified structural differences automatically
- Categorized by methodology not just content
- Extracted defining characteristics
- Provided representative examples
- Built comparison matrices

---

## OUTCOME UNDERSTANDING

**What this skill does:**
Takes a search scope and discovers ALL distinct pattern types within it, rather than finding instances of ONE known pattern. The key difference from grep/search:
- Grep: "Find X" (you know what X is)
- discover-taxonomy: "What types exist?" (you don't know yet)

**Key insight:** Agent-driven exploration finds diversity you didn't know existed
- User knew "we have different formats"
- User didn't know there were 10 distinct types
- Agent systematically discovered and categorized them

**Success criteria:** Complete taxonomy showing:
- All distinct types found (not a sampling)
- Clear distinguishing characteristics
- Representative examples
- Comparison showing relationships

**Practical value:** Transforms "I know we have variety" into "Here are the 10 types, when to use each, and how they differ"

**Generalizability:** Same pattern works for:
- Code patterns (find all class structure types)
- Test patterns (find all testing approaches)
- Config patterns (find all configuration styles)
- API patterns (find all endpoint designs)

The corpus and pattern_type change, but the discover-categorize-compare workflow remains constant.
