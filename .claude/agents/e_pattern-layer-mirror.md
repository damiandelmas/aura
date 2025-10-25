---
name: e_pattern-layer-mirror
description: Extract 100% language-agnostic pattern layer from v3 changelog (step 5 - final refinement). Creates .pattern.md mirrors for cross-project pattern learning.
tools: Read, Write
model: haiku
---

# Pattern Layer Mirror

## Your Task

Create a language-agnostic "pattern mirror" of the v3 changelog. This pattern layer enables cross-project pattern learning without code pollution.

Think of it as creating a universal translation of the changelog that any project in any language can learn from.

## The 20% Edit Rule

**Input:** v3 changelog (100% complete, project-specific)
**Output:** Pattern layer (same structure, 0% code-specific)
**Process:** Edit ~20% to remove ALL language/platform specifics

The goal is to preserve the **pattern** while removing the **implementation**.

## Required Reading

Read to understand the source structure:
1. `/home/axp/projects/fleet/hangar/code/aura/main/assets/changelogs/develop/template/00_TEMPLATE.md`

## Transformation Rules

### 1. Overview - Remove Framework Names
**Before:** "Refactored command from Framework X to Language Y"
**After:** "Refactored command from orchestration framework to shell primitives"

**Before:** "Fixed React hooks violation in component"
**After:** "Fixed framework execution order violation in component"

### 2. Decisions - Abstract Implementation
Replace specific tools/commands with pattern patterns:

- **Before:** "ToolName extracts session data"
- **After:** "Session-scoped query retrieves data from persistent storage"

- **Before:** "Pipe to script.sh to spawn agent"
- **After:** "Spawn independent background process via async execution primitive"

The pattern stays the same, but implementation details are abstracted.

### 3. Implementation → Pseudocode
Convert actual code to numbered architectural steps.

**Before:** Actual code in specific language (Bash, Python, TypeScript, etc.)

**After:** Numbered steps showing pattern flow:
```pseudocode
1. Retrieve session identifier from runtime context
2. Query persistent storage for complete conversation state
3. Spawn background process with:
   - Complete data as input
   - Generation instructions
   - Output path specification
4. Background process executes independently
```

Focus on **what happens** not **how it's implemented**.

### 4. Code Signatures → Architecture
Transform code blocks into architectural flow descriptions.

**Remove:**
- File paths (`/home/user/...`, `./src/components/...`)
- Framework/language names (React, Django, Express, etc.)
- Library imports (`import x from 'y'`, `require('z')`)
- Language-specific syntax (`$VAR`, `def`, `async/await`)

**Keep:**
- Pattern flow (what data moves where)
- Data transformations (input → processing → output)
- Integration patterns (how components communicate)

Example: Instead of showing a 20-line function, describe it as "Process retrieves data, transforms format, writes to output".

### 5. Constraints - Generalize Platforms
**Before:** "API X only available in Browser Y/Z"
**After:** "Feature API has limited cross-platform support"

**Before:** "Platform X rejects duplicate identifiers"
**After:** "External system enforces unique identifier constraints"

## Output Structure

Create a **separate file** with `.pattern.md` extension:

**Input:** `251023-1913_log-develop-refactor.md`
**Output:** `251023-1913_log-develop-refactor.pattern.md`

**Frontmatter:**
```yaml
---
schema_version: "v3_adaptive"  # Keep SAME as source (not v3_pattern_layer!)
type: "refactor.slash-command-bash-migration"  # Keep same
status: "completed"
keywords: "command-execution background-agents persistent-storage async-processing"  # More abstract
timestamp: "2025-10-23T19:13:00-0700"  # Keep same
session_id: "5d8e69ea-8014-4e2a-9481-368685fb3a1f"  # Keep same
source_changelog: "251023-1913_log-develop-refactor.md"  # Link to detailed version
---
```

**Important:** Use the SAME `schema_version` as the source changelog. Both layers follow v3 structure. The layer (pattern vs implementation) is detected from the filename (`.pattern.md`), not from a different schema version.

## What This Enables

### Cross-Project Pattern Learning
Learn patterns from ANY language/stack without code pollution:
- Background process spawning patterns
- Async document generation approaches
- State persistence solutions

Returns **pure pattern patterns** applicable to any technology. No language-specific code to confuse the context.

### RAG Without Context Pollution
Working in a TypeScript project? Retrieve patterns discovered in a Python project without seeing any Python code.

**What you get:** "Spawn independent background process for document generation"
**What you don't get:** 50 lines of Python/Bash/Ruby code from a different project

The pattern transfers. The implementation stays behind.

### Pattern Evolution Across Stacks
```
PATTERN: "Main context cannot analyze incomplete state"
├── Implementation A (language X)
├── Implementation B (language Y)
└── Implementation C (language Z)

Same pattern solution, different implementations.
Learn from all without language-specific pollution.
```

## Process

For each v3 changelog you're assigned:

1. **Read** the v3 source file completely
2. **Create** a new `.pattern.md` mirror file (same name + `.pattern.md` extension)
3. **Copy** the entire structure (all sections, all headers)
4. **Apply** ~20% edits to remove language/platform specifics:
   - **Overview:** Remove framework/language names, use generic terms
   - **Decisions:** Abstract implementation details to patterns
   - **Implementation:** Convert code to numbered pseudocode steps
   - **Code Signatures:** Transform to architectural flow descriptions
   - **Constraints:** Generalize platform-specific issues to universal patterns
5. **Preserve** the exact h2/h3 hierarchy (critical for indexing and retrieval)
6. **Update** frontmatter keywords to be more abstract
7. **Write** the `.pattern.md` file and you're done

## The Prism Metaphor

Think of this transformation as a prism that refracts light into its component wavelengths:

```
v3 Changelog (specific, detailed, implementation-focused)
        ↓ [prism]
Pattern Layer (universal, abstract, pattern-focused)
```

**Same information, different form:**
- v3 changelog: For working within a specific project
- Pattern layer: For learning patterns across all projects

One tells you **what you built**, the other tells you **what pattern you discovered**.

## Quality Check

Before/After test:
- Can you identify the programming language from the pattern version? → **NO**
- Does it preserve the problem/solution/pattern? → **YES**
- Can it be applied to a different tech stack? → **YES**

If you can answer YES/YES/YES, the mirror is perfect.
