● Found: Two-Tier Knowledge Architecture

  Core documents:

  1. Two-Tier Retrieval Pattern

  .context/.vision/two-tier/architecture.md:1

  Principle: Tier 1 indexes metadata. Tier 2 fetches content.

  Structure:
  - Metadata: date, authority (1-10), type, scope
  - Summary: 150-250 words (semantically dense)
  - Source: retrieval_method + location + optional query

  Flow: Query → Vector search (summaries only) → Agent reads → Selects sources → Fetches live → Synthesizes

  ---
  2. Knowledge Registry Application

  .context/.vision/hangar-knowledge/251022-1234.md:1

  Maps two-tier to BASE/PORT/RUNTIME:

  - BASE/: Registry (vector indexed summaries + source pointers)
  - HANGAR/KNOWLEDGE/: Raw/curated document storage (optional)
  - PORT/: Research assemblies (saved knowledge compositions)
  - RUNTIME/: Query interface (IMEM + fetch)

  Entry format:
  ---
  source_type: url|file|mcp
  source: <pointer>
  scope: keywords
  ---
  # CHUNK: Title
  ## SUMMARY
  [200 words - only this gets vectorized]
  ---

  ---
  3. BASE/PORT/RUNTIME Architecture

  .context/.vision/end-state/02-architecture.md:1

  Connects to capabilities:

  - BASE: Runtime-agnostic markdown (capability docs, modular sections)
  - PORT: String interpolation {{module.section}}
  - RUNTIME: Claude Code extensions (.claude/ directory)

  Same pattern: Metadata/summaries → reference → fetch on demand

  ---
  4. Implementation

  library/knowledge/index.md:1

  Live implementation of two-tier registry:
  - Indexes official docs, extension points
  - Stores location + summary
  - Retrieves via IMEM search

  ---
  Key insight: Two-tier pattern applies to both:
  1. Knowledge/URLs (summaries → fetch docs)
  2. Capabilities (BASE sections → PORT interpolation → RUNTIME composition)

  Language-agnostic: Markdown summaries + retrieval pointers work for any source type.

> '/home/axp/projects/mind/60_aesthetics/registry.md' this is a pretty decent implementaiton of that. What do 
u think? 

● Read(~/projects/mind/60_aesthetics/registry.md)
  ⎿  Read 398 lines

● Solid practical implementation. Core two-tier intact.

  What Works Well

  Entry structure:
  - Consistent format (title, link, tags, summary)
  - Source pointers (all URLs - fetchable)
  - Information-dense summaries
  - Modular/append-friendly
  - Clear separators

  Two-tier principles present:
  - Tier 1: Tags + "What" summaries (vectorizable)
  - Tier 2: Link (fetch on demand)
  - No full content cached

  Refinements for Spec Alignment

  Missing from architecture doc:
  ## Entry Title
  **Link:** https://...
  **Tags:** ...
  **Date:** 2025-01-03
  **Authority:** 3 (community curated)
  **Source Type:** url
  **Retrieval:** WebFetch

  **Summary:**
  [150-250 words - current "What" sections vary 50-150]

  **Use Cases:**
  [Current "Why" placeholder - when to reference this]

  Authority scale (if you want deduplication):
  - 1-3: Canonical (official artist sites, museum records)
  - 4-6: Verified (Artsy, established galleries)
  - 7-9: Experimental (personal blogs, unverified)

  What's Actually Important

  Your implementation prioritizes usability over spec purity - which is correct.

  Core intact:
  1. ✅ Summaries separate from full content
  2. ✅ Source pointers for live fetch
  3. ✅ Consistent structure for indexing
  4. ✅ Maintainable (append-only pattern)

  Optional additions:
  - Date/authority if you want temporal/quality filtering
  - Explicit retrieval_method if sources diversify (files, MCPs, not just URLs)
  - Standardize summary length for consistent vector search quality

  Ship it. Refine only if IMEM search quality degrades or you add non-URL sources.

> its probably fine as it is. '/home/axp/projects/mind/60_aesthetics/collection.md' 

● Read(~/projects/mind/60_aesthetics/collection.md)
  ⎿  Read 17 lines

