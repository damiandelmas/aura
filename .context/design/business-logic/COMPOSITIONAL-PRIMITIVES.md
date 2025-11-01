# Compositional Primitives

**Core Insight: Provide building blocks, not strategies. Let agents discover patterns.**

---

## What This Means

Primitives:
- Orthogonal building blocks (siblings, genealogy, temporal)
- Pure functions with no cross-dependencies
- Composable in any combination
- No rigid modes or strategies

Discovery:
- Agents compose freely based on need
- Usage patterns emerge organically
- Proven compositions become presets
- System learns what's valuable

---

## Why

**Flexibility:** Can't predict all use cases upfront

**Discovery:** Agents find patterns designers didn't anticipate

**Evolution:** New compositions emerge without code changes

**Simplicity:** N primitives > N² strategies

---

## Core Principles

**Orthogonal primitives** - Each does one thing, no overlap

**Infinite compositions** - Any combination is valid

**Observable usage** - Track which compositions recur

**Emergent presets** - Capture proven patterns, don't prescribe them

---

## Anti-Patterns

When someone proposes fixed query types, ask:

**Are we locking agents into our predictions?**
- Strategy pattern with modes → requires code for new patterns
- Compositional primitives → agents discover combinations

**Example:**
- ❌ Build "explain decision" mode with genealogy+siblings hardcoded
- ✅ Build genealogy primitive + siblings primitive, let agents compose

**Can agents discover what we didn't predict?**
- Fixed modes → designers decide what's possible
- Compositional → usage reveals valuable patterns

---

## Implications

Systems must support:
- Pure, orthogonal primitives
- Flexible composition (any combination valid)
- Usage tracking (which compositions recur?)
- Preset capture (proven patterns → shortcuts)

Future sessions will:
- Compose primitives based on query intent
- Discover new useful compositions
- Benefit from captured presets (proven patterns)

They won't:
- Be limited to pre-designed query modes
- Need code changes for new patterns

Build blocks, not strategies.
