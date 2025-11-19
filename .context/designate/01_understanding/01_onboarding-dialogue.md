# IMEM v3: Onboarding Dialogue

**A conversation to build understanding**

---

## What Are We Building?

**Q: What is IMEM?**

A knowledge compiler for AI agent memories.

**Q: What does that mean?**

Agents produce output—markdown files, conversations, git commits. IMEM compiles this into structured, queryable knowledge.

**Q: Like a RAG system?**

Yes, but specialized. Not "index documents for retrieval." Instead: "resolve agent workflows into canonical structure."

**Q: What's the canonical structure?**

Four lifecycle phases: design → designate → develop → document. All markdown output (design logs, develop logs, research, message sequences between user and assistant) maps to one of these.

**Q: Why do we need phases?**

Because agents say "planning", "spec", "implementation", "notes"—all meaning different things. We normalize to: design, designate, develop, document.

**Q: That's compilation?**

Exactly. Parsing + normalization + storage = compilation.

---

## The Current Problem

**Q: What's broken right now?**

We have new architecture (v3) but it's tangled with old code (v2).

**Q: What's the old code doing?**

Hardcoded Qdrant everywhere. Indexing → must use Qdrant. Search → must use Qdrant. No abstraction.

**Q: What's the new architecture?**

VectorStore protocol. Backend could be SQLite, Qdrant, HNSW—doesn't matter. Code uses interface, not concrete implementation.

---

## Why Isolation First?

**Q: Why not just refactor everything at once?**

Because we'll mix concerns. Fixing imports + changing schemas + rewriting indexing = too many changes to debug.

**Q: What if we're careful?**

You'll think you are. But 3 hours in, you'll be debugging why relationships aren't populating and realize you changed the indexing path AND the schema AND the CLI all at once.

**Q: So isolation means...?**

Move files. Update imports. Document intent. STOP. Don't fix, don't enhance, don't optimize.

**Q: Then what?**

Test. See what works and what's broken. Make a list.

**Q: Then refactor?**

Then fix ONE thing. Not "indexing + relationships + discovery." Just "make spatial relationships work end-to-end."

**Q: One vertical slice?**

Exactly.

---

## The Architecture We Want

**Q: What does "clean architecture" mean here?**

Four domains, each with single responsibility:

**Q: What are the domains?**

- **COMPILE:** Parse + normalize structure (markdown → chunks, "planning" → "design")
- **MANAGE:** Normalize entities (concepts, projects, metadata enrichment)
- **STORAGE:** Backend abstraction (SQLite, Qdrant, HNSW—all behind same interface)
- **RETRIEVE:** Query orchestration (search + rank + discover)

**Q: Why separate COMPILE and MANAGE?**

Different normalization types. COMPILE = structural ("what phase is this?"). MANAGE = semantic ("what entities appear?").

**Q: Can you give an example?**

COMPILE: "## Planning Notes" → section_type="Design", phase="design"

MANAGE: "We use JWT for auth" → entity="jwt", type="technology"

**Q: They're both resolution?**

Yes, but different layers. COMPILE = universal structure. MANAGE = project-specific concepts.

---

## Metadata vs Relationships

**Q: What's the difference?**

Metadata = properties OF a chunk. Relationships = connections BETWEEN chunks.

**Q: Example?**

Metadata: `{phase: "develop", section_type: "Decision", timestamp: "2025-11-18"}`

Relationship: `chunk_A --[decision_implements]--> chunk_B`

**Q: Where do they live?**

Metadata = columns on `chunks` table. Relationships = separate `relationships` table.

**Q: Why separate?**

Because relationships are graph edges. You query them with JOINs, traverse them for discovery.

**Q: What kind of relationships exist?**

- `spatial_proximity`: chunks in same document
- `conversation_continues`: chunks in same session
- `temporal_cluster`: chunks from similar time period
- `decision_implements`: decision chunk → code chunk

**Q: How do we detect these?**

During indexing. Parse metadata → detect patterns → insert into relationships table.

---

## The "Siblings" Confusion

**Q: What's wrong with "siblings"?**

It's imprecise. Two chunks in the same document aren't siblings—they just have spatial proximity.

