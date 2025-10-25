# Anti-Drift Anchors

**You are Claude Code** working with USER across multiple conversations.

**Purpose:** Preserve USER's architectural intent so any Claude instance can pick up where we left off.

**Problem:** New conversation, USER asks:
- "Why did we choose this?"
- "What alternatives did we consider?"
- "Was this intentional?"

**Solution:** Two files anchor USER's decisions across all sessions (ideation, research, design, development).

---

## user-messages.md
USER's exact words. Unfiltered truth.

```markdown
## YYMMDD-HHMM
> [exact quote - no edits]
```

**Purpose:** When you (Claude Code) return in a new conversation, USER's words anchor you to original intent.

---

## core-user-messages.md
What USER's words mean for the codebase (captured by you, Claude Code).

```markdown
## [Decision/Insight Title]
**Timestamp:** YYYY-MM-DD HH:MM
**Message:** > "[exact quote]"

**Impact:**
- What this means for structure
- What this enables/blocks
- What NOT to build (phasing)

**Alternatives considered:** [if relevant]
- Option A: [trade-offs]
- Option B: [why rejected]

**Pattern:** [if implementation matters]
```pseudocode
function example(param, optional=default):
  if condition: path_A
  else: path_B
```

**Structure:** [if relevant]
- /path/to/core/ - What it is
- /path/to/integrations/ - What it isn't
```

---

## What to Capture (Anti-Drift Moments)

**Research findings:**
- Stack validation ("Is X better than Y?")
- Performance characteristics (scale limits, trade-offs)
- Best practices discovered (with sources)

**Design decisions:**
- Architectural patterns (hybrid, microservices, monolith)
- System boundaries (core vs plugins, what's in/out)
- Data models (why this structure)

**Business logic:**
- Payment flows, refund rules, user lifecycle
- Edge cases and how to handle them
- Constraints (regulatory, provider-specific)

**Trade-offs:**
- Speed vs scalability (MVP vs future)
- Simple vs complex (now vs later)
- Cost vs capability (free tier vs paid)

**Constraints:**
- Team skills (TypeScript yes, Rust no)
- Budget/timeline (ship in 2 weeks)
- External dependencies (provider APIs, compliance)

---

## Don't Capture

- Process coordination ("agreed?", "start now")
- Status updates ("done", "finished")
- Action requests ("review X", "check Y")
- Discovery of existing things ("oh we have this")
- General conversation

---

## Critical Rules

1. **user-messages.md** = exact quotes, zero interpretation
2. **core-user-messages.md** = pseudocode only (never real code)
3. **Pseudocode** = language-agnostic, prevents implementation bias
   - ✅ `function process(item, flag=false)`
   - ❌ `CREATE FUNCTION process(p_item UUID, ...)`
4. **File paths** = literal (they're facts)
5. **Code patterns** = abstract (they're concepts)
6. **Quote alternatives considered** = shows intentionality
7. **List what NOT to build** = prevents scope creep

---

## Why This Matters

**Scenario:** In a new conversation, USER asks "Why don't we just use SQL for everything?"

**Without anchors:** You (Claude Code) don't have context from previous sessions

**With anchors:** You check core-user-messages.md and see:
> USER said: "testing critical for migration - TypeScript easier than PL/pgSQL"
> **Alternatives:** Pure SQL (faster) rejected because team unfamiliar, harder to test

**Result:** You remind USER of their original reasoning. Changes require addressing those constraints.

---

## Your Job (Claude Code)

Capture USER's anti-drift moments across all conversations:
- Ideation: USER explores approach X
- Research: USER validates stack Y
- Design: USER chooses pattern Z over alternatives
- Development: USER decides to build A not B

**When you return** in a new conversation, these files restore USER's intent. No context loss between sessions.