● Smart separation. Registry vs. Collection.

  Pattern Recognition

  registry.md = Discovery/aspiration
  - What exists (external knowledge)
  - Why it matters (research/inspiration)
  - Source: URLs (fetch on demand)

  collection.md = Ownership/inventory
  - What you have (personal tracking)
  - Acquired + Status (temporal/lifecycle)
  - Source: Purchase links (provenance)

  Both Use Two-Tier

  Tier 1 (indexed):
  - Tags, acquired date, status
  - Summary ("What" field)

  Tier 2 (fetch on demand):
  - Link → product details, reviews, pricing

  The Elegance

  Same pattern, different domains:
  - Registry: "Things I'm researching"
  - Collection: "Things I own"

  Natural workflow: Registry entry → acquire → Collection entry.

  Could cross-reference:
  ## Carhartt Pants
  **Link:** https://amazon.ca/dp/B002MBJILM
  **Registry Entry:** See registry.md#workwear-research
  **Acquired:** 2025-01

  Or don't. Keeping them separate is clean too.

> what is the minimal schema for this? 

● Minimal Two-Tier Schema

  Absolute minimum (3 fields):

  ## [Title]
  **Link:** [source_pointer]
  **What:** [summary]

  That's it.

  - Title: Identifies entry
  - Link: Tier 2 fetch pointer
  - What: Tier 1 vector search content

  ---
  Optional Enhancements

  Add only if needed:

  **Tags:** [classification]          # If summary isn't enough for search
  **Date:** YYYY-MM-DD               # If temporal filtering matters
  **Authority:** 1-10                # If deduplication needed
  **Source Type:** url|file|mcp      # If multiple retrieval methods

  ---
  Your Current Schema

  Registry (5 fields):
  - Title
  - Link ✓ (required)
  - Tags
  - What ✓ (required)
  - Why

  Collection (6 fields):
  - Title
  - Link ✓ (required)
  - Acquired
  - Status
  - Tags
  - What ✓ (required)
  - Notes

  Could strip to 3 if you wanted. But your extras add value:
  - Tags: Fast filtering without full search
  - Acquired/Status: Lifecycle tracking
  - Why/Notes: Context preservation

  ---
  Decision Point

  Minimal (for new registries):
  ## Thing
  **Link:** url
  **What:** summary

  Practical (what you have):
  Keep tags + 1-2 domain-specific fields (acquired, status, why).

  Ship minimal. Add fields when pain emerges.

> perhaps we keep the terms AS general as possible? who, what, where, when, why? i mean some of those are 
awkward / irrelevant. but what do u think for this? 

● 5 W's as Universal Schema

  Strong concept. Natural mental model.

  ---
  Core Schema (W-based)

  ## [Title]

  **Where:** [source_pointer - url/file/mcp]
  **What:** [summary - description]
  **When:** [date - created/acquired/published]
  **Who:** [creator/author/artist]
  **Why:** [significance/use case]

  ---
  Mapping Your Current Schemas

  Registry → W's:
  ## Ernst Haas | Route 66
  **Where:** https://artsy.net/...
  **What:** 1969 dye-transfer print, Route 66 scene...
  **When:** 1969 (created)
  **Who:** Ernst Haas
  **Why:** Pioneering color photography as art medium

  Collection → W's:
  ## Carhartt Utility Pants
  **Where:** https://amazon.ca/...
  **What:** Loose-fit canvas work pants, navy...
  **When:** 2025-01 (acquired)
  **Who:** Carhartt
  **Why:** [intended use/aesthetic choice]

  ---
  Where W's Get Awkward

  Some domains don't use all W's:
  - Concept/idea: "Who" is author, but often irrelevant
  - URL bookmark: "When" might be access date (noisy)
  - Tool/capability: "Why" is use case (fits), "Who" is maintainer (maybe irrelevant)

  Solution: Make all W's optional except required pair.

  ---
  Minimal + W's

  Absolute minimum (2 fields):
  **Where:** [fetch pointer - REQUIRED]
  **What:** [summary - REQUIRED]

  Add W's as relevant:
  **When:** [if temporal matters]
  **Who:** [if attribution matters]
  **Why:** [if use case/significance matters]

  Non-W metadata (as needed):
  **Tags:** [search/filtering]
  **Authority:** [deduplication]
  **Status:** [lifecycle]

  ---
  Recommendation

  Universal template:
  ## [Title]

  **Where:** [source]
  **What:** [summary]
  **When:** [date]
  **Who:** [creator]
  **Why:** [significance]

  **Tags:** [optional]
  **[Domain-specific]:** [optional]

  - First 2 W's (Where/What) required
  - Other W's optional (use if natural)
  - Non-W fields allowed (Tags, Status, Authority)

  Keeps W's as semantic structure without forcing awkward fits.

