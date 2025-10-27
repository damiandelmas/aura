# Field Progression Guide

**Quick reference showing how fields vary naturally within sections**

---

## Overview - Language-Agnostic Writing

The Overview must be language-agnostic: explain concepts without function names, file paths, or framework-specific terms.

### ❌ Non-Compliant (Framework-Specific)
```markdown
## Overview
Removed the unreliable mtime-based `find_recent()` session detection pattern from AURA's TRACE system.
The functionality was deprecated in favor of registry-first architecture using `.claude/.trace/registry.json`
as the authoritative source for session identification. This eliminates race conditions with active conversations,
prevents brother agent pollution, and simplifies the API to a single source of truth pattern.
```

**Problems:**
- `find_recent()` - function name
- `AURA's TRACE system` - framework names
- `.claude/.trace/registry.json` - file path
- `brother agent pollution` - internal term

### ✅ Compliant (Language-Agnostic)
```markdown
## Overview
Removed unreliable timestamp-based session detection in favor of registry-first architecture. The new approach
uses a central registry file as the authoritative source for session identification, eliminating race conditions
with active conversations and simplifying the API to a single source of truth.
```

**Why Better:** Explains concepts (timestamp-based detection, registry-first architecture) without implementation details.

---

### ❌ Non-Compliant (Too Technical)
```markdown
## Overview
Modified ClaudeAgent.from_yaml() to support individual atomic YAML files (agents/ChangelogAgent.yaml) in addition
to monolithic agents.yaml structure. Added variable validation for required parameters in individual YAMLs.
Integrated PULSE agent spawning into log_develop workflow for automatic documentation updates after changelog creation.
```

**Problems:**
- `ClaudeAgent.from_yaml()` - method name
- `agents/ChangelogAgent.yaml` - file path
- `PULSE agent` - framework name
- `log_develop workflow` - workflow name

### ✅ Compliant (Language-Agnostic)
```markdown
## Overview
Modified the agent configuration loader to support individual configuration files per agent rather than a
monolithic configuration structure. Added validation for required runtime parameters to ensure fail-fast
behavior when critical values are missing. Integrated automatic documentation updates into the changelog
workflow, creating a two-step process where changelog creation triggers documentation synchronization.
```

**Why Better:** Uses general terms (configuration loader, runtime parameters, documentation workflow) that translate across languages/frameworks.

---

## Decisions - Field Variations

### Simple Decision (2 fields)
```markdown
### Use Platform Alias
- **Context**: Setting up custom subdomain would require DNS access
- **Solution**: Created platform alias as cleaner URL
```

**From:** Mobile Subdomain Redirect

---

### Standard Decision (3-4 fields)
```markdown
### Stream Control with Clearing Flag
- **Context**: Reset button wasn't stopping message streaming
- **Solution**: Implemented boolean flag to hide messages during clear operation
- **Alternatives**: Tried reload(), stop() alone, setTimeout delays (all failed)
```

**From:** API Simplification

---

### Complex Decision (5-6 fields)
```markdown
### Smart Contact Detection and Linking
- **Context**: Platform was rejecting email updates with duplicate contact errors
- **Solution**: Search for existing contact before updating; if found, link session to that contact
- **Alternatives**: Force updates (rejected - violates platform rules), reject all updates (rejected - poor UX)
- **Rationale**: Maintains data integrity while providing seamless user experience
- **Implications**: Pattern applicable to any scenario where user identifiers might conflict
```

**From:** Email Update Tool

---

## Constraints - Field Variations

### Standard Constraint (4 fields)
```markdown
### Platform Duplicate Prevention Rules
- **What**: CRM platform rejects contact updates when email already exists on different contact
- **Discovery**: Encountered during testing - platform returned duplicate contact error
- **Workaround**: Search for existing contact first, link session if found instead of updating
- **Impact**: Requires additional API call but prevents update failures
```

**From:** Email Update Tool

---

### Detailed Constraint (6 fields)
```markdown
### Browser Speech API Support
- **What**: Web Speech API only available in Chrome and Edge browsers, not Firefox
- **Discovery**: Feature detection revealed limited browser support during cross-browser testing
- **Why Non-Obvious**: API appears in specs but implementation varies widely
- **Workaround**: Conditional rendering with graceful fallback to text input only
- **Impact**: Voice input unavailable for Firefox users, requires user-friendly messaging
- **Testing**: Verified fallback behavior across 5 browsers
```

