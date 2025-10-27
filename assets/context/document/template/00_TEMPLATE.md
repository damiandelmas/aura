# Eternal Architecture Template

**Version:** v1.0
**Last Updated:** 2025-10-25
**Purpose:** Static architecture documentation for `.document/architecture/`

---

## Template

```markdown
---
schema_version: "v3_adaptive"
type: "architecture.{system}-{scope}"
status: "stable"
keywords: "space separated terms"
timestamp: "YYYY-MM-DDTHH:MM:SS-0700"
---

# {System Name} Architecture

## Purpose

Write 1-2 paragraphs describing what this system does and what problem it solves.
Use present tense, language-agnostic terms. Focus on timeless concepts, not implementation details.

**This section answers:** "What is this system for?"

<!-- Example:
The system provides data extraction for application sessions. It parses session files,
extracts structured information (events, actions, metadata), and presents this through
an interface. The system enables retrieval of historical data, analysis of usage patterns,
and export of formatted reports.
-->

## Components

Describe what EXISTS in the system. List modules, files, classes, or services.
For each component, explain what it does (not how it evolved).

**This section answers:** "What are the parts?"

**{ComponentName}** (`path/to/file`) - Brief description of what this component does.
Explain its role in the system, what data it handles, what operations it provides.
Use present tense. Focus on behavior, not history.

**{AnotherComponent}** (`path/to/file`) - Another component description.

<!-- Supporting elements -->
**{SupportingFile}** - Configuration, utilities, or supporting code.

<!-- Example:
**DataFinder** (`finder.py`) - Locates data files by scanning storage directories.
Provides search by identifier, content filters, and modification time. Returns file paths sorted
by recency.

**DataParser** (`parser.py`) - Parses serialized data files into structured objects.
Extracts events, actions, and metadata. Provides unified chronological view of all entries.
-->

## Data Flow

Describe HOW data moves through the system. Use present tense to map the pipeline.
Show the sequence of operations without implementation details.

**This section answers:** "How does it work?"

**{LayerName}** - User/System triggers action. {Component} performs operation. Result flows to next layer.

**{NextLayer}** - Receives data from previous layer. Transforms or processes it. Outputs to destination.

**{FinalLayer}** - Consumes processed data. Presents to user or integrates with external system.

<!-- You can use numbered steps if clearer:
1. User invokes command → Finder locates file
2. Retrieval loads file → Parses into structured data
3. Formatter receives data → Generates markdown output
4. Output flows to terminal or file
-->

<!-- Example:
**Discovery Layer** - User provides identifier. Finder scans storage for matching files.
Returns path to data file.

**Processing Layer** - Loads data file sequentially. Parses each entry into structured format.
Extraction methods build datasets (events, metadata, timeline).

**Output Layer** - Receives processed data. Generates formatted output. Result flows
to display or file.
-->

## Integration Points

Describe HOW this system connects to external systems, APIs, or services.
List each integration point and explain the interaction pattern.

**This section answers:** "How does it connect to other systems?"

**{ExternalSystem}** - How this system interacts with external dependency. What data is exchanged.
What protocol or format is used.

**{AnotherIntegration}** - Another external connection or API surface.

<!-- Example:
**Filesystem Access** - Reads data files from application storage directories. Requires read
permissions. No write operations to source data.

**Document Format** - Generates structured output compatible with document parsers. Section headers
serve as chunk boundaries for indexing and search.

**Command Interface** - Uses framework for command definition and argument parsing. Commands map to
handler functions with metadata.
-->

## Patterns & Principles

Describe WHY the system is designed this way. List design patterns, architectural principles,
or mental models that guide the structure. Use timeless concepts.

**This section answers:** "What are the design principles?"

**{PatternName}** - Description of the pattern or principle. Why it's used. What benefit it provides.
Keep it conceptual and language-agnostic.

**{AnotherPrinciple}** - Another design decision or architectural pattern.

<!-- Example:
**Single Responsibility Separation** - Each component handles one concern. Finder locates resources.
Parser extracts data. Formatter generates output. Changes to one layer don't affect others.

**Unified Data Source** - Single method provides complete view of all data.
All other access patterns filter this source. Ensures consistency across operations.

**One Format Philosophy** - Single output format serves all consumers (interfaces, search, display).
Avoids format proliferation. Optimization benefits all use cases simultaneously.
-->

## Usage

Describe HOW to interact with the system. Show commands, API calls, or integration examples.
Use real syntax but keep examples focused on common patterns.

**This section answers:** "How do I use this?"

**Installation**
```bash
# Installation steps
```

**Common Commands**
```bash
# Example command patterns
```

**Programmatic Access**
```language
// Example code showing API usage
```

**Integration Example**
```bash
# How to integrate with other systems
```

<!-- Example:
**Installation**
```bash
cd /path/to/system
package-manager install .
```

**Discovery Commands**
```bash
system list
system list --filter "criteria"
```

**Display Commands**
```bash
system show data <identifier>
system show summary <identifier>
```

**Programmatic Access**
```language
import system.Component

component = Component()
data = component.load(path)
result = component.process(data)
```
-->
```

---

## Metadata Schema

### Required Fields
```yaml
schema_version: "v3_adaptive"
type: "architecture.{system}-{scope}"  # Examples: architecture.imem-overview, architecture.trace-parsing
status: "stable" | "draft" | "deprecated"
keywords: "space separated terms"
timestamp: "YYYY-MM-DDTHH:MM:SS-0700"  # Last refresh/verification time (update when architecture changes)
```

### Type Format
**Pattern:** `architecture.{system}-{scope}`

**System:** The codebase being documented (imem, trace, aura)

**Scope:** The aspect, subsystem, or depth of coverage (flexible, descriptive)
- **Breadth**: overview, reference, detailed
- **Subsystem**: indexing, search, registry, parsing, export
- **Aspect**: dataflow, patterns, integration, business-logic

