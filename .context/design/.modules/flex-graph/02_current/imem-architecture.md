# IMEM Architecture

**FlexGraph Implementation for Coding Agents**

*Status: Phases 1-5 complete, Phases 6-8 (FlexGraph core) in development*

---

## System Overview

IMEM = First FlexGraph implementation using clean layered architecture.

**Point of Use (Everything supports this):**
```bash
imem compose '{"search": {...}, "discovery": {...}, "output": {...}}'
```

**Architecture Layers:**
```
Layer 0: Client (Point of Use)
    imem compose '{...json...}'   # ONE command
    ↓
Layer 1: Primitives (Pure Functions)
    search, siblings, genealogy, temporal, graph_build, graph_apply
    ↓
Layer 2: Orchestrator (Composition Logic)
    compose.py - Executes pipeline based on config
    ↓
Layer 3: Templates (Presentation)
    Jinja2 templates for structured output
    ↓
Layer 4: CLI (Thin Wrapper)
    JSON parsing + registry lookup + compose()
```

**Foundation:** Template-as-schema (100% metadata compliance)
**Layer 2A:** Metadata discovery primitives (siblings, genealogy, temporal)
**Layer 2B:** Graph operations (optional, if validated)

---

## Foundation: Template Enforcement

### Template Structure

```markdown
## Decisions
### Use JWT Authentication
- **Context**: Sessions don't scale beyond single server
- **Solution**: Stateless JWT tokens with claims
- **Rationale**: Enables horizontal scaling without session store
- **Alternatives**: OAuth (too complex), API keys (less secure)

## Constraints
### Token Expiry Mandatory
- **Description**: JWTs can't be revoked
- **Impact**: Security risk if stolen
- **Mitigation**: Short expiry (15min) + refresh tokens

## Failures
### Tried Redis Session Store
- **Attempted**: Centralized Redis for session storage
- **Why Failed**: Single point of failure, added latency
- **Lesson**: Stateless > stateful for horizontal scaling
```

### Enforcement Mechanism

**Write-time validation:**
```python
def validate_changelog(content: str) -> bool:
    """Validate document against template schema"""

    required_sections = ['## Decisions', '## Constraints', '## Failures']
    for section in required_sections:
        if section not in content:
            raise ValidationError(f"Missing required section: {section}")

    # Validate decision fields
    decisions = extract_sections(content, '## Decisions')
    for decision in decisions:
        required_fields = ['**Context**:', '**Solution**:']
        for field in required_fields:
            if field not in decision:
                raise ValidationError(f"Decision missing field: {field}")

    return True
```

**Result:** 100% metadata compliance, deterministic queries

---

## Core: Metadata → Edge Mapping

### Chunk-Level Edges

| Edge Type | Metadata Predicate | Weight | Discovery Method |
|-----------|-------------------|--------|------------------|
| SIBLING | `file_path == X` | 0.9 | `filter(file_path=chunk.file_path)` |
| GENEALOGY | `session_id == Y` | 0.85 | `filter(session_id=chunk.session_id)` |
| TEMPORAL | `timestamp > Z ∧ semantic > 0.85` | 0.7 | `filter(timestamp__gt=chunk.timestamp)` + similarity |
| SECTION_TYPE | `section_type == T` | 0.6 | `filter(section_type=chunk.section_type)` |

### Document-Level Edges

| Edge Type | Discovery Predicate | Use Case |
|-----------|---------------------|----------|
| SEQUENTIAL | Filename chronology + semantic > 0.7 | Project narrative arc |
| THEMATIC | Topic keywords overlap + different phase | Design → develop → document continuity |

### Discovery Primitives (Layer 1)

**Module:** `imem/src/imem/primitives/discovery.py`

**Design principle:** Primitives are pure functions. No cross-dependencies.

```python
def get_siblings(collection_name, chunk_id):
    """Returns: List[{id, score, payload}]"""
    chunk = retrieve(collection_name, chunk_id)
    return scroll(
        collection_name,
        filter={'file_path': chunk.payload['file_path']}
    )

def get_genealogy(collection_name, chunk_id):
    """Returns: List[{id, payload}]"""
    chunk = retrieve(collection_name, chunk_id)
    return scroll(
        collection_name,
        filter={
            'session_id': chunk.payload['session_id'],
            'source': 'conversation'
        }
    )

def get_temporal(collection_name, chunk_id, direction='after'):
    """Returns: List[{id, payload}]"""
    chunk = retrieve(collection_name, chunk_id)
    similar = semantic_search(chunk.vector, limit=50, threshold=0.85)

    if direction == 'after':
        return [r for r in similar if r.timestamp > chunk.timestamp]
    return [r for r in similar if r.timestamp < chunk.timestamp]

def cross_phase_search(collection_name, chunk_id, target_phase):
    """Returns: List[{id, payload}]"""
    chunk = retrieve(collection_name, chunk_id)
    return search(
        ' '.join(chunk.keywords),
        filters={'phase': target_phase}
    )
```

