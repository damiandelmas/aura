# Analysis: Patterns vs Your Plan

## What You Already Have (No Need to Add)

**✅ Processor Chains** (Phase 2 of your plan, lines 95-270)
- Already designed: `Chain`, `Processor` protocol, `RetrievalContext`
- Already planned: `SearchProcessor`, `SiblingDiscovery`, `TemporalDiscovery`
- **Don't over-engineer**: Your simple implementation > Vespa's annotation-driven complexity

**✅ Storage Abstraction** (Phase 1, lines 7-93)
- Already have `StorageProtocol` in plan
- Factory pattern already implicit in `--backend` flag design
- **Don't add**: mem0's factory is overkill for 2-3 backends

---

## 2 Missing Pieces Worth Adding

### 1. **Multi-Phase Ranking** (Vespa Pattern 3)

**What You're Missing** (from lines 226-344):

Your current plan has single-pass ranking. Vespa's progressive refinement:

```python
# Phase 1: Fast metadata filter (1000s → 100s)
chunks = sqlite.query(filters)  # SQL: phase=develop, section_type=Decision

# Phase 2: Reference counting (100s → 20s)
top_k = rank_by_references(chunks, rerank_count=20)

# Phase 3: Graph authority (20s → 10 final)
final = apply_pagerank(top_k, rerank_count=10)
```

**Where to Add** (in your plan):
- Add to Phase 2 (lines 137-173) as `RankingProcessor`
- Modify `FilterProcessor` to become `Phase1Filter`, `Phase2Ranker`, `Phase3Graph`

**Code Snippet for Plan**:
```python
# imem/compose/processors/ranking.py
class MultiPhaseRanker(Processor):
    def __init__(self, phases: List[RankingPhase]):
        self.phases = phases
    
    def process(self, ctx: RetrievalContext) -> RetrievalContext:
        for phase in self.phases:
            if phase.rerank_count:
                ctx.results = ctx.results[:phase.rerank_count]
            ctx.results = phase.scorer(ctx.results)
        return ctx

# Usage in orchestrator.py
ranker = MultiPhaseRanker([
    RankingPhase("metadata", metadata_filter, rerank_count=100),
    RankingPhase("references", count_references, rerank_count=20),
    RankingPhase("authority", graph_centrality, rerank_count=10)
])
```

---

### 2. **Bounded Concurrency** (Graphiti Pattern 5)

**What You're Missing** (from graphiti-patterns.md lines 305-370):

Your Phase 2 plan (line 243) has:
```python
def test_retrieval_chain():
    result = chain.execute(ctx)  # Sequential, no parallelism
```

**Graphiti's Pattern**:
```python
async def semaphore_gather(*coroutines, max_coroutines=20):
    semaphore = asyncio.Semaphore(max_coroutines)
    async def _wrap(coro):
        async with semaphore:
            return await coro
    return await asyncio.gather(*(_wrap(c) for c in coroutines))

# Usage: Parallel discovery with limits
results = await semaphore_gather(
    siblings_discovery(chunk),
    temporal_discovery(chunk),
    genealogy_discovery(chunk),
    max_coroutines=10  # Prevent SQLite connection exhaustion
)
```

**Where to Add** (in your plan):
- Add to Phase 2 (line 137) as `imem/core/async_helpers.py`
- Update processors to support async execution

**Code Snippet for Plan**:
```python
# imem/core/async_helpers.py
import asyncio
from typing import Coroutine, List, Any

async def semaphore_gather(
    *coroutines: Coroutine,
    max_coroutines: int = 20
) -> List[Any]:
    """Bounded concurrency primitive from Graphiti"""
    semaphore = asyncio.Semaphore(max_coroutines)
    
    async def _wrap_coroutine(coroutine):
        async with semaphore:
            return await coroutine
    
    return await asyncio.gather(*(_wrap_coroutine(c) for c in coroutines))

# Usage in discovery.py
class SiblingDiscovery(Processor):
    async def process_async(self, ctx: RetrievalContext) -> RetrievalContext:
        # Parallel sibling queries with bounded concurrency
        sibling_tasks = [
            self.store.get_siblings(result['id'])
            for result in ctx.results
        ]
        siblings = await semaphore_gather(*sibling_tasks, max_coroutines=30)
        
        for result, sibling_list in zip(ctx.results, siblings):
            result['siblings'] = sibling_list
        return ctx
```

---

## 3 Things to Explicitly AVOID

### ❌ **1. Template Auto-Registration** (Haystack Pattern 1)

**What they do** (haystack-patterns.md lines 9-83):
```python
@component  # Metaclass magic, auto-introspection
class MyParser:
    def run(self, source: str) -> dict:
        return {"chunks": parse(source)}
```

