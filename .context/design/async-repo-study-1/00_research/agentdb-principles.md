# Architectural Principles: agentdb

## Executive Summary

AgentDB implements a **layered memory architecture** where controllers own domain logic, storage is abstracted through dependency injection, and intelligence emerges through multi-tier composition. The system separates raw storage (SQLite/WASM) from semantic operations (embedding, causal inference) from high-level memory patterns (reflexion, skills). **Key insight**: Memory types are horizontally composed controllers that share infrastructure but remain independently replaceable. This enables agentdb to evolve frontier memory features (causal graphs, explainable recall, RL) without disrupting core vector search—highly relevant for IMEM's need to layer compile/manage/retrieve operations over pluggable storage.

---

## System Overview

AgentDB is a **production-ready episodic memory engine** for autonomous agents. It combines:
- **Episodic memory** (Reflexion-style self-critique storage)
- **Skill consolidation** (automatic learning from trajectories)
- **Causal reasoning** (intervention-based causal graphs)
- **Semantic search** (HNSW vector indexing, MMR diversity)
- **RL integration** (9 algorithms with experience replay)
- **Distributed sync** (QUIC protocol coordination)

Architecture philosophy: **Controllers as domain specialists** + **Shared infrastructure** (db, embedder) + **Declarative schema** (SQL as source of truth).

---

## Principle 1: Controller-as-Service with Dependency Injection

**Observed in:** `ReflexionMemory.ts`, `SkillLibrary.ts`, `CausalMemoryGraph.ts`, `EmbeddingService.ts`, `index.ts`

### The Principle

**Controllers are stateless domain services** that receive infrastructure (database, embedder) via constructor injection. Each controller owns one memory pattern (episodes, skills, causal edges) and exposes a focused API. No controller directly instantiates storage or embedding—these are **injected dependencies**.

### How It Works

**Construction pattern** (every controller follows this):
```typescript
// ReflexionMemory.ts
export class ReflexionMemory {
  private db: Database;           // Injected storage
  private embedder: EmbeddingService;  // Injected embedding

  constructor(db: Database, embedder: EmbeddingService) {
    this.db = db;
    this.embedder = embedder;
  }

  async storeEpisode(episode: Episode): Promise<number> {
    // 1. Use injected db for SQL operations
    const stmt = this.db.prepare(`INSERT INTO episodes ...`);
    const episodeId = stmt.run(...);

    // 2. Use injected embedder for semantic operations
    const embedding = await this.embedder.embed(text);
    this.storeEmbedding(episodeId, embedding);

    return episodeId;
  }
}
```

**Storage abstraction** (`db-fallback.ts`):
```typescript
// WASM SQLite (sql.js) wrapper that mimics better-sqlite3 API
function createSqlJsWrapper(SQL: any) {
  return class SqlJsDatabase {
    prepare(sql: string) {
      return {
        run: (...params) => { /* execute query */ },
        get: (...params) => { /* return single row */ },
        all: (...params) => { /* return all rows */ }
      };
    }
  };
}
```

**Composition at entry point** (`index.ts`):
```typescript
// Export controllers, not instances
export { ReflexionMemory } from './controllers/ReflexionMemory.js';
export { SkillLibrary } from './controllers/SkillLibrary.js';
export { EmbeddingService } from './controllers/EmbeddingService.js';
export { createDatabase } from './db-fallback.js';

// Users compose:
const db = await createDatabase('agent.db');
const embedder = new EmbeddingService({ model: 'Xenova/all-MiniLM-L6-v2', ... });
await embedder.initialize();

const memory = new ReflexionMemory(db, embedder);
const skills = new SkillLibrary(db, embedder);
```

### Why It Matters

- **Storage agnostic**: Controllers work with any db implementing the interface (sql.js, better-sqlite3, future Postgres)
- **Testability**: Mock db/embedder for unit tests—no filesystem/network dependencies
- **Composition flexibility**: Same db instance shared across all controllers (single transaction boundary)
- **Runtime swapping**: Switch embedding models without touching memory logic
- **Zero coupling**: Controllers don't know about each other—only shared infrastructure

### Application to IMEM

**Where:** All three layers (compile/, manage/, retrieve/)

**How:** Apply controller-as-service pattern:

```python
# compile/parser.py
class Parser:
    def __init__(self, storage: ChunkStore, templates: TemplateRegistry):
        self.storage = storage  # Injected SQLite/Qdrant adapter
        self.templates = templates  # Injected template plugins

    def parse(self, file_path: Path) -> List[Chunk]:
        template = self.templates.select(file_path)
        chunks = template.extract(file_path)
        self.storage.batch_insert(chunks)
        return chunks

# manage/temporal.py
class TemporalValidator:
    def __init__(self, storage: ChunkStore, git: GitOracle):
        self.storage = storage
        self.git = git

    def validate(self, chunk: Chunk) -> ValidationResult:
        commits = self.git.find_related(chunk.file_path, chunk.timestamp)
        return self.score_authority(chunk, commits)

# Entry point
storage = SQLiteStore('imem.db')  # or QdrantStore(...)
git = GitOracle(repo_path)
templates = TemplateRegistry()
templates.register(ChangelogTemplate())
templates.register(ConversationTemplate())

parser = Parser(storage, templates)
temporal = TemporalValidator(storage, git)
```

**Example:** Switch from SQLite to Qdrant without changing Parser/TemporalValidator:
```python
# Before
storage = SQLiteStore('imem.db')

# After
storage = QdrantStore(url='localhost:6333', collection='imem')

# Parser/TemporalValidator work unchanged
parser = Parser(storage, templates)
```

### Trade-offs

**Pros:**
- Perfect abstraction layer for storage backends
- Controllers testable in isolation
- Clear ownership boundaries (one controller = one memory type)
- Easy to add new memory types (new controller, same infrastructure)

**Cons:**
- Coordination logic must live elsewhere (no inter-controller communication)
- Interface must support all storage backend capabilities (lowest common denominator)
- Requires discipline—tempting to couple controllers

**Adoption Recommendation:** **Adopt** — Critical for IMEM's storage-agnostic principle. Enables SQLite-first development with Qdrant as optional semantic layer.

---

## Principle 2: Schema-as-Source-of-Truth with Multi-Tier Tables

**Observed in:** `frontier-schema.sql`, `schema.sql`, `ReflexionMemory.ts:storeEpisode`, `SkillLibrary.ts:consolidateEpisodesIntoSkills`

### The Principle

**SQL schema is the canonical type system.** Controllers implement business logic, but schema defines data model, indexes, relationships, and constraints. Memory types are **tiered tables**—raw episodic data (bottom tier) feeds into consolidated skills (mid tier) feeds into causal graphs (top tier). Each tier adds intelligence without mutating lower tiers.

### How It Works

**Three-tier architecture** (from schema):