**Key property:** Each primitive is independent. They don't call each other.

---

## Intelligence: Query-Adaptive Bundling

### Strategy 1: Authority (PageRank)

**Intent:** "What's the most important authentication pattern?"

**Workflow:**
```
1. Multi-query search:
   - "auth" + decisions
   - "auth" + patterns
   - "auth" + failures
2. Build graph from combined results (30 nodes)
3. Add edges: siblings, genealogy, semantic
4. Apply PageRank
5. Return top 10 by authority score
```

**Result:** Most-referenced decisions surface

### Strategy 2: Bridge (Centrality)

**Intent:** "What connects auth and caching?"

**Workflow:**
```
1. Search "auth" → 15 results
2. Search "caching" → 15 results
3. Build graph from 30 combined results
4. Apply betweenness centrality
5. Return top 5 bridge nodes
```

**Result:** Concepts like "token storage" or "session cache" surface

### Strategy 3: Timeline (Temporal Chain)

**Intent:** "Trace JWT decision evolution"

**Workflow:**
```
1. Search "JWT decision"
2. Get primary decision
3. Discover temporal edges (earlier/later)
4. Topological sort by timestamp
5. Render chronologically
```

**Result:** Design → decision → constraints → refinements

### Strategy 4: Explanation (Sibling Bundle)

**Intent:** "Explain this decision fully"

**Workflow:**
```
1. Search decision
2. Get siblings (same document sections)
3. Get genealogy (origin conversation)
4. Get pattern (abstraction layer)
5. Render with template
```

**Result:** Decision + constraints + origin + pattern

---

## Orchestrator (Layer 2)

**Module:** `imem/src/imem/compose.py`

**Design principle:** Orchestrator composes primitives. All composition logic here.

```python
def compose(collection_name: str, config: dict) -> dict:
    """
    Single entry point. Executes full pipeline.

    Config format:
    {
        "search": {...},          # Required
        "discovery": {...},       # Optional
        "graph": {...},           # Optional
        "output": {...}           # Optional
    }

    Returns: {"results": [...]} or {"rendered": "..."}
    """
    # Stage 1: Search (always happens)
    results = _execute_search(collection_name, config['search'])

    # Stage 2: Discovery (if requested)
    if config.get('discovery'):
        results = _enrich_with_discovery(collection_name, results, config['discovery'])

    # Stage 3: Graph (if requested)
    if config.get('graph'):
        results = _apply_graph_operations(collection_name, results, config['graph'])

    # Stage 4: Render (if template specified)
    if config.get('output', {}).get('template'):
        return {"rendered": _render_template(results, config['output']['template'])}

    return {"results": results}


def _execute_search(collection_name, search_config):
    """Execute search stage"""
    from .primitives.search import search

    if 'queries' in search_config:
        # Multi-query
        all_results = []
        for query_cfg in search_config['queries']:
            r = search(
                collection_name,
                query_cfg['text'],
                filters=query_cfg.get('filters'),
                limit=query_cfg.get('limit', 10)
            )
            all_results.extend(r)
        return all_results
    else:
        # Single query
        return search(
            collection_name,
            search_config['text'],
            filters=search_config.get('filters'),
            limit=search_config.get('limit', 10)
        )


def _enrich_with_discovery(collection_name, results, discovery_config):
    """Execute discovery stage"""
    from .primitives.discovery import get_siblings, get_genealogy, get_temporal, cross_phase_search

    for result in results:
        chunk_id = result['id']

        if discovery_config.get('siblings'):
            result['siblings'] = get_siblings(collection_name, chunk_id)

        if discovery_config.get('genealogy'):
            result['genealogy'] = get_genealogy(collection_name, chunk_id)

        if discovery_config.get('temporal'):
            direction = discovery_config.get('temporal_direction', 'after')
            result['temporal'] = get_temporal(collection_name, chunk_id, direction)

        if discovery_config.get('cross_phase'):
            target_phase = discovery_config['cross_phase']
            result['cross_phase'] = cross_phase_search(collection_name, chunk_id, target_phase)

    return results


def _apply_graph_operations(collection_name, results, graph_config):
    """Execute graph stage (optional)"""
    from .primitives.graph import build_graph, apply_algorithm

    # Build graph from results
    graph_id = build_graph([r['id'] for r in results], graph_config['edges'])

    # Apply algorithm
    algorithm = graph_config['algorithm']
    ranked = apply_algorithm(graph_id, algorithm, top=graph_config.get('top', 10))

    # Reorder results by graph scores
    score_map = {item['id']: item['score'] for item in ranked}
    for result in results:
        result['graph_score'] = score_map.get(result['id'], 0)

    results.sort(key=lambda r: r['graph_score'], reverse=True)
    return results


def _render_template(results, template_name):
    """Render with template"""
    from .templates import render
    return render(results, template_name)
```

