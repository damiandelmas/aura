---
type: "designate.specification"
status: "staged"
timestamp: "2025-10-23T19:35:00"
version: "v3.0"
---

# Implementation Specification: LlamaIndex Section-Level Indexing

**Phase 5A+B: Complete Two-Tier Architecture**

_Staged execution plan - consolidates design R&D into actionable implementation steps_

---

## Scope

Implement section-level chunking using LlamaIndex MarkdownNodeParser for:
- **Tier 1:** Changelogs (H3-level, ~15 vectors/doc)
- **Tier 2:** Conversations (H2-level, ~5 vectors/conversation)

With phase-based filtering (`--in design/develop/document/conversations`) and section filtering (`--section "Decisions"`).

---

## File Changes Summary

| File | Lines | Changes |
|------|-------|---------|
| `imem/src/imem/ingest.py` | +40 | Add LlamaIndex chunking, phase extraction |
| `imem/src/imem/search.py` | +15 | Add FieldCondition filtering |
| `imem/src/imem/cli.py` | +20 | Add `--in`, `--section` flags |
| `trace/src/aura_trace/query.py` | +35 | Structured markdown export |
| `trace/src/aura_trace/cli.py` | +20 | Add `--index` integration |
| `imem/setup.py` | +1 | Add llama-index-core dependency |
| **Total** | **~131** | **~4-6 hours** |

---

## 1. Dependencies

### Add to `imem/setup.py`

```python
setup(
    name='aura-imem',
    version='3.0.0',
    install_requires=[
        'qdrant-client>=1.7.0',
        'sentence-transformers>=2.2.0',
        'click>=8.0.0',
        'llama-index-core>=0.11.0',  # NEW
    ],
    ...
)
```

**Installation:**
```bash
cd imem/
pip install -e .
```

---

## 2. IMEM: Section-Level Ingestion

### File: `imem/src/imem/ingest.py`

**Add imports:**
```python
from llama_index.core.node_parser import MarkdownNodeParser
from llama_index.core.schema import Document as LlamaDocument
```

**Add to DocumentIngestion class:**

```python
class DocumentIngestion:
    def __init__(self):
        self.parser = MarkdownNodeParser()  # NEW
        self.model = SentenceTransformer('intfloat/e5-large-v2')
        self.qdrant = QdrantService()

    def ingest_markdown_chunked(self, file_path: Path, phase: str = None):
        """Ingest markdown with section-level chunking"""

        # Auto-detect phase from path if not provided
        if not phase:
            phase = self._extract_phase(file_path)

        # Read file
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Extract frontmatter metadata
        frontmatter = self._extract_frontmatter(content)

        # Parse with LlamaIndex
        llama_doc = LlamaDocument(
            text=content,
            metadata={'file_path': str(file_path)}
        )

        nodes = self.parser.get_nodes_from_documents([llama_doc])

        # Index each section
        for node in nodes:
            # Generate embedding
            embedding = self.model.encode(node.get_content()).tolist()

            # Extract type category/subtype
            doc_type = frontmatter.get('type', '')
            category = doc_type.split('.')[0] if '.' in doc_type else doc_type
            subtype = doc_type.split('.')[1] if '.' in doc_type else None

            # Build payload
            payload = {
                'source': 'changelog',
                'phase': phase,
                'section_type': node.metadata.get('header_path'),
                'section_level': node.metadata.get('header_level'),
                'category': category,
                'subtype': subtype,
                'timestamp': frontmatter.get('timestamp'),
                'content': node.get_content(),
                'file_path': str(file_path)
            }

            # Store in Qdrant
            self.qdrant.client.upsert(
                collection_name=self.collection_name,
                points=[{
                    'id': str(uuid4()),
                    'vector': embedding,
                    'payload': payload
                }]
            )

    def ingest_conversation_chunked(self, markdown_path: Path, session_id: str, metadata: dict):
        """Ingest conversation with H2-level chunking"""

        with open(markdown_path, 'r') as f:
            content = f.read()

        # Parse with LlamaIndex
        llama_doc = LlamaDocument(
            text=content,
            metadata={'session_id': session_id}
        )

        nodes = self.parser.get_nodes_from_documents([llama_doc])

        # Index each H2 section
        for node in nodes:
            embedding = self.model.encode(node.get_content()).tolist()

            payload = {
                'source': 'conversation',
                'session_id': session_id,
                'section_type': node.metadata.get('header_path'),
                'section_level': node.metadata.get('header_level'),
                'content': node.get_content(),
                'start_time': metadata.get('start_time'),
                'duration_minutes': metadata.get('duration_minutes'),
                'message_count': metadata.get('message_count'),
                'has_changelog': metadata.get('has_changelog', False),
                'changelog_path': metadata.get('changelog_path')
            }

            self.qdrant.client.upsert(
                collection_name=self.collection_name,
                points=[{
                    'id': str(uuid4()),
                    'vector': embedding,
                    'payload': payload
                }]
            )

    def _extract_phase(self, file_path: Path) -> str:
        """Extract phase from file path"""
        path_str = str(file_path)

        if '/design/' in path_str:
            return 'design'
        elif '/designate/' in path_str:
            return 'designate'
        elif '/develop/' in path_str:
            return 'develop'
        elif '/document/' in path_str:
            return 'document'
        else:
            return 'unknown'

    def _extract_frontmatter(self, content: str) -> dict:
        """Extract YAML frontmatter"""
        import re

        match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
        if not match:
            return {}

        try:
            import yaml
            return yaml.safe_load(match.group(1))
        except:
            return {}
```

