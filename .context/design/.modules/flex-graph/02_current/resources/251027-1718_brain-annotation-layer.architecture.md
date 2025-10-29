---
date: 2025-10-27
type: architecture.implementation
status: endstate
keywords: "json-storage anthropic-haiku annotation-pipeline python"
---

# Architecture: BRAIN + Annotation Layer Implementation

## Components

**Location:** `imem/src/imem/brain.py`, `imem/src/imem/annotate.py`
**Status:** Endstate (12-18 months post-MVP)
**Effort:** ~150 lines (brain) + ~100 lines (annotate)

---

## BRAIN Storage

### Data Structure

```python
# ~/.context/imem_brain/brain.json

{
  "version": "1.0",
  "updated_at": "2024-10-27T17:30:00",

  "chunks": {
    "abc123-result-id": {
      "chunk_id": "abc123",
      "content_summary": "Use Redis for caching",
      "section_type": "Decisions",
      "file_path": ".context/develop/.changes/231015-1200_caching.md",

      # Temporal state
      "created_at": "2023-10-15T12:00:00",
      "age_months": 18,
      "last_referenced": "2024-09-12T15:30:00",

      # Usage state
      "reference_count": 23,
      "query_contexts": ["caching", "redis", "session storage"],

      # Authority state
      "pagerank_score": 0.72,
      "centrality_score": 0.45,
      "authority_rank": 15,  # Out of N total chunks

      # Supersession state
      "superseded_by": ["xyz789"],
      "supersession_confidence": 0.89,
      "supersession_detected_at": "2024-10-20T14:00:00",
      "supersession_reason": "Performance requirements"
    },

    "xyz789-result-id": {
      "chunk_id": "xyz789",
      "content_summary": "Use Memcached for caching",
      "section_type": "Decisions",

      # This supersedes Redis decision
      "supersedes": ["abc123"],
      "supersedes_confidence": 0.89,

      # Current authority
      "reference_count": 87,
      "pagerank_score": 0.94,
      "authority_rank": 2  # High authority
    }
  },

  # Global patterns
  "patterns": {
    "supersession_threshold": 0.85,
    "temporal_decay_rate": 0.05,  # 5% decay per month
    "authority_percentiles": {
      "p50": 0.45,
      "p90": 0.78,
      "p95": 0.92
    }
  }
}
```

---

## BRAIN Update Logic

### Update After Query

```python
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict

BRAIN_PATH = Path.home() / '.context' / 'imem_brain' / 'brain.json'

def update_brain_after_query(
    results: List[Dict],
    query_text: str,
    graph_scores: Dict[str, float] = None
):
    """Update BRAIN with usage data from query"""

    # Load current BRAIN
    brain = load_brain()

    # Update each result
    for result in results:
        chunk_id = result['id']

        # Initialize if new
        if chunk_id not in brain['chunks']:
            brain['chunks'][chunk_id] = _init_chunk_state(result)

        chunk_state = brain['chunks'][chunk_id]

        # 1. Increment reference count
        chunk_state['reference_count'] += 1
        chunk_state['last_referenced'] = datetime.now().isoformat()

        # 2. Track query context
        if 'query_contexts' not in chunk_state:
            chunk_state['query_contexts'] = []
        if query_text not in chunk_state['query_contexts']:
            chunk_state['query_contexts'].append(query_text)

        # 3. Update authority scores (if graph ops ran)
        if graph_scores and chunk_id in graph_scores:
            chunk_state['pagerank_score'] = graph_scores[chunk_id]

        # 4. Compute age
        created = datetime.fromisoformat(chunk_state['created_at'])
        age_delta = datetime.now() - created
        chunk_state['age_months'] = age_delta.days // 30

    # 5. Detect supersession patterns
    _detect_supersession(brain, results)

    # 6. Save updated BRAIN
    save_brain(brain)

def _detect_supersession(brain: Dict, recent_results: List[Dict]):
    """Detect potential supersession relationships"""

    for r1 in recent_results:
        for r2 in recent_results:
            if r1['id'] == r2['id']:
                continue

            # Same section type
            if r1['section_type'] != r2['section_type']:
                continue

            # One newer than other
            t1 = datetime.fromisoformat(r1['timestamp'])
            t2 = datetime.fromisoformat(r2['timestamp'])

            if t2 <= t1:
                continue  # r2 not newer

            # High semantic similarity
            similarity = cosine_similarity(r1['vector'], r2['vector'])
            if similarity > brain['patterns']['supersession_threshold']:
                # r2 supersedes r1
                r1_state = brain['chunks'][r1['id']]
                r2_state = brain['chunks'][r2['id']]

                if r2['id'] not in r1_state.get('superseded_by', []):
                    r1_state.setdefault('superseded_by', []).append(r2['id'])
                    r1_state['supersession_confidence'] = similarity
                    r1_state['supersession_detected_at'] = datetime.now().isoformat()

                if r1['id'] not in r2_state.get('supersedes', []):
                    r2_state.setdefault('supersedes', []).append(r1['id'])
                    r2_state['supersedes_confidence'] = similarity
```