```sql
-- TIER 1: Raw episodic data (bottom)
CREATE TABLE episodes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
  session_id TEXT NOT NULL,
  task TEXT NOT NULL,
  input TEXT, output TEXT, critique TEXT,
  reward REAL NOT NULL,
  success BOOLEAN NOT NULL,
  latency_ms INTEGER,
  tags JSON, metadata JSON
);
CREATE INDEX idx_episodes_reward ON episodes(reward DESC);
CREATE INDEX idx_episodes_session ON episodes(session_id);

CREATE TABLE episode_embeddings (
  episode_id INTEGER PRIMARY KEY,
  embedding BLOB NOT NULL,  -- 384-dim Float32Array
  FOREIGN KEY(episode_id) REFERENCES episodes(id)
);

-- TIER 2: Consolidated skills (mid)
CREATE TABLE skills (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  description TEXT,
  signature JSON NOT NULL,  -- { inputs: {...}, outputs: {...} }
  code TEXT,
  success_rate REAL NOT NULL,
  uses INTEGER DEFAULT 0,
  avg_reward REAL,
  avg_latency_ms REAL,
  created_from_episode INTEGER,
  metadata JSON  -- { extractedPatterns: [...], successIndicators: [...] }
);

CREATE TABLE skill_links (
  parent_skill_id INTEGER NOT NULL,
  child_skill_id INTEGER NOT NULL,
  relationship TEXT NOT NULL,  -- 'prerequisite' | 'alternative' | 'refinement'
  weight REAL NOT NULL,
  PRIMARY KEY (parent_skill_id, child_skill_id, relationship)
);

-- TIER 3: Causal relationships (top)
CREATE TABLE causal_edges (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  from_memory_id INTEGER NOT NULL,
  from_memory_type TEXT NOT NULL,  -- 'episode' | 'skill' | 'note' | 'fact'
  to_memory_id INTEGER NOT NULL,
  to_memory_type TEXT NOT NULL,

  similarity REAL NOT NULL DEFAULT 0.0,
  uplift REAL,  -- E[y|do(x)] - E[y] (intervention effect)
  confidence REAL DEFAULT 0.5,
  sample_size INTEGER,

  mechanism TEXT,  -- Causal explanation
  evidence_ids TEXT,  -- JSON array
  experiment_ids TEXT  -- A/B test IDs
);
CREATE INDEX idx_causal_edges_uplift ON causal_edges(uplift DESC);
```

**Data flow up the tiers** (SkillLibrary.ts:232):
```typescript
async consolidateEpisodesIntoSkills(config: {
  minAttempts?: number;
  minReward?: number;
  timeWindowDays?: number;
  extractPatterns?: boolean;
}): Promise<{ created: number; updated: number; patterns: [...] }> {
  // 1. Aggregate TIER 1 (episodes) → candidates
  const candidates = this.db.prepare(`
    SELECT
      task,
      COUNT(*) as attempt_count,
      AVG(reward) as avg_reward,
      AVG(success) as success_rate,
      GROUP_CONCAT(id) as episode_ids
    FROM episodes
    WHERE ts > strftime('%s', 'now') - ?
      AND reward >= ?
    GROUP BY task
    HAVING attempt_count >= ?
  `).all(timeWindowDays * 86400, minReward, minAttempts);

  // 2. Extract patterns from TIER 1 episodes
  for (const candidate of candidates) {
    const episodeIds = candidate.episode_ids.split(',').map(Number);
    const patternData = await this.extractPatternsFromEpisodes(episodeIds);

    // 3. Create TIER 2 skill with metadata
    const skill: Skill = {
      name: candidate.task,
      description: `Skill learned from ${episodeIds.length} successful episodes`,
      successRate: candidate.success_rate,
      metadata: {
        sourceEpisodes: episodeIds,
        extractedPatterns: patternData.commonPatterns,  // ML-derived insights
        successIndicators: patternData.successIndicators,
        patternConfidence: this.calculatePatternConfidence(...)
      }
    };
    await this.createSkill(skill);
  }
}
```

**Polymorphic causal edges** (ties all tiers together):
```sql
-- Causal edge can connect ANY memory types
INSERT INTO causal_edges (from_memory_id, from_memory_type, to_memory_id, to_memory_type, uplift)
VALUES
  (123, 'episode', 456, 'episode', 0.25),     -- episode → episode
  (789, 'skill', 123, 'episode', 0.40),       -- skill → episode
  (101, 'skill', 102, 'skill', -0.15);        -- skill → skill
```

### Why It Matters

- **Schema evolution visible**: All changes in SQL migrations (version control)
- **Multi-tier intelligence**: Raw data → consolidated patterns → causal relationships
- **Query optimization**: SQL indexes optimize by tier (fast episode queries, fast skill lookups)
- **Referential integrity**: Foreign keys + triggers enforce invariants
- **Declarative constraints**: `UNIQUE`, `NOT NULL`, `CHECK` in schema (not scattered in code)

### Application to IMEM

**Where:** All storage layers (compile output, manage state, retrieve indexes)

**How:** Define IMEM's multi-tier schema:

```sql
-- TIER 1: Parsed chunks (compile/ output)
CREATE TABLE chunks (
  id INTEGER PRIMARY KEY,
  content TEXT NOT NULL,
  section_type TEXT NOT NULL,  -- Decision | Pattern | Implementation | Context
  section_name TEXT,

  -- Document metadata (inherited)
  file_path TEXT NOT NULL,
  doc_type TEXT NOT NULL,      -- changelog | conversation | adr | spec
  doc_subtype TEXT,             -- implementation | pattern | design
  phase TEXT NOT NULL,          -- design | designate | develop | document
  session_id TEXT,
  timestamp INTEGER NOT NULL,

  -- Searchable
  content_hash TEXT NOT NULL UNIQUE,
  embedding_vector BLOB         -- Optional: for semantic search
);
CREATE INDEX idx_chunks_section_type ON chunks(section_type);
CREATE INDEX idx_chunks_phase ON chunks(phase);
CREATE INDEX idx_chunks_file ON chunks(file_path);

-- TIER 2: Resolved entities (manage/Resolver output)
CREATE TABLE entities (
  id INTEGER PRIMARY KEY,
  canonical_name TEXT NOT NULL UNIQUE,  -- 'jwt'
  entity_type TEXT NOT NULL,            -- 'technology' | 'pattern' | 'decision'

  -- Aliases
  aliases TEXT NOT NULL,                -- JSON: ['JWT', 'jwt-tokens', 'json-web-tokens']

  -- Cross-project
  first_seen_project TEXT,
  occurrences_count INTEGER DEFAULT 0,

  metadata JSON
);

CREATE TABLE chunk_entities (
  chunk_id INTEGER NOT NULL,
  entity_id INTEGER NOT NULL,
  occurrence_count INTEGER DEFAULT 1,
  PRIMARY KEY (chunk_id, entity_id),
  FOREIGN KEY(chunk_id) REFERENCES chunks(id),
  FOREIGN KEY(entity_id) REFERENCES entities(id)
);

-- TIER 3: Authority scores (manage/Temporal + Qualification output)
CREATE TABLE chunk_authority (
  chunk_id INTEGER PRIMARY KEY,

  -- Temporal validation (project-level)
  git_validated BOOLEAN DEFAULT FALSE,
  validation_score REAL DEFAULT 0.5,   -- 0-1
  last_git_check INTEGER,

  -- Cross-project qualification
  reference_count INTEGER DEFAULT 0,
  usage_frequency REAL DEFAULT 0.0,
  recency_score REAL DEFAULT 1.0,

  -- Composite
  authority_score REAL NOT NULL,       -- Weighted composite

  FOREIGN KEY(chunk_id) REFERENCES chunks(id)
);

-- TIER 4: Graph relationships (retrieve/ runtime)
-- Note: Not stored—computed on demand from metadata predicates
-- But we track query patterns for preset library:
CREATE TABLE query_patterns (
  id INTEGER PRIMARY KEY,
  pattern_name TEXT NOT NULL UNIQUE,   -- 'auth-decisions-with-impl'
  query_spec JSON NOT NULL,            -- Orchestrator composition config
  usage_count INTEGER DEFAULT 0,
  avg_latency_ms REAL,
  last_used INTEGER
);
```

**Example:** Three-tier query:
```python
# TIER 1: Fast metadata query (SQLite)
chunks = storage.query("""
  SELECT * FROM chunks
  WHERE section_type = 'Decision'
    AND phase IN ('design', 'designate')
    AND timestamp > ?
""", (cutoff_time,))

# TIER 2: Entity-enriched context
for chunk in chunks:
    chunk.entities = storage.query("""
      SELECT e.canonical_name, e.entity_type
      FROM chunk_entities ce
      JOIN entities e ON ce.entity_id = e.id
      WHERE ce.chunk_id = ?
    """, (chunk.id,))

# TIER 3: Authority-ranked results
ranked = storage.query("""
  SELECT c.*, ca.authority_score
  FROM chunks c
  JOIN chunk_authority ca ON c.id = ca.chunk_id
  WHERE ca.git_validated = TRUE
  ORDER BY ca.authority_score DESC
  LIMIT 10
""")
```

