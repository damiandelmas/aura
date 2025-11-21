# Implementation Plan (Phase 4-6: Completion)

**Status:** Phases 1-3 complete (SQLite-first foundation), Phases 4-6 complete the vision

---

## Phase 1-3: Complete ✅

**Shipped (~19 hours):**
- ✅ Storage abstraction (VectorStore protocol, SQLite + Qdrant backends)
- ✅ Processor chain pattern (declarative retrieval pipelines)
- ✅ Domain separation (cli/, compile/, manage/, compose/)
- ✅ Two-layer resolution (COMPILE structural, MANAGE entity)
- ✅ CLI composition root (shared resources, 72% LOC reduction)

**Changelogs:**
- 251117-1900: Storage abstraction foundation
- 251117-2015: Processor chain architecture
- 251117-2045: Domain separation completion
- 251117-2117: SQLite-first architecture
- 251117-2119: Critical bug fixes
- 251117-2121: CLI protocol fixes

---

## Phase 4: Protocol Separation & Discovery (~4h)

**Goal:** Extract Qdrant to vector-only, complete discovery processors

### 4.1 Split VectorStore Protocol (1h)

**Problem:** Current VectorStore mixes vector search + graph operations. Qdrant pretends to implement graph methods but can't (no metadata indexing).

**Solution:**
```python
# storage/protocol.py

class VectorSearch(Protocol):
    """Vector similarity + metadata filters"""
    def search(query: str, filters: Dict, limit: int, use_vector: bool) -> List[SearchResult]
    def upsert(chunks: List[Dict]) -> bool

class GraphStore(Protocol):
    """Metadata queries + relationship traversal"""
    def get_siblings(chunk_id: str, limit: int) -> List[SearchResult]
    def get_temporal(chunk_id: str, window_days: int) -> List[SearchResult]
    def get_genealogy(chunk_id: str, depth: int) -> List[SearchResult]
    def get_implementations(chunk_id: str) -> List[SearchResult]  # Phase 5
    def get_stats() -> Dict
```

**Changes:**
- `storage/protocol.py`: Split VectorStore → VectorSearch + GraphStore
- `storage/sqlite.py`: Implement both protocols
- `storage/qdrant_backend.py`: Implement VectorSearch only, remove graph methods
- `compose/processors/search.py`: Accept VectorSearch dependency
- `compose/processors/discovery.py`: Accept GraphStore dependency

---

### 4.2 Qdrant Extraction (30min)

**Remove from Qdrant:**
```python
# storage/qdrant_backend.py - DELETE these methods
def get_siblings(...):  # Can't do this - no file_path indexing
def get_temporal(...):  # Can't do this - no timestamp queries
def get_genealogy(...): # Can't do this - no session_id tracking
```

**Keep in Qdrant:**
```python
# VectorSearch implementation ONLY
def search(query, filters, limit, use_vector=True):
    # Vector similarity + payload filters
    return self.client.search(...)

def upsert(chunks):
    # Upload vectors + minimal metadata
    return self.client.upload_points(...)
```

---

### 4.3 Implement Discovery Processors (2h)

**Current:** Stubbed with NotImplementedError
**Target:** Working processors using GraphStore

```python
# compose/processors/discovery.py

class SiblingDiscovery(Processor):
    """Expand results with spatial neighbors"""
    def __init__(self, graph_store: GraphStore, limit: int = 3):
        self.store = graph_store
        self.limit = limit

    def process(self, ctx: RetrievalContext) -> RetrievalContext:
        result_ids = [r['id'] for r in ctx.results]

        # Parallel discovery with bounded concurrency
        sibling_tasks = [
            self.store.get_siblings(id, limit=self.limit)
            for id in result_ids
        ]
        siblings = await semaphore_gather(*sibling_tasks, max_coroutines=30)

        # Merge siblings into results
        for i, result in enumerate(ctx.results):
            result['siblings'] = [s.to_dict() for s in siblings[i]]

        return ctx
```

Similar for TemporalDiscovery, GenealogyDiscovery.

---

### 4.4 Add Relationships Table (30min)