**Lines added:** ~40

---

## 3. IMEM: Search with Filtering

### File: `imem/src/imem/search.py`

**Add to SearchEngine class:**

```python
from qdrant_client import models

class SearchEngine:
    def search(self, query: str, filters: dict = None, limit: int = 5, **kwargs):
        """Search with optional metadata filtering"""

        # Generate query embedding
        embedding = self.model.encode(query).tolist()

        # Build Qdrant filter
        qdrant_filter = None
        if filters:
            must_conditions = []

            for key, value in filters.items():
                must_conditions.append(
                    models.FieldCondition(
                        key=key,
                        match=models.MatchValue(value=value)
                    )
                )

            qdrant_filter = models.Filter(must=must_conditions)

        # Search
        results = self.qdrant.client.search(
            collection_name=self.collection_name,
            query_vector=embedding,
            query_filter=qdrant_filter,
            limit=limit
        )

        return results
```

**Lines added:** ~15

---

## 4. IMEM CLI: Phase and Section Filters

### File: `imem/src/imem/cli.py`

**Update search command:**

```python
@cli.command('search')
@click.argument('query')
@click.option('--in', 'phase_filter',
              type=click.Choice(['design', 'designate', 'develop', 'document', 'conversations', 'all']),
              default='all',
              help='Filter by document phase')
@click.option('--section',
              help='Filter by section type (e.g., "Decisions", "User Messages")')
@click.option('--limit', default=5, help='Number of results')
@click.option('--show-metadata', is_flag=True, help='Show metadata')
def search(query, phase_filter, section, limit, show_metadata):
    """Search institutional memory with phase/section filters"""

    from .search import SearchEngine

    # Build filters
    filters = {}

    if phase_filter == 'conversations':
        filters['source'] = 'conversation'
    elif phase_filter != 'all':
        filters['source'] = 'changelog'
        filters['phase'] = phase_filter

    if section:
        # Fuzzy match section type (contains)
        filters['section_type'] = section

    # Search
    engine = SearchEngine()
    results = engine.search(query, filters=filters, limit=limit)

    # Display
    for i, result in enumerate(results, 1):
        click.echo(f"\n{i}. {result.payload['section_type']} [Score: {result.score:.2f}]")
        click.echo(f"   Phase: {result.payload.get('phase', 'N/A')}")
        click.echo(f"   Source: {result.payload['source']}")

        if show_metadata:
            click.echo(f"   Metadata: {result.payload}")

        click.echo(f"   {result.payload['content'][:200]}...")
```

**Add new command:**

```python
@cli.command('index-conversation')
@click.argument('markdown_file', type=click.Path(exists=True))
@click.option('--session-id', required=True, help='Session ID')
def index_conversation(markdown_file, session_id):
    """Index a conversation markdown file"""

    from .ingest import DocumentIngestion
    import json

    # Read metadata from sidecar JSON if exists
    metadata_file = markdown_file.replace('.md', '.json')
    metadata = {}
    if Path(metadata_file).exists():
        with open(metadata_file) as f:
            metadata = json.load(f)

    # Index
    ingester = DocumentIngestion()
    ingester.ingest_conversation_chunked(
        Path(markdown_file),
        session_id,
        metadata
    )

    click.echo(f"✅ Indexed conversation {session_id[:12]}")
```

**Lines added:** ~20

---

## 5. TRACE: Structured Markdown Export

### File: `trace/src/aura_trace/query.py`

