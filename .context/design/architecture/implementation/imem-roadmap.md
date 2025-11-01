# IMEM Roadmap

**Sequenced Implementation Plan**

*This is a working plan. Phases 6-8 represent hypotheses to be validated, not proven systems.*

---

## Current State (Phase 5 Complete)

**What works:**
- ✅ Vector search (Qdrant + E5 embeddings)
- ✅ Metadata filtering (file_path, session_id, section_type)
- ✅ Basic retrieval (search + filter)
- ✅ CLI interface (`imem search`, `imem filter`)

**What's missing:**
- ❌ Relationship discovery (siblings, genealogy, temporal)
- ❌ Graph operations (PageRank, centrality)
- ❌ Batch parallelization
- ❌ Pattern layer generation
- ❌ Template serve-time rendering

---

## MVP: Phases 6-7 (FlexGraph Core)

### Phase 6: Layer 1 (Primitives) + Layer 2 (Compose) - BIG BANG

**Goal:** Build foundational layers in one session, test immediately

**Effort:** ~300 lines, 4-6 hours

**Rationale:** Primitives without composition are useless. Build together, test together, decide on graphs with data.

**Create:**
```
imem/src/imem/primitives/
├── __init__.py
├── discovery.py  (~150 lines)
│   ├── get_siblings(collection_name, chunk_id)
│   ├── get_genealogy(collection_name, chunk_id)
│   ├── get_temporal(collection_name, chunk_id, direction)
│   └── cross_phase_search(collection_name, chunk_id, target_phase)
│
└── graph.py  (~50 lines, optional - build if time permits)
    ├── build_graph(chunk_ids, edge_types)
    └── apply_algorithm(graph_id, algorithm)

imem/src/imem/compose.py  (~150 lines)
├── compose(collection_name, config)
├── _execute_search(collection_name, search_config)
├── _enrich_with_discovery(collection_name, results, discovery_config)
├── _apply_graph_operations(collection_name, results, graph_config)
└── _render_template(results, template_name)
```

**Test immediately with 5 real queries:**
```python
# Query 1: Explain decision (siblings + genealogy)
config1 = {
    "search": {"text": "JWT authentication", "phase": "develop", "limit": 1},
    "discovery": {"siblings": True, "genealogy": True}
}

# Query 2: Trace evolution (temporal)
config2 = {
    "search": {"text": "caching", "phase": "develop", "limit": 1},
    "discovery": {"temporal": True, "siblings": True}
}

# Query 3: Cross-phase journey (design→develop)
config3 = {
    "search": {"text": "template-aware chunking", "phase": "develop", "limit": 1},
    "discovery": {"cross_phase": "design", "genealogy": True, "siblings": True}
}

# Query 4: Multi-phase search
config4 = {
    "search": {
        "queries": [
            {"text": "authentication", "phase": "design"},
            {"text": "authentication", "phase": "develop"}
        ]
    }
}

# Query 5: Authority test (CRITICAL - decides on graphs)
config5 = {
    "search": {"text": "caching decisions", "phase": "develop"},
    "discovery": {"siblings": True}
}
# For each result: authority = len(siblings) + len(genealogy)
# QUESTION: Do high authority results rise naturally? Or need PageRank?
```

**Success criteria:**
- ✅ All primitives work independently
- ✅ Compose orchestrates correctly
- ✅ Queries 1-4 return expected results
- ✅ Query 5 reveals: **Do we need graphs or is reference counting sufficient?**

**Critical decision after Phase 6:**
- If reference counting (siblings + genealogy count) approximates authority well → Skip graphs, move to Phase 7 (Templates + CLI)
- If results feel insufficient → Build graph.py primitives

**Unlocks:** Clear validation of Layer 2B value

---

### Phase 7: Layer 3 (Templates) + Layer 4 (CLI)

**Goal:** Add presentation layer and CLI wrapper

**Effort:** ~150 lines, 2-3 hours

**Conditional:** Only build graph operations if Phase 6 testing shows clear need

**Create:**
```
imem/templates/
├── __init__.py
├── genealogy.md.j2
├── timeline.md.j2
└── authority.md.j2

imem/src/imem/cli.py  (+30 lines)
└── compose command
```

