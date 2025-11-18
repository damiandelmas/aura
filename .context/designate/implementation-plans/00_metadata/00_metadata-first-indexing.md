---
session_id: ee1bcc0b-50c7-4352-b1fa-92872f876d87
---

# Implementation Plan: Metadata-First Indexing

## Objective

Parse entire document corpus (284 files) without vectorization. Store in SQLite for fast metadata queries. Enable selective vectorization later.

**Timeline:** 2-3 hours
**Complexity:** Low (no ML, no vectors, pure data extraction)

---

## Current State

**Problem:**
- Only 8/284 files indexed (document phase only)
- Vectorization required for all indexing (slow, expensive)
- Missing design/develop/designate phases (276 files)
- Can't query full corpus

**Current Flow:**
```
Markdown → LlamaIndex parser → Qdrant (vectors required)
```

**Target Flow:**
```
Markdown → Lightweight parser → SQLite (metadata only)
         → Optional: Selective vectorization → Qdrant (10-20% of chunks)
```

---

## Architecture

### Three Components

**1. Lightweight Parser** (`imem/src/imem/parse/`)
- Extract frontmatter (python-frontmatter)
- Split by headers (H2/H3 depending on document type)
- Enrich with metadata (phase from path, timestamps, etc.)

**2. SQLite Storage** (`imem/src/imem/storage/sqlite.py`)
- Schema: chunks table with JSON metadata column
- Indexes on: phase, section_type, file_path, timestamp
- Fast queries (<10ms)

**3. Query Interface** (`imem/src/imem/query/metadata.py`)
- Filter by: phase, section_type, file_path, timestamp, has_rationale, etc.
- Returns: chunks with full metadata
- No vectors needed

---

## Implementation Steps

### Step 1: Lightweight Parser (30 min)

**File:** `imem/src/imem/parse/markdown.py`

```python
import frontmatter
from pathlib import Path
from typing import Dict, List, Any

class MarkdownParser:
    """Parse markdown without vectorization"""

    def parse_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """
        Parse single markdown file into chunks

        Returns list of chunks:
        {
            'id': str (file_path + section hash),
            'file_path': str,
            'phase': str (from path),
            'section_type': str (from header or frontmatter),
            'section_name': str (header text),
            'content': str,
            'timestamp': str (from frontmatter or file mtime),
            'metadata': dict (all frontmatter + inherited)
        }
        """
        post = frontmatter.load(file_path)

        # Detect phase from path
        phase = self._detect_phase(file_path)

        # Document-level metadata
        doc_metadata = {
            'file_path': str(file_path),
            'phase': phase,
            'timestamp': post.get('timestamp') or self._get_mtime(file_path),
            'frontmatter': post.metadata
        }

        # Split into sections
        sections = self._split_sections(post.content, phase)

        # Create chunks (section + inherited doc metadata)
        chunks = []
        for section in sections:
            chunk = {
                'id': self._generate_id(file_path, section),
                'section_type': section['type'],
                'section_name': section['name'],
                'content': section['content'],
                **doc_metadata  # Inherit document metadata
            }
            chunks.append(chunk)

        return chunks

    def _detect_phase(self, file_path: Path) -> str:
        """Extract phase from path (.context/design/ → design)"""
        parts = file_path.parts
        if '.context' in parts:
            idx = parts.index('.context')
            if idx + 1 < len(parts):
                return parts[idx + 1]
        return 'unknown'

    def _split_sections(self, content: str, phase: str) -> List[Dict[str, str]]:
        """
        Split by headers (H2 or H3 depending on document type)

        Changelogs: H3 level (### Decision, ### Implementation)
        Conversations: H2 level (## Message 1)
        Architecture: H2 level (## Core Capabilities)
        """
        # Detect document type from content patterns
        doc_type = self._detect_document_type(content)

        if doc_type == 'changelog':
            return self._split_by_h3(content)
        else:
            return self._split_by_h2(content)

    def _split_by_h2(self, content: str) -> List[Dict[str, str]]:
        """Split by ## headers"""
        sections = []
        current_section = None

        for line in content.split('\n'):
            if line.startswith('## '):
                if current_section:
                    sections.append(current_section)
                current_section = {
                    'type': self._infer_type(line),
                    'name': line[3:].strip(),
                    'content': ''
                }
            elif current_section:
                current_section['content'] += line + '\n'

        if current_section:
            sections.append(current_section)

        return sections

    def _split_by_h3(self, content: str) -> List[Dict[str, str]]:
        """Split by ### headers (for changelogs)"""
        # Similar to _split_by_h2 but for H3
        pass

    def _infer_type(self, header: str) -> str:
        """
        Infer section_type from header text

        "## Decision" → "Decision"
        "## Core Capabilities" → "Core Capabilities"
        "### Implementation" → "Implementation"
        """
        # Strip markdown, clean
        return header.replace('#', '').strip().split(':')[0]

    def _detect_document_type(self, content: str) -> str:
        """
        Detect if changelog, architecture, conversation, etc.

        Heuristics:
        - Has "### Decision" or "### Implementation" → changelog
        - Has "## Message" → conversation
        - Else → generic architecture/design doc
        """
        if '### Decision' in content or '### Implementation' in content:
            return 'changelog'
        elif '## Message' in content:
            return 'conversation'
        return 'architecture'
```