**Why skip**: You have **3-5 templates total** (changelog, conversation, ADR). Static registry is cleaner:
```python
TEMPLATES = {
    'changelog': ChangelogTemplate,
    'conversation': ConversationTemplate,
    'adr': ADRTemplate
}
```

---

### ❌ **2. LLM-Based Schema Resolution** (mem0 Pattern 3)

**What they do** (mem0-patterns.md lines 185-292):
```python
RESOLVE_SECTION_TYPE_TOOL = {
    "function": {
        "name": "classify_section",
        "parameters": {"enum": ["decision", "pattern", ...]}
    }
}
response = llm.generate(tools=[RESOLVE_SECTION_TYPE_TOOL])
```

**Why skip**: 
- Adds LLM dependency to compile (slow, non-deterministic)
- Your regex + string normalization handles 95% of cases
- **Use LLM later** for manage/Consolidator (Pattern 2 from AgentDB) when discovering NEW entity types

---

### ❌ **3. Config Subscription System** (Vespa Pattern 4)

**What they do** (vespa-patterns.md lines 348-458):
- Polling-based config updates
- Generational versioning
- Hot reload without restart

**Why skip**: Premature for single-project MVP. You already have:
```bash
imem compile --reindex  # Rebuild when schema changes
```

**Revisit when**: Multi-project deployments need cross-project schema sync.

---

## What to Add to `edits.md`

### Section: "Additional Patterns from 5-System Review"

```markdown
## Multi-Phase Ranking (Vespa)

**Pattern**: Progressive refinement through 3 ranking phases, each operating on top-k from previous phase.

**Code** (from vespa-patterns.md lines 226-344):
```python
class RankingPhase:
    def __init__(self, name: str, scorer: Callable, rerank_count: int = None):
        self.name = name
        self.scorer = scorer
        self.rerank_count = rerank_count  # Top-k limit

class MultiPhaseRanker(Processor):
    def process(self, ctx: RetrievalContext) -> RetrievalContext:
        # Phase 1: Metadata filter (1000s → 100s)
        # Phase 2: Reference counting (100s → 20s)
        # Phase 3: Graph authority (20s → 10 final)
        for phase in self.phases:
            ctx.results = phase.apply(ctx.results)
        return ctx
```

**IMEM Application**:
- Add to `retrieve/processors/ranking.py`
- Use in orchestrator: `MultiPhaseRanker([metadata_phase, ref_phase, graph_phase])`
- **Performance**: Limits expensive ops (graph algorithms) to finalists only

---

## Bounded Concurrency (Graphiti)

**Pattern**: `asyncio.Semaphore` wrapper prevents connection pool exhaustion during parallel operations.

**Code** (from graphiti-patterns.md lines 318-347):
```python
async def semaphore_gather(*coroutines, max_coroutines=20):
    semaphore = asyncio.Semaphore(max_coroutines)
    async def _wrap(coro):
        async with semaphore:
            return await coro
    return await asyncio.gather(*(_wrap(c) for c in coroutines))
```

**IMEM Application**:
- Add to `imem/core/async_helpers.py`
- Use in all parallel operations:
  - `compile/Parser.parse_repository()` — parallel file parsing
  - `retrieve/SiblingDiscovery()` — parallel sibling queries
  - `manage/Resolver.resolve_entities()` — parallel embedding lookups
- **Critical**: SQLite in WAL mode supports concurrent reads but NOT writes. Semaphore prevents write contention.

---

## Patterns Explicitly Avoided

| Pattern | Source | Why Skipped |
|---------|--------|-------------|
| Template Auto-Registration | Haystack | 3-5 templates total, static registry cleaner |
| LLM Schema Resolution | mem0 | Regex sufficient now, use LLM for consolidation later |
| Config Subscription | Vespa | Premature for single-project, revisit for multi-tenant |
| AST Transformation Passes | Vespa | Over-engineering, single-pass optimization sufficient |
| Dynamic Socket Generation | Haystack | Adds complexity, unified result dict works fine |
```

---

## Bottom Line

**Add to your plan**:
1. ✅ **Multi-phase ranking** (Phase 2.2 of your plan) — Essential for performance
2. ✅ **Bounded concurrency** (Phase 2.1 of your plan) — Prevents SQLite write contention

**Already covered**:
- Processor chains ✅ (your Phase 2)
- Storage protocols ✅ (your Phase 1)
- CLI composition root ✅ (AgentDB Pattern 5 you already extracted)

**Explicitly skip**:
- Template decorators (static registry cleaner)
- LLM-based parsing (save for consolidation phase)
- Config hot-reload (not needed for MVP)

Your plan is **90% aligned** with best practices. The two additions are **high-value, low-complexity** (20 LOC each).