**Add new method to ConversationQuery class:**

```python
class ConversationQuery:
    def export_structured_markdown(self, entries: List[ConversationEntry],
                                   session_id: str) -> str:
        """Export conversation as structured markdown for LlamaIndex chunking"""

        from .retrieval import ConversationRetrieval

        retrieval = ConversationRetrieval()

        # Get summary metadata
        summary = retrieval.get_summary(entries)

        # Build structured markdown
        md = f"# Conversation: {session_id[:12]}\n\n"
        md += f"**Duration:** {summary['duration_minutes']:.0f}min | "
        md += f"**Messages:** {summary['message_count']}\n\n"

        # User Messages section
        user_messages = [e for e in entries if e.type == 'user']
        if user_messages:
            md += "## User Messages\n\n"
            for entry in user_messages:
                if entry.message and entry.message.get('content'):
                    for content in entry.message['content']:
                        if content.get('type') == 'text':
                            md += f"- {content.get('text', '')}\n"
            md += "\n"

        # Assistant Responses section
        assistant_messages = [e for e in entries if e.type == 'assistant']
        if assistant_messages:
            md += "## Assistant Responses\n\n"
            for entry in assistant_messages:
                if entry.message and entry.message.get('content'):
                    for content in entry.message['content']:
                        if content.get('type') == 'text':
                            md += f"{content.get('text', '')}\n\n"

        # Code Changes section
        patches = retrieval.extract_patches(entries)
        if patches:
            md += "## Code Changes\n\n"
            for patch in patches:
                md += f"### {patch['file']}\n\n"
                md += f"**Operation:** {patch['operation']}\n\n"
                if patch.get('diff_lines'):
                    md += "```diff\n"
                    for line in patch['diff_lines'][:50]:  # Limit to 50 lines
                        md += f"{line}\n"
                    md += "```\n\n"

        # Tools Used section
        tools = retrieval.extract_tools(entries)
        if tools:
            md += "## Tools Used\n\n"
            for tool_name, count in sorted(tools.items(), key=lambda x: -x[1]):
                md += f"- **{tool_name}**: {count}×\n"
            md += "\n"

        # Files Modified section
        files = retrieval.extract_files(entries)
        if files:
            md += "## Files Modified\n\n"
            for file_info in files:
                md += f"- {file_info['path']} ({file_info['type']})\n"

        return md
```

**Lines added:** ~35

---

## 6. TRACE CLI: Indexing Integration

### File: `trace/src/aura_trace/cli.py`

**Add to trace command:**

```python
@click.option('--index', is_flag=True,
              help='Index this conversation into IMEM')
@click.option('--index-all', is_flag=True,
              help='Index all conversations into IMEM (batch)')
def trace(..., index, index_all):
    """TRACE CLI with indexing integration"""

    if index or index_all:
        from .finder import ConversationFinder
        from .retrieval import ConversationRetrieval
        from .query import ConversationQuery
        import subprocess
        import json
        import tempfile

        finder = ConversationFinder()
        retrieval = ConversationRetrieval()
        query = ConversationQuery()

        # Get conversations to index
        if index_all:
            conversations = finder.list_all()
        else:
            conversations = [session_file]  # Current session

        for conv_file in conversations:
            # Load conversation
            entries = retrieval.load_conversation(conv_file)
            if not entries:
                continue

            # Get session ID
            session_id = next((e.session_id for e in entries if e.session_id), None)
            if not session_id:
                continue

            # Export structured markdown
            markdown = query.export_structured_markdown(entries, session_id)

            # Get metadata
            summary = retrieval.get_summary(entries)

            # Write to temp file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
                f.write(markdown)
                md_path = f.name

            # Write metadata sidecar
            metadata_path = md_path.replace('.md', '.json')
            with open(metadata_path, 'w') as f:
                json.dump({
                    'start_time': summary['start_time'].isoformat() if summary.get('start_time') else None,
                    'duration_minutes': summary.get('duration_minutes'),
                    'message_count': summary.get('message_count')
                }, f)

            # Call IMEM to index
            try:
                subprocess.run([
                    'imem', 'index-conversation',
                    md_path,
                    '--session-id', session_id
                ], check=True)

                click.echo(f"✅ Indexed {session_id[:12]}")
            except subprocess.CalledProcessError:
                click.echo(f"❌ Failed to index {session_id[:12]}")

        return  # Exit after indexing

    # ... existing trace logic
