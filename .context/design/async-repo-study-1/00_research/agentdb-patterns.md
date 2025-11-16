# Pattern Extraction: agentdb

## Executive Summary

AgentDB (from agentic-flow) is a **state-of-the-art agent memory system** implementing five cutting-edge patterns for autonomous learning: reflexion-style episodic replay, skill consolidation from trajectories, causal memory graphs, mixed memory (facts + vectors), and HNSW-accelerated vector search. Architecturally relevant to IMEM for its **controller pattern separation**, **embedding service abstraction**, **progressive skill consolidation**, **causal reasoning over memories**, and **HNSW index management with graceful degradation**.

Built on SQLite with embeddings stored as BLOBs, the system achieves p95 latency ≤ 50ms for k-NN over 50k memories and 80% hit rate for relevant episode retrieval. Key architectural strengths: clean separation between storage and intelligence layers, async consolidation jobs that don't block primary operations, and runtime composition of causal graphs from stored edges.

---

## Pattern 1: Controller Pattern with Embedding Service Abstraction

**Location:** `packages/agentdb/src/controllers/ReflexionMemory.ts:46-354`

**Description:**

AgentDB separates **data access logic** (controllers) from **embedding generation** (service) through dependency injection. Each controller (ReflexionMemory, SkillLibrary, CausalMemoryGraph) receives a database handle and optional embedding service in its constructor. Controllers never instantiate their dependencies—composition happens at the entry point (CLI or programmatic API).

**Why it exists:**

- **Testability**: Mock embedding service without filesystem I/O
- **Swap providers**: Change from Transformers.js to OpenAI embeddings without touching controllers
- **Lazy initialization**: Embedding service initializes async, controllers remain sync-constructible
- **Single responsibility**: Controllers handle business logic, service handles ML inference

**Code Example:**

```typescript
// packages/agentdb/src/controllers/ReflexionMemory.ts:46-53
export class ReflexionMemory {
  private db: Database;
  private embedder: EmbeddingService;

  constructor(db: Database, embedder: EmbeddingService) {
    this.db = db;
    this.embedder = embedder;
  }
```

**Entry point composition:**

```typescript
// packages/agentdb/src/cli/agentdb-cli.ts:110-129
async initialize(dbPath: string = './agentdb.db'): Promise<void> {
  this.db = await createDatabase(dbPath);

  // Single embedding service shared across controllers
  this.embedder = new EmbeddingService({
    model: 'Xenova/all-MiniLM-L6-v2',
    dimension: 384,
    provider: 'transformers'
  });
  await this.embedder.initialize();

  // Inject into all controllers
  this.causalGraph = new CausalMemoryGraph(this.db);
  this.reflexion = new ReflexionMemory(this.db, this.embedder);
  this.skills = new SkillLibrary(this.db, this.embedder);
}
```

**Relevance to IMEM:**

- **Module:** `compile/Templates` + `storage/`
- **Use case:** Template parsers (changelog, conversation, ADR) receive embedding service as dependency. Storage backends (SQLite, Qdrant) receive database handles. Compiler orchestrates composition.
- **Why useful:** IMEM's template system needs to swap embedding providers (local Transformers.js vs OpenAI API) and storage backends (SQLite-only vs SQLite+Qdrant) without rewriting parsers. Controller pattern enables this.

**Adoption Strategy:**

- [x] **Adapt** — Create base `TemplateParser` interface requiring `(db: Database, embedder: EmbeddingService)` constructor. Templates like `ChangelogTemplate`, `ConversationTemplate` implement interface. Compiler instantiates dependencies once, injects into templates.

**Implementation Priority:** **High**

---

## Pattern 2: Episodic Consolidation with Pattern Extraction

**Location:** `packages/agentdb/src/controllers/SkillLibrary.ts:232-347`

**Description:**

SkillLibrary's `consolidateEpisodesIntoSkills()` implements **progressive learning**: successful episodes (reward ≥ 0.7, attempts ≥ 3) are grouped by task, analyzed for common patterns using NLP-inspired keyword extraction, and consolidated into reusable skills. This runs **async** (nightly cron job or post-success hook) and includes:

1. **Aggregate query**: Group episodes by task, filter by quality thresholds
2. **Pattern extraction**: Analyze outputs/critiques for keyword frequency (stop-word filtering, min frequency 2)
3. **Metadata synthesis**: Extract consistent parameters across episodes
4. **Learning curve analysis**: Compare first-half vs second-half rewards to detect improvement
5. **Skill creation**: Store with `extractedPatterns` and `patternConfidence` in metadata

**Why it exists:**

- **Offline intelligence**: Pattern extraction is expensive (NLP over all episode text). Running async prevents blocking primary operations.
- **Evidence-based learning**: Skills aren't manually coded—they emerge from actual successful trajectories.
- **Confidence scoring**: Pattern confidence based on sample size and success rate prevents overfitting to outliers.

**Code Example:**

```typescript
// packages/agentdb/src/controllers/SkillLibrary.ts:232-347 (simplified)
async consolidateEpisodesIntoSkills(config: {
  minAttempts?: number;
  minReward?: number;
  timeWindowDays?: number;
  extractPatterns?: boolean;
}): Promise<{ created: number; patterns: Array<{...}> }> {
  const { minAttempts = 3, minReward = 0.7, timeWindowDays = 7 } = config;

  // Step 1: Find candidate tasks
  const candidates = this.db.prepare(`
    SELECT task, COUNT(*) as attempt_count, AVG(reward) as avg_reward,
           GROUP_CONCAT(id) as episode_ids
    FROM episodes
    WHERE ts > strftime('%s', 'now') - ? AND reward >= ?
    GROUP BY task
    HAVING attempt_count >= ?
  `).all(timeWindowDays * 86400, minReward, minAttempts);

  for (const candidate of candidates) {
    const episodeIds = candidate.episode_ids.split(',').map(Number);

    // Step 2: Extract patterns
    const patternData = await this.extractPatternsFromEpisodes(episodeIds);

    // Step 3: Create skill with metadata
    const skill: Skill = {
      name: candidate.task,
      description: `Learned from ${episodeIds.length} episodes. Patterns: ${patternData.commonPatterns.join(', ')}`,
      successRate: candidate.success_rate,
      avgReward: candidate.avg_reward,
      metadata: {
        sourceEpisodes: episodeIds,
        extractedPatterns: patternData.commonPatterns,
        successIndicators: patternData.successIndicators,
        patternConfidence: this.calculatePatternConfidence(episodeIds.length, candidate.success_rate)
      }
    };

    await this.createSkill(skill);
  }
}
```

**Pattern extraction logic:**

```typescript
// packages/agentdb/src/controllers/SkillLibrary.ts:352-421
private async extractPatternsFromEpisodes(episodeIds: number[]): Promise<{
  commonPatterns: string[];
  successIndicators: string[];
}> {
  const episodes = this.db.prepare(`SELECT * FROM episodes WHERE id IN (...)`).all(...episodeIds);

  // 1. Keyword frequency from outputs
  const keywordFrequency = this.extractKeywordFrequency(episodes.map(ep => ep.output));
  const topKeywords = this.getTopKeywords(keywordFrequency, 5);

  // 2. Critique patterns
  const critiqueKeywords = this.extractKeywordFrequency(episodes.map(ep => ep.critique));

  // 3. Reward distribution analysis
  const avgReward = episodes.reduce((sum, ep) => sum + ep.reward, 0) / episodes.length;
  const highRewardRatio = episodes.filter(ep => ep.reward > avgReward).length / episodes.length;

  // 4. Metadata consistency
  const metadataPatterns = this.extractMetadataPatterns(episodes);

  // 5. Learning trend
  const learningTrend = this.analyzeLearningTrend(episodes);

  return { commonPatterns: [...topKeywords, ...metadataPatterns], successIndicators: [...critiqueKeywords, learningTrend] };
}
```

**Relevance to IMEM:**