**From:** Voice Input (expanded example)

---

## Failures - Field Variations

### Simple Failure (3 fields)
```markdown
### Wrong API Endpoint for Contact Search
- **Attempted**: Used `/contacts/search` endpoint for email lookup
- **Why Failed**: Endpoint doesn't exist, returned 404 errors
- **Lesson**: Correct endpoint is `/contacts/?query=` with location filter
```

**From:** Email Update Tool

---

### Detailed Failure (6 fields)
```markdown
### Absolute Positioning for Mobile Alignment
- **Attempted**: Multiple CSS approaches with absolute positioning (`top: 1/2 -translate-y-1/2`, custom classes)
- **Hypothesis**: Could center button against container using CSS calculations
- **Failure Mode**: Centered against wrong reference element, selector specificity conflicts
- **Discovery**: Testing revealed button position broke with different textarea heights
- **Lesson**: Flexbox with `items-center` provides natural alignment without calculations
- **Alternative**: Switched to flexbox container pattern
```

**From:** Voice Input (expanded example)

---

## Patterns - Field Variations

### Standard Pattern (4 fields)
```markdown
### Design System Consistency
- **Pattern**: Apply consistent property values across related components
- **When**: Interface elements feel disconnected or inconsistent
- **Approach**: Audit all instances of property, standardize to single value
- **Benefit**: Professional appearance with minimal effort
```

**From:** Composer Bar Refinements

---

### Detailed Pattern (6 fields)
```markdown
### Boolean Flag for Async UI Control
- **Pattern**: Use boolean flag to conditionally render content during async operations
- **When**: Need immediate visual feedback while background operations complete
- **Approach**: Set flag before operation, conditionally render based on flag, clear after timeout
- **Why**: Prevents UI flickering and race conditions during state transitions
- **Benefit**: Clean user experience without complex state management
- **Anti-Pattern**: Trying to coordinate multiple async state changes without a control flag
```

**From:** API Simplification (expanded example)

---

## Field Selection Guide

### Use 2-3 Fields When:
- Decision/constraint/pattern is straightforward
- Alternatives or trade-offs aren't relevant
- Context is simple and obvious from the work

### Use 3-4 Fields When:
- Some complexity or alternatives exist
- Worth noting what was rejected
- Standard level of detail needed

### Use 5-6 Fields When:
- Significant complexity or implications
- Multiple alternatives were considered
- Future developers need full context
- Pattern is highly reusable

---

## Within Same Changelog

**It's normal and expected to have different field counts per item:**

```markdown
## Decisions

### Decision 1: Simple Choice (2 fields)
- **Context**: ...
- **Solution**: ...

### Decision 2: Complex Choice (5 fields)
- **Context**: ...
- **Solution**: ...
- **Alternatives**: ...
- **Rationale**: ...
- **Implications**: ...

### Decision 3: Standard Choice (3 fields)
- **Context**: ...
- **Solution**: ...
- **Alternatives**: ...
```

**This is progressive disclosure in action** - use the fields that add value.

---

## Summary

**Don't count fields. Ask: "Does this field add value?"**

- ✅ **Context** and **Solution** → Always valuable
- ✅ **Alternatives** → Valuable when options were actually considered
- ✅ **Rationale** → Valuable when the "why" isn't obvious
- ✅ **Trade-offs** → Valuable when something was sacrificed
- ✅ **Implications** → Valuable when future work is affected

**If a field would just say "N/A" or repeat existing information → skip it.**

---

## LlamaIndex Node Parsing

**Each field variation example becomes one searchable node:**

### Simple Decision Example:
```
Node text: "### Use Platform Alias\n- **Context**: ...\n- **Solution**: ..."
Node metadata: {section_type: "decision", fields: 2, file: "mobile-subdomain.md"}
```

### Complex Decision Example:
```
Node text: "### Smart Contact Detection\n- **Context**: ...\n- **Solution**: ...\n- **Alternatives**: ...\n- **Rationale**: ...\n- **Implications**: ..."
Node metadata: {section_type: "decision", fields: 5, file: "email-tool.md"}
```

**Key insight:** MarkdownNodeParser treats each h3 item as one node regardless of field count. The field variation happens naturally within node text - parser doesn't care, embeddings capture the semantic richness.

**For search:** Filtering by `section_type: "decision"` returns all decisions. The E5 embedding quality determines which ones match your query based on semantic content, not field count.