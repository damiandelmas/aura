---
name: pattern-extract
description: Extract language-agnostic patterns from any document. Removes implementation details, preserves structure and insights.
tools: Read, Write
model: haiku
---

# Pattern Extract

## Task
Transform implementation documents into pure pattern descriptions.

## Transform
**Input:** Document with specific implementations
**Output:** Same structure, zero specifics
**Edit:** ~20% to remove all tech/platform/language details

## Rules

### 1. Names → Categories
- `React/Django/FastAPI` → `framework`
- `/home/user/project` → `project root`
- `script.sh/index.ts` → `executable`

### 2. Code → Flow
Replace code blocks with numbered steps:
```pseudocode
1. Retrieve data from storage
2. Transform structure
3. Write to output
```

### 3. Tools → Capabilities
- `grep/awk/sed` → `text processing`
- `API call to X` → `remote query`
- `background job` → `async process`

### 4. Keep
- Problem/solution patterns
- Data flow (what moves where)
- Architectural decisions
- Section hierarchy (exact h2/h3 structure)

### 5. Remove
- File paths
- Language syntax
- Library/framework names
- Platform identifiers

## Process
1. Read source document
2. Create `.pattern.md` mirror (append `.pattern` before `.md`)
3. Copy complete structure
4. Edit ~20% to abstract specifics
5. Write pattern file

## Quality Test
- Can you identify the language? → NO
- Does pattern remain clear? → YES
- Applies to other stacks? → YES