**Dependencies:**
- `pip install python-frontmatter`

**Testing:**
```python
parser = MarkdownParser()
chunks = parser.parse_file(Path('.context/develop/.changes/251117-1227_multi-source-routing-clean-output.md'))
assert len(chunks) > 0
assert chunks[0]['phase'] == 'develop'
```

---

### Step 2: SQLite Storage (30 min)

**File:** `imem/src/imem/storage/sqlite.py`

```python
import sqlite3
import json
from pathlib import Path
from typing import List, Dict, Any

class SQLiteStore:
    """Store chunks in SQLite for fast metadata queries"""

    def __init__(self, project_root: Path):
        self.db_path = project_root / '.imem' / 'metadata.db'
        self.db_path.parent.mkdir(exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self._create_schema()

    def _create_schema(self):
        """Create chunks table with indexes"""
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS chunks (
                id TEXT PRIMARY KEY,
                file_path TEXT NOT NULL,
                phase TEXT,
                section_type TEXT,
                section_name TEXT,
                content TEXT,
                timestamp TEXT,
                metadata JSON,
                indexed_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Indexes for fast filtering
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_phase ON chunks(phase)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_section_type ON chunks(section_type)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_file_path ON chunks(file_path)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON chunks(timestamp)')

        self.conn.commit()

    def upsert_chunks(self, chunks: List[Dict[str, Any]]):
        """Insert or update chunks"""
        for chunk in chunks:
            # Extract metadata to JSON column
            metadata = {
                'frontmatter': chunk.get('frontmatter', {}),
                'source': chunk.get('source', 'context'),
                # Add other metadata fields
            }

            self.conn.execute('''
                INSERT OR REPLACE INTO chunks
                (id, file_path, phase, section_type, section_name, content, timestamp, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                chunk['id'],
                chunk['file_path'],
                chunk.get('phase'),
                chunk.get('section_type'),
                chunk.get('section_name'),
                chunk.get('content'),
                chunk.get('timestamp'),
                json.dumps(metadata)
            ))

        self.conn.commit()

    def query(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Query chunks by metadata filters"""
        sql = "SELECT * FROM chunks WHERE 1=1"
        params = []

        if filters.get('phase'):
            sql += " AND phase = ?"
            params.append(filters['phase'])

        if filters.get('section_type'):
            sql += " AND section_type = ?"
            params.append(filters['section_type'])

        if filters.get('file_path'):
            sql += " AND file_path LIKE ?"
            params.append(f"%{filters['file_path']}%")

        if filters.get('timestamp_after'):
            sql += " AND timestamp >= ?"
            params.append(filters['timestamp_after'])

        # Content search (SQLite FTS if needed later)
        if filters.get('text'):
            sql += " AND content LIKE ?"
            params.append(f"%{filters['text']}%")

        cursor = self.conn.execute(sql, params)

        # Convert rows to dicts
        columns = [desc[0] for desc in cursor.description]
        results = []
        for row in cursor.fetchall():
            chunk = dict(zip(columns, row))
            chunk['metadata'] = json.loads(chunk['metadata'])
            results.append(chunk)

        return results

    def get_stats(self) -> Dict[str, Any]:
        """Get indexing statistics"""
        total = self.conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]

        phases = self.conn.execute('''
            SELECT phase, COUNT(*) as count
            FROM chunks
            GROUP BY phase
        ''').fetchall()

        return {
            'total_chunks': total,
            'by_phase': dict(phases)
        }
```