- **Module:** `manage/Resolver` + `manage/Registry`
- **Use case:** After compiling chunks, run **nightly consolidation** to discover canonical entity types. Example: Chunks mention "jwt", "JWT", "jwt-tokens"—consolidation extracts keyword frequency, creates canonical `jwt` entity, stores in `manage/Registry` with confidence score.
- **Why useful:** IMEM's entity resolution (Tier 1: Registry) needs evidence-based canonical types. Rather than hardcoding "jwt" as canonical, discover it from usage patterns. Pattern extraction = automatic taxonomy discovery.

**Adoption Strategy:**

- [x] **Adapt** — Implement `manage/Consolidator` job:
  1. Query chunks grouped by `section_type` (Decision, Pattern, Implementation)
  2. Extract keyword frequency from `content` field
  3. Detect entity variations using Levenshtein distance (e.g., "jwt" ≈ "JWT")
  4. Create canonical entity in `manage/Registry` with `extractedVariations` metadata
  5. Run nightly via cron or post-compilation hook

**Implementation Priority:** **High**

---

## Pattern 3: Causal Memory Graph with Intervention Tracking

**Location:** `packages/agentdb/src/controllers/CausalMemoryGraph.ts:1-200`

**Description:**

CausalMemoryGraph implements **do-calculus** (Pearl's causal inference) for agent memories. Instead of storing "X correlates with Y," it tracks **interventional effects**: "When we forced X (do(X)), Y changed by ΔY." The graph is stored as:

- **Edges table**: `(from_memory_id, to_memory_id, uplift, confidence, sample_size, confounder_score)`
- **Experiments table**: A/B tests with treatment/control groups
- **Observations table**: Individual episode outcomes under treatment

Uplift is calculated as `E[y|do(x)] - E[y]` using Welch's t-test for statistical significance.

**Why it exists:**

- **Causality over correlation**: Agents learn "using skill X causes 20% higher reward" (causal) vs "skill X appears in 90% of successful episodes" (correlation). The latter might be spurious (confounding).
- **Evidence-based decision-making**: Before recommending a strategy, the system checks if past interventions (experiments) validated the causal effect.
- **Confounder detection**: Tracks `confounder_score` to flag spurious relationships.

**Code Example:**

```typescript
// packages/agentdb/src/controllers/CausalMemoryGraph.ts:81-170 (simplified)
export class CausalMemoryGraph {
  private db: Database;

  // Create A/B test experiment
  createExperiment(experiment: CausalExperiment): number {
    const stmt = this.db.prepare(`
      INSERT INTO causal_experiments (
        name, hypothesis, treatment_id, treatment_type, control_id,
        start_time, sample_size, status
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    `);

    return stmt.run(
      experiment.name,
      experiment.hypothesis,
      experiment.treatmentId,  // e.g., skill ID 42
      experiment.treatmentType, // "skill"
      experiment.controlId,     // baseline skill ID or null
      experiment.startTime,
      0, // sample_size starts at 0
      'running'
    ).lastInsertRowid;
  }

  // Record outcome for treatment or control group
  recordObservation(observation: CausalObservation): void {
    this.db.prepare(`
      INSERT INTO causal_observations (
        experiment_id, episode_id, is_treatment, outcome_value, outcome_type
      ) VALUES (?, ?, ?, ?, ?)
    `).run(
      observation.experimentId,
      observation.episodeId,
      observation.isTreatment ? 1 : 0,
      observation.outcomeValue,  // e.g., episode reward
      observation.outcomeType    // "reward" | "success" | "latency"
    );
  }

  // Calculate causal uplift using Welch's t-test
  calculateUplift(experimentId: number): {
    uplift: number;
    pValue: number;
    confidenceInterval: [number, number];
  } {
    const observations = this.db.prepare(`
      SELECT is_treatment, outcome_value
      FROM causal_observations
      WHERE experiment_id = ?
    `).all(experimentId);

    const treatmentValues = observations.filter(o => o.is_treatment === 1).map(o => o.outcome_value);
    const controlValues = observations.filter(o => o.is_treatment === 0).map(o => o.outcome_value);

    const treatmentMean = this.mean(treatmentValues);
    const controlMean = this.mean(controlValues);
    const uplift = treatmentMean - controlMean;

    // Welch's t-test for significance
    const pValue = this.welchTTest(treatmentValues, controlValues);

    return { uplift, pValue, confidenceInterval: [...] };
  }
}
```

**Usage flow:**

```typescript
// Hypothesis: "Using skill 'error_handling_pattern' improves code quality"
const experimentId = causalGraph.createExperiment({
  name: "error_handling_ab_test",
  hypothesis: "error_handling_pattern skill increases reward",
  treatmentId: 42,        // skill ID
  treatmentType: "skill",
  controlId: null,        // no control = baseline
  startTime: Date.now(),
  sampleSize: 0,
  status: 'running'
});

// Over next 100 episodes, randomly assign treatment
for (const episode of nextEpisodes) {
  const useTreatment = Math.random() < 0.5;
  // ... execute episode with/without skill ...

  causalGraph.recordObservation({
    experimentId,
    episodeId: episode.id,
    isTreatment: useTreatment,
    outcomeValue: episode.reward,
    outcomeType: 'reward'
  });
}

// After 100 observations, calculate uplift
const result = causalGraph.calculateUplift(experimentId);
// result: { uplift: 0.23, pValue: 0.002, confidenceInterval: [0.15, 0.31] }
// Interpretation: Treatment increases reward by 23% (p < 0.01)
```

**Relevance to IMEM:**

- **Module:** `manage/Temporal` + `retrieve/Graph`
- **Use case:** IMEM's temporal validation compares documented decisions vs git outcomes. Extend this to **causal validation**: Did implementing pattern X cause code quality improvement? Track experiments: "Hypothesis: Switching to JWT auth reduces auth bugs." Compare commit periods before/after decision, measure bug frequency as outcome.
- **Why useful:** Current IMEM detects **drift** (code diverged from docs). Causal graphs detect **failed predictions** (docs claim X improves Y, but intervention data shows no effect). This flags unreliable documentation.

**Adoption Strategy:**

- [ ] **Avoid for MVP** — Causal inference requires A/B testing infrastructure (randomized interventions). IMEM is retrospective (analyzes existing commits). However, **bookmark for research phase**: Could infer causality from observational data using instrumental variables (e.g., "commits authored by senior devs" as instrument for "design quality").

**Implementation Priority:** **Low** (research-phase feature)

---

## Pattern 4: HNSW Index with Graceful Degradation

**Location:** `packages/agentdb/src/controllers/HNSWIndex.ts:76-250`

**Description:**

HNSWIndex wraps the HNSW (Hierarchical Navigable Small World) algorithm for approximate nearest-neighbor search, achieving **10-100x speedup** over brute-force cosine similarity. Key architectural decisions:

1. **Separate index lifecycle**: Index is built explicitly via `buildIndex()`, not on every query
2. **Label mapping**: HNSW uses integer labels (0, 1, 2...), but database uses arbitrary IDs. Bidirectional map maintains correspondence.
3. **Persistent index**: Serialize index to disk, reload on startup (avoid rebuild)
4. **Rebuild threshold**: Track updates since last build; rebuild when updates exceed 10% of corpus
5. **Graceful degradation**: If index build fails, fall back to brute-force without crashing

**Why it exists:**

- **Performance**: Brute-force k-NN over 50k vectors = 200ms. HNSW = 5ms (40x faster).
- **Incremental updates**: Small updates don't require full rebuild. Track drift percentage.
- **Index persistence**: Building HNSW index for 100k vectors takes 30 seconds. Persisting avoids rebuild on every startup.

**Code Example:**

```typescript
// packages/agentdb/src/controllers/HNSWIndex.ts:76-188 (simplified)
export class HNSWIndex {
  private db: Database;
  private config: HNSWConfig;
  private index: any | null = null;
  private idToLabel: Map<number, number> = new Map();  // DB ID → HNSW label
  private labelToId: Map<number, number> = new Map();  // HNSW label → DB ID
  private nextLabel: number = 0;
  private indexBuilt: boolean = false;
  private updatesSinceLastBuild: number = 0;

  constructor(db: Database, config?: Partial<HNSWConfig>) {
    this.db = db;
    this.config = {
      M: 16,                     // Connections per layer
      efConstruction: 200,       // Build-time candidates
      efSearch: 100,             // Search-time candidates
      metric: 'cosine',
      dimension: 1536,
      maxElements: 100000,
      persistIndex: true,
      rebuildThreshold: 0.1,     // Rebuild after 10% updates
      ...config
    };

    // Try to load existing index from disk
    if (this.config.persistIndex && this.config.indexPath) {
      this.loadIndex();
    }
  }

  async buildIndex(tableName: string = 'pattern_embeddings'): Promise<void> {
    const start = Date.now();

    // Fetch all vectors
    const rows = this.db.prepare(`SELECT pattern_id as id, embedding FROM ${tableName}`).all();

    // Initialize HNSW index
    this.index = new HierarchicalNSW(this.config.metric, this.config.dimension);
    this.index.initIndex(
      Math.max(rows.length, this.config.maxElements),
      this.config.M,
      this.config.efConstruction
    );
    this.index.setEf(this.config.efSearch);

    // Add vectors with label mapping
    this.idToLabel.clear();
    this.labelToId.clear();
    this.nextLabel = 0;

    for (const row of rows) {
      const id = row.id;
      const embedding = new Float32Array(row.embedding.buffer, row.embedding.byteOffset, row.embedding.byteLength / 4);

      const label = this.nextLabel++;
      this.index.addPoint(Array.from(embedding), label);

      this.idToLabel.set(id, label);
      this.labelToId.set(label, id);
    }

    this.indexBuilt = true;
    this.updatesSinceLastBuild = 0;
    this.lastBuildTime = Date.now();

    // Persist to disk
    if (this.config.persistIndex && this.config.indexPath) {
      await this.saveIndex();
    }
  }

  async search(query: Float32Array, k: number): Promise<HNSWSearchResult[]> {
    if (!this.index || !this.indexBuilt) {
      throw new Error('Index not built. Call buildIndex() first.');
    }

    // HNSW search (returns labels)
    const result = this.index.searchKnn(Array.from(query), k);

    // Map labels back to database IDs
    const results: HNSWSearchResult[] = [];
    for (let i = 0; i < result.neighbors.length; i++) {
      const label = result.neighbors[i];
      const distance = result.distances[i];
      const id = this.labelToId.get(label);

      if (id === undefined) continue;

      results.push({
        id,
        distance,
        similarity: this.distanceToSimilarity(distance)
      });
    }

    return results;
  }

  // Track updates and trigger rebuild if threshold exceeded
  notifyUpdate(): void {
    this.updatesSinceLastBuild++;

    if (this.indexBuilt && this.updatesSinceLastBuild / this.labelToId.size > this.config.rebuildThreshold) {
      console.warn(`[HNSWIndex] Update threshold exceeded (${this.config.rebuildThreshold * 100}%), triggering rebuild`);
      this.buildIndex().catch(err => console.error('[HNSWIndex] Rebuild failed:', err));
    }
  }
}
```

**Relevance to IMEM:**

- **Module:** `storage/Qdrant` + `retrieve/Primitives`
- **Use case:** IMEM's semantic search uses Qdrant (external vector DB). For **offline/local deployments**, replace Qdrant with HNSW index stored in SQLite. Pattern: Build HNSW index during compilation (post-chunk ingestion), persist to `imem_hnsw.index` file, reload on query.
- **Why useful:** HNSW enables **local vector search** without external dependencies. For projects that don't want to run Qdrant, HNSW provides 90% of the performance in-process. Graceful degradation means system works even if index build fails (falls back to SQLite full-scan).

**Adoption Strategy:**

- [x] **Adopt directly** — Create `storage/HNSWBackend` implementing same interface as `storage/Qdrant`. Configuration choice in `imem compile --backend sqlite` (no vectors) vs `--backend sqlite+hnsw` (local HNSW) vs `--backend qdrant` (external).

**Implementation Priority:** **Medium**

---

## Pattern 5: CLI-Driven Controller Composition

**Location:** `packages/agentdb/src/cli/agentdb-cli.ts:51-130`

**Description:**

AgentDB's CLI acts as the **composition root**: it instantiates the database, embedding service, and all controllers, then exposes them via CLI commands. Each command is a thin wrapper calling controller methods. This pattern:

1. **Single initialization point**: `initialize()` creates all dependencies once
2. **Shared embedding service**: One embedding service instance reused across all controllers (memory efficiency)
3. **Database pragmas**: Performance tuning (`WAL`, `cache_size`) applied once at initialization
4. **Schema loading**: Loads multiple schema files (`schema.sql`, `frontier-schema.sql`) from fallback paths
5. **Lazy controller creation**: Controllers created only after database and embedder are ready

**Why it exists:**

- **DRY principle**: Avoid duplicating initialization logic in every command
- **Performance**: Embedding service initialization (model download) is slow (~2s). Do it once.
- **Schema versioning**: Separate schema files allow incremental feature additions without breaking existing tables
- **Error handling**: If schema files missing, CLI warns but continues (graceful degradation)

**Code Example:**

```typescript
// packages/agentdb/src/cli/agentdb-cli.ts:51-130
class AgentDBCLI {
  public db?: any;
  private causalGraph?: CausalMemoryGraph;
  private reflexion?: ReflexionMemory;
  private skills?: SkillLibrary;
  private embedder?: EmbeddingService;

  async initialize(dbPath: string = './agentdb.db'): Promise<void> {
    // 1. Create database
    this.db = await createDatabase(dbPath);

    // 2. Configure for performance
    this.db.pragma('journal_mode = WAL');
    this.db.pragma('synchronous = NORMAL');
    this.db.pragma('cache_size = -64000');  // 64MB cache

    // 3. Load schemas from multiple fallback paths
    const schemaFiles = ['schema.sql', 'frontier-schema.sql'];
    const basePaths = [
      path.join(__dirname, '../schemas'),
      path.join(__dirname, '../../src/schemas'),
      path.join(process.cwd(), 'dist/schemas'),
      path.join(process.cwd(), 'src/schemas'),
      path.join(process.cwd(), 'node_modules/agentdb/dist/schemas')
    ];

    let schemasLoaded = 0;
    for (const basePath of basePaths) {
      if (fs.existsSync(basePath)) {
        for (const schemaFile of schemaFiles) {
          const schemaPath = path.join(basePath, schemaFile);
          if (fs.existsSync(schemaPath)) {
            const schema = fs.readFileSync(schemaPath, 'utf-8');
            this.db.exec(schema);
            schemasLoaded++;
          }
        }
        if (schemasLoaded > 0) break;  // Found schemas, stop searching
      }
    }

    if (schemasLoaded === 0) {
      log.warning('Schema files not found, database may not be initialized properly');
    }

    // 4. Initialize embedding service (slow, do once)
    this.embedder = new EmbeddingService({
      model: 'Xenova/all-MiniLM-L6-v2',
      dimension: 384,
      provider: 'transformers'
    });
    await this.embedder.initialize();  // Downloads model if needed

    // 5. Initialize all controllers (inject dependencies)
    this.causalGraph = new CausalMemoryGraph(this.db);
    this.reflexion = new ReflexionMemory(this.db, this.embedder);
    this.skills = new SkillLibrary(this.db, this.embedder);
    this.nightlyLearner = new NightlyLearner(this.db, this.embedder);
  }

  // CLI commands delegate to controllers
  async reflexionStore(params: {...}): Promise<void> {
    if (!this.reflexion) throw new Error('Not initialized');
    await this.reflexion.storeEpisode(params);
  }

  async skillsSearch(task: string, k: number): Promise<void> {
    if (!this.skills) throw new Error('Not initialized');
    const results = await this.skills.searchSkills({ task, k });
    console.log(results);
  }
}

// Entry point
const cli = new AgentDBCLI();
await cli.initialize('./agentdb.db');
await cli.reflexionStore({ sessionId: 'sess-1', task: 'implement_auth', reward: 0.9, ... });
```

**Relevance to IMEM:**

- **Module:** `imem/cli.py` (main entry point)
- **Use case:** IMEM's CLI (`imem compile`, `imem compose`) should follow same pattern: single initialization function creates database, embedding service, all controllers (Parser, Resolver, Orchestrator), then CLI commands delegate. Example:
  ```python
  class IMEMCLI:
      def __init__(self):
          self.db = None
          self.embedder = None
          self.parser = None
          self.composer = None

      async def initialize(self, db_path: str):
          self.db = create_database(db_path)
          self.embedder = EmbeddingService(model='all-MiniLM-L6-v2')
          await self.embedder.initialize()

          self.parser = Parser(self.db, self.embedder)
          self.composer = Composer(self.db, self.embedder)

      def compile_command(self, source_path: str):
          chunks = self.parser.parse(source_path)
          self.db.store_chunks(chunks)

      def compose_command(self, query: dict):
          results = self.composer.orchestrate(query)
          print(results)
  ```
- **Why useful:** Prevents **shotgun initialization** (every command creates its own database connection, embedding service). Single initialization = faster startup, shared resources, consistent configuration.

**Adoption Strategy:**

- [x] **Adopt directly** — Refactor `imem/cli.py` to use composition root pattern. Create `IMEMCLI` class with `initialize()` method, instantiate once at entry point, delegate to controllers.

**Implementation Priority:** **High**

---

## Summary Table

| Pattern | IMEM Module | Priority | Strategy |
|---------|-------------|----------|----------|
| **Controller Pattern with Embedding Service Abstraction** | `compile/Templates` + `storage/` | High | Adapt — Base `TemplateParser` interface with injected dependencies |
| **Episodic Consolidation with Pattern Extraction** | `manage/Resolver` + `manage/Registry` | High | Adapt — Implement `manage/Consolidator` for automatic entity discovery |
| **Causal Memory Graph with Intervention Tracking** | `manage/Temporal` + `retrieve/Graph` | Low | Avoid for MVP — Research-phase feature, requires A/B testing |
| **HNSW Index with Graceful Degradation** | `storage/` + `retrieve/Primitives` | Medium | Adopt — Create `storage/HNSWBackend` for local vector search |
| **CLI-Driven Controller Composition** | `imem/cli.py` | High | Adopt — Single initialization point, shared resources |

---

## Key Files Examined

- `packages/agentdb/src/index.ts` — Controller exports and API surface
- `packages/agentdb/src/controllers/ReflexionMemory.ts` — Episodic memory with self-critique
- `packages/agentdb/src/controllers/SkillLibrary.ts` — Skill consolidation and pattern extraction
- `packages/agentdb/src/controllers/CausalMemoryGraph.ts` — Causal inference over memories
- `packages/agentdb/src/controllers/HNSWIndex.ts` — HNSW vector search with label mapping
- `packages/agentdb/src/cli/agentdb-cli.ts` — CLI composition root
- `packages/agentdb/src/schemas/schema.sql` — Database schema (episodes, skills, facts)
- `packages/agentdb/src/schemas/frontier-schema.sql` — Causal graph schema

---

## References

**Research Citations:**

- Reflexion: Shinn et al., "Reflexion: Language Agents with Verbal Reinforcement Learning" (2023)
- Voyager: Wang et al., "Voyager: An Open-Ended Embodied Agent with LLMs" (2023)
- Pearl's Causal Inference: "Causality: Models, Reasoning, and Inference" (2009)
- HNSW: Malkov & Yashunin, "Efficient and robust approximate nearest neighbor search using HNSW" (2018)

**Architectural Decisions:**

- Dependency injection for testability and composability
- Async consolidation jobs for offline intelligence (non-blocking)
- Embedding service abstraction for provider swapping
- Graceful degradation (HNSW fallback, schema loading fallback)
- Label mapping for HNSW (DB IDs ≠ HNSW labels)
- SQLite WAL mode + cache tuning for performance
- Multi-schema loading for incremental feature additions