### Trade-offs

**Pros:**
- Single source of truth for data model
- SQL optimizer handles complex queries
- Schema evolution via migrations (traceable)
- Indexes defined co-located with tables
- Multi-tier = progressive enrichment (no data duplication)

**Cons:**
- Schema changes require migrations (not just code)
- SQL can be verbose for complex queries
- Polymorphic types (`from_memory_type`) lose some type safety
- Requires SQL expertise for optimization

**Adoption Recommendation:** **Adopt** — Essential for IMEM's compilation model. Schema defines canonical chunk structure, manage layers add intelligence tiers.

---

## Principle 3: Intelligence Emergence Through Consolidation Pipelines

**Observed in:** `SkillLibrary.ts:consolidateEpisodesIntoSkills` (lines 232-347), `SkillLibrary.ts:extractPatternsFromEpisodes` (lines 352-421), `NightlyLearner.ts`, pattern extraction techniques

### The Principle

**Intelligence emerges from observing patterns across raw data, not from manual rules.** System automatically consolidates raw experiences (episodes) into reusable skills by analyzing frequency, reward trends, keyword patterns, metadata consistency, and learning curves. Uses 5 ML-inspired techniques to extract semantic patterns from unstructured episode data. This is **automated knowledge distillation**—system learns which strategies work without explicit programming.

### How It Works

**5-technique pattern extraction** (SkillLibrary.ts:352-421):

```typescript
private async extractPatternsFromEpisodes(episodeIds: number[]): Promise<{
  commonPatterns: string[];
  successIndicators: string[];
}> {
  const episodes = this.db.prepare(`
    SELECT id, task, input, output, critique, reward, success, metadata
    FROM episodes WHERE id IN (${episodeIds.join(',')}) AND success = 1
  `).all();

  const commonPatterns: string[] = [];
  const successIndicators: string[] = [];

  // TECHNIQUE 1: Keyword frequency analysis (NLP-inspired)
  const outputTexts = episodes.map(ep => ep.output).filter(Boolean);
  if (outputTexts.length > 0) {
    const keywordFrequency = this.extractKeywordFrequency(outputTexts);  // TF-IDF lite
    const topKeywords = this.getTopKeywords(keywordFrequency, 5);
    if (topKeywords.length > 0) {
      commonPatterns.push(`Common techniques: ${topKeywords.join(', ')}`);
    }
  }

  // TECHNIQUE 2: Critique pattern analysis (failure mode learning)
  const critiques = episodes.map(ep => ep.critique).filter(Boolean);
  if (critiques.length > 0) {
    const critiqueKeywords = this.extractKeywordFrequency(critiques);
    const topCritiquePatterns = this.getTopKeywords(critiqueKeywords, 3);
    if (topCritiquePatterns.length > 0) {
      successIndicators.push(...topCritiquePatterns);
    }
  }

  // TECHNIQUE 3: Reward distribution analysis (statistical)
  const avgReward = episodes.reduce((sum, ep) => sum + ep.reward, 0) / episodes.length;
  const highRewardCount = episodes.filter(ep => ep.reward > avgReward).length;
  const highRewardRatio = highRewardCount / episodes.length;
  if (highRewardRatio > 0.6) {
    successIndicators.push(`High consistency (${(highRewardRatio * 100).toFixed(0)}% above average)`);
  }

  // TECHNIQUE 4: Metadata pattern extraction (configuration learning)
  const metadataPatterns = this.extractMetadataPatterns(episodes);
  // Finds fields with consistent values across all episodes
  // Example: If all episodes used { "temperature": 0.7 }, record that
  if (metadataPatterns.length > 0) {
    commonPatterns.push(...metadataPatterns);
  }

  // TECHNIQUE 5: Learning curve analysis (temporal trends)
  const learningTrend = this.analyzeLearningTrend(episodes);
  // Compares first-half vs second-half reward (improvement detection)
  if (learningTrend) {
    successIndicators.push(learningTrend);  // "Strong learning curve (+25% improvement)"
  }

  return { commonPatterns, successIndicators };
}
```

**Consolidation trigger** (automatic or manual):
```typescript
// Automatic: NightlyLearner runs consolidation every N hours
export class NightlyLearner {
  async runLearningCycle() {
    // 1. Discover causal patterns in episodes
    await this.discoverCausalPatterns();

    // 2. Consolidate high-reward episodes into skills
    const result = await this.skillLibrary.consolidateEpisodesIntoSkills({
      minAttempts: 3,
      minReward: 0.7,
      timeWindowDays: 7,
      extractPatterns: true
    });

    // 3. Prune low-quality skills
    await this.skillLibrary.pruneSkills({ minSuccessRate: 0.4 });
  }
}

// Manual: CLI command
// $ agentdb skill consolidate --min-attempts 3 --min-reward 0.7 --extract-patterns
```

**Pattern confidence scoring**:
```typescript
private calculatePatternConfidence(sampleSize: number, successRate: number): number {
  const sampleFactor = Math.min(sampleSize / 10, 1.0);  // Saturates at 10 samples
  const successFactor = successRate;
  return Math.min(sampleFactor * successFactor, 0.99);  // Composite confidence
}
```

**Skill metadata carries learned insights**:
```typescript
const skill: Skill = {
  name: "debug-authentication-flow",
  description: "Skill learned from 8 successful episodes",
  signature: { inputs: { task: 'string' }, outputs: { result: 'any' } },
  successRate: 0.87,
  uses: 8,
  avgReward: 0.82,
  metadata: {
    sourceEpisodes: [101, 102, 105, 107, ...],  // Lineage
    autoGenerated: true,
    extractedPatterns: [
      "Common techniques: jwt, token, middleware, verify, decode",
      "Consistent auth_type: bearer"
    ],
    successIndicators: [
      "validation", "expiry", "signature",
      "High consistency (75% above average)",
      "Strong learning curve (+28% improvement)"
    ],
    patternConfidence: 0.79  // 8 samples * 0.87 success rate
  }
};
```

### Why It Matters

- **Zero manual curation**: System learns from observation, not programming
- **Continuous improvement**: New episodes → better skills (adaptive)
- **Semantic understanding**: Keywords + critiques + metadata = strategy extraction
- **Confidence tracking**: Pattern confidence based on sample size + success rate
- **Lineage preserved**: Skills link back to source episodes (explainability)

### Application to IMEM

**Where:** manage/Observer, manage/Resolver, retrieve/Orchestrator (preset library)

**How:** Apply consolidation to discover canonical types and query patterns:

**1. Schema evolution (compile/Resolver)**:
```python
class SchemaResolver:
    def __init__(self, storage: ChunkStore):
        self.storage = storage

    async def discover_canonical_types(self, project: str) -> Dict[str, List[str]]:
        """Observe section headers across corpus, consolidate into canonical types."""
        # Find all unique section headers
        headers = self.storage.query("""
            SELECT DISTINCT section_name, COUNT(*) as frequency
            FROM chunks
            WHERE project = ?
            GROUP BY section_name
            ORDER BY frequency DESC
        """, (project,))

        # Extract patterns using keyword clustering
        clusters = self.cluster_by_keywords(headers)
        # clusters = {
        #   'decision': ['Decision', 'Choice', 'We Decided', 'Verdict'],
        #   'pattern': ['Pattern', 'Approach', 'Strategy', 'Technique'],
        #   ...
        # }

        # Store mappings
        for canonical, variants in clusters.items():
            self.storage.execute("""
                INSERT INTO type_mappings (canonical_type, variants)
                VALUES (?, ?)
            """, (canonical, json.dumps(variants)))

        return clusters
```