**CLI implementation:**
```python
@imem.command()
@click.argument('config_json')
def compose(config_json):
    """Execute composition pipeline

    Examples:
        imem compose '{"search": {...}, "discovery": {...}}'
    """
    import json
    from .compose import compose as execute_compose
    from .registry import SimpleRegistry

    # Parse config
    config = json.loads(config_json)

    # Get collection
    registry = SimpleRegistry()
    project_root = registry.get_project_root()
    info = registry.get_project_info(project_root)
    collection_name = info['collection']

    # Execute
    result = execute_compose(collection_name, config)

    # Output
    if 'rendered' in result:
        click.echo(result['rendered'])
    else:
        click.echo(json.dumps(result, indent=2))
```

**Test end-to-end:**
```bash
imem compose '{
  "search": {"text": "JWT authentication", "phase": "develop", "limit": 1},
  "discovery": {"siblings": true, "genealogy": true},
  "output": {"template": "genealogy"}
}'
```

**Expected output:**
```markdown
# GENEALOGY: JWT Authentication

## Design Exploration
[Design docs if any]

## Origin Conversation
Session: cb91d93d...
[Conversation chunks]

## Decision
**Context**: Sessions don't scale...
**Solution**: Stateless JWT tokens...

## Related Sections
- Constraints: Token expiry
- Patterns: Refresh tokens
```

**Success criteria:**
- ✅ Single bash call returns full genealogy
- ✅ Templates structure output correctly
- ✅ CLI is thin wrapper (just JSON parsing + compose call)

---

### Phase 8: Template Validation (Moved to V2)

**Note:** Template validation deferred to V2 (polish, not MVP)

---

### Phase 8: Observable Compositions & Preset Library

**Goal:** Let AI agents discover useful composition patterns through flexible usage

**The Philosophy:** Not prescriptive. Usage-driven.

---

#### The Learning Process

**Step 1: Flexible Composition**

Agents compose primitives ANY way based on query intent:

```json
// Query: "Explain this decision"
{"genealogy": true, "siblings": {"section_types": ["Decisions", "Failures"]}}

// Query: "How did this evolve?"
{"temporal": true, "siblings": {"section_types": ["Patterns"]}}

// Query: "What failed?"
{"siblings": {"section_types": ["Failures"]}}
```

**No restrictions. Any combination valid.**

---

**Step 2: Usage Observation**

System tracks which compositions recur:

```python
# Usage tracking
usage_log = {
    'composition_a': {
        'config': {"genealogy": true, "siblings": {...}},
        'count': 30,
        'queries': [
            "Explain JWT decision",
            "Why debounce approach",
            "How caching works",
            # ... 27 more
        ]
    },
    'composition_b': {
        'config': {"temporal": true, "siblings": {"section_types": ["Patterns"]}},
        'count': 20,
        'queries': [
            "Evolution of auth",
            "How caching changed",
            # ... 18 more
        ]
    }
}
```

---

**Step 3: Pattern Recognition**

After 10-20 uses of same composition → Pattern detected:

```python
def detect_patterns():
    """Analyze usage log for recurring patterns"""

    for composition_hash, data in usage_log.items():
        if data['count'] >= 15:
            # Pattern detected
            pattern_name = suggest_name(data['queries'])
            # e.g., "Explain Decision" from query patterns

            confidence = data['count'] / 15  # 2.0 = high confidence

            yield {
                'name': pattern_name,
                'composition': data['config'],
                'usage_count': data['count'],
                'confidence': confidence
            }
```

---

**Step 4: Preset Capture**

Proven pattern becomes slash command:

```python
def capture_as_preset(pattern):
    """Create slash command from proven pattern"""

    filename = slugify(pattern['name'])  # "explain-decision"

    content = f"""# {pattern['name']}

{infer_description(pattern['queries'])}

Usage: /{filename} <query>

---

**Captured from {pattern['usage_count']} observed uses.**

Internally expands to:
```json
{json.dumps(pattern['composition'], indent=2)}
```
"""

    write_file(f".claude/commands/{filename}.md", content)
```

---

#### Emergent Presets (Examples)

**Pattern 1: Narrative Reconstruction**

Detected after 30 uses:
```json
{
  "genealogy": true,
  "cross_phase": "design",
  "siblings": {
    "section_types": ["Decisions", "Failures", "Patterns"]
  }
}
```

Queries that used this:
- "Explain JWT authentication"
- "Why did we choose debounce?"
- "How does caching work?"
- "What's the variant system?"
- [26 more similar queries]