**Key property:** Compose is just orchestration. No business logic. Just calls primitives.

**Performance:** Parallelization handled internally (ThreadPoolExecutor for multi-query)

---

## Transfer: Pattern Layer

### Dual-Layer Architecture

Every decision exists at two abstraction levels:

```
auth.md (Implementation)
├─ Context: Sessions don't scale beyond single server
├─ Solution: Use JWT library in TypeScript with Express.js
├─ Rationale: Stateless tokens enable horizontal scaling
└─ Alternatives: OAuth2 (too complex for our use case)

auth.pattern.md (Pattern)
├─ Context: Distributed system without shared state
├─ Solution: Token-based authentication with asymmetric signing
├─ Rationale: Horizontal scaling without session store
└─ Trade-off: Can't revoke tokens immediately
```

**Key difference:**
- Implementation: TypeScript, JWT library, Express.js
- Pattern: Language-agnostic, principle-based

### Generation Process

**One-time at creation:**
```python
def generate_pattern(changelog_content: str) -> str:
    """Extract pattern using Haiku LLM"""

    prompt = f"""
Extract language-agnostic pattern from this decision:

{changelog_content}

Remove:
- Specific technologies (TypeScript, Express.js, JWT library)
- Framework names
- Implementation details

Keep:
- Problem statement (abstract)
- Solution principle
- Rationale
- Trade-offs

Output pattern in same template structure.
    """

    pattern = haiku.generate(prompt)  # ~200ms, ~$0.0001
    return pattern
```

**Storage:**
```
.changes/251018-1200_auth.md (original)
.changes/251018-1200_auth.pattern.md (pattern)
```

**Indexing:** Both indexed separately, queryable independently

### Cross-Project Transfer

**Query isolation:**

```python
# In-project query (default): Returns implementation
search("auth", filters={'project': 'current'})
→ Returns: auth.md (TypeScript + JWT)

# Cross-project query: Returns patterns only
search("auth", filters={'layer': 'pattern', 'all_projects': true})
→ Returns: auth.pattern.md (language-agnostic)
```

**Anti-contamination:** Pattern layer prevents framework leakage across projects

**Authority accumulation:** Pattern in 5 projects = validated approach

---

## Supersession Mechanism

### Three-Level Approach

**1. Detection Hints (at indexing):**
```python
def compute_supersession_hints(new_chunk):
    """Find top-5 similar older chunks as supersession candidates"""
    # Query older chunks of same section_type
    older_chunks = client.search(
        collection_name=collection,
        query_vector=new_chunk.vector,
        query_filter=Filter(must=[
            FieldCondition(key='section_type', match=MatchValue(value=new_chunk.section_type)),
            FieldCondition(key='timestamp', range={'lt': new_chunk.timestamp})
        ]),
        limit=5,
        score_threshold=0.85
    )

    # Store as metadata hints (not facts)
    new_chunk.payload['supersession_candidates'] = [
        {'id': c.id, 'similarity': c.score} for c in older_chunks
    ]
```

**Properties:**
- O(k) per new chunk (not O(n²) precomputation)
- Semantic similarity threshold: 0.85
- Stored as hints, not hard facts (model interprets)

**2. Serving Logic (at query time):**
```python
def serve_chunk(chunk, force_full_resolution=False):
    """Flippable chunks: metadata controls serving mode"""
    if chunk.payload.get('superseded_by') and not force_full_resolution:
        # Default: Serve pattern abstraction
        pattern_variant = find_pattern_variant(chunk.payload['file_path'])
        return pattern_variant
    else:
        # Full resolution or not superseded
        return chunk
```