**2. Entity resolution (manage/Resolver)**:
```python
class EntityResolver:
    async def consolidate_entities(self, min_occurrences: int = 3) -> List[Entity]:
        """Find entity aliases and consolidate into canonical names."""
        # Extract potential entities from chunk content
        entities = self.extract_entity_candidates()  # NER-lite

        # Group by semantic similarity
        clusters = self.cluster_by_similarity(entities, threshold=0.85)
        # clusters = [
        #   ['jwt', 'JWT', 'json-web-tokens', 'jwt-tokens'],
        #   ['redis', 'Redis', 'redis-cache'],
        #   ...
        # ]

        # Create canonical entities
        consolidated = []
        for cluster in clusters:
            if len(cluster) >= min_occurrences:
                canonical = self.select_canonical_name(cluster)  # Most frequent
                entity = Entity(
                    canonical_name=canonical,
                    aliases=cluster,
                    occurrences=sum(self.count_occurrences(variant) for variant in cluster)
                )
                consolidated.append(entity)

        return consolidated
```

**3. Query preset discovery (retrieve/Orchestrator)**:
```python
class PresetLibrary:
    async def consolidate_query_patterns(self, min_uses: int = 5) -> List[Preset]:
        """Observe frequent query patterns, create reusable presets."""
        # Analyze query logs
        patterns = self.storage.query("""
            SELECT query_spec, COUNT(*) as frequency
            FROM query_log
            WHERE timestamp > ?
            GROUP BY query_spec
            HAVING frequency >= ?
            ORDER BY frequency DESC
        """, (cutoff, min_uses))

        presets = []
        for pattern in patterns:
            spec = json.loads(pattern['query_spec'])

            # Extract common config patterns
            common_filters = self.extract_common_filters(spec)
            common_discovery = self.extract_common_discovery(spec)

            preset = Preset(
                name=self.generate_preset_name(spec),  # "auth-decisions-with-siblings"
                spec=spec,
                usage_frequency=pattern['frequency'],
                common_filters=common_filters,
                metadata={'auto_generated': True}
            )
            presets.append(preset)

        return presets
```

**Example output** (discovered preset):
```json
{
  "name": "auth-implementation-lineage",
  "description": "Auto-discovered: Traces authentication decisions through implementation",
  "spec": {
    "search": {
      "text": "auth OR authentication OR jwt",
      "filters": {"section_type": "Decision", "phase": "design"}
    },
    "discovery": {
      "cross_phase": {"target_phases": ["develop"], "limit": 5},
      "siblings": {"section_types": ["Implementation"], "limit": 3}
    },
    "graph": {"algorithm": "authority", "top": 10}
  },
  "usage_frequency": 23,
  "success_rate": 0.91,
  "avg_latency_ms": 45
}
```

### Trade-offs

**Pros:**
- System learns from usage patterns (adaptive)
- No manual curation required (scales)
- Confidence scores guide trustworthiness
- Lineage preserved (explainable)

**Cons:**
- Requires sufficient data (cold start problem)
- Statistical patterns may miss semantic nuance
- Consolidation can be expensive (background job)
- Pattern quality depends on input quality

**Adoption Recommendation:** **Adopt** — Critical for IMEM's "schema evolution" and "observable usage → preset library" goals. Enables universal onboarding without manual configuration.

---

## Principle 4: Layered Caching Strategy for Performance

**Observed in:** `EmbeddingService.ts:cache`, `QueryOptimizer.ts`, `HNSWIndex.ts`, `BatchOperations.ts`

### The Principle