Captured as:
```markdown
# .claude/commands/explain-decision.md

Find a decision and reconstruct complete context:
- Origin conversation (brainstorming, debugging)
- Design decisions (alternatives, rationale)
- Related failures (what didn't work)
- Working solution (what did work)
- Extracted patterns (reusable learnings)

Usage: /explain-decision <query>
```

**Pattern name:** Explain Decision
**Confidence:** 2.0 (30 uses / 15 threshold)

---

**Pattern 2: Evolution Timeline**

Detected after 20 uses:
```json
{
  "temporal": {"direction": "both"},
  "siblings": {
    "section_types": ["Patterns"],
    "order_by": "timestamp"
  }
}
```

Queries that used this:
- "Evolution of caching strategy"
- "How did auth approach change?"
- "Trace debounce refinements"
- [17 more similar queries]

Captured as:
```markdown
# .claude/commands/evolution-trace.md

Trace how thinking evolved over time:
- Earlier attempts (temporal: before)
- Current approach (primary)
- Later refinements (temporal: after)
- Patterns extracted at each stage

Usage: /evolution-trace <query>
```

**Pattern name:** Evolution Trace
**Confidence:** 1.33 (20 uses / 15 threshold)

---

**Pattern 3: Anti-Pattern Search**

Detected after 15 uses:
```json
{
  "siblings": {
    "section_types": ["Failures"]
  }
}
```

Queries that used this:
- "What auth approaches failed?"
- "Failed caching attempts"
- "Rejected solutions for debounce"
- [12 more similar queries]

Captured as:
```markdown
# .claude/commands/anti-patterns.md

Find what didn't work across all documents:
- Failed attempts
- Why they failed
- Lessons learned
- What to avoid

Usage: /anti-patterns <query>
```

**Pattern name:** Anti-Patterns
**Confidence:** 1.0 (15 uses / 15 threshold)

---

**Pattern 4: Design Journey**

Detected after 12 uses:
```json
{
  "cross_phase": "design",
  "siblings": {
    "section_types": ["Decisions"],
    "has_rationale": true
  }
}
```

Queries that used this:
- "Design thinking for variant system"
- "Abstract decisions before caching impl"
- "Pre-implementation choices for auth"
- [9 more similar queries]

Captured as:
```markdown
# .claude/commands/design-journey.md

Show pre-implementation design thinking:
- Abstract decisions (design phase)
- Alternatives considered
- Rationale for choices
- Before code was written

Usage: /design-journey <query>
```

**Pattern name:** Design Journey
**Confidence:** 0.8 (12 uses / 15 threshold)

---

**Pattern 5: Pattern Library**

Detected after 10 uses:
```json
{
  "siblings": {
    "section_types": ["Patterns"],
    "order_by": "timestamp"
  }
}
```

Queries that used this:
- "All caching patterns"
- "Authentication patterns library"
- "Reusable debugging patterns"
- [7 more similar queries]

Captured as:
```markdown
# .claude/commands/pattern-library.md

Build domain-specific pattern library:
- All patterns for topic
- Ordered by recency
- Reusable learnings
- Cross-document compilation

Usage: /pattern-library <query>
```

**Pattern name:** Pattern Library
**Confidence:** 0.67 (10 uses / 15 threshold)

---

#### Implementation

**Composition tracking:**
```python
# imem/src/imem/tracking.py

import hashlib
import json
from pathlib import Path

USAGE_LOG_PATH = Path.home() / '.context' / 'imem_usage.json'

def track_composition(config, query):
    """Log composition usage for pattern detection"""

    # Load existing log
    usage_log = load_usage_log()

    # Hash composition config
    composition_str = json.dumps(config.get('discovery', {}), sort_keys=True)
    composition_hash = hashlib.sha256(composition_str.encode()).hexdigest()[:16]

    # Initialize or update
    if composition_hash not in usage_log:
        usage_log[composition_hash] = {
            'config': config['discovery'],
            'count': 0,
            'queries': [],
            'first_used': datetime.now().isoformat()
        }

    usage_log[composition_hash]['count'] += 1
    usage_log[composition_hash]['queries'].append({
        'query': query,
        'timestamp': datetime.now().isoformat()
    })

    # Save
    save_usage_log(usage_log)

    # Check for pattern
    if usage_log[composition_hash]['count'] in [10, 15, 20, 30]:
        suggest_preset(composition_hash, usage_log[composition_hash])
```

