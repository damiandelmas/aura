# catalog-types

## OVERVIEW

Transforms categorized findings into a structured reference document that others can use. Takes taxonomy data with examples and synthesizes it into organized markdown with intelligent example embedding—short examples appear inline for quick reference, long examples link to source files to avoid overwhelming the reader. Adds comparison matrices to show relationships between types, includes use case guidance for when to apply each pattern, and structures everything into logical sections. The result is a comprehensive catalog that serves as both quick reference and deep dive resource, generated automatically from the taxonomy data.

---

## SPECIFICATION

**Purpose:** Synthesize taxonomy into structured reference documentation

**Input:**
- Taxonomy data (types + characteristics)
- Examples (content or file paths)
- Comparison dimensions (density, structure, etc.)

**Output:**
- Markdown catalog file with:
  - One section per type
  - Overview + characteristics
  - 1-3 examples (inline if short, linked if long)
  - Comparison matrices
  - Use case guidance
  - Meta-principles

**Process:**
```
1. Structure document sections
   - Create hierarchy (one section per type)
   - Add overview + characteristics per type

2. Embed examples intelligently
   - Short examples (< ~80 lines): Inline markdown
   - Long examples: Link to file path
   - Include description for each

3. Add comparison matrices
   - Density spectrum
   - Structural approaches
   - Unique characteristics
   - Use case mapping

4. Write file (Write tool)
```

**Tool Composition:**
```
Synthesis (structure + examples) → Write (markdown file)
```

---

## ACTUAL CONVERSATION EXECUTION

### Request: Create Catalog Document

**User asked:**
> "create a file with each kind + overview of that kind + 1-3 examples of entries. if they are sufficently long (the example) then just link the file so i can open it."

**What I did:**