**Schema:**
```sql
CREATE TABLE IF NOT EXISTS relationships (
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    type TEXT NOT NULL,  -- decision_implements, pattern_applied, etc.
    confidence REAL DEFAULT 1.0,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSON,  -- Detection method, score details
    PRIMARY KEY (source_id, target_id, type),
    FOREIGN KEY (source_id) REFERENCES chunks(id) ON DELETE CASCADE,
    FOREIGN KEY (target_id) REFERENCES chunks(id) ON DELETE CASCADE
);

CREATE INDEX idx_rel_source ON relationships(source_id, type);
CREATE INDEX idx_rel_target ON relationships(target_id, type);
CREATE INDEX idx_rel_type ON relationships(type);
```

**Implementation:**
- Update `storage/sqlite.py` schema
- Add `get_implementations(chunk_id)` to GraphStore protocol
- Query relationships table in SQLite implementation

---

## Phase 5: Semantic Relationship Layer (~3h)

**Goal:** Detect and cache semantic relationships (decision → implementation, pattern → usage)

### 5.1 Relationship Analyzer (2h)

**Create manage/analyzer.py:**

```python
class SemanticAnalyzer:
    """Detect semantic relationships between chunks"""

    def __init__(self, db: Connection):
        self.db = db

    def analyze_decision_implementations(self, min_confidence=0.6):
        """Find code chunks implementing decisions"""

        # Get all decision chunks
        decisions = self.db.execute('''
            SELECT id, content, metadata
            FROM chunks
            WHERE phase = 'designate' AND section_type = 'Decision'
        ''').fetchall()

        # Get all code chunks
        code = self.db.execute('''
            SELECT id, content, metadata
            FROM chunks
            WHERE phase = 'develop'
        ''').fetchall()

        relationships = []
        for decision in decisions:
            # Extract entities from decision
            decision_entities = self._extract_entities(decision['content'])

            for code_chunk in code:
                # Extract entities from code
                code_entities = self._extract_entities(code_chunk['content'])

                # Calculate overlap (Jaccard similarity)
                overlap = len(decision_entities & code_entities)
                union = len(decision_entities | code_entities)
                confidence = overlap / union if union > 0 else 0

                if confidence >= min_confidence:
                    relationships.append({
                        'source_id': decision['id'],
                        'target_id': code_chunk['id'],
                        'type': 'decision_implements',
                        'confidence': confidence,
                        'metadata': json.dumps({
                            'overlap': overlap,
                            'decision_entities': list(decision_entities),
                            'code_entities': list(code_entities)
                        })
                    })

        # Bulk insert
        self.db.executemany('''
            INSERT OR REPLACE INTO relationships
            (source_id, target_id, type, confidence, metadata)
            VALUES (:source_id, :target_id, :type, :confidence, :metadata)
        ''', relationships)

        return len(relationships)

    def _extract_entities(self, text: str) -> Set[str]:
        """Simple entity extraction (identifiers, tech terms)"""
        # Regex for camelCase, snake_case, UPPER_CASE identifiers
        pattern = r'\b[a-z][a-zA-Z0-9_]+\b|\b[A-Z][A-Z0-9_]+\b'
        entities = set(re.findall(pattern, text))

        # Filter common words, keep technical terms
        stopwords = {'the', 'and', 'for', 'with', ...}
        return {e.lower() for e in entities if e.lower() not in stopwords}
```

---

### 5.2 CLI Command (30min)

```python
# cli/commands.py

@imem.command('analyze')
@click.option('--type', type=click.Choice(['decision_implements', 'pattern_applied', 'all']), default='all')
@click.option('--min-confidence', type=float, default=0.6)
def analyze_relationships(type, min_confidence):
    """Detect semantic relationships in corpus"""

    analyzer = app.get_analyzer()

    if type == 'decision_implements' or type == 'all':
        count = analyzer.analyze_decision_implementations(min_confidence)
        click.echo(f"✅ Detected {count} decision → implementation links")

    if type == 'pattern_applied' or type == 'all':
        count = analyzer.analyze_pattern_usage(min_confidence)
        click.echo(f"✅ Detected {count} pattern → usage links")
```