**Q: Why does precision matter?**

Because "siblings" implies a knowledge graph relationship (same parent). But we're just saying "same file_path."

**Q: What should we call it?**

`spatial_proximity` relationship type. Explicit, precise, queryable.

**Q: Does this matter for code?**

Yes. When you query: `SELECT * FROM relationships WHERE type = 'spatial_proximity'` is clear. `WHERE type = 'siblings'` is ambiguous.

---

## SQL-First Thinking

**Q: Why SQLite primary instead of vectors?**

Because most queries are metadata-based: "show me develop phase decisions from last week."

**Q: Don't we need vectors for semantic search?**

Yes, but that's ONE use case. Metadata filtering, temporal queries, relationship traversal—all SQL.

**Q: So vectors are optional?**

Exactly. Modality you can add. Not required for core functionality.

**Q: How does this change the architecture?**

Storage backend provides metadata queries (fast SQL). Optionally provides vector search (if embeddings exist).

**Q: What about Qdrant?**

It's one backend option. For users who want external vector service. But not the only path.

**Q: What's the alternative?**

HNSW embedded in SQLite. Local vectors, no Docker, 15s build time.

**Q: Why haven't we added HNSW yet?**

Because we need to clean the foundation first. Adding HNSW to tangled code = more mess.

---

## The Processor Chain

**Q: What is it?**

Config-driven pipeline. User specifies: search → discover → rank. System builds chain of processors.

**Q: Why not just hardcode the pipeline?**

Because we want to experiment. Try different ranking strategies. A/B test discovery approaches.

**Q: How does it work?**

```python
config = {
  "search": {"mode": "metadata", "filters": {"phase": "develop"}},
  "discovery": {"relationships": ["spatial_proximity"]},
  "ranking": {"phases": [{"name": "recency"}]}
}

chain = build_chain(config)  # Creates [SearchProcessor, DiscoveryProcessor, RankingProcessor]
results = chain.execute(context)
```

**Q: What if discovery isn't implemented yet?**

It raises NotImplementedError with clear message. Explicit failure, not silent bug.

---

## Common Mistakes to Avoid

**Q: What's the biggest pitfall?**

Trying to fix everything at once.

**Q: Example?**

"Let's extract Qdrant AND build relationships schema AND unify indexing AND add HNSW." That's 4 changes. When it breaks, good luck debugging.

**Q: What should we do instead?**

Extract Qdrant. Stop. Test. See what broke. THEN fix one thing.

**Q: Another pitfall?**

Reading architecture docs and thinking "we need to build all of this now."

**Q: Why is that wrong?**

Architecture is vision, not requirement. Build foundation first (metadata + relationships + retrieval). Advanced features come later.

**Q: How do I know if I'm overbuilding?**

If your plan touches more than 2 domains, it's too big. Break it down.

**Q: What about abstractions?**

Build ONE concrete implementation. When you add the second, THEN abstract.

**Q: Why wait?**

Because you don't know what the abstraction should be until you have two examples.

---

## What We're NOT Building (Yet)

**Q: Multi-tier knowledge extraction?**

Not yet. That's probably a wrapper around IMEM. We're building IMEM first.

**Q: Full graph algorithms (PageRank, etc.)?**

Not yet. Get relationships working first. Then add graph operations.

**Q: Comprehensive discovery (siblings, temporal, genealogy)?**

Not all at once. Pick ONE. Build it end-to-end. Then add next.

**Q: HNSW backend?**

Soon, but AFTER cleaning foundation. Not before.

---

## What Success Looks Like

**Q: How do I know I understand the context?**

You can explain:
- Why we're isolating Qdrant before refactoring
- The difference between metadata and relationships
- Why "siblings" is wrong terminology
- When a task is too big (touches >2 domains)

**Q: How do I know I'm ready to code?**

You resist the urge to:
- "Fix everything at once"
- Build abstractions before concrete examples
- Mix multiple concerns in one change
- Add features before validating foundation works

---

**Remember:** We're building a compiler for agent memories. Incremental, clean, testable. Not perfect, not complete, but solid foundation that we can build on.