**Performance through progressive caching layers**—embedding cache (in-memory LRU), query result cache (TTL-based), HNSW index (persistent), and batch operations (transaction-level). Each layer optimizes different access patterns: hot embeddings (repeated text), hot queries (repeated searches), ANN search (vector similarity), and bulk writes (insertion). Caches are **transparent** (controllers don't know they exist) and **composable** (can disable individually).

### How It Works

**Layer 1: Embedding cache** (EmbeddingService.ts:18-88):
```typescript
export class EmbeddingService {
  private cache: Map<string, Float32Array>;  // In-memory LRU

  async embed(text: string): Promise<Float32Array> {
    // Check cache
    const cacheKey = `${this.config.model}:${text}`;
    if (this.cache.has(cacheKey)) {
      return this.cache.get(cacheKey)!;  // O(1) cache hit
    }

    // Generate embedding (expensive)
    let embedding: Float32Array;
    if (this.config.provider === 'transformers' && this.pipeline) {
      const output = await this.pipeline(text, { pooling: 'mean', normalize: true });
      embedding = new Float32Array(output.data);
    } else {
      embedding = this.mockEmbedding(text);  // Fallback
    }

    // Cache with LRU eviction
    if (this.cache.size > 10000) {
      const keysToDelete = Array.from(this.cache.keys()).slice(0, 5000);  // Evict 50%
      keysToDelete.forEach(k => this.cache.delete(k));
    }
    this.cache.set(cacheKey, embedding);

    return embedding;
  }

  clearCache(): void {
    this.cache.clear();  // Manual cache invalidation
  }
}
```

**Layer 2: Query result cache** (QueryOptimizer.ts):
```typescript
export class QueryOptimizer {
  private cache: Map<string, { result: any; expiresAt: number; hitCount: number }>;
  private config: { maxSize: number; ttl: number; enabled: boolean };

  async executeQuery(sql: string, params: any[]): Promise<any> {
    if (!this.config.enabled) {
      return this.db.prepare(sql).all(...params);  // Bypass cache
    }

    // Generate cache key
    const cacheKey = this.hashQuery(sql, params);
    const cached = this.cache.get(cacheKey);

    // Check TTL
    if (cached && Date.now() < cached.expiresAt) {
      cached.hitCount++;
      this.stats.cacheHits++;
      return cached.result;  // Cache hit
    }

    // Execute query (cache miss)
    const result = this.db.prepare(sql).all(...params);

    // Store with TTL
    this.cache.set(cacheKey, {
      result,
      expiresAt: Date.now() + this.config.ttl,  // Default 60s
      hitCount: 1
    });

    // Evict if max size exceeded
    if (this.cache.size > this.config.maxSize) {
      this.evictLRU();
    }

    this.stats.cacheMisses++;
    return result;
  }

  getStats() {
    return {
      cacheHits: this.stats.cacheHits,
      cacheMisses: this.stats.cacheMisses,
      hitRate: this.stats.cacheHits / (this.stats.cacheHits + this.stats.cacheMisses)
    };
  }
}
```

**Layer 3: HNSW index cache** (HNSWIndex.ts):
```typescript
export class HNSWIndex {
  private index: any;  // hnswlib-node index (persistent)

  async buildIndex(vectors: Float32Array[]): Promise<void> {
    // Check if index exists on disk
    if (fs.existsSync(this.indexPath)) {
      this.index.readIndex(this.indexPath);  // Load from disk
      console.log('✅ HNSW index loaded from disk');
      return;
    }

    // Build index (expensive)
    for (let i = 0; i < vectors.length; i++) {
      this.index.addPoint(vectors[i], i);
    }

    // Persist to disk
    this.index.writeIndex(this.indexPath);
    console.log('✅ HNSW index built and persisted');
  }

  async search(query: Float32Array, k: number): Promise<Array<{ id: number; distance: number }>> {
    // Search uses in-memory index (10-100x faster than brute force)
    const result = this.index.searchKnn(query, k);
    return result.neighbors.map((id, i) => ({
      id,
      distance: result.distances[i]
    }));
  }
}
```

**Layer 4: Batch operations** (BatchOperations.ts):
```typescript
export class BatchOperations {
  async insertBatch(items: any[], onProgress?: (progress) => void): Promise<number> {
    const batchSize = this.config.batchSize || 100;
    let totalInserted = 0;

    // Transaction wrapper (all-or-nothing)
    const transaction = this.db.transaction(() => {
      for (let i = 0; i < items.length; i += batchSize) {
        const batch = items.slice(i, i + batchSize);

        // Parallel embedding generation (if needed)
        const embeddings = await Promise.all(
          batch.map(item => this.embedder.embed(item.text))
        );

        // Batch insert (single SQL statement)
        const stmt = this.db.prepare(`
          INSERT INTO episodes (task, reward, embedding)
          VALUES ${batch.map(() => '(?, ?, ?)').join(', ')}
        `);

        const params = batch.flatMap((item, idx) => [
          item.task,
          item.reward,
          this.serializeEmbedding(embeddings[idx])
        ]);

        stmt.run(...params);
        totalInserted += batch.length;

        onProgress?.({ itemsInserted: totalInserted, total: items.length });
      }
    });

    transaction();  // Execute in single transaction (ACID)
    return totalInserted;
  }
}
```

**Performance comparison**:
```typescript
// WITHOUT batch operations (141x slower)
for (const item of items) {
  const embedding = await embedder.embed(item.text);  // N network calls
  db.prepare('INSERT INTO episodes ...').run(...);    // N transactions
}

// WITH batch operations (141x faster)
await batchOps.insertBatch(items);  // 1 transaction, parallel embeddings
```

### Why It Matters

- **Embedding cache**: Repeated text (e.g., task names) → instant retrieval
- **Query cache**: Repeated searches (e.g., dashboard queries) → 60s TTL
- **HNSW index**: 10-100x faster vector search (sub-millisecond for 100k vectors)
- **Batch operations**: 141x faster bulk inserts (single transaction)
- **Transparent**: Controllers don't know about caching (separation of concerns)

### Application to IMEM

**Where:** All layers—compile/ (parsing), manage/ (entity resolution), retrieve/ (queries)

**How:** Implement tiered caching:

**Layer 1: Template parse cache** (compile/Parser):
```python
class Parser:
    def __init__(self, storage: ChunkStore, templates: TemplateRegistry):
        self.storage = storage
        self.templates = templates
        self.parse_cache = {}  # file_hash -> List[Chunk]

    def parse(self, file_path: Path) -> List[Chunk]:
        # Check if file changed
        file_hash = self.hash_file(file_path)
        if file_hash in self.parse_cache:
            return self.parse_cache[file_hash]  # Cache hit

        # Parse (expensive)
        template = self.templates.select(file_path)
        chunks = template.extract(file_path)

        # Cache result
        self.parse_cache[file_hash] = chunks
        return chunks
```

**Layer 2: Entity resolution cache** (manage/Resolver):
```python
class EntityResolver:
    def __init__(self, storage: ChunkStore):
        self.storage = storage
        self.entity_cache = {}  # text -> canonical_name
        self.cache_ttl = 3600  # 1 hour

    def resolve(self, text: str) -> str:
        # Check cache with TTL
        if text in self.entity_cache:
            cached = self.entity_cache[text]
            if time.time() < cached['expires_at']:
                return cached['canonical']  # Cache hit

        # Query database (cache miss)
        canonical = self.storage.query("""
            SELECT canonical_name FROM entities
            WHERE ? IN (SELECT value FROM json_each(aliases))
        """, (text,))

        # Cache result
        self.entity_cache[text] = {
            'canonical': canonical,
            'expires_at': time.time() + self.cache_ttl
        }
        return canonical
```

**Layer 3: Vector index** (retrieve/Orchestrator with Qdrant):
```python
class QdrantStore:
    def __init__(self, url: str, collection: str):
        self.client = QdrantClient(url)
        self.collection = collection
        # Qdrant handles indexing internally (HNSW)

    def search(self, query_vector: np.ndarray, limit: int = 10) -> List[Chunk]:
        # Qdrant's HNSW index is persistent and pre-built
        results = self.client.search(
            collection_name=self.collection,
            query_vector=query_vector.tolist(),
            limit=limit
        )
        return [self.chunk_from_point(r) for r in results]
```

**Layer 4: Batch compilation** (compile/Parser):
```python
class BatchParser:
    async def parse_project(self, repo_path: Path, parallelism: int = 4) -> List[Chunk]:
        files = list(repo_path.rglob('*.md'))

        # Parallel parsing
        chunks = await asyncio.gather(
            *[self.parser.parse(f) for f in files],
            return_exceptions=True
        )

        # Batch insert (single transaction)
        all_chunks = [c for batch in chunks if not isinstance(batch, Exception) for c in batch]
        self.storage.batch_insert(all_chunks)  # One transaction

        return all_chunks
```

**Performance monitoring**:
```python
@dataclass
class CacheStats:
    embedding_hits: int = 0
    embedding_misses: int = 0
    query_hits: int = 0
    query_misses: int = 0

    @property
    def embedding_hit_rate(self) -> float:
        total = self.embedding_hits + self.embedding_misses
        return self.embedding_hits / total if total > 0 else 0.0

    @property
    def query_hit_rate(self) -> float:
        total = self.query_hits + self.query_misses
        return self.query_hits / total if total > 0 else 0.0
```

### Trade-offs

**Pros:**
- Massive performance gains (10-100x for hot paths)
- Transparent to business logic (separation of concerns)
- Configurable (can disable per layer)
- Observable (cache stats for monitoring)

**Cons:**
- Memory overhead (cache size limits)
- Cache invalidation complexity (when to evict?)
- Stale data risk (TTL vs consistency trade-off)
- Debugging harder (cached vs fresh results)

**Adoption Recommendation:** **Adopt with discipline** — Essential for IMEM's performance. Use embedding cache for semantic search, query cache for dashboard/CLI, batch operations for compilation. Monitor cache hit rates and tune TTLs.

---

## Principle 5: Distributed Coordination Through Sync Abstraction

**Observed in:** `SyncCoordinator.ts`, `QUICClient.ts`, `QUICServer.ts`, conflict resolution strategies, state persistence

### The Principle

**Multi-agent coordination via bidirectional sync with conflict resolution.** SyncCoordinator orchestrates change detection, push/pull operations, conflict resolution (4 strategies), and state persistence. Uses **QUIC protocol** for low-latency sync. Key insight: sync state is **first-class data** (stored in database, versioned, observable). This enables agent swarms to share memory without central authority.

### How It Works

**Sync phases** (SyncCoordinator.ts:98-202):
```typescript
async sync(onProgress?: (progress: SyncProgress) => void): Promise<SyncReport> {
  // Phase 1: Detect changes since last sync
  onProgress?.({ phase: 'detecting', current: 0, total: 100 });
  const changes = await this.detectChanges();  // Query: ts > lastSyncAt

  // Phase 2: Push local changes to remote
  if (changes.episodes.length > 0 || changes.skills.length > 0) {
    onProgress?.({ phase: 'pushing', current: 0, total: changes.length });
    const pushResult = await this.pushChanges(changes, onProgress);
    itemsPushed = pushResult.itemsPushed;
  }

  // Phase 3: Pull remote changes
  onProgress?.({ phase: 'pulling', current: 0, total: 100 });
  const pullResult = await this.pullChanges(onProgress);
  itemsPulled = pullResult.itemsPulled;

  // Phase 4: Resolve conflicts
  if (pullResult.conflicts && pullResult.conflicts.length > 0) {
    onProgress?.({ phase: 'resolving', current: 0, total: pullResult.conflicts.length });
    conflictsResolved = await this.resolveConflicts(pullResult.conflicts);
  }

  // Phase 5: Apply changes to local DB
  onProgress?.({ phase: 'applying', current: 0, total: itemsPulled });
  await this.applyChanges(pullResult.data);

  // Phase 6: Update sync state
  this.syncState.lastSyncAt = Date.now();
  this.syncState.totalItemsSynced += itemsPushed + itemsPulled;
  this.saveSyncState();  // Persist to database

  return { success, itemsPushed, itemsPulled, conflictsResolved, ... };
}
```

**Change detection** (incremental sync):
```typescript
private async detectChanges(): Promise<{ episodes: any[]; skills: any[]; edges: any[] }> {
  const { lastEpisodeSync, lastSkillSync, lastEdgeSync } = this.syncState;

  // Incremental queries (only new/modified items)
  const episodes = this.db.prepare('SELECT * FROM episodes WHERE ts > ?').all(lastEpisodeSync);
  const skills = this.db.prepare('SELECT * FROM skills WHERE ts > ?').all(lastSkillSync);
  const edges = this.db.prepare('SELECT * FROM causal_edges WHERE ts > ?').all(lastEdgeSync);

  return { episodes, skills, edges };
}
```

**Conflict resolution** (4 strategies):
```typescript
private async resolveConflicts(conflicts: any[]): Promise<number> {
  let resolved = 0;

  for (const conflict of conflicts) {
    switch (this.config.conflictStrategy) {
      case 'local-wins':
        // Keep local version (default for offline-first)
        break;

      case 'remote-wins':
        // Keep remote version (default for server-authoritative)
        this.applyChanges([conflict.remote]);
        resolved++;
        break;

      case 'latest-wins':
        // Keep version with latest timestamp (last-write-wins)
        if (conflict.remote.ts > conflict.local.ts) {
          this.applyChanges([conflict.remote]);
          resolved++;
        }
        break;

      case 'merge':
        // Attempt to merge fields (simplified CRDTs)
        const merged = this.mergeConflict(conflict.local, conflict.remote);
        this.applyChanges([merged]);
        resolved++;
        break;
    }
  }

  return resolved;
}
```

**Sync state persistence** (database table):
```sql
CREATE TABLE sync_state (
  id INTEGER PRIMARY KEY,
  last_sync_at INTEGER,
  last_episode_sync INTEGER,
  last_skill_sync INTEGER,
  last_edge_sync INTEGER,
  total_items_synced INTEGER,
  total_bytes_synced INTEGER,
  sync_count INTEGER,
  last_error TEXT
);
```

**Auto-sync** (background process):
```typescript
private startAutoSync(): void {
  this.autoSyncInterval = setInterval(async () => {
    try {
      await this.sync();
    } catch (error) {
      console.error('Auto-sync failed:', error.message);
    }
  }, this.config.syncIntervalMs);  // Default 60s
}
```

### Why It Matters

- **Agent swarms**: Multiple agents share memory without central server
- **Offline-first**: Agents work offline, sync when connected
- **Conflict resolution**: Deterministic conflict handling (no manual intervention)
- **Observable**: Sync state persisted (audit trail, debugging)
- **Incremental**: Only sync changes since last sync (efficient)

### Application to IMEM

**Where:** Cross-project collaboration (manage/Registry, manage/Qualification)

**How:** Sync pattern libraries and qualification metadata across projects:

**Pattern library sync**:
```python
class PatternSync:
    def __init__(self, local_db: ChunkStore, remote_url: str):
        self.local = local_db
        self.remote = QdrantClient(remote_url)  # Pattern collection
        self.sync_state = self.load_sync_state()

    async def sync_patterns(self) -> SyncReport:
        # Phase 1: Detect local pattern changes
        local_patterns = self.local.query("""
            SELECT * FROM chunks
            WHERE collection = 'pattern'
              AND timestamp > ?
        """, (self.sync_state.last_pattern_sync,))

        # Phase 2: Push to remote Qdrant
        if local_patterns:
            points = [self.chunk_to_point(p) for p in local_patterns]
            self.remote.upsert(collection_name='patterns', points=points)

        # Phase 3: Pull remote patterns
        remote_patterns = self.remote.scroll(
            collection_name='patterns',
            scroll_filter=models.Filter(
                must=[models.FieldCondition(
                    key='timestamp',
                    range=models.Range(gt=self.sync_state.last_pattern_sync)
                )]
            )
        )

        # Phase 4: Apply to local DB
        for pattern in remote_patterns:
            self.local.insert_chunk(self.point_to_chunk(pattern))

        # Phase 5: Update sync state
        self.sync_state.last_pattern_sync = time.time()
        self.save_sync_state()

        return SyncReport(
            patterns_pushed=len(local_patterns),
            patterns_pulled=len(remote_patterns)
        )
```

**Qualification metadata sync** (authority scores):
```python
class QualificationSync:
    async def sync_authority_scores(self, conflict_strategy: str = 'max-wins'):
        # Detect local changes
        local_scores = self.local.query("""
            SELECT chunk_id, authority_score, last_updated
            FROM chunk_authority
            WHERE last_updated > ?
        """, (self.sync_state.last_qual_sync,))

        # Pull remote scores
        remote_scores = await self.remote.fetch_authority_scores(
            since=self.sync_state.last_qual_sync
        )

        # Resolve conflicts
        conflicts = self.detect_conflicts(local_scores, remote_scores)
        for conflict in conflicts:
            if conflict_strategy == 'max-wins':
                # Keep higher authority score
                winner = max(conflict.local, conflict.remote, key=lambda x: x.authority_score)
                self.local.update_authority(conflict.chunk_id, winner)
            elif conflict_strategy == 'latest-wins':
                # Keep most recently updated
                winner = max(conflict.local, conflict.remote, key=lambda x: x.last_updated)
                self.local.update_authority(conflict.chunk_id, winner)

        # Merge and persist
        self.sync_state.last_qual_sync = time.time()
        self.save_sync_state()
```

**Sync CLI**:
```bash
# Manual sync
imem sync patterns --remote http://patterns.imem.io

# Auto-sync (background)
imem sync patterns --auto --interval 300  # Every 5 minutes

# Sync status
imem sync status
# Output:
# Last sync: 2025-01-14 10:23:45
# Patterns pushed: 23
# Patterns pulled: 45
# Conflicts resolved: 3 (max-wins)
# Next auto-sync: 10:28:45
```

### Trade-offs

**Pros:**
- Enables multi-agent collaboration (distributed)
- Offline-first (no network dependency)
- Deterministic conflict resolution (no manual intervention)
- Observable sync state (debugging, audit trail)

**Cons:**
- Complexity (sync logic, conflict resolution)
- Network overhead (incremental sync still needs bandwidth)
- Conflict strategies are simplistic (real CRDTs harder)
- Requires sync protocol agreement (QUIC, HTTP, etc.)

**Adoption Recommendation:** **Consider** — Useful for IMEM's cross-project pattern library, but not critical for MVP. Implement if multiple teams share pattern collections. Start with manual sync, add auto-sync later.

---

## Principle 6: Security Through Input Validation and Least Privilege

**Observed in:** `security/input-validation.ts`, `db-fallback.ts:pragma` (lines 170-185), SQL injection prevention, PRAGMA whitelisting

### The Principle

**Defense-in-depth through strict input validation at boundaries.** All external inputs (table names, column names, PRAGMA commands) validated against **whitelists**. All SQL queries use **parameterized statements** (no string interpolation). Schema enforces **constraints** (NOT NULL, UNIQUE, CHECK). This prevents SQL injection, arbitrary code execution, and data corruption.

### How It Works

**Input validation module** (`security/input-validation.ts`):
```typescript
// Table name whitelist
const SAFE_TABLES = new Set([
  'episodes', 'episode_embeddings', 'skills', 'skill_embeddings',
  'causal_edges', 'causal_experiments', 'facts', 'notes', ...
]);

export function validateTableName(tableName: string): string {
  if (!SAFE_TABLES.has(tableName)) {
    throw new ValidationError(`Invalid table name: ${tableName}`);
  }
  return tableName;
}

// PRAGMA command whitelist (prevent SQL injection via PRAGMA)
const SAFE_PRAGMAS = new Set([
  'journal_mode', 'synchronous', 'foreign_keys', 'cache_size',
  'temp_store', 'mmap_size', 'page_size', 'auto_vacuum'
]);

export function validatePragmaCommand(pragma: string): string {
  const [command] = pragma.split('=').map(s => s.trim().toLowerCase());
  if (!SAFE_PRAGMAS.has(command)) {
    throw new ValidationError(`Unsafe PRAGMA command: ${pragma}`);
  }
  return pragma;
}

// Safe WHERE clause builder (parameterized)
export function buildSafeWhereClause(
  filters: Record<string, any>
): { clause: string; params: any[] } {
  const conditions: string[] = [];
  const params: any[] = [];

  for (const [column, value] of Object.entries(filters)) {
    validateColumnName(column);  // Whitelist check
    conditions.push(`${column} = ?`);
    params.push(value);
  }

  return {
    clause: conditions.length > 0 ? `WHERE ${conditions.join(' AND ')}` : '',
    params
  };
}
```

**Usage in database wrapper** (`db-fallback.ts:170-185`):
```typescript
pragma(pragma: string, options?: any) {
  try {
    // SECURITY: Validate PRAGMA command against whitelist
    const validatedPragma = validatePragmaCommand(pragma);

    // Execute validated PRAGMA
    const result = this.db.exec(`PRAGMA ${validatedPragma}`);
    return result[0]?.values[0]?.[0];
  } catch (error) {
    if (error instanceof ValidationError) {
      console.error(`❌ Invalid PRAGMA command: ${error.message}`);
      throw error;
    }
    throw error;
  }
}
```

**Parameterized queries** (everywhere):
```typescript
// ❌ BAD: String interpolation (SQL injection risk)
const task = userInput;  // Could be: "'; DROP TABLE episodes; --"
const stmt = this.db.prepare(`SELECT * FROM episodes WHERE task = '${task}'`);

// ✅ GOOD: Parameterized query
const stmt = this.db.prepare('SELECT * FROM episodes WHERE task = ?');
const results = stmt.all(userInput);  // SQL injection impossible
```

**Schema constraints**:
```sql
-- Enforce data integrity at schema level
CREATE TABLE episodes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,           -- Prevent NULL
  task TEXT NOT NULL,
  reward REAL NOT NULL,
  success BOOLEAN NOT NULL,
  CHECK(reward >= 0 AND reward <= 1), -- Range validation
  CHECK(success IN (0, 1))            -- Boolean validation
);

-- Trigger-based validation
CREATE TRIGGER validate_causal_confidence
BEFORE INSERT ON causal_edges
BEGIN
  SELECT CASE
    WHEN NEW.confidence < 0 OR NEW.confidence > 1 THEN
      RAISE(ABORT, 'Confidence must be between 0 and 1')
  END;
END;
```

### Why It Matters

- **SQL injection prevention**: Parameterized queries + whitelist validation
- **Arbitrary code execution**: PRAGMA whitelist prevents malicious commands
- **Data corruption**: Schema constraints enforce invariants
- **Least privilege**: Controllers only access validated tables/columns
- **Auditability**: ValidationError exceptions log suspicious inputs

### Application to IMEM

**Where:** All storage boundaries (compile/Parser, manage/Resolver, retrieve/Orchestrator)

**How:** Implement validation at IMEM's boundaries:

**Input validation module** (`storage/validation.py`):
```python
from enum import Enum
from typing import Set, Dict, Any

class ValidationError(Exception):
    pass

# Whitelist safe tables
SAFE_TABLES: Set[str] = {
    'chunks', 'entities', 'chunk_entities', 'chunk_authority',
    'query_patterns', 'type_mappings', 'sync_state'
}

# Whitelist safe columns (by table)
SAFE_COLUMNS: Dict[str, Set[str]] = {
    'chunks': {
        'id', 'content', 'section_type', 'section_name', 'file_path',
        'doc_type', 'doc_subtype', 'phase', 'session_id', 'timestamp',
        'content_hash', 'embedding_vector'
    },
    'chunk_authority': {
        'chunk_id', 'git_validated', 'validation_score', 'reference_count',
        'usage_frequency', 'recency_score', 'authority_score'
    }
}

def validate_table_name(table: str) -> str:
    if table not in SAFE_TABLES:
        raise ValidationError(f"Invalid table name: {table}")
    return table

def validate_column_name(table: str, column: str) -> str:
    if table not in SAFE_COLUMNS or column not in SAFE_COLUMNS[table]:
        raise ValidationError(f"Invalid column: {table}.{column}")
    return column

def build_safe_filter(table: str, filters: Dict[str, Any]) -> tuple[str, list]:
    """Build parameterized WHERE clause with validation."""
    validate_table_name(table)

    conditions = []
    params = []
    for column, value in filters.items():
        validate_column_name(table, column)
        conditions.append(f"{column} = ?")
        params.append(value)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    return where_clause, params
```

**Usage in storage adapter** (`storage/sqlite.py`):
```python
from .validation import validate_table_name, build_safe_filter, ValidationError

class SQLiteStore:
    def query(self, table: str, filters: Dict[str, Any] = None) -> List[Chunk]:
        # Validate inputs
        validate_table_name(table)

        if filters:
            where_clause, params = build_safe_filter(table, filters)
            sql = f"SELECT * FROM {table} {where_clause}"
            cursor = self.conn.execute(sql, params)  # Parameterized
        else:
            sql = f"SELECT * FROM {table}"
            cursor = self.conn.execute(sql)

        return [self.row_to_chunk(row) for row in cursor.fetchall()]

    def update_authority(self, chunk_id: int, score: float):
        # Validate range
        if not (0 <= score <= 1):
            raise ValidationError(f"Authority score must be 0-1, got {score}")

        # Parameterized update
        self.conn.execute(
            "UPDATE chunk_authority SET authority_score = ? WHERE chunk_id = ?",
            (score, chunk_id)
        )
```

**Schema constraints** (`storage/schema.sql`):
```sql
-- Enforce data integrity
CREATE TABLE chunks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  content TEXT NOT NULL,                  -- Prevent empty chunks
  section_type TEXT NOT NULL,
  file_path TEXT NOT NULL,
  doc_type TEXT NOT NULL,
  phase TEXT NOT NULL CHECK(phase IN ('design', 'designate', 'develop', 'document')),
  timestamp INTEGER NOT NULL,
  content_hash TEXT NOT NULL UNIQUE,      -- Prevent duplicates
  CHECK(length(content) > 0)              -- Non-empty content
);

CREATE TABLE chunk_authority (
  chunk_id INTEGER PRIMARY KEY,
  authority_score REAL NOT NULL CHECK(authority_score >= 0 AND authority_score <= 1),
  validation_score REAL CHECK(validation_score >= 0 AND validation_score <= 1),
  reference_count INTEGER DEFAULT 0 CHECK(reference_count >= 0),
  FOREIGN KEY(chunk_id) REFERENCES chunks(id) ON DELETE CASCADE
);

-- Trigger: Update timestamp on modification
CREATE TRIGGER update_chunk_timestamp
AFTER UPDATE ON chunks
BEGIN
  UPDATE chunks SET timestamp = strftime('%s', 'now') WHERE id = NEW.id;
END;
```

### Trade-offs

**Pros:**
- Prevents SQL injection (critical security)
- Schema enforces invariants (data integrity)
- Whitelists are explicit (clear boundaries)
- Validation errors are auditable

**Cons:**
- Whitelists require maintenance (add new tables/columns)
- Parameterized queries more verbose than interpolation
- Triggers add complexity (implicit behavior)
- Validation overhead (performance cost)

**Adoption Recommendation:** **Adopt** — Non-negotiable for production systems. IMEM handles user-provided queries (CLI, API) and git data (untrusted sources).

---

## Synthesis: Implications for IMEM

### Recommended Structural Changes

1. **Adopt controller-as-service pattern** for all layers (compile/, manage/, retrieve/)
   - Controllers receive `storage: ChunkStore` via dependency injection
   - Storage adapters implement unified interface (`SQLiteStore`, `QdrantStore`)
   - Enables storage swapping without code changes

2. **Define multi-tier SQL schema** as source of truth
   - Tier 1: Raw chunks (compile output)
   - Tier 2: Entities + resolved types (manage output)
   - Tier 3: Authority scores (manage/Qualification output)
   - Tier 4: Query patterns (retrieve/Orchestrator presets)

3. **Implement consolidation pipelines** for intelligence emergence
   - Schema evolution: Observe headers → canonical types
   - Entity resolution: Cluster aliases → canonical names
   - Preset discovery: Analyze query logs → reusable presets

4. **Add layered caching** for performance
   - Embedding cache (in-memory, LRU)
   - Query result cache (TTL-based)
   - Vector index (Qdrant's HNSW)
   - Batch compilation (transaction-level)

5. **Implement input validation** at all boundaries
   - Whitelist table/column names
   - Parameterized queries only
   - Schema constraints (NOT NULL, CHECK, UNIQUE)

6. **(Optional) Add pattern library sync** for cross-project collaboration
   - Sync coordinator for pattern collections
   - Conflict resolution (max-wins for authority scores)
   - Observable sync state

### Directory Structure Implications

```
imem/
├── compile/
│   ├── parser.py                    # Controller with injected storage
│   ├── template_registry.py         # Template plugin system
│   ├── templates/
│   │   ├── changelog.py
│   │   ├── conversation.py
│   │   └── adr.py
│   └── schema_resolver.py           # Consolidation: headers → canonical types
│
├── manage/
│   ├── temporal.py                  # Controller with injected storage + git
│   ├── entity_resolver.py           # Consolidation: aliases → entities
│   ├── registry.py                  # Cross-project tier 1 (objective facts)
│   ├── qualification.py             # Cross-project tier 2 (authority scoring)
│   └── git_oracle.py                # Git interface (injected dependency)
│
├── retrieve/
│   ├── orchestrator.py              # Controller with injected storage
│   ├── primitives.py                # Discovery operations (siblings, genealogy, ...)
│   ├── graph.py                     # Runtime graph composition (NetworkX)
│   ├── ranking.py                   # Authority, recency scoring
│   └── preset_library.py            # Consolidation: query logs → presets
│
├── structure/
│   ├── templates/                   # Jinja2 presentation templates
│   ├── contextualize.py             # Add graph metadata to chunks
│   └── render.py                    # Format output
│
├── storage/
│   ├── interface.py                 # ChunkStore abstract interface
│   ├── sqlite.py                    # SQLite implementation
│   ├── qdrant.py                    # Qdrant implementation
│   ├── validation.py                # Input validation (whitelists)
│   └── schema.sql                   # Multi-tier schema (source of truth)
│
├── optimization/
│   ├── embedding_cache.py           # In-memory LRU cache
│   ├── query_cache.py               # TTL-based result cache
│   └── batch_operations.py          # Transaction-level batching
│
└── sync/                            # (Optional) Cross-project sync
    ├── coordinator.py
    └── conflict_resolution.py
```

### Key Interfaces to Define

**1. ChunkStore (storage abstraction)**:
```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class ChunkStore(ABC):
    """Abstract storage interface for chunks."""

    @abstractmethod
    def insert(self, chunk: Chunk) -> int:
        """Insert single chunk, return ID."""
        pass

    @abstractmethod
    def batch_insert(self, chunks: List[Chunk]) -> List[int]:
        """Batch insert chunks in single transaction."""
        pass

    @abstractmethod
    def query(self, table: str, filters: Dict[str, Any] = None, limit: int = None) -> List[Chunk]:
        """Query chunks with filters. Uses parameterized queries internally."""
        pass

    @abstractmethod
    def semantic_search(self, query_vector: np.ndarray, limit: int = 10, filters: Dict[str, Any] = None) -> List[Chunk]:
        """Vector similarity search (only if storage supports embeddings)."""
        pass

    @abstractmethod
    def update_authority(self, chunk_id: int, score: float) -> None:
        """Update authority score for chunk."""
        pass
```

**2. Template (parsing abstraction)**:
```python
class Template(ABC):
    """Abstract template for parsing documents."""

    @abstractmethod
    def matches(self, file_path: Path) -> bool:
        """Check if template handles this file."""
        pass

    @abstractmethod
    def extract(self, file_path: Path) -> List[Chunk]:
        """Parse file into chunks."""
        pass
```

**3. GitOracle (git abstraction)**:
```python
class GitOracle(ABC):
    """Abstract interface to git repository."""

    @abstractmethod
    def find_related_commits(self, file_path: str, timestamp: int) -> List[Commit]:
        """Find commits touching file around timestamp."""
        pass

    @abstractmethod
    def get_diff(self, commit: Commit, file_path: str) -> Diff:
        """Get diff for file in commit."""
        pass
```

### Extension Points to Establish

1. **Template plugins** (compile/templates/):
   - New document types register via `TemplateRegistry.register(template)`
   - Example: Add RFC template, OpenAPI template, etc.

2. **Discovery primitives** (retrieve/primitives.py):
   - New query patterns register via `Primitives.register(name, fn)`
   - Example: Add `cross_project` primitive for pattern library queries

3. **Storage backends** (storage/):
   - New backends implement `ChunkStore` interface
   - Example: Add Postgres, Elasticsearch, etc.

4. **Consolidation algorithms** (manage/):
   - New consolidation strategies (entity resolution, schema evolution, preset discovery)
   - Example: Add LLM-based entity resolution, active learning for canonical types

5. **Conflict resolution strategies** (sync/):
   - New strategies register in `ConflictResolver`
   - Example: Add CRDT-based merge, user-prompted resolution

---

## Summary Table

| Principle | Impact on IMEM | Adoption | Priority |
|-----------|----------------|----------|----------|
| **Controller-as-Service with DI** | Storage-agnostic architecture; SQLite ↔ Qdrant swapping | **Adopt** | **P0** |
| **Schema-as-Source-of-Truth** | Multi-tier intelligence (chunks → entities → authority); SQL migrations | **Adopt** | **P0** |
| **Intelligence via Consolidation** | Automated schema evolution, entity resolution, preset discovery | **Adopt** | **P1** |
| **Layered Caching** | 10-100x performance gains (embedding cache, query cache, batch ops) | **Adopt** | **P1** |
| **Distributed Sync** | Cross-project pattern library sharing (optional for MVP) | **Consider** | **P2** |
| **Security via Validation** | SQL injection prevention, data integrity | **Adopt** | **P0** |

---

## References

### Key Architectural Documents Consulted

- `/home/axp/projects/fleet/hangar/code/aura/main/.context/designate/overview.md` — IMEM architectural overview
- `/home/axp/projects/fleet/hangar/code/agentic-flow/main/packages/agentdb/README.md` — AgentDB documentation

### Critical Modules Examined

**Core Controllers:**
- `src/controllers/ReflexionMemory.ts` — Episodic memory with dependency injection
- `src/controllers/SkillLibrary.ts` — Consolidation pipeline with pattern extraction
- `src/controllers/EmbeddingService.ts` — Embedding cache with LRU eviction
- `src/controllers/SyncCoordinator.ts` — Distributed sync orchestration

**Infrastructure:**
- `src/db-fallback.ts` — Storage abstraction (sql.js wrapper)
- `src/schemas/frontier-schema.sql` — Multi-tier schema definition
- `src/security/input-validation.ts` — Input validation and SQL injection prevention
- `src/optimizations/QueryOptimizer.ts` — Query result cache with TTL
- `src/optimizations/BatchOperations.ts` — Transaction-level batching

**Entry Points:**
- `src/index.ts` — Controller exports (composition at user level)
- `src/mcp/agentdb-mcp-server.ts` — MCP tool integration

### Design Decisions Observed

1. **No controller interdependencies** — Controllers share infrastructure (db, embedder) but don't know about each other
2. **SQL as canonical type system** — Schema defines data model, controllers implement logic
3. **Polymorphic memory types** — Causal edges connect any memory types (`from_memory_type`, `to_memory_type`)
4. **Automated pattern extraction** — 5 ML-inspired techniques (keyword frequency, critique analysis, reward distribution, metadata consistency, learning curves)
5. **Transparent caching** — Controllers don't know about caching layers (separation of concerns)
6. **Conflict resolution strategies** — 4 built-in strategies (local-wins, remote-wins, latest-wins, merge)
7. **Input validation at boundaries** — Whitelists for table/column names, parameterized queries only
8. **Progressive intelligence tiers** — Episodes → Skills → Causal Graphs → Explainable Recall