**Preset suggestion:**
```python
def suggest_preset(composition_hash, data):
    """Suggest creating preset from pattern"""

    count = data['count']
    confidence = count / 15

    # Infer name from queries
    queries = [q['query'] for q in data['queries']]
    suggested_name = infer_preset_name(queries)

    print(f"""
    🎯 PATTERN DETECTED ({count} uses, confidence: {confidence:.1f}×)

    Suggested preset: /{slugify(suggested_name)}

    Composition:
    {json.dumps(data['config'], indent=2)}

    Recent queries:
    {chr(10).join(f'  - {q}' for q in queries[-5:])}

    Create preset? (y/n)
    """)
```

---

#### Success Metrics

**MVP validates when:**

- [ ] Agents use flexible composition (not rigid queries)
- [ ] 3+ distinct patterns detected (10+ uses each)
- [ ] Presets captured successfully
- [ ] Presets reused by agents (validation)

**V2 features:**

- Automatic preset suggestions (no manual approval)
- Preset refinement (update based on continued usage)
- Preset analytics (which presets most useful)
- Cross-project preset sharing

---

#### Deliverables

**Phase 8 output:**
```
.claude/commands/
├── explain-decision.md       (30+ uses, conf: 2.0×)
├── evolution-trace.md        (20+ uses, conf: 1.33×)
├── anti-patterns.md          (15+ uses, conf: 1.0×)
├── design-journey.md         (12+ uses, conf: 0.8×)
└── pattern-library.md        (10+ uses, conf: 0.67×)

.context/imem_usage.json      (usage tracking log)
```

**Usage log structure:**
```json
{
  "a7f3c21e9b4d8f6a": {
    "config": {
      "genealogy": true,
      "siblings": {"section_types": ["Decisions", "Failures", "Patterns"]}
    },
    "count": 30,
    "first_used": "2025-10-28T12:00:00",
    "queries": [
      {"query": "Explain JWT", "timestamp": "2025-10-28T12:00:00"},
      {"query": "Why debounce", "timestamp": "2025-10-28T14:30:00"},
      ...
    ]
  },
  ...
}
```

---

#### The Value Proposition

**Traditional approach:**
```
Developer: "We need these 5 query types"
System: [Implements 5 rigid patterns]
Reality: Agents need 12 different patterns
Result: Manual updates needed
```

**FlexGraph approach:**
```
Developer: "Here are compositional primitives"
System: [Flexible composition]
Agents: [Discover 12 useful patterns through use]
System: [Captures proven patterns automatically]
Result: Self-improving preset library
```

**Key differences:**

| Traditional | FlexGraph |
|------------|-----------|
| Prescriptive | Usage-driven |
| Fixed patterns | Emergent patterns |
| Manual updates | Auto-capture |
| Developer defines | System learns |
| Static | Self-improving |

---

#### Why This Matters

**FlexGraph = Compositional + Observable + Self-Improving**

1. **Compositional:** ANY primitive combination works
2. **Observable:** System tracks what agents do
3. **Self-Improving:** Proven patterns captured automatically

**Not:**
- "Here are the allowed queries"
- "These are the patterns you can use"

**But:**
- "Compose freely"
- "System learns what works"
- "Useful patterns captured automatically"

**The innovation: System that learns from usage.**

---

### Phase 9: Infrastructure

**Goal:** Batch primitive + pattern layer

**Effort:** ~250 lines, 3 days

#### Part A: Batch Primitive (~150 lines)

**Add:**
```python
# imem/src/imem/batch.py

async def batch_execute(config: Dict) -> Dict:
    """Execute operations in parallel"""
    pass

async def _execute_query_sugar(config: Dict) -> Dict:
    """Handle queries + combine + graph sugar"""
    pass
```

**CLI:**
```bash
imem batch '{"queries": [...], "combine": true, "graph": {...}}'
```

**Test:**
```python
async def test_parallel_execution():
    # 3 queries in parallel
    # Assert latency < 120ms (not 300ms)

async def test_query_sugar():
    # Multi-query + graph
    # Assert returns PageRank-ranked results
```

#### Part B: Pattern Layer (~100 lines)

