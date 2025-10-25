---
schema_version: "v3"
type: "implementation.pattern-layer-dual-retrieval"
status: "completed"
keywords: "pattern-layer language-agnostic conceptual-mirror dual-layer-retrieval implementation-vs-pattern cross-project-learning semantic-search metadata-schema cli-enhancement"
timestamp: "2025-10-24T16:43:00-0700"
---

# Pattern Layer: Dual-Layer Retrieval System for Cross-Project Learning

## Request
> "I think we should change the language of one or two of the passes >>> and say something like DO NOTHING TO OVERVIEW OR DECISIONS OR HEADERS CONTENT IF THEY SATISFY REQUIREMENTS."
> "maybe we should create two workflows then. one for capture and one for convert?"
> "(1) Overview is ALWAYS language agnostic (2) REST of base changelog is language specific for actual develop logging (3) prismatic changelog is entirely language agnostic for general insight."

## Overview
Implemented a dual-layer retrieval architecture where each changelog exists in two forms: an implementation layer (code-specific) and a pattern layer (language-agnostic). The implementation layer preserves exact technical details for current project work, while the pattern layer extracts reusable patterns applicable across any technology stack. Search defaults to implementation layer for daily development (95% use case), with optional pattern layer queries for cross-project learning. The system indexes both layers simultaneously, uses filename detection for layer classification, and enforces phase-based filtering to exclude noisy design documents by default.

## Decisions

### Rename Conceptual Layer to Pattern Layer
- **Context**: Original naming used "conceptual.md" which was abstract and unclear in purpose
- **Solution**: Renamed to ".pattern.md" to explicitly convey "reusable patterns"
- **Rationale**: "Pattern" is more actionable - developers search for "authentication pattern" not "authentication concept"
- **Implementation**: Updated agent name, file extensions, metadata schema (v3_pattern_layer), all documentation
- **Impact**: Clearer user intent - "I want the pattern" vs "I want the implementation"

### Default Search to Implementation Layer Only
- **Context**: Initial design defaulted to searching both layers, causing 2x retrieval overhead
- **User Insight**: "95% of the time you want implementation (actual code), 5% you want patterns"
- **Solution**: Changed default `--layer` flag from `both` to `implementation`
- **Rationale**: Daily development needs code-specific answers; pattern discovery is intentional, not default
- **Benefit**: 50% faster searches (half the vectors), cleaner results, explicit opt-in for patterns

### Exclude Design Phase from Default Indexing
- **Context**: Design folder contains varied content (vision docs, research, abandoned ideas)
- **Solution**: Index only `develop`, `designate`, `document` phases by default; design requires `--include-design` flag
- **Rationale**: Design files are too heterogeneous (philosophical vs technical) and often outdated
- **Implementation**: Updated CLI to filter indexed phases, added opt-in flag for design
- **Impact**: Cleaner search results, faster indexing, reduced noise from exploratory documents

### Use Single Collection with Layer Metadata Field
- **Context**: Considered three approaches: (1) single collection + layer field, (2) separate collections, (3) named vectors
- **Solution**: Single collection with `layer` metadata field (`implementation` | `pattern`)
- **Rationale**: Unified search allows vector similarity to rank across both layers; simpler mental model
- **Alternatives Rejected**:
  - Separate collections: requires dual searches, can't compare relevance across layers
  - Named vectors: overkill complexity for same embedding model on different content
- **Benefit**: One query returns best matches regardless of layer, ranked by semantic similarity

### Remove Content Truncation from Search Display
- **Context**: Search results truncated at 500 chars, cutting off critical information mid-sentence
- **Discovery**: User noticed "Tests now require `--no-check` flag due to Sale type strictness (9/9 passing..." was cut off
- **Insight**: "Our chunks are extremely intelligent - sections are already optimal retrieval units"
- **Solution**: Removed all truncation - display full section content
- **Rationale**: H3 sections are self-contained (200-800 chars), already perfect size for complete context
- **Impact**: Users see full Context/Solution/Rationale/Code without artificial truncation

### Suppress Pydantic Warnings from LlamaIndex
- **Context**: Every search showed "UnsupportedFieldAttributeWarning" from pydantic internals
- **Solution**: Added `warnings.filterwarnings('ignore', category=UserWarning, module='pydantic')` to CLI and enhanced.py
- **Rationale**: Warning is cosmetic (LlamaIndex internal code issue), not actionable by users
- **Implementation**: Import warnings before LlamaIndex imports to suppress at load time
- **Impact**: Clean search output, professional user experience

