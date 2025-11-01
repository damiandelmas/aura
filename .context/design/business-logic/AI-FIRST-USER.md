# AI-First User

**Core Insight: The user is Claude (AI agents), not humans.**

---

## What This Means

AI agents:
- Construct interfaces programmatically
- Introspect systems for capabilities
- Optimize for latency (single calls > multiple calls)
- Parse structured output (not text)

---

## Design North Star

**Ask:** Does this help AI agents compose queries efficiently?

**NOT:** Does this help humans type commands?

---

## Core Principles

**Complexity is acceptable** - AI constructs programmatically, no cognitive load

**Single atomic calls** - Latency matters, minimize round-trips

**Schema over modules** - Systems expose capabilities programmatically, modules drift

**Structured output** - Parseable data, not text for humans

---

## Anti-Patterns

When someone suggests simplification, ask: For who?

- "This config is too complex" → AI doesn't care, constructs it
- "Users won't remember" → AI introspects, doesn't memorize
- "Need better help text" → AI reads schema, not help
- "Split into steps" → Multi-step = latency penalty

**Optimizing for human ergonomics often degrades AI efficiency.**

---

## Validation Filter

Interface decisions pass if:
1. Programmatically constructable
2. Minimizes latency (round-trips)
3. Schema introspectable
4. Returns structured data
5. Atomic operations

Fail if optimizing for human typing/memory/ergonomics.

---

## Brother Agent Context

Future sessions will:
- Introspect system capabilities (schema endpoints)
- Construct complex queries in one call
- Parse structured responses

They won't:
- Type commands manually

Design for the agent, not the human.