**Add:**
```python
# imem/src/imem/pattern.py

def generate_pattern(changelog_content: str) -> str:
    """Use Haiku to extract language-agnostic pattern"""
    pass

def index_pattern(file_path: str, pattern_content: str):
    """Index .pattern.md twin"""
    pass
```

**Workflow:**
```python
# At changelog creation:
content = generate_changelog(session)
pattern = generate_pattern(content)  # Haiku LLM ~200ms

index_changelog(content)  # auth.md
index_pattern(pattern)    # auth.pattern.md
```

**Test:**
```python
def test_pattern_generation():
    # Given: Decision with TypeScript + JWT
    # When: generate_pattern()
    # Then: Pattern has no TypeScript/JWT mentions

def test_cross_project_isolation():
    # Query patterns from Python project
    # Assert: No TypeScript code returned
```

**Success criteria:**
- ✅ Batch reduces 3-query latency 2-3×
- ✅ Pattern generation < 500ms
- ✅ Cross-project query returns patterns only

---

## MVP Validation (End of Phase 7)

**Checklist:**

| Capability | Working | Test Passing |
|------------|---------|--------------|
| Siblings primitive | ☐ | ☐ |
| Genealogy primitive | ☐ | ☐ |
| Temporal primitive | ☐ | ☐ |
| Cross-phase primitive | ☐ | ☐ |
| Compose orchestration | ☐ | ☐ |
| Template rendering | ☐ | ☐ |
| CLI wrapper | ☐ | ☐ |

**Optional (if Phase 6 testing showed need):**
| Capability | Working | Test Passing |
|------------|---------|--------------|
| Graph build | ☐ | ☐ |
| PageRank ranking | ☐ | ☐ |

**Performance targets:**
- Primitives (siblings/genealogy/temporal): < 50ms each
- Compose (search + discovery): < 100ms
- Graph operations (if built): < 100ms
- End-to-end (CLI call): < 150ms

**User experience test:**
```bash
# Full genealogy via single command
imem compose '{
  "search": {"text": "JWT authentication", "phase": "develop", "limit": 1},
  "discovery": {
    "siblings": true,
    "genealogy": true,
    "temporal": true,
    "cross_phase": "design"
  },
  "output": {"template": "genealogy"}
}'

# Should return: Complete genealogy in structured format in < 150ms
```

---

## V2: Enhanced Capabilities (Post-MVP)

### V2.1: Template Serve-Time (~100 lines, 1 day)

**Goal:** Relationship-labeled presentation

**Add:**
```python
# imem/src/imem/serve.py

def serve_with_template(
    primary_chunk,
    relationships: Dict,
    template: str = 'decision'
) -> str:
    """Render with Jinja2 template"""
    pass

# imem/templates/decision.md.j2
# (Jinja2 template files)
```

**Benefit:** ~30-40% token savings (explicit relationship labels)

### V2.2: Flippable Chunks (~50 lines, 1 day)

**Goal:** Supersession → abstraction (not deletion)

**Add:**
```python
# Metadata field
chunk.payload['superseded_by'] = 'newer-chunk-id'
chunk.payload['serve_mode'] = 'pattern'  # 'impl' or 'pattern'

# Query logic
if chunk.superseded:
    if force_full_resolution:
        return chunk  # Implementation
    else:
        return find_pattern_variant(chunk)  # Pattern abstraction
```

**Benefit:** Zero-loss memory degradation

### V2.3: BRAIN Basics (~200 lines, 2 days)

**Goal:** Persistent relationship metadata accumulation

**Structure:**
```json
{
  "chunks": {
    "chunk-id": {
      "superseded_by": ["newer-chunk-id"],
      "supersession_confidence": 0.89,
      "age_months": 18,
      "reference_count": 23,
      "pagerank_score": 0.72
    }
  }
}
```

**Updates:** Every query increments reference counts, graph operations cache PageRank

**Feeds:** Annotation layer (endstate Phase 10+)

**Dependencies:**
- BRAIN needs data (reference counts, supersession patterns, authority scores)
- 3-6 months usage accumulation required
- Annotation latency must be acceptable (~200ms per chunk with Haiku)

**Build Order:** Primitives (Phase 6-7) → Usage logs (Phase 8) → BRAIN accumulation (Phase 9, 3-6 months) → Annotation layer (Phase 10)

---

## Endstate: BRAIN + Annotation (12-18 months)

### Phase 10+: LLM Annotation Layer

**Goal:** Soft decay language via cheap LLM pass