### Conservative QA Agent Edits (5-15% vs 10-20%)
- **Context**: QA agent was rewriting good content, making it "better before QA than after"
- **Solution**: Updated instructions: "Don't touch what is already compliant. If something must be changed, only edit those exact parts (5-15% targeted edits)"
- **Rationale**: QA should polish violations, not rewrite compliant content
- **Impact**: Preserves original voice and detail while ensuring v3 compliance

## Implementation

### Architecture

1. **Layer Detection** → Filename-based: `*.pattern.md` → pattern layer, `*.md` → implementation layer
2. **Dual Indexing** → `imem init` indexes both files automatically, creates separate vectors per file
3. **Metadata Enrichment** → Adds `layer` field to payload alongside `source`, `phase`, `section_type`
4. **CLI Filtering** → `--layer` flag filters Qdrant query: `implementation` | `pattern` | `both`
5. **Phase Filtering** → `--in` flag defaults to `develop`, excludes `design` unless `--include-design`
6. **Display Logic** → Shows full section content with layer badge `[impl]` or `[pattern]` during indexing

### Code Signatures

**Layer Detection** (`imem/src/imem/ingest.py`)
```python
def _detect_layer(self, file_path: Path, phase: str) -> str:
    """Detect layer based on filename and phase.

    Only develop phase has pattern mirrors.
    Other phases are always 'implementation'.
    """
    if phase != 'develop':
        return 'implementation'

    if '.pattern.md' in str(file_path):
        return 'pattern'
    else:
        return 'implementation'
```

**Metadata Payload** (`imem/src/imem/ingest.py`)
```python
payload = {
    'source': 'changelog',
    'phase': phase,              # develop | designate | document
    'layer': layer,              # implementation | pattern
    'section_type': section_name,
    'category': category,
    'session_id': session_id,
    'content': node.get_content(),
    'file_path': str(file_path)
}
```

**Search Filter Logic** (`imem/src/imem/cli.py`)
```python
# Build filters based on phase and layer
filters = {}
if phase_filter != 'all':
    filters['source'] = 'changelog'
    filters['phase'] = phase_filter

# Add layer filter (only applies to develop phase)
if layer != 'both' and phase_filter == 'develop':
    filters['layer'] = layer
```

**Phase Exclusion** (`imem/src/imem/cli.py`)
```python
@click.option('--include-design', is_flag=True,
              help='Include design phase files (excluded by default)')
def init(force, vscode, include_design):
    # Define phases to index
    indexed_phases = ['develop', 'designate', 'document']
    if include_design:
        indexed_phases.append('design')

    for phase in indexed_phases:
        # ... index files in phase
```

**Content Display Without Truncation** (`imem/src/imem/cli.py`)
```python
# Show full section content (no truncation - sections are already optimal chunks)
content = result.get('content', '')
if content:
    # Indent each line for readability
    indented = '\n    '.join(content.split('\n'))
    click.echo(f"    {indented}")
    click.echo()  # Blank line between results
```

**Layer Badge Display** (`imem/src/imem/cli.py`)
```python
# Show layer badge in output during indexing
layer_badge = "[pattern]" if '.pattern.md' in str(md_file) else "[impl]"
click.echo(f"   ✅ {layer_badge:10} {md_file.relative_to(project_root)}")
```

## Patterns

### Dual-Layer Knowledge Representation
- **Pattern**: Same changelog exists in two forms - implementation (code-specific) and pattern (language-agnostic)
- **When**: Need to preserve technical details for current project while extracting transferable wisdom
- **Approach**: Pipeline stage [e] creates `.pattern.md` mirror that removes all language/framework specifics
- **Benefit**: Work in TypeScript project, learn from Python patterns without code pollution
- **Trade-off**: 2x storage (30 vectors per session vs 15), but enables cross-project learning

### Default to Common Case, Opt-In to Special Case
- **Pattern**: Search defaults to implementation layer (95% use case), requires explicit flag for patterns
- **When**: Optimizing for common workflow while preserving specialized functionality
- **Approach**: `--layer implementation` (default) vs `--layer pattern` (explicit) vs `--layer both` (nuclear)
- **Benefit**: Fast common case, discoverable advanced features, no accidental performance penalties
- **Anti-Pattern**: Don't default to "both" - forces users to pay 2x cost for rare use case

### Filename-Based Layer Detection
- **Pattern**: Use file extension to determine semantic layer without parsing content
- **When**: Need fast classification before content processing begins
- **Approach**: `*.pattern.md` → pattern layer, `*.md` → implementation layer
- **Benefit**: O(1) detection, no regex parsing, clear file organization
- **Alternative**: Content-based detection (rejected - slower, ambiguous, requires parsing)