**Properties:**
- No deletion (both impl + pattern indexed)
- No re-indexing (supersession = metadata flag)
- Runtime flip (metadata read, O(1))
- Reversible (`--full-resolution` flag)

**3. BRAIN Annotation (endstate, 12-18mo):**
```python
def annotate_chunk(chunk, brain_context):
    """Haiku adds soft temporal context before serving"""
    if brain_context['superseded_by']:
        prompt = f"""
Add gentle temporal context to this chunk:

Content: {chunk.content}
Age: {brain_context['age_months']} months
References: {brain_context['reference_count']}
Superseded by: {brain_context['superseded_by']}

Add soft language:
- "This was later refined..." (not "obsolete")
- "While originally chosen for X, later work showed Y..."
- Preserve genealogy, signal currency

Output annotated chunk.
        """
        return haiku.generate(prompt)  # ~200ms, ~$0.0001
    return chunk.content
```

**Cost:** ~$0.001 per 10-chunk query
**Value:** Unknown until tested (may improve comprehension vs clutter)

---

## Template Serve-Time Structure

### Role 3: Presentation (Beyond Enforcement & Filtering)

Templates operate at **three lifecycle stages:**

1. **Write time:** Enforce structure (Context/Solution required)
2. **Query time:** Enable filtering (has_context=true)
3. **Serve time:** Structure presentation (relationship-labeled)

**Innovation:** Prompt engineering at retrieval layer. Chunks served with explicit relationship labels based on metadata queries. Traditional RAG dumps flat chunks, model infers structure. AURA serves pre-structured, relationship-explicit context.

**Token savings:** ~30-40% (no relationship parsing overhead for Claude)

### Decision Template (Jinja2)

```jinja2
# DECISION: {{ primary.section_name }}

## Primary Decision ({{ primary.file_path }})
**Context**: {{ extract_field(primary, 'Context') }}
**Solution**: {{ extract_field(primary, 'Solution') }}
**Rationale**: {{ extract_field(primary, 'Rationale') }}

{% if siblings %}
---
## RELATED SECTIONS (Same Changelog)
Found {{ siblings|length }} related sections:

{% for sibling in siblings %}
### {{ sibling.section_type }}: {{ sibling.section_name }}
{{ sibling.content }}
{% endfor %}
{% endif %}

{% if genealogy %}
---
## CONVERSATION ORIGIN (Session {{ primary.session_id }})
{{ render_conversation(genealogy) }}
{% endif %}

{% if pattern %}
---
## PATTERN ABSTRACTION (Cross-Project)
{{ pattern.content }}
{% endif %}
```

### Field Extraction

```python
def extract_field(chunk, field_name: str) -> str:
    """Extract template field using schema knowledge"""
    content = chunk.payload['content']
    pattern = rf'\*\*{field_name}\*\*:\s*(.+?)(?=\n-\s*\*\*|\n##|\Z)'
    match = re.search(pattern, content, re.DOTALL)
    return match.group(1).strip() if match else None
```

**Benefit:** ~30-40% token savings (no relationship parsing needed by model)

---

## Graph Operations

### Primitive 1: build_graph

```python
def build_graph(
    result_ids: List[str],
    edge_types: List[str] = ['sibling', 'genealogy', 'semantic']
) -> str:
    """Build NetworkX graph from result IDs"""

    # 1. Load chunks
    results = client.retrieve(collection_name="imem", ids=result_ids)

    # 2. Create graph
    G = nx.DiGraph()
    for result in results:
        G.add_node(result.id, result=result, metadata=result.payload)

    # 3. Add edges
    for r1, r2 in combinations(results, 2):
        # Sibling edges
        if 'sibling' in edge_types:
            if r1.payload['file_path'] == r2.payload['file_path']:
                G.add_edge(r1.id, r2.id, type='sibling', weight=0.9)

        # Genealogy edges
        if 'genealogy' in edge_types:
            if r1.payload.get('session_id') == r2.payload.get('session_id'):
                G.add_edge(r1.id, r2.id, type='genealogy', weight=0.85)

        # Semantic edges
        if 'semantic' in edge_types:
            similarity = cosine_similarity(r1.vector, r2.vector)
            if similarity > 0.85:
                G.add_edge(r1.id, r2.id, type='semantic', weight=similarity)

    # 4. Persist
    graph_id = _generate_graph_id(result_ids)
    nx.write_gpickle(G, f"~/.context/imem_graphs/{graph_id}.pkl")

    return graph_id
```

