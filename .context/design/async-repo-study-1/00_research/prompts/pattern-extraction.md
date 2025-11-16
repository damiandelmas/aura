# Agent Prompt: Pattern Extraction from $REPO_NAME

## Mission
Extract **concrete architectural patterns** from $REPO_NAME that apply to IMEM's knowledge compilation infrastructure.

Focus on **specific implementations** - code patterns, not abstract principles.

---

## Context: IMEM Architecture

Read this first: `/home/axp/projects/fleet/hangar/code/aura/main/.context/designate/overview.md`

**TL;DR:**
IMEM is a **universal knowledge compiler** that transforms heterogeneous AI development artifacts (markdown, conversations, git commits) into a queryable, validated knowledge network.

**Three roles:**
- **Compiler** (compile/) — Parse any AI workflow → canonical chunks
- **Manager** (manage/) — Resolve entities, validate vs git, maintain intelligence
- **Composer** (retrieve/) — Query orchestration with graph operations

**Key properties:**
- Resolution, not validation (maps any structure → four-phase schema)
- Template-based parsing (domain plugins)
- Runtime graph composition (metadata = edges, no storage)
- Storage agnostic (SQLite for metadata, Qdrant optional for vectors)
- Git = ground truth (validates develop phase claims)

---

## Your Task

**1. Find Concrete Patterns**

Look for:
- **Plugin/extension mechanisms** — How are plugins discovered, registered, and invoked?
- **Template systems** — How are domain-specific extractors separated from core logic?
- **Query composition** — How are multi-stage pipelines built and executed?
- **Metadata extraction** — How is structured data pulled from unstructured sources?
- **Index management** — How are metadata indexes built and maintained?
- **Graph operations** — How are relationships materialized and queried?

**2. Document 3-5 Patterns**

For each pattern:

```markdown
## Pattern: {Name}

**Location:** `path/to/file:line-range`

**Description:**
{What it does, why it exists, how it works}

**Code Example:**
{Minimal snippet showing the pattern}

**Relevance to IMEM:**
- **Module:** compile | manage | retrieve | structure | storage
- **Use case:** {Specific application in our architecture}
- **Why useful:** {Concrete benefit}

**Adoption Strategy:**
- [ ] Adopt directly (use as-is)
- [ ] Adapt (modifications needed: ...)
- [ ] Avoid (reason: ...)

**Implementation Priority:** High | Medium | Low
```

**3. Map to IMEM Modules**

Which component benefits:
- **compile/** — Template parsing, schema evolution, pattern discovery
- **manage/** — Entity resolution, temporal validation, authority scoring
- **retrieve/** — Query orchestration, discovery primitives, graph algorithms
- **structure/** — Result enrichment, presentation templates
- **storage/** — Backend adapters (SQLite, Qdrant)

---

## Constraints

- **Depth over breadth** — 3-5 patterns deeply understood > 10 surface-level
- **Actionable** — Must be implementable, not theoretical
- **Cite sources** — File paths and line numbers required
- **Code required** — Show actual implementation, not just description
- **Respect architecture** — Don't suggest breaking compiler/manager/composer separation

---

## Output Format

Save to: `/home/axp/projects/fleet/hangar/code/aura/main/.context/design/async-repo-study-1/$REPO_NAME-patterns.md`

```markdown
# Pattern Extraction: $REPO_NAME

## Executive Summary
3-4 sentences: What this codebase does well architecturally and why it's relevant to IMEM.

---

## Pattern 1: {Name}
{Full pattern documentation as specified above}

---

## Pattern 2: {Name}
{Full pattern documentation as specified above}

---

## Summary Table

| Pattern | IMEM Module | Priority | Strategy |
|---------|-------------|----------|----------|
| ...     | ...         | ...      | ...      |

---

## Key Files Examined
- path/to/file1
- path/to/file2

## References
- Documentation consulted
- Key architectural decisions observed
```

---

## Example Pattern (for reference)

**Pattern: Plugin Registry with Lazy Loading (Babel)**

**Location:** `packages/babel-core/src/config/files/plugins.ts:45-120`

**Description:**
Babel uses a registry pattern where plugins are discovered via naming convention (`babel-plugin-*`), registered lazily on first use, and cached. Plugins receive a standard API object and return visitor objects. No central hardcoded list.

**Code Example:**
```typescript
function loadPlugin(name: string): Plugin {
  if (cache.has(name)) return cache.get(name);
  const plugin = require(`babel-plugin-${name}`);
  cache.set(name, plugin);
  return plugin;
}
```

**Relevance to IMEM:**
- **Module:** compile/Templates
- **Use case:** Domain parsers (changelog, conversation, ADR) auto-discover via naming convention
- **Why useful:** No hardcoded template list, extensible without core changes

**Adoption Strategy:**
- [x] Adapt — Use similar auto-discovery for template plugins in `compile/Templates/`. Templates named `template_changelog.py`, `template_conversation.py` auto-register. Standard interface: `parse(source, context) -> chunks[]`.

**Implementation Priority:** High

---

Begin extraction from $REPO_NAME.
