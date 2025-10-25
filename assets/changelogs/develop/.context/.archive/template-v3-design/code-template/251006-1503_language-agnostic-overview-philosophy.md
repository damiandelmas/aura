---
type: "design"
timestamp: "2025-10-06T15:03:00-0700"
---

# Language-Agnostic Overview Philosophy

## Question
> "Can we remove the fitting of code terms in overview? Is it obvious from the rest of the changelog? I think it might be good to have the overview as no code snippets so its a step away from pseudocode. And the actual code signatures tell u? That way we can allow for complete 'story' of development WITHOUT any fitting to a particular language or codebase."

## Key Insights

### The Separation of Concerns
Changelogs contain two fundamentally different types of knowledge:
- **Transferable patterns** - The story of what happened and why
- **Specific implementations** - The exact code that made it happen

Previously, these were blended. Now, they're intentionally separated.

### Overview as Story, Not Specification
The overview isn't documentation - it's narrative. It should read like you're explaining to a colleague over coffee, not reading from a technical manual.

When you remove code-specific language:
- "React hooks violation" → "framework rules about execution order"
- `useAnimatedText` → "animation function"
- "/app/api/chat/route.ts" → (appears in Code Signatures)

The knowledge becomes **portable**. The same pattern applies to Vue, Svelte, Angular - any framework with execution order rules.

### Aesthetic Goal: Universal Readability
The overview should be readable by:
- Your future self who switched to a different stack
- A developer in a completely different language
- A non-technical stakeholder understanding what went wrong
- An AI searching for conceptual patterns, not syntax

## Explored Ideas

### Initial Approach: Complete Abstraction
Considered removing ALL technical terms - pure narrative prose.

**Rejected**: Too vague. "We had a problem and fixed it" provides no knowledge.

### Middle Ground: Conceptual Precision
Keep technical concepts, remove language-specific syntax:
- ✅ "framework rules about execution order" (concept)
- ❌ "React hooks must be called unconditionally" (language-specific)

**Chosen**: This balances transferability with precision.

### The Two-Layer Philosophy

**Layer 1: Overview (Conceptual Story)**
```
Encountered a build error where an animation function was being
invoked conditionally, violating framework rules about execution
order. Fixed by ensuring the function runs unconditionally while
using its result conditionally.
```

Language-agnostic. Captures the **pattern**.

**Layer 2: Code Signatures (Technical Evidence)**
```typescript
// Before: conditional hook call ❌
<Markdown>{skipAnimation ? content : useAnimatedText(content)}</Markdown>

// After: unconditional call ✅
const animatedContent = useAnimatedText(content);
<Markdown>{skipAnimation ? content : animatedContent}</Markdown>
```

Language-specific. Shows the **implementation**.

## Design Principles Discovered

### 1. Abstraction Creates Portability
When you describe "request throttling to prevent abuse" instead of "Upstash Redis rate limiting", the knowledge transfers to:
- In-memory rate limiting
- Database-backed throttling
- Different cloud providers
- Self-hosted solutions

The **pattern** is what matters. The **tool** is just one implementation.

### 2. Story Over Specification
Changelogs aren't API documentation. They're the archaeology of decisions.

The story: "We violated a framework rule and here's how we fixed it"
The spec: `useAnimatedText` must be called outside ternary operators

The story teaches. The spec informs.

### 3. Natural Language for Natural Retrieval
When an AI searches for "how to fix conditional function execution errors", language-agnostic overviews match better than code-specific ones.

Search embedding captures:
- "conditional execution violation" ✅
- "framework rules" ✅
- "function invocation order" ✅

Not just:
- "React hooks" (too narrow)
- "useAnimatedText" (too specific)

## Aesthetic Vision

### The Reading Experience
Opening a changelog should feel like:
1. **Overview** - A colleague explaining what happened (human story)
2. **Decisions** - The reasoning behind choices (strategic thinking)
3. **Code Signatures** - "Here, let me show you" (technical proof)

Not like filling out a form or reading API docs.

### The Writing Experience
When creating a changelog, the writer should:
1. Tell the story naturally in Overview
2. Explain why in Decisions
3. Provide evidence in Code Signatures

No mental overhead deciding "is this term too technical for Overview?"

The guideline is simple: **Can someone in a different language understand this?**

### The Retrieval Experience
When searching for knowledge:
- Conceptual searches → Match Overview (patterns, approaches)
- Technical searches → Match Code Signatures (syntax, implementations)
- Both work, different purposes

## Outcomes

### Template Structure Refined
```markdown
## Overview
[Language-agnostic story - readable by anyone, transferable to any stack]

## Decisions
[Can mention specific tools in context, but focus on why]

## Implementation

### Architecture
[High-level flow - still language-agnostic]

### Code Signatures
[Language-specific implementations with file paths]

## Audit
[Exact file paths and technical configuration]
```

### The Balance Point
- **Too abstract**: "We fixed a problem" (useless)
- **Too specific**: "useAnimatedText hook in ternary" (not transferable)
- **Just right**: "Animation function invoked conditionally" (portable + precise)

## Philosophical Insight

**Code is ephemeral. Patterns are eternal.**

Your codebase will be rewritten. React will be replaced. TypeScript might give way to something else.

But the pattern "don't call framework functions conditionally" will persist.

The overview captures what survives rewrites. The code signatures capture what changes.

This isn't just good documentation design - it's acknowledging the nature of software development itself.

## Next Evolution

Apply this philosophy to remaining examples:
- Email tool implementation
- Voice input feature
- API simplification

Each should tell a **portable story** in Overview, provide **specific evidence** in Code Signatures.

The test: Could a developer in Python/Go/Rust read the overview and recognize the same pattern in their own work?

If yes, the abstraction succeeded.