**Dependencies:**
- BRAIN accumulation (3-6 months usage data)
- Supersession hints validated
- Authority scores meaningful
- Soft language needs refinement (test what works: "later refined" vs "superseded" vs "evolved")

**Implementation:**
```python
def annotate_chunk(chunk, brain_context):
    """Haiku adds soft temporal context before serving"""
    prompt = f"""
Add soft temporal context:

Chunk: {chunk.content}
Age: {brain_context['age_months']} months
References: {brain_context['reference_count']}
Superseded: {brain_context['superseded_by']}

Add language: "This was later refined..." not "OBSOLETE"
"""
    return haiku.generate(prompt)  # ~200ms, ~$0.0001
```

**Cost:** ~$0.001 per 10-chunk query

**Value uncertainty:**
- Unknown if soft language improves retrieval vs clutters
- Unknown if temporal decay matters in practice
- Unknown if Claude benefits from annotations vs raw chunks

**Serve pipeline:**
```
1. Semantic search (Qdrant)
2. Relationship discovery (siblings/genealogy/temporal)
3. Graph operations (if requested—pagerank/centrality)
4. BRAIN lookup (load supersession/authority/decay state)
5. LLM annotation (Haiku adds soft language)
6. Template assembly (structure with relationship labels)
```

**Example output:**
```markdown
# DECISION: Use Redis for Caching [⏳ SUPERSEDED]

🔄 **Evolution Note**: This decision (18 months old) was later refined
in October 2024 after performance testing. Original context preserved
for genealogy.

**Context**: Need distributed cache...
**Solution**: Redis cluster with 3 nodes...

💡 **Why Changed**: Performance analysis showed Memcached 3× faster for
our access patterns. See [current decision](memcached-id).
```

**Benefit:** Knowledge never deleted, always contextualized

---

## Timeline

### MVP (Phases 6-7)
- **Duration:** ~6-9 hours (1 focused day)
- **Effort:** ~450 lines (primitives + compose + templates + CLI)
- **Validation:** Single command returns full genealogy

**Breakdown:**
- Phase 6 (Big Bang): 4-6 hours for primitives + compose + immediate testing
- Phase 7: 2-3 hours for templates + CLI

### Phase 8 (Slash Commands)
- **Duration:** Ongoing (10-20 min per command as patterns emerge)
- **Effort:** 10-20 lines markdown per command
- **Validation:** Proven composition patterns captured

### V2 (Enhanced) - Conditional
- **Duration:** ~1 week
- **Effort:** ~400 lines
- **Components:**
  - Template validation (~80 lines)
  - Pattern layer (~100 lines)
  - Flippable chunks (~50 lines)
  - BRAIN basics (~200 lines)

### Endstate (BRAIN + Annotation)
- **Duration:** 12-18 months post-MVP
- **Effort:** ~500 lines
- **Validation:** Soft decay annotation, accumulated wisdom

---

## Sequencing Rationale

**Why Big Bang (Phases 6+7 together)?**
- Primitives without compose are useless for testing
- Compose without primitives has nothing to orchestrate
- Can't validate value until full pipeline works
- Testing 5 queries immediately reveals if graphs needed

**Why Templates + CLI together (Phase 7)?**
- Both are thin layers (templates = Jinja2, CLI = JSON parsing)
- Can't test end-to-end without CLI
- Quick to build after compose works (~2-3 hours)

**Why Slash Commands ongoing (Phase 8)?**
- Emerge from usage patterns
- Can't predict which compositions are common
- Build incrementally as patterns repeat (10+ uses)

**Why V2 deferred?**
- Template validation = polish (not core functionality)
- Pattern layer = optimization (works without)
- Flippable chunks = enhancement (not MVP)
- BRAIN = accumulates over time (needs data)

**Why endstate 12-18mo?**
- Needs 3-6 months usage data
- Needs BRAIN metadata accumulation
- Needs soft language prompt refinement

---

## Dependencies

### Phase 6
```
- Existing: Qdrant client
- New: None
```

### Phase 7
```
- Existing: Qdrant client, numpy
- New: networkx>=3.0
```

### Phase 8
```
- Existing: asyncio (stdlib)
- New: Anthropic Claude API (Haiku)
```

### V2
```
- New: jinja2>=3.1.0 (template rendering)
```

---

## Risk Mitigation

### Risk 1: Graph construction too slow