---

## Annotation Service

### Core Annotation Function

```python
from anthropic import Anthropic

client = Anthropic()

def annotate_chunk(
    chunk: Dict,
    brain_state: Dict
) -> Dict:
    """Add temporal/supersession context via LLM annotation

    Args:
        chunk: Original chunk data
        brain_state: BRAIN context for this chunk

    Returns:
        Annotated chunk with soft language
    """

    # Build annotation prompt
    prompt = _build_annotation_prompt(chunk, brain_state)

    # Call fast model (Haiku)
    response = client.messages.create(
        model="claude-3-haiku-20240307",
        max_tokens=1000,
        temperature=0.3,  # Consistent annotations
        messages=[{"role": "user", "content": prompt}]
    )

    annotated_content = response.content[0].text

    # Return annotated chunk
    return {
        **chunk,
        'content': annotated_content,
        'annotations': {
            'temporal': _extract_temporal_note(annotated_content),
            'supersession': _extract_supersession_note(annotated_content),
            'authority': _extract_authority_note(annotated_content)
        }
    }

def _build_annotation_prompt(chunk: Dict, brain_state: Dict) -> str:
    """Construct annotation prompt"""

    # Determine annotation type
    annotations_needed = []

    if brain_state.get('superseded_by') and brain_state.get('supersession_confidence', 0) > 0.85:
        annotations_needed.append('supersession')

    if brain_state.get('age_months', 0) > 12:
        annotations_needed.append('temporal_decay')

    if brain_state.get('reference_count', 0) < 5:
        annotations_needed.append('low_usage')

    if brain_state.get('pagerank_score', 0) > 0.9:
        annotations_needed.append('high_authority')

    # Build prompt
    prompt = f"""You are an annotation assistant. Add brief, gentle context to this knowledge chunk.

CHUNK (Original):
{chunk['content']}

BRAIN CONTEXT:
- Age: {brain_state.get('age_months', 0)} months old
- Superseded by: {', '.join(brain_state.get('superseded_by', []))}
- Supersession confidence: {brain_state.get('supersession_confidence', 0.0):.2f}
- Reference count: {brain_state.get('reference_count', 0)}
- Last referenced: {brain_state.get('last_referenced', 'never')}
- Authority (PageRank): {brain_state.get('pagerank_score', 0.0):.2f}

ANNOTATIONS NEEDED: {', '.join(annotations_needed)}

INSTRUCTIONS:
1. If superseded (confidence > 0.85): Add gentle evolution note explaining what changed
2. If old (>12 months): Add temporal context note about age
3. If rarely referenced (<5): Add usage note (niche vs common)
4. If high authority (>0.9): Add canonical note (established pattern)
5. Use soft language: "refined", "evolved", "later work" (not "obsolete", "deprecated")
6. Preserve original content entirely - add notes before/after original
7. Use emoji indicators: ⏳ (temporal), 🔄 (supersession), 💡 (usage), ⭐ (authority)

Output annotated chunk in markdown format."""

    return prompt
```

---

## Annotation Pipeline Integration

### Serve with Annotation

```python
def serve_with_annotation(
    primary_chunk,
    relationships: Dict = None,
    template: str = 'decision'
) -> str:
    """Serve chunks with BRAIN annotation layer

    Pipeline:
    1. Load BRAIN state
    2. Annotate chunks (LLM pass)
    3. Assemble with template
    4. Return structured + annotated prompt
    """

    # 1. Load BRAIN
    brain = load_brain()

    # 2. Annotate primary chunk
    primary_brain_state = brain['chunks'].get(primary_chunk['id'], {})
    annotated_primary = annotate_chunk(primary_chunk, primary_brain_state)

    # 3. Annotate related chunks
    annotated_relationships = {}
    if relationships:
        for rel_type, chunks in relationships.items():
            annotated_relationships[rel_type] = [
                annotate_chunk(c, brain['chunks'].get(c['id'], {}))
                for c in chunks
            ]

    # 4. Assemble with template
    return render_template(
        f'{template}.md.j2',
        {
            'primary': annotated_primary,
            **annotated_relationships
        }
    )
```

---

## Header Annotation

### Status Badge Injection

```python
def add_header_badges(
    chunk: Dict,
    brain_state: Dict
) -> str:
    """Add status badges to header"""

    header = f"# DECISION: {chunk['section_name']}"
    badges = []

    # Supersession badge
    if brain_state.get('superseded_by'):
        badges.append("[⏳ SUPERSEDED]")

    # Current badge
    elif brain_state.get('age_months', 0) < 6 and brain_state.get('reference_count', 0) > 50:
        badges.append("[⭐ CURRENT]")

    # Historical badge
    elif brain_state.get('age_months', 0) > 18:
        badges.append("[🗂️ HISTORICAL]")

    # Date badge
    created = brain_state.get('created_at', '').split('T')[0]
    badges.append(f"[📅 {created}]")

    # Combine
    if badges:
        header += " " + " ".join(badges)

    # Status note
    if brain_state.get('superseded_by'):
        superseded_date = brain_state.get('supersession_detected_at', '').split('T')[0]
        header += f"\n\n*Status: This decision was superseded in {superseded_date}. Preserved for context.*"

    return header
```

