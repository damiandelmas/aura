---
session_id: "current"
status: "research"
---

# Difftastic for Design Evolution Analysis

**Research into using structural diff tools for knowledge extraction from design evolution.**

---

## Tool Selection

**Difftastic** identified as most viable option for semantic diff analysis:
- Active maintenance (Rust, 20k+ stars)
- Works standalone (no git required)
- Understands markdown structure (H2/H3 hierarchy)
- CLI-based (requires subprocess + output parsing)

**Limitation**: No programmatic API. Terminal output designed for humans, not machines.

**Alternative considered**: ast-grep has Python bindings but less suited for markdown document comparison.

---

## Proposed Applications

### 1. Vision Drift Detection

Compare canonical vision against design modules and implementation reality:

```bash
# Vision → Design drift
difft .context/.vision/architecture.md design/module-x/.vision

# Design → Implementation drift  
difft design/module-x/.vision document/.architecture/current.md
```

**Value**: Surfaces conceptual divergence between phases. Enables early correction before implementation.

### 2. Module Conflict Detection

Compare parallel design streams before integration:

```bash
difft design/module-a/architecture.md design/module-b/architecture.md
```

**Value**: Identifies conflicting approaches across concurrent design work. Addresses stated need to "pull out the diff and ensure alignment before implementation."

### 3. Design Evolution Tracking

Analyze sequential changes within `.changes/` directory:

```bash
cd design/module/.changes
difft 001-initial.md 002-revised.md
difft 002-revised.md 003-final.md
```

**Value**: Creates timeline of how thinking evolved. Supports "block-chaining ideation" goal.

---

## Novel Concept: Recursive Change Density Analysis

**Hypothesis**: Measuring change density at multiple levels could identify pivotal design moments.

### Three-Level Analysis

**Level 1 - File Comparison**: Overall evolution between sequential design documents

**Level 2 - Section Comparison**: Changes within modified sections (Decision, Constraint, Pattern sections)

**Level 3 - Field Comparison**: Changes within section fields (Context, Solution, Rationale)

### Density Metric

```
density = changed_content_size / total_section_size
```

**Interpretation**:
- Low (0.1-0.3): Refinement
- Medium (0.4-0.6): Significant evolution
- High (0.7-1.0): Pivotal moment

**Application**: Automatically surface where thinking shifted most dramatically across design evolution, extracting "dense inertia" - concentrated conceptual change.

### Change Classification

Potential categories for detected changes:
- `reversal`: Previous decision contradicted
- `constraint_cascade`: Discovery of constraint revealed others
- `pattern_recognition`: Realized similarity to existing pattern
- `scope_adjustment`: Requirements changed
- `refinement`: Incremental improvement
- `pivot`: Fundamental approach change

---

## Implementation Requirements

### Parsing Challenge

Difftastic outputs terminal-formatted text. Extraction of structured data requires:

```python
import subprocess

def semantic_diff(file1, file2):
    result = subprocess.run(
        ['difft', '--color=never', file1, file2],
        capture_output=True, text=True
    )
    
    # Parse terminal output into structured data
    # Extract: changed sections, added/removed content, context
    return parse_difft_output(result.stdout)
```

**Note**: No existing libraries found for parsing difftastic output into structured data.

### Recursive Analysis Pipeline

```
Stage 1: File-level diffs → identify changed documents
Stage 2: Section-level diffs → isolate modified sections  
Stage 3: Field-level diffs → analyze subsection changes
Stage 4: Density calculation → identify pivotal moments
Stage 5: Classification → categorize change types
```

---

## Integration with IMEM Architecture

### Relationship to Existing Components

**Template-as-Type-System**: Provides structural boundaries for diff analysis. H2/H3 hierarchy enables section-level comparison.

**Document Properties**: Frontmatter metadata (session_id, timestamp) enables temporal sequencing of diffs.

**BRAIN Temporal Intelligence**: Recursive density analysis could enhance git-based supersession detection. Instead of binary supersession, calculate narrative distance using change density.

### Proposed Workflow

```
Design phase:
1. Write sequential .changes/ files (messy exploration)
2. Run recursive diff analysis across sequence
3. Extract pivotal moments automatically
4. Generate "Key Design Pivots" summary

Implementation phase:
1. Compare final design/.plan against document/architecture
2. Surface divergences
3. Feed to changelog generation (explain why implementation differs)

Maintenance phase:
1. Git hook triggers difft on markdown changes
2. Calculate narrative radius using density metric
3. Update BRAIN supersession metadata
```

---

## Open Questions

1. **Parsing Complexity**: How much structure can be reliably extracted from difftastic terminal output? May require custom markdown parser instead.

2. **Density Threshold Tuning**: What density values actually correlate with "pivotal moments"? Requires empirical testing on real design evolution data.

3. **Classification Accuracy**: Can change types be reliably classified from diff output alone, or does this require LLM analysis of the semantic content?

4. **Storage Strategy**: Should recursive diff results be stored in BRAIN knowledge registry, or computed on-demand?

5. **Scale**: Does recursive analysis remain performant with 20+ sequential design files? May need optimization or sampling strategies.

---

## Current Status

**Research phase**. No implementation exists. Difftastic is primarily used as git diff replacement; programmatic analysis for knowledge extraction appears novel.

Next step: Build proof-of-concept parser for difftastic output to validate structured data extraction feasibility.

---

## References

- Difftastic: https://github.com/Wilfred/difftastic
- Related IMEM concepts: template-as-type-system.md, document-properties.md, brain-temporal-intelligence.md