### Primitive 2: apply_algorithm

```python
def apply_algorithm(graph_id: str, algorithm: str, top: int = 10) -> List[Dict]:
    """Apply ranking algorithm"""

    G = nx.read_gpickle(f"~/.context/imem_graphs/{graph_id}.pkl")

    if algorithm == 'pagerank':
        scores = nx.pagerank(G, weight='weight')
    elif algorithm == 'centrality':
        scores = nx.betweenness_centrality(G, weight='weight')
    elif algorithm == 'communities':
        from networkx.algorithms import community
        return community.louvain_communities(G, weight='weight')

    # Rank and return
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [
        {
            'id': node_id,
            'content': G.nodes[node_id]['result'].payload['content'],
            'score': score,
            'metadata': G.nodes[node_id]['metadata']
        }
        for node_id, score in ranked[:top]
    ]
```

**Performance:**
- build_graph: ~40-100ms (k=20-50)
- apply_algorithm: ~20-50ms
- Total: ~60-150ms

---

## Phase Integration

### Phase 1-5: Vector Search (Existing)

Standard semantic search with metadata filtering.

### Phase 6: Soft-Graph Primitives

**Add:**
- siblings (file_path filter)
- temporal (timestamp + semantic)
- session (session_id filter)

**Effort:** ~200 lines

### Phase 7: Graph Operations

**Add:**
- build_graph (NetworkX construction)
- apply_algorithm (PageRank, centrality)

**Effort:** ~200 lines

### Phase 8: Infrastructure & Pattern Layer

**Add:**
- batch primitive (parallelization)
- pattern.md generation (Haiku LLM)
- template serve-time rendering

**Effort:** ~250 lines

**Total MVP:** ~650 new lines (phases 6-8)

---

## Retrieval Modes

| Mode | Primitives Used | Template | Use Case |
|------|----------------|----------|----------|
| **Recall** | search | None | Basic retrieval |
| **Explain** | search + siblings + genealogy + pattern | decision.md.j2 | Full context |
| **Trace** | search + temporal | timeline.md.j2 | Evolution |
| **Authority** | multi-search + batch + graph (PageRank) | authority.md.j2 | Most important |
| **Bridge** | multi-search + batch + graph (centrality) | bridge.md.j2 | Connectors |

**Composition at prompt level:** Claude Code decides which mode based on user query

---

## Key Properties

**Creation-time enforcement:**
- Template validation before indexing
- Guaranteed metadata (100% vs ~70%)
- Enables deterministic queries

**Runtime discovery:**
- Edges from metadata queries
- O(k²) not O(n²)
- Zero maintenance

**Query-adaptive:**
- Different graph per query
- Same chunks, different algorithms
- Context-specific ranking

**Ephemeral graphs:**
- Build, use, discard
- Optional session persistence
- No precomputation

**Pattern isolation:**
- Dual-layer (impl + pattern)
- Cross-project transfer
- Anti-contamination

**Batch infrastructure:**
- Parallel execution
- 3× speedup
- Observable compositions

---

## Success Metrics

**MVP validates when:**
1. ✅ Siblings primitive works (file_path filter)
2. ✅ Graph construction < 100ms (k=20-50)
3. ✅ PageRank improves relevance vs pure semantic
4. ✅ Batch reduces latency 2-3×
5. ✅ Pattern layer prevents cross-project contamination

**V2 features (beyond MVP):**
- BRAIN (persistent relationship metadata)
- Flippable chunks (supersession → abstraction)
- Soft decay annotation (LLM contextualizes old knowledge)

---

## Summary

**IMEM = FlexGraph for coding agents** (first implementation)

**The Moat (validated):** Template-as-schema (100% metadata, AI-written docs)
**Layer 2A (planned):** Metadata discovery (siblings/genealogy/temporal) - No graphs
**Layer 2B (experimental):** Graph operations (PageRank/centrality) - Actual graphs
**Infrastructure (planned):** Compositional batch API (single-call compositions)
**Transfer (proposed):** Pattern layer (cross-project anti-contamination)

**Estimated effort:** ~650 lines for MVP (phases 6-8)
**Timeline:** ~1 week implementation
**Key validation:** Whether Layer 2B provides value over Layer 2A alone