### Intelligent Section Chunking Without Truncation
- **Pattern**: H2/H3 sections are self-contained knowledge units that should never be truncated
- **Discovery**: User noticed critical test results cut off mid-sentence: "9/9 passing..."
- **Insight**: "Our chunks are extremely intelligent - sections are already optimal retrieval units"
- **Solution**: Display full section content (200-800 chars typically), no artificial limits
- **Benefit**: Complete context (Context/Solution/Rationale/Code) in single retrieval, no information loss

## Constraints

### H1 Title Nodes Appear as "Just Headers" in Results
- **What**: Searching "typescript" returns H1 title nodes (37 chars) instead of rich H3 Decision sections
- **Discovery**: LlamaIndex's MarkdownNodeParser creates separate nodes for each header level
- **Analysis**: 15 nodes per doc: 1 frontmatter, 1 H1, ~3 H2 headers, ~10 H3 sections (only H3s have rich content)
- **Is This a Problem?**:
  - NO: H1 nodes useful for discovery ("Find changelog titled X")
  - NO: Specific queries ("migrate JSON to TypeScript") return rich H3 sections
  - YES: Generic queries ("typescript") match shallow H1 nodes
- **Potential Fix**: Filter nodes with `len(content) < 100` to skip header-only nodes
- **Decision**: Ship as-is for MVP, add filtering later if H1 noise becomes problematic

### Pattern Layer Only Exists for Develop Phase
- **What**: Only `develop/*.pattern.md` files get pattern layer; other phases always `implementation`
- **Rationale**: `designate/` (specs) and `document/` (architecture) are already language-agnostic
- **Implementation**: `_detect_layer()` returns `implementation` if `phase != 'develop'`
- **Impact**: Simpler metadata (pattern layer only where it adds value), reduced complexity

## Audit

### Created
- `.claude/agents/e_pattern-layer-mirror.md` - Renamed from e_conceptual-layer-mirror.md
- `.context/develop/.changes/*.pattern.md` - Pattern mirrors for all changelogs (16 files in test sandbox)

### Modified
- `imem/src/imem/ingest.py` - Added `_detect_layer()` method, `layer` field in payload
- `imem/src/imem/cli.py` - Added `--layer` flag, `--include-design` flag, removed content truncation, warning suppression
- `imem/src/imem/enhanced.py` - Fixed content retrieval key (`content` vs `information`), warning suppression
- `.claude/agents/d_quality-assurance.md` - Updated to 5-15% targeted edits (was 10-20%)
- `.claude/agents/e_pattern-layer-mirror.md` - All references updated from "conceptual" to "pattern"
- `.context/develop/.changes/*.conceptual.md` - Renamed to `.pattern.md` (2 files)

### Configuration
- Schema version: `v3_pattern_layer` (pattern mirrors)
- Metadata field: `layer` with values `implementation` | `pattern`
- Default search layer: `implementation` (not `both`)
- Indexed phases: `develop`, `designate`, `document` (design excluded)
- Display limit: None (was 500 chars) - show full sections
- Warning suppression: Pydantic UserWarning filtered

### Verification
- **Integration Test**: Indexed 32 files (16 impl + 16 pattern) in sandbox project
  - Total vectors: ~480 (15 vectors per file × 32 files)
  - Collection: `imem_2012b868`
  - Indexing time: ~5 minutes
- **Search Quality**:
  - Default search (`typescript`): Returns implementation files ✓
  - Pattern search (`typescript --layer pattern`): Returns pattern files ✓
  - Both layers (`provider agnostic --layer both`): Returns mixed results ranked by score ✓
- **Content Display**: Full sections shown without truncation ✓
- **Warning Suppression**: Clean output, no Pydantic warnings ✓
- **Layer Detection**: Badges `[impl]` and `[pattern]` displayed correctly during indexing ✓

### Deployment
- Install command: `pip install -e ./imem` (picks up all changes)
- Re-index command: `imem init --force` (recreates collection with layer metadata)
- Test command: `imem search "query" --layer pattern` (pattern-only search)
- Commands available:
  - `imem init` - Index develop, designate, document (excludes design)
  - `imem init --include-design` - Include design phase files
  - `imem search "query"` - Default: develop + implementation
  - `imem search "query" --layer pattern` - Pattern-only search
  - `imem search "query" --layer both` - Both layers
  - `imem search "query" --in all` - All phases