---

## Performance Characteristics

**BRAIN updates:**
- Per query: ~10ms (JSON load + increment + save)
- Per week: ~100ms (recompute decay, detect patterns)

**Annotation:**
- Haiku call: ~200ms per chunk
- 5 chunks: ~1000ms (can parallelize)
- Cost: ~$0.0001 per chunk = $0.0005 per query

**Total overhead:** ~1200ms per annotated query

**Optimization:** Cache annotations (invalidate on BRAIN update)

---

## Caching Strategy

```python
from functools import lru_cache
import hashlib

@lru_cache(maxsize=1000)
def annotate_chunk_cached(
    chunk_id: str,
    chunk_content_hash: str,
    brain_state_hash: str
) -> Dict:
    """Cache annotations (invalidate when BRAIN or chunk changes)"""

    # Load actual data
    chunk = load_chunk(chunk_id)
    brain_state = load_brain()['chunks'][chunk_id]

    # Annotate
    return annotate_chunk(chunk, brain_state)

def get_brain_state_hash(chunk_id: str) -> str:
    """Hash BRAIN state for cache key"""
    brain = load_brain()
    state = brain['chunks'].get(chunk_id, {})
    return hashlib.md5(json.dumps(state, sort_keys=True).encode()).hexdigest()
```

**Cache hit:** ~1ms (no LLM call)
**Cache miss:** ~200ms (LLM annotation)

**Hit rate:** ~80% (same chunks queried repeatedly)

---

## CLI Interface

```python
# imem/src/imem/cli.py

@develop.command()
@click.argument('query')
@click.option('--annotate/--no-annotate', default=False)
def explain(query, annotate):
    """Explain decision with optional annotation

    Example:
        imem develop explain "JWT auth" --annotate
    """
    if annotate:
        result = serve_with_annotation(query, template='decision')
    else:
        result = serve_with_template(query, template='decision')

    click.echo(result)

@click.command()
def brain_status():
    """Show BRAIN statistics

    Example:
        imem brain status
    """
    brain = load_brain()

    total_chunks = len(brain['chunks'])
    superseded_count = sum(1 for c in brain['chunks'].values() if c.get('superseded_by'))
    high_authority_count = sum(1 for c in brain['chunks'].values() if c.get('pagerank_score', 0) > 0.9)

    click.echo(f"BRAIN Statistics:")
    click.echo(f"  Total chunks: {total_chunks}")
    click.echo(f"  Superseded: {superseded_count}")
    click.echo(f"  High authority: {high_authority_count}")
    click.echo(f"  Last updated: {brain['updated_at']}")
```

---

## Testing Strategy

```python
# test_annotation.py

def test_supersession_annotation():
    """Test supersession annotation language"""
    chunk = {
        'id': 'abc123',
        'content': '### Use Redis\n- **Context**: ...',
        'section_name': 'Use Redis'
    }

    brain_state = {
        'age_months': 18,
        'superseded_by': ['xyz789'],
        'supersession_confidence': 0.89,
        'reference_count': 23
    }

    annotated = annotate_chunk(chunk, brain_state)

    # Should contain evolution language
    assert '🔄' in annotated['content'] or 'Evolution' in annotated['content']
    assert 'refined' in annotated['content'].lower() or 'superseded' in annotated['content'].lower()

    # Should preserve original
    assert 'Use Redis' in annotated['content']
    assert '**Context**' in annotated['content']

def test_brain_update():
    """Test BRAIN state updates"""
    results = [{'id': 'abc123', 'timestamp': '...', 'vector': [...]}]

    brain_before = load_brain()
    ref_count_before = brain_before['chunks'].get('abc123', {}).get('reference_count', 0)

    update_brain_after_query(results, "test query")

    brain_after = load_brain()
    ref_count_after = brain_after['chunks']['abc123']['reference_count']

    assert ref_count_after == ref_count_before + 1
```

---

## Dependencies

```python
# requirements.txt
anthropic>=0.25.0  # For Haiku annotation
```

---

## Summary

**Implementation:**
- ~150 lines (brain.py - state management)
- ~100 lines (annotate.py - LLM annotation)
- JSON storage (~/.context/imem_brain/)
- Haiku for annotation (~$0.0001 per chunk)

**BRAIN tracks:**
- Reference counts (usage)
- Authority scores (PageRank/centrality)
- Supersession patterns (newer + similar)
- Temporal decay (age)

**Annotation targets:**
- Chunk content (inline notes)
- Headers (status badges)
- Template sections (interpretive notes)

**Overhead:** ~1200ms per annotated query (cacheable)

**Timeline:** Endstate (12-18 months post-MVP)

**Next:** See `.pattern.md` for language-agnostic principle.