**Mitigation:**
- Limit result set (k <= 50)
- Only compute necessary edge types
- Cache graphs for session reuse

**Fallback:** Skip graph ops, return semantic ranking

### Risk 2: Pattern generation unreliable

**Mitigation:**
- Test on 20+ diverse decisions
- Validate output structure
- Human review loop initially

**Fallback:** Skip pattern layer, implement later

### Risk 3: Batch overhead > benefit

**Mitigation:**
- Benchmark parallel vs sequential
- Profile async overhead
- Consider ThreadPoolExecutor vs asyncio

**Fallback:** Keep sequential, defer batch primitive

---

## Success Metrics (To Be Validated)

### MVP Success = All True

- [ ] Siblings primitive returns correct chunks (< 50ms)
- [ ] Graph construction works (< 100ms for k=20-50)
- [ ] **Critical:** PageRank ranking improves relevance vs semantic search alone
- [ ] Batch reduces latency 2-3× vs sequential
- [ ] Pattern layer prevents cross-project contamination

**Open question:** Does Layer 2B (graph operations) justify the complexity over Layer 2A (metadata discovery)?

### V2 Success = All True

- [ ] Template serving reduces tokens 30-40%
- [ ] Flippable chunks preserve superseded decisions
- [ ] BRAIN accumulates reference counts correctly

### Endstate Success = All True

- [ ] LLM annotation adds value (not clutter)
- [ ] Soft language improves comprehension
- [ ] Knowledge genealogy preserved

---

## Next Steps

### Immediate: Phase 6 (Big Bang) - One 4-6 hour session

1. **Create primitives module** (~2 hours)
   - `imem/src/imem/primitives/discovery.py`
   - Test each primitive independently

2. **Create compose module** (~1.5 hours)
   - `imem/src/imem/compose.py`
   - Test with config objects (Python dict)

3. **Test 5 queries immediately** (~1 hour)
   - Explain decision (siblings + genealogy)
   - Trace evolution (temporal)
   - Cross-phase journey
   - Multi-phase search
   - **Authority test** (critical - decides on graphs)

4. **Decision point:** Do we need graphs?
   - If reference counting sufficient → Skip to Phase 7
   - If results insufficient → Build graph.py primitives

### Next: Phase 7 (Templates + CLI) - One 2-3 hour session

1. **Create templates** (~1 hour)
   - `imem/templates/genealogy.md.j2`
   - Test rendering with compose results

2. **Add CLI command** (~30 min)
   - `cli.py`: Add compose command
   - Test end-to-end bash call

3. **Validate MVP** (~30 min)
   - Run full genealogy query via CLI
   - Verify output structure and performance

**Total: 6-9 hours to MVP (can be done in 1 focused day)**

**Critical validation:** Single command returns complete genealogy in < 150ms

**Deferred (pending MVP validation):**
- Phase 9+: Template serving, flippable chunks, BRAIN (V2, 1 week)
- Phase 10+: Annotation layer (endstate, 12-18 months)

---

## Summary

**MVP (Phases 6-7) - One Focused Day:**
- Layer 1: Discovery primitives (siblings, genealogy, temporal, cross_phase)
- Layer 2: Compose orchestrator (search + discovery + optional graph)
- Layer 3: Jinja2 templates (genealogy, timeline)
- Layer 4: CLI wrapper (JSON parsing + compose call)

**Result:** `imem compose '{...}'` returns complete genealogy in one call

**Phase 8 (Slash Commands) - Ongoing:**
- Capture proven composition patterns as they emerge
- Build slash command after 10+ uses of same composition

**V2 (Enhanced) - Conditional (~1 week):**
- Template validation (~80 lines)
- Pattern layer (~100 lines)
- Flippable chunks (~50 lines)
- BRAIN basics (~200 lines)

**Endstate (12-18mo) - Speculative:**
- LLM annotation (soft decay language)
- Accumulated wisdom (authority scores)
- Genealogy preservation (zero loss)

**Timeline:** 6-9 hours MVP, ongoing slash commands, 1 week V2 (conditional), 12-18mo endstate
**Effort:** ~450 lines MVP, 10-20 lines per slash command, ~400 lines V2, ~500 lines endstate

**Working hypothesis:** Big bang (primitives + compose) → Test immediately → Decide on graphs with data → Add templates + CLI → Ship MVP