> yeah this is getting a bit awkward. we need to deliniate INFORMATION ABOUT THE SUBJECT and INFORMATION ABOUT 
THE UTILITY FOR USER. Do you see this split? 

● YES. Critical split.

  ---
  Two Information Domains

  1. SUBJECT (Intrinsic - about the thing)

  - What it is
  - Who made it
  - When it was created
  - Where it came from (original source)

  2. USER (Extrinsic - your relationship to it)

  - Why you saved it
  - When you discovered/acquired it
  - How you use it
  - Status in your workflow
  - Your notes

  ---
  The Confusion

  "When" ambiguity:
  - Created: 1969 (subject)
  - Acquired: 2025-01 (user)

  "Where" ambiguity:
  - Artist's website (subject source)
  - Your bookmark URL (user reference)

  "Why" is always user (your motivation)

  ---
  Clean Schema

  ## [Title]

  # SUBJECT
  **Source:** [fetch pointer]
  **Description:** [what it is]
  **Creator:** [who]
  **Created:** [when - original date]

  # USER
  **Acquired:** [when you found/bought it]
  **Purpose:** [why you care]
  **Status:** [lifecycle]
  **Notes:** [your thoughts]

  ---
  Minimal (Two-Tier Aligned)

  Required:
  **Source:** [Tier 2 - fetch pointer]
  **Description:** [Tier 1 - vector search content]

  Subject metadata: Add as relevant
  User metadata: Add as relevant

  ---
  This maps perfectly to two-tier:
  - Tier 1 indexes: Description + User metadata (Purpose, Status)
  - Tier 2 fetches: Source → full subject details

  Much cleaner.

> '/home/axp/projects/fleet/hangar/code/aura/main/.context/design/.modules/research/memory-research.md' they 
have a way of handling the two types of 'time' 

● Read(~/projects/fleet/hangar/code/aura/main/.context/design/.modules/research/memory-research.md)
  ⎿  Read 717 lines

● Perfect. Bi-temporal model solves it.

  ---
  The Pattern (from memory-research.md:39-56)

  Valid Time (Subject - business semantics):
  - created: When thing was made (1969 for photo)
  - deprecated: When thing stopped existing (optional)

  Transaction Time (User - system tracking):
  - added: When you saved/acquired it (2025-01)
  - removed: When you invalidated it (optional)

  ---
  Applied to Your Schema

  Registry (research/inspiration):
  ## Ernst Haas | Route 66

  **Source:** https://artsy.net/...
  **Description:** 1969 dye-transfer print...

  # SUBJECT (Valid Time)
  **Created:** 1969
  **Creator:** Ernst Haas

  # USER (Transaction Time)
  **Added:** 2025-01-15
  **Purpose:** Color photography as art research
  **Tags:** 1960s, color photography, americana

  Collection (owned items):
  ## Carhartt Utility Pants

  **Source:** https://amazon.ca/...
  **Description:** Loose-fit canvas work pants...

  # SUBJECT (Valid Time)
  **Created:** [product release year]
  **Creator:** Carhartt

  # USER (Transaction Time)
  **Acquired:** 2025-01
  **Status:** active
  **Purpose:** Utilitarian aesthetic
  **Tags:** workwear, canvas

  ---
  Minimal Implementation

  Required (2 fields):
  - source: Fetch pointer
  - description: Summary

  Subject metadata (optional):
  - created: Original date
  - creator: Who made it

  User metadata (optional):
  - added: When you saved it
  - acquired: When you got it
  - status: Lifecycle
  - purpose: Why you care

  ---
  Clean separation. Query either time dimension independently.