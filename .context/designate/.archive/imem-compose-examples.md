# IMEM Compose Query Examples

## Example 1: Metadata Search with Discovery Primitives

**Use Case:** Find decisions about routing and discover related Implementation/Pattern sections (ultra-fast, no vectors)

```bash
imem compose '{
  "search": {
    "mode": "metadata",
    "text": "routing",
    "filters": {"phase": "develop", "section_type": "Decisions"},
    "limit": 2
  },
  "discovery": {
    "siblings": {
      "limit": 2,
      "section_types": ["Implementation", "Patterns"]
    },
    "temporal": {"direction": "both", "limit": 3}
  }
}'
```

**What This Does:**
1. **Metadata search** (0.1-1ms) - No vectors, pure SQLite filtering
2. Finds decisions mentioning "routing" in develop phase
3. **For each result**, discovers:
   - **Siblings:** 2 Implementation or Patterns sections from same file
   - **Temporal:** 3 chunks before/after in git timeline
4. Returns structured JSON with enriched context

**Why It's Fast:** All discovery uses SQLite metadata queries (no vector search)

**✅ Full Feature Parity:** Metadata mode now supports all discovery primitives (siblings/genealogy/temporal) with 100% corpus coverage!


---

## Example 2: Multi-Source Query (Context + Conversations)

**Use Case:** Search for "authentication" across both context docs and conversations

```bash
imem compose '{
  "search": {
    "queries": [
      {
        "mode": "metadata",
        "text": "authentication",
        "filters": {"source": "context", "phase": "develop"},
        "limit": 3
      },
      {
        "mode": "metadata",
        "text": "authentication",
        "filters": {"source": "conversation", "chunk_type": "message"},
        "limit": 3
      }
    ]
  },
  "discovery": {
    "genealogy": true,
    "temporal": {"direction": "both", "limit": 2}
  }
}'
```

**What This Does:**
1. **Query 1:** Search context docs (markdown files) for "authentication" in develop phase
2. **Query 2:** Search conversation chunks (messages only) for "authentication"
3. Merge results from both sources (deduplicated)
4. For each result:
   - **Genealogy:** Find parent/child conversation chunks (for conversation results)
   - **Temporal:** Find chunks before/after in git timeline (for context results)

**Output:** Unified view across documentation and conversation history


---

## Example 3: Hybrid Metadata → Semantic Search

**Use Case:** Fast metadata filter, then semantic search on the subset

```bash
# First: Metadata-only to identify high-value chunks
imem compose '{
  "search": {
    "mode": "metadata",
    "filters": {"phase": "develop", "section_type": "Implementation"},
    "limit": 50
  }
}' > candidates.json

# Then: Semantic search on filtered subset (future capability)
imem compose '{
  "search": {
    "mode": "semantic",
    "text": "database migration patterns",
    "filters": {"phase": "develop", "section_type": "Implementation"},
    "limit": 5
  },
  "discovery": {
    "siblings": {"limit": 3},
    "cross_phase": {"phases": ["design", "designate"], "limit": 2}
  }
}'
```

**What This Does:**
1. **Fast metadata pre-filter:** Narrow to 50 Implementation sections in develop phase
2. **Semantic search:** Find most relevant results using embeddings (when vectorized)
3. **Cross-phase discovery:** Find related decisions from design/designate phases
4. **Sibling enrichment:** Add related sections from same document

**Why This Matters:**
- Metadata filters reduce semantic search scope (faster + more accurate)
- Only vectorize the 50 high-value chunks instead of all 2,455
- Cross-phase discovery connects implementation to original design decisions


---

## Advanced: Pattern Discovery Workflow

**Use Case:** Find all "Pattern" sections, analyze them, build taxonomy

```bash
# Step 1: Extract all pattern sections
imem compose '{
  "search": {
    "mode": "metadata",
    "filters": {"section_type": "Patterns"},
    "limit": 100
  }
}' | jq '.results[] | {name: .section_name, content: .content, file: .file_path}' > patterns.json

# Step 2: Find patterns about a specific topic
imem query-metadata --section-type Patterns --text "vector" --limit 5

# Step 3: Discover siblings to understand full context
imem compose '{
  "search": {
    "mode": "metadata",
    "filters": {"section_type": "Patterns"},
    "limit": 10
  },
  "discovery": {
    "siblings": {"section_types": ["Implementation", "Decision"], "limit": 2}
  }
}'
```

**Output:**
- All documented patterns extracted
- Patterns grouped by topic
- Each pattern linked to implementing code and originating decisions

---

## Key Advantages of Metadata Mode

✅ **Speed:** 0.1-1ms queries (200x faster than vector search)
✅ **Coverage:** All 283 files indexed immediately (no vectorization needed)
✅ **Precision:** Exact matches on phase, section_type, timestamps
✅ **Scalability:** Add metadata filters to reduce vector search scope
✅ **Cost:** No embedding costs for metadata-only queries

## When to Use Each Mode

**Metadata Mode:**
- Exact filtering (phase, section_type, file_path)
- Temporal queries (recent changes)
- Pattern discovery (find all X sections)
- Lineage tracking (session_id filtering)

**Semantic Mode:**
- Conceptual similarity ("find related ideas")
- Synonym matching ("auth" → "authentication")
- Cross-language queries
- Fuzzy matching

**Hybrid (Best of Both):**
1. Metadata filter → narrow scope
2. Semantic search → find most relevant
3. Discovery primitives → enrich context