```
1. Received taxonomy data from previous discover-taxonomy execution:
   - 10 distinct format types
   - Structure descriptions
   - Characteristics per format
   - Content samples (some short, some long)
   - Comparison data

2. Structured the document hierarchy:

   # Design Capture Format Catalog
   ## Overview
   ## FORMAT 1: Quote + Why Pattern
      ### Overview
      ### Structure
      ### Characteristics
      ### Examples (1-3)
   ## FORMAT 2: Timestamp + Message
      [same structure]
   ... (repeat for all 10)
   ## Format Comparison Matrix
   ## Meta-Principles
   ## Use Case Guidance

3. Made intelligent example embedding decisions:

   SHORT FORMATS (embedded inline):
   - FORMAT 1 (Quote + Why): 3 examples inline
     Each example ~5 lines, total ~15 lines
     Decision: Inline (shows pattern clearly)

   - FORMAT 2 (Timestamp + Message): 3 examples inline
     Each example ~3 lines, total ~9 lines
     Decision: Inline (ultra-short)

   - FORMAT 9 (Extended Context): 2 examples inline
     Each example ~20 lines, total ~40 lines
     Decision: Inline (shows structure), PLUS link to full file

   LONG FORMATS (linked to files):
   - FORMAT 3 (Hypothesis + Components): Linked
     File: .designate/methodologies/flexschema/overview.md
     Decision: Link only (80+ lines)
     Added: Sample snippet showing hypothesis + first component

   - FORMAT 4 (Visual Diagrams): Linked
     File: .designate/.inbox/imem/brain/statements/temporal_statement-4.md
     Decision: Link only (complex ASCII diagrams)
     Added: Sample snippet showing layer diagram

   - FORMAT 5 (Vision Alignment): Linked
     File: .designate/.inbox/fleet/vision/statement-2.md
     Decision: Link only (80+ lines)

   - FORMAT 6 (Concept + Properties): Linked
     File: .designate/.inbox/imem/flippable-chunks/flippable-chunks.md
     Decision: Link only (80+ lines)
     Added: Sample snippet showing concept + value

   - FORMAT 7 (Question + Insights): Linked
     File: assets/.context/design/251011-0145_four-phase-changelog-architecture.md
     Decision: Link only (complex exploration)

   - FORMAT 8 (Central Question): Linked
     File: .context/design/.changes/251018-1919_design-rationale-precision-and-completeness.md
     Decision: Link only (deep analysis)

   - FORMAT 10 (Meta-Analysis): Linked
     File: .context/design/.changes/251007-2235_trace-journey-complete-review.md
     Decision: Link only (timeline document)

4. Created comparison matrices:

   ### Information Architecture Spectrum
   Minimal → Maximal ordering of all 10 formats

   ### Density Spectrum
   Ultra-Dense: FORMAT 1, 2, 6
   Balanced: FORMAT 3, 5, 7
   Verbose: FORMAT 8, 9, 10

   ### Structural Approaches
   Chronological: FORMAT 2
   Principle-Driven: FORMAT 1, 5
   Question-Driven: FORMAT 7, 8
   [etc.]

   ### Unique Characteristics Table
   | Format | Unique Feature |
   |--------|---------------|
   | FORMAT 1 | Preserves typos for authenticity |
   | FORMAT 2 | Zero interpretation layer |
   [etc.]

5. Added meta-principles section:

   ### 1. No Code Emphasis
   All formats emphasize design thinking, not implementation code

   ### 2. User Voice Preservation
   Formats prioritizing authentic voice: FORMAT 1, 2, 9
   Philosophy: User's words = ground truth

   ### 3. Progressive Disclosure
   Quick reference: FORMAT 1, 2
   Conceptual: FORMAT 3, 5, 6
   Deep dive: FORMAT 8, 9, 10

   [etc. - 6 meta-principles total]

6. Added use case guidance:

   **When to use FORMAT 1 (Quote + Why):**
   - Capturing architectural principles from conversations
   - Distilling user messages into design rules
   - Creating communication style guides

   **When to use FORMAT 2 (Timestamp + Message):**
   - Raw conversation preservation
   - Archaeological records
   - Input for later analysis

   [etc. for all 10 formats]

7. Added file location patterns:

   ### .claude/.vision/
   - Core architectural principles (FORMAT 1)
   - Raw user messages (FORMAT 2)

   ### .designate/methodologies/
   - System methodologies (FORMAT 3)
   - Scientific documentation

   [etc.]

8. Used Write tool to create file:
   Write(
     file_path: .designate/methodologies/design-capture-formats.md
     content: [complete structured catalog]
   )

   Final document:
   - 10 format sections with overviews
   - 15+ inline examples (short formats)
   - 7 linked examples (long formats)
   - 4 comparison matrices
   - 6 meta-principles
   - Use case guidance for all 10
   - File location patterns
   - Evolution notes

   Total: ~1000 lines, well-structured, navigable
```

**Tools used:**
1. Synthesis (structure catalog from taxonomy data)
2. Write (create markdown file)

**Design decisions made:**
- Inline vs linked based on ~80 line threshold
- Added sample snippets even for linked files
- Comparison matrices show relationships
- Meta-principles extract patterns across formats
- Use case guidance makes it actionable

---

## OUTCOME UNDERSTANDING

**What this skill does:**
Takes raw taxonomy data (which could be a list, a table, unstructured findings) and transforms it into a navigable reference document that humans actually want to read. The key operations:
1. Structuring (organize into logical sections)
2. Example embedding (smart inline/link decisions)
3. Relationship mapping (comparison matrices)
4. Guidance (when to use what)

**Key insight:** Size-aware example handling prevents document bloat
- Short examples: Immediate visibility aids learning
- Long examples: Links prevent overwhelm
- Sample snippets: Give taste of linked content

**Success criteria:** Usable reference that serves both:
- Quick lookup ("What's FORMAT 3?")
- Deep exploration ("Show me all 10 formats compared")

**Practical value:** Transforms discovery output into knowledge artifact
- Discovery finds the patterns
- Catalog makes them usable
- Team can reference it repeatedly

**Generalizability:** Same pattern works for cataloging:
- Code patterns found → code pattern catalog
- Test patterns found → test pattern catalog
- Config patterns found → config pattern catalog
- API patterns found → API design catalog

The input is always "categorized types + examples", output is always "structured reference with smart example handling". The domain changes but the cataloging workflow remains constant.