---

### 5.3 Graph Traversal (30min)

**Implement in GraphStore:**
```python
# storage/sqlite.py

def get_implementations(self, chunk_id: str, limit: int = 10) -> List[SearchResult]:
    """Get code chunks implementing this decision (via cached relationships)"""

    rows = self.db.execute('''
        SELECT c.*, r.confidence
        FROM relationships r
        JOIN chunks c ON c.id = r.target_id
        WHERE r.source_id = ? AND r.type = 'decision_implements'
        ORDER BY r.confidence DESC
        LIMIT ?
    ''', (chunk_id, limit)).fetchall()

    return [self._row_to_search_result(row) for row in rows]
```

---

## Phase 6: Git Integration (~3h)

**Goal:** Parse git commits as chunks, validate decisions against code changes

### 6.1 Git Commit Parser (1h)

```python
# compile/git_parser.py

class GitCommitParser:
    """Parse git history into chunks"""

    def parse_commits(self, repo_path: Path, since_date: str = None) -> List[Dict]:
        """Extract commits as chunks"""

        import subprocess

        cmd = ['git', 'log', '--pretty=format:%H|||%an|||%ae|||%at|||%s|||%b', '--no-merges']
        if since_date:
            cmd.extend(['--since', since_date])

        result = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True)
        commits = result.stdout.split('\n')

        chunks = []
        for commit_line in commits:
            if not commit_line.strip():
                continue

            hash, author, email, timestamp, subject, body = commit_line.split('|||')

            chunks.append({
                'id': f'git_commit_{hash[:12]}',
                'source_type': 'git_commit',
                'content': f"{subject}\n\n{body}",
                'phase': 'develop',  # Commits are code changes
                'section_type': 'Implementation',
                'timestamp': datetime.fromtimestamp(int(timestamp)).isoformat(),
                'metadata': {
                    'commit_hash': hash,
                    'author': author,
                    'author_email': email
                }
            })

        return chunks
```

---

### 6.2 Temporal Validation (2h)

```python
# manage/temporal.py

class TemporalValidator:
    """Validate indexed chunks against git history"""

    def mark_superseded(self, project_id: str):
        """Mark chunks superseded by later git commits"""

        # Find decisions with code changes after decision timestamp
        superseded = self.db.execute('''
            SELECT
                d.id as decision_id,
                c.id as commit_id,
                d.timestamp as decision_time,
                c.timestamp as commit_time
            FROM chunks d
            JOIN chunks c ON
                c.source_type = 'git_commit' AND
                c.timestamp > d.timestamp AND
                c.content LIKE '%' || d.metadata->>'entity' || '%'
            WHERE
                d.phase = 'designate' AND
                d.section_type = 'Decision'
        ''').fetchall()

        # Update metadata
        for row in superseded:
            self.db.execute('''
                UPDATE chunks
                SET metadata = json_set(metadata, '$.superseded_by', ?)
                WHERE id = ?
            ''', (row['commit_id'], row['decision_id']))

        return len(superseded)
```

---

## Success Criteria

**Phase 4 complete when:**
- ✅ VectorSearch + GraphStore protocols separated
- ✅ Qdrant implements VectorSearch only (no graph methods)
- ✅ Discovery processors work (SiblingDiscovery, TemporalDiscovery, GenealogyDiscovery)
- ✅ Relationships table exists in SQLite schema

**Phase 5 complete when:**
- ✅ manage/analyzer.py detects semantic relationships
- ✅ `imem analyze` command populates relationships table
- ✅ get_implementations() returns cached semantic links
- ✅ Query: "Show me what implements JWT auth decision" works

**Phase 6 complete when:**
- ✅ Git commits indexed as chunks (source_type='git_commit')
- ✅ manage/temporal.py validates decisions against commits
- ✅ Superseded decisions marked in metadata
- ✅ Query: "Find decisions invalidated by code changes" works

---

## Timeline

**Completed:** ~19 hours (Phases 1-3)
**Remaining:** ~10 hours (Phases 4-6)
**Total:** ~29 hours to complete original SQLite-first vision
