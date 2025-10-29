---
session_id: eee3b7a5-3870-4b50-984c-19eb2e2fa729
date: 2025-10-27
type: vision.innovation
resolution: level-1
keywords: "intellectual-capital anti-contamination language-agnostic cross-project-transfer"
---

# Cross-Project Patterns: Intellectual Capital Transfer

## The Insight

**Knowledge has two forms: implementation (tech-specific) and principle (universal).**

Traditional RAG: Query cross-project → code contamination inevitable.

AURA: Pattern layer isolation → principles transfer, code doesn't.

---

## The Problem

**Scenario:** Building Python auth while TypeScript project solved similar problem.

**Traditional retrieval:**
```
Query: "authentication solution"

Returns:
- "Use jsonwebtoken library" (TypeScript-specific)
- "Install @nestjs/passport" (wrong framework)
- "Similar Python project used Django sessions" (wrong architecture)

Result: Framework confusion, copy-paste antipatterns
```

**The failure:** Can't distinguish principle from implementation.

---

## The Solution

**Pattern layer = language-agnostic abstraction.**

Same query, pattern-only search:
```
Query: "authentication solution" --pattern-only --all-projects

Returns:
- Stateless Authentication Pattern
  - Context: Distributed system without shared state
  - Solution: Token-based with asymmetric signing
  - Rationale: Horizontal scaling without session store
  - No TypeScript. No libraries. No framework names.

Result: Apply principle, choose tools for current stack
```

**The win:** Intellectual capital without contamination.

---

## The Geometry

```
Project A (TypeScript):
├─ Implementation: JWT + Express.js
└─ Pattern: Stateless auth via signed tokens

Project B (Python):
├─ Implementation: (building now)
└─ Pattern: Query A's pattern → apply with PyJWT/Authlib

Project C (Rust):
├─ Implementation: Custom token with Ed25519
└─ Pattern: Same principle, different tools
```

**Bridge = pattern layer.** Implementations isolated. Principles shared.

---

## The Properties

**Anti-contamination:**
- Pattern queries: Language-agnostic only
- Implementation queries: Project-specific only
- Never mix unless explicit override

**Authority via accumulation:**
- Pattern in 5 projects > pattern in 1 project
- Cross-project graph: patterns as bridge nodes
- PageRank on pattern layer = most validated solutions

**Progressive abstraction:**
- Write implementation first (natural workflow)
- Extract pattern later (optional, when reuse emerges)
- No upfront overhead

---

## The Vision

**Intellectual capital compounds across projects:**
- TypeScript project validates auth pattern
- Python project validates same pattern (different tech)
- Rust project validates again (different paradigm)
- Pattern authority: proven 3× across stacks

**Query from any project → receive most validated principles.**

Not code transfer. **Wisdom transfer.**