**Testing:**
```python
store = SQLiteStore(Path('.'))
store.upsert_chunks(chunks)
results = store.query({'phase': 'develop', 'section_type': 'Decision'})
assert len(results) > 0
```

---

### Step 3: Indexing CLI Command (20 min)

**File:** Modify `imem/src/imem/cli.py`

```python
@imem.command('index-metadata')
@click.option('--force', is_flag=True, help='Re-index existing chunks')
def index_metadata(force):
    """Index all markdown files (metadata only, no vectors)"""
    from imem.parse.markdown import MarkdownParser
    from imem.storage.sqlite import SQLiteStore

    project_root = Path.cwd()
    parser = MarkdownParser()
    store = SQLiteStore(project_root)

    # Find all markdown files
    context_files = list((project_root / '.context').rglob('*.md'))

    click.echo(f"Found {len(context_files)} markdown files")

    # Parse all files
    all_chunks = []
    for md_file in context_files:
        try:
            chunks = parser.parse_file(md_file)
            all_chunks.extend(chunks)
            click.echo(f"  ✓ {md_file.relative_to(project_root)} ({len(chunks)} chunks)")
        except Exception as e:
            click.echo(f"  ✗ {md_file.relative_to(project_root)}: {e}")

    # Store in SQLite
    store.upsert_chunks(all_chunks)

    # Show stats
    stats = store.get_stats()
    click.echo(f"\n✅ Indexed {stats['total_chunks']} chunks")
    click.echo(f"By phase: {stats['by_phase']}")
```

**Testing:**
```bash
imem index-metadata
# Expected:
# Found 284 markdown files
# ✓ .context/develop/.changes/251117-1227_multi-source-routing-clean-output.md (8 chunks)
# ...
# ✅ Indexed 1200+ chunks
# By phase: {'develop': 400, 'design': 300, 'designate': 250, 'document': 50}
```

---

### Step 4: Query CLI Command (20 min)

**File:** Modify `imem/src/imem/cli.py`

```python
@imem.command('query-metadata')
@click.option('--phase', help='Filter by phase')
@click.option('--section-type', help='Filter by section type')
@click.option('--file-path', help='Filter by file path')
@click.option('--text', help='Text search in content')
@click.option('--limit', default=10, help='Max results')
def query_metadata(phase, section_type, file_path, text, limit):
    """Query metadata without vectors"""
    from imem.storage.sqlite import SQLiteStore

    store = SQLiteStore(Path.cwd())

    filters = {}
    if phase:
        filters['phase'] = phase
    if section_type:
        filters['section_type'] = section_type
    if file_path:
        filters['file_path'] = file_path
    if text:
        filters['text'] = text

    results = store.query(filters)[:limit]

    click.echo(f"Found {len(results)} results\n")

    for result in results:
        click.echo(f"📄 {result['file_path']}")
        click.echo(f"   Phase: {result['phase']} | Type: {result['section_type']}")
        click.echo(f"   {result['section_name']}")
        click.echo(f"   {result['content'][:200]}...")
        click.echo()
```

**Testing:**
```bash
imem query-metadata --phase develop --section-type Decision
imem query-metadata --text "authentication"
imem query-metadata --file-path "compose.py"
```

---

### Step 5: Integration with Compose (30 min)

**Goal:** Let compose use SQLite for metadata filtering, then optionally Qdrant for semantic.

**File:** `imem/src/imem/compose.py`

```python
# Modify _execute_search to support metadata-only mode

async def _execute_search(collection_name: str, search_config: dict, ...):
    """Execute search with optional vector bypass"""

    # Check if this is metadata-only query
    if search_config.get('mode') == 'metadata':
        # Use SQLite instead of Qdrant
        from imem.storage.sqlite import SQLiteStore
        store = SQLiteStore(Path.cwd())

        results = store.query(search_config.get('filters', {}))

        # Convert to standard result format
        return [{
            'id': r['id'],
            'score': 1.0,  # No semantic score
            'payload': r
        } for r in results]

    # Otherwise, use existing Qdrant flow
    # ... existing code
```

