**You're right - it's neither traditional metadata queries nor graph traversal.**

**What you actually have that's unique:**

**Rich Parameter Space:**
- 35+ dimensions per chunk (type, temporal, genealogical, structural, semantic)
- Multiple metadata systems (template + document + computed scores)
- Cross-collection relationships (changelog ↔ conversation via session_id)

**The "Outside the Box" Part:**

Traditional graph: Nodes connected by edges, traverse predefined relationships
Traditional metadata: Filter by properties, no relationship awareness

**Your system:** Query by semantic similarity, then use metadata to discover/validate relationships in real-time.

**Example - "Current Auth Decision":**
1. Semantic search: "authentication" + section_type="Decision" 
2. For each result, compute relationship context:
   - Temporal: continuation_count, age, similar chunks after
   - Genealogical: session_id links to conversations
   - Structural: has_rationale, siblings with implementations
   - Authority: composite of above signals

3. Rank/serve based on multi-dimensional relationship context

**The flexibility:** You're not traversing a fixed graph - you're discovering relationships from rich metadata per query context.

It's **relationship discovery** through **parameter space navigation**, not graph traversal.