```

**Lines added:** ~20

---

## 7. Update IMEM init for Chunked Mode

### File: `imem/src/imem/cli.py`

**Update init command:**

```python
@cli.command('init')
@click.option('--chunked', is_flag=True,
              help='Use section-level chunking (LlamaIndex)')
def init(chunked):
    """Initialize IMEM for current project"""

    from .ingest import DocumentIngestion
    from pathlib import Path

    ingester = DocumentIngestion()

    # Find .context directory
    context_dir = Path('.context')
    if not context_dir.exists():
        click.echo("❌ No .context/ directory found")
        return

    # Collect markdown files
    files = []
    for phase in ['design', 'designate', 'develop', 'document']:
        phase_dir = context_dir / phase
        if phase_dir.exists():
            files.extend(phase_dir.glob('**/*.md'))

    click.echo(f"Found {len(files)} markdown files")

    # Index
    for file_path in files:
        if chunked:
            ingester.ingest_markdown_chunked(file_path)
        else:
            ingester.ingest_document(file_path)  # Old method

    click.echo(f"✅ Indexed {len(files)} files")
```

---

## Implementation Workflow

### Step 1: Add Dependencies
```bash
cd imem/
# Add llama-index-core to setup.py
pip install -e .
```

### Step 2: Implement IMEM Changes
1. Add LlamaIndex parsing to `ingest.py` (+40 lines)
2. Add filtering to `search.py` (+15 lines)
3. Update `cli.py` with filters (+20 lines)

### Step 3: Implement TRACE Changes
1. Add structured export to `query.py` (+35 lines)
2. Add indexing to `cli.py` (+20 lines)

### Step 4: Test

**Test changelog indexing:**
```bash
cd /path/to/project
imem init --chunked
imem search "JWT" --in develop --section "Decisions"
```

**Test conversation indexing:**
```bash
trace --index-all
imem search "database" --in conversations --section "Code Changes"
```

---

## Success Criteria

✅ Can index changelogs with H3-level chunking
✅ Can index conversations with H2-level chunking
✅ Can filter by phase: `--in develop/design/document/designate`
✅ Can filter by section: `--section "Decisions"`
✅ Can search conversations: `--in conversations`
✅ Bidirectional linking works (session_id ↔ changelog_path)
✅ LlamaIndex metadata extracted (header_path, header_level)

---

## Testing Plan

### Unit Tests

**Test phase extraction:**
```python
assert _extract_phase('.context/develop/.changes/file.md') == 'develop'
assert _extract_phase('.context/design/.modules/file.md') == 'design'
```

**Test chunking:**
```python
nodes = parser.get_nodes_from_documents([doc])
assert len(nodes) > 1  # Multiple sections
assert all(n.metadata.get('header_level') for n in nodes)
```

### Integration Tests

**End-to-end:**
```bash
# Index changelogs
imem init --chunked

# Verify searchable
imem search "test" --in develop

# Index conversations
trace --index-all

# Verify searchable
imem search "test" --in conversations
```

---

## Rollout Plan

### Phase 5A (Changelogs) - 2-3 hours
1. Add LlamaIndex dependency
2. Implement chunked ingestion
3. Add phase filtering
4. Test on existing changelogs

### Phase 5B (Conversations) - 2-3 hours
1. Implement structured markdown export
2. Implement conversation indexing
3. Add `--index` CLI flag
4. Test on real conversations

### Total: 4-6 hours

---

## Edge Cases

**Empty sections:** If H2/H3 has no content, LlamaIndex creates minimal node (fine, will be low relevance)

**Malformed markdown:** LlamaIndex handles gracefully, falls back to full-doc chunking

**Missing frontmatter:** Phase extraction falls back to 'unknown', search still works

**No changelog link:** `has_changelog: False` in conversation metadata

---

## Migration Strategy

**Existing indexed data:** Remains unchanged (backward compatible)

**New indexing:** Use `--chunked` flag for section-level

**Gradual migration:**
1. Test chunked mode on new changelogs
2. Once validated, re-index all: `imem init --chunked --force`
3. Old data auto-purged by collection recreation

---

## Performance Optimization

**Batch embedding:** Generate embeddings for all nodes before upserting (reduces Qdrant roundtrips)

**Deduplication:** Track indexed files by hash, skip unchanged

**Incremental indexing:** Only index new/modified files during `imem update`

---

## References

- `01_two-tier-architecture.md` - System architecture
- `03_metadata-schema.md` - Payload structure
- LlamaIndex docs: https://docs.llamaindex.ai/en/stable/module_guides/loading/node_parsers/