**Usage:**
```bash
imem compose '{"search": {"mode": "metadata", "filters": {"phase": "develop"}}, "discovery": {"siblings": true}}'
```

---

## Testing Strategy

### Unit Tests

**Test 1: Parser**
```python
def test_parse_changelog():
    parser = MarkdownParser()
    chunks = parser.parse_file('test-changelog.md')
    assert chunks[0]['phase'] == 'develop'
    assert chunks[0]['section_type'] == 'Decision'
```

**Test 2: SQLite Store**
```python
def test_sqlite_query():
    store = SQLiteStore(Path('.'))
    store.upsert_chunks([...])
    results = store.query({'phase': 'develop'})
    assert len(results) > 0
```

**Test 3: Full Flow**
```bash
imem index-metadata
imem query-metadata --phase develop
# Should return results
```

### Integration Tests

**Test Full Corpus:**
```bash
imem index-metadata
# Expected: 1200+ chunks from 284 files
# Speed: <10 seconds
```

**Test Discovery Primitives:**
```bash
imem compose '{"search": {"mode": "metadata", "filters": {"phase": "develop"}}, "discovery": {"siblings": true}}'
# Should return siblings from SQLite chunks
```

---

## Migration Path

### Phase 1: Metadata-Only (This Plan)
- Parse all markdown → SQLite
- Query by metadata (fast)
- No vectors needed

### Phase 2: Selective Vectorization (Future)
- Identify high-value chunks (authority score, recency, user queries)
- Vectorize 10-20% → Qdrant
- Hybrid queries: metadata filter → semantic search subset

### Phase 3: Full Integration (Future)
- Discovery primitives use SQLite for metadata, Qdrant for semantic
- Compose orchestrates both backends
- Templates use rich metadata from SQLite

---

## File Structure

```
imem/
├── src/imem/
│   ├── parse/
│   │   ├── __init__.py
│   │   └── markdown.py          # NEW: Lightweight parser
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── sqlite.py            # NEW: SQLite storage
│   │   └── qdrant.py            # EXISTING: Vector storage
│   ├── query/
│   │   ├── __init__.py
│   │   └── metadata.py          # NEW: Metadata queries
│   ├── compose.py               # MODIFIED: Support metadata mode
│   └── cli.py                   # MODIFIED: New commands
└── .imem/
    └── metadata.db              # NEW: SQLite database
```

---

## Success Criteria

**After implementation:**
1. ✅ All 284 files indexed (not just 8)
2. ✅ Query metadata in <10ms (vs 200ms+ with Qdrant)
3. ✅ Full phase coverage (design/designate/develop/document)
4. ✅ Discovery primitives work with full corpus
5. ✅ No vectors required for metadata queries
6. ✅ Foundation for selective vectorization

**Performance targets:**
- Parse 284 files: <10 seconds
- Store in SQLite: <2 seconds
- Query metadata: <10ms
- Full indexing: <15 seconds total

---

## Dependencies

**New:**
- `python-frontmatter` (metadata extraction)

**Existing:**
- `sqlite3` (standard library)
- `pathlib` (standard library)

**No changes to:**
- Qdrant (still used for existing vector queries)
- LlamaIndex (still used for vector ingestion if needed)

---

## Risks & Mitigations

**Risk 1: Section splitting varies by document type**
- Mitigation: Implement heuristics, add manual overrides if needed

**Risk 2: Metadata inheritance rules unclear**
- Mitigation: Start simple (copy all frontmatter), refine iteratively

**Risk 3: SQLite FTS for text search may be slow**
- Mitigation: Start with LIKE queries, add FTS index if needed

**Risk 4: Migration from existing Qdrant data**
- Mitigation: SQLite is additive, doesn't replace Qdrant. Run in parallel.

---

## Next Steps

**Immediate (implement this plan):**
1. Create `parse/markdown.py` (30 min)
2. Create `storage/sqlite.py` (30 min)
3. Add CLI commands (40 min)
4. Test on full corpus (20 min)

**Then:**
- Test presets with full indexing
- Identify high-value chunks for vectorization
- Build hybrid metadata+semantic queries

**Timeline:** 2-3 hours for core implementation, 1 hour for testing and refinement.