**Examples:**
```yaml
type: "architecture.imem-overview"        # High-level IMEM introduction
type: "architecture.imem-indexing"        # Deep dive into indexing subsystem
type: "architecture.trace-parsing"        # How TRACE parsing works
type: "architecture.aura-ecosystem"       # How AURA components interact
```

**Parsing:** At index time, split to extract `category` (architecture), `system` (imem), `scope` (overview)

### Forbidden Fields
- ❌ `phase` - Architecture docs always in .document/architecture/
- ❌ `session_id` - Not linked to specific conversation

---

## Section Requirements

### Always Include (6 Required Sections):
1. **Purpose** - What the system does, what problem it solves
2. **Components** - What exists (modules, files, classes)
3. **Data Flow** - How it works (pipeline, sequence)
4. **Integration Points** - How it connects to external systems
5. **Patterns & Principles** - Why it's designed this way
6. **Usage** - How to interact with it

### Never Include:
- ❌ "Recent Changes" or "History" section
- ❌ "Migration Guide" or "Upgrade Path"
- ❌ "Evolution" or "Timeline"
- ❌ Temporal language in content (dates belong in frontmatter only)

---

## Writing Guidelines

### Language-Agnostic Descriptions

Write about CONCEPTS, not code:

❌ **Framework-Specific:**
> "Modified `ClaudeAgent.from_yaml()` to support individual YAML files"

✅ **Language-Agnostic:**
> "Modified agent configuration loader to support individual files per agent"

❌ **Framework-Specific:**
> "Uses Click decorators for command routing in cli.py"

✅ **Language-Agnostic:**
> "Uses declarative command framework for routing user actions"

### Present Tense Only

Describe what EXISTS, not what CHANGED:

❌ **Past Tense:**
> "We refactored from 4 layers to 3 for simplicity"

✅ **Present Tense:**
> "The system uses 3 layers for clean separation of concerns"

❌ **Temporal:**
> "Recently added support for partial session ID matching"

✅ **Eternal:**
> "Supports partial session ID matching (minimum 8 characters)"

### Descriptive, Not Narrative

Show STRUCTURE, not STORY:

❌ **Narrative:**
> "First, the user runs a command, then the system finds the file, after that it parses..."

✅ **Descriptive:**
> "User invokes command → Finder locates file → Retrieval parses data → Formatter generates output"

❌ **Narrative:**
> "We designed this to handle edge cases and make it more robust"

✅ **Descriptive:**
> "Wraps parsing in try-except blocks. Logs warnings but continues processing remaining entries."

---

## For LlamaIndex MarkdownNodeParser

**This template is optimized for hierarchical parsing:**

### Node Structure
- **H1** (`# Title`): Document root node
- **H2** (`## Purpose`, `## Components`): Section parent nodes
- **Content under H2**: Section body (can include lists, code blocks)

**Each H2 section becomes a searchable node** with metadata and full content.

### Why Not H3 Subsections?

Architecture docs describe **stable structure**, not **variable items**.

**Changelogs** use H3 for items because:
- Variable number of decisions, constraints, failures
- Each item is independent and searchable
- Progressive disclosure (2-6 fields per item)

**Architecture docs** use H2 sections because:
- Fixed structure (always 6 sections)
- Components listed in one section (not separate H3s)
- Stable content that changes rarely

### Metadata Enrichment

**MarkdownNodeParser automatically extracts:**
- `header_path`: "Components" or "Data Flow"
- `node_type`: "h2"
- `file_path`: `architecture_trace.md`

**Custom metadata added at index time:**
- `type`: From frontmatter (`architecture.imem-overview`)
- `category`: Extracted from type (`architecture`)
- `system`: Extracted from type (`imem`)
- `scope`: Extracted from type (`overview`)
- `status`: From frontmatter (`stable`)
- `keywords`: From frontmatter
- `timestamp`: From frontmatter (last refresh date)

### Query Patterns Enabled

```python
# Find all architecture docs
filter={'type': {'$glob': 'architecture.*'}}

# Find all IMEM architecture docs
filter={'type': {'$glob': 'architecture.imem-*'}}

# Find all overview docs across systems
filter={'type': {'$glob': 'architecture.*-overview'}}

# Find stable architecture docs
filter={'type': {'$glob': 'architecture.*'}, 'status': 'stable'}

# Find stale docs (not updated in 6 months)
filter={'type': {'$glob': 'architecture.*'}, 'timestamp': {'$lt': six_months_ago}}
```

---

## Complementarity with Changelogs

**Architecture answers:** "What exists and how does it work?"

**Changelogs answer:** "What changed and why?"

### Example: Same System, Different Docs

**.document/architecture/architecture_system.md** (Eternal):
```markdown
## Components

**DataFinder** (`finder.py`) - Locates data files by scanning
storage directories. Supports search by identifier, filters, and date ranges.

**DataParser** (`parser.py`) - Parses serialized files into structured
objects. Provides unified chronological view of all entries.

**OutputFormatter** (`formatter.py`) - Generates formatted output from
processed data. Creates sections for indexing and chunking.
```

**.develop/.changes/YYMMDD-HHMM_layer-cleanup.md** (Temporal):
```markdown
## Overview
Removed intermediate wrapper layer between parser and formatter.
Updated consumers to call parser + formatter directly. Simplified from 4 layers
to 3 for cleaner architecture.

## Implementation
### Before
Interface → finder → parser → wrapper → formatter (4 layers)

### After
Interface → finder → parser → formatter (3 layers)
```

**Zero overlap.** Architecture describes current state. Changelog describes journey.

---

**This template is for AI agents creating `.document/architecture/` static maps in the AURA documentation system.**
