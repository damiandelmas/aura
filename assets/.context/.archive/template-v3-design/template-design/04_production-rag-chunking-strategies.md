# How Production RAG Systems Do Section-Level Chunking

## 🎯 **The Core Problem They Solve**

**Naive chunking:** Split text every N characters/tokens
- Result: Sentences cut in half, context lost, relationships broken

**Smart chunking:** Split at semantic boundaries while preserving structure
- Result: Meaningful units that can stand alone OR be reassembled

---

## 📚 **Production RAG Chunking Strategies**

### **1. LlamaIndex: Hierarchical Node System**

**Concept:** Documents are trees of nodes with parent-child relationships

```
Document
├── Chapter 1 (parent node)
│   ├── Section 1.1 (child node)
│   │   ├── Paragraph 1 (leaf node)
│   │   └── Paragraph 2 (leaf node)
│   └── Section 1.2 (child node)
└── Chapter 2 (parent node)
```

**How it works:**

1. **Parse structure** - Detect markdown headers, HTML tags, section breaks
2. **Create hierarchy** - Each section becomes a node with parent/child links
3. **Store separately** - Each node gets its own vector embedding
4. **Metadata tracking** - Each node knows its position in the tree

**When searching:**
- Find relevant leaf node (specific paragraph)
- Optionally traverse UP to parent (get section context)
- Optionally traverse DOWN to children (get details)

**Your use case:**
- Your changelog = Document
- "## Key Decisions" = Parent node
- "### Decision 1" = Child node

---

### **2. LangChain: Recursive Character Splitter**

**Concept:** Try multiple separators in priority order until chunks are right size

**Separator priority:**
1. Double newline (paragraphs)
2. Single newline (sentences)
3. Spaces (words)
4. Characters (last resort)

**How it works:**

1. **Try first separator** - Split on double newlines
2. **Check size** - Are chunks 500-1000 tokens?
3. **If too big** - Split again using next separator
4. **If too small** - Merge with adjacent chunks
5. **Preserve boundaries** - Never split mid-sentence unless forced

**Overlap strategy:**
- Last 50 tokens of Chunk 1 = First 50 tokens of Chunk 2
- Prevents context loss at boundaries
- Search can find relevant info even if it spans chunks

**Your use case:**
- Your sections naturally split on headers (double newline + ##)
- Already perfect semantic boundaries
- No overlap needed because headers provide context

---

### **3. Semantic Chunking (Newer Approach)**

**Concept:** Use embeddings to detect topic shifts, split there

**How it works:**

1. **Embed sentences** - Generate vector for each sentence
2. **Measure similarity** - Compare adjacent sentence embeddings
3. **Detect boundaries** - Big similarity drop = topic change
4. **Split there** - Create chunk boundary at topic shifts

**Example:**
```
Sentence 1: "We chose E5-Large-v2 for accuracy" (embedding A)
Sentence 2: "The model requires 500MB disk space" (embedding B)
Similarity: 0.85 (same topic - model choice)

Sentence 3: "File operations trigger permissions" (embedding C)
Similarity to B: 0.42 (different topic - NEW CHUNK)
```

**Benefit:** Chunks are semantically coherent, not just mechanically split

**Your use case:**
- Your headers already mark topic shifts
- "## Key Decisions" → new topic
- "## Knowledge Capture" → new topic
- Don't need semantic detection, structure already provides it

---

### **4. Notion-Style Block System**

**Concept:** Everything is a block with a type and relationships

**Block types:**
- Heading block
- Text block
- Code block
- List block
- Table block

**How it works:**

1. **Parse into blocks** - Each markdown element = block
2. **Assign types** - Detect block type from syntax
3. **Link relationships** - Track which blocks are inside which headings
4. **Store with metadata** - Type, parent, position, siblings

**Metadata example:**
```
Block: "Bash truncates at 30K characters"
Type: text
Parent: "Tool Output Limits" (heading block)
Section: "Knowledge Capture"
Position: 3rd paragraph under this heading
Previous: "Built-in Tool Limits" (text block)
Next: "MCP Tool Limits" (text block)
```

**When searching:**
- Find relevant text block
- Retrieve parent heading for context
- Optionally get sibling blocks (surrounding paragraphs)

**Your use case:**
- Each "##" heading = heading block
- Content under it = text blocks
- Subsections "###" = child heading blocks
- Natural hierarchical structure

---

## 🔍 **Metadata Strategies Production Systems Use**

### **Strategy 1: Position Tracking**
Every chunk knows where it sits in the document

**Metadata stored:**
- Document ID
- Section number (1, 2, 3...)
- Depth level (H1, H2, H3)
- Character offset (starts at position 2450)
- Token offset (starts at token 512)

**Why:** Enables reconstruction of original document

---

### **Strategy 2: Relationship Mapping**
Every chunk knows its neighbors

**Metadata stored:**
- Previous chunk ID
- Next chunk ID
- Parent chunk ID
- Child chunk IDs (array)
- Sibling chunk IDs

**Why:** Enables context expansion (give me 2 sections before/after this)

---

### **Strategy 3: Type Classification**
Every chunk is categorized

**Common types:**
- Introduction
- Problem statement
- Solution
- Code example
- Summary
- Reference
- Warning/Note

**Your types:**
- Decision
- Constraint
- Failure
- Pattern
- Implementation
- Audit

**Why:** Enables type filtering ("show me only failures")

---

### **Strategy 4: Semantic Tags**
Auto-extracted themes and topics

**Extraction methods:**
- Keyword extraction (TF-IDF, RAKE)
- Named entity recognition (tools, technologies)
- Topic modeling (LDA, clustering)
- LLM extraction (ask Claude to tag)

**Example tags from your changelog:**
```
Technologies: [Bash, Read tool, Write tool, Claude CLI]
Concepts: [Permission system, Output limits, File operations]
Problems: [Truncation, Tilde expansion]
Solutions: [File-based retrieval, Absolute paths]
```

**Why:** Enables multi-faceted search

---

## 🧩 **How They Handle Your Specific Case**

### **Your Changelog Structure:**
```
---
frontmatter
---

# Title

## Section 1: Decisions
### Decision 1
### Decision 2

## Section 2: Implementation
### Pattern A
### Pattern B

## Section 3: Knowledge Capture
### Constraint 1
### Constraint 2
```

### **LlamaIndex Would:**
1. Create parent node for entire document
2. Create child nodes for each ## header
3. Create leaf nodes for each ### subsection
4. Store metadata: parent="Decision 1", type="decision", doc="250927-2217.md"
5. Link nodes: Decision 1 → Decision 2 (siblings), Decision 1 → Decisions section (parent)

### **LangChain Would:**
1. Split on ## headers first
2. If section too large, split on ### headers
3. Add 50-token overlap between sections
4. Store metadata: section_type="decision", position=3

### **Semantic Chunker Would:**
1. Embed each paragraph
2. Detect topic boundary at "## Implementation" (big similarity drop from Decisions)
3. Split there
4. Store embeddings + metadata

### **Notion Would:**
1. Parse markdown into blocks
2. "## Key Decisions" = heading block (level 2)
3. "### Decision 1" = heading block (level 3, child of previous)
4. Paragraph = text block (child of Decision 1 heading)
5. Store block tree with relationships

---

## 🔗 **Cross-Document Relationships**

### **Production Systems Track:**

**Explicit links:**
- Markdown links: `[see this](other-doc.md)`
- References: "As mentioned in Decision-003..."
- Citations: "Source: 250927-2217.md"

**Implicit links:**
- Shared entities (same tool mentioned in multiple docs)
- Temporal (documents from same day/week)
- Similarity (similar embeddings = related topics)
- Co-occurrence (terms that appear together)

**How they store it:**
```
Chunk A metadata:
  explicit_links: ["DECISION-003", "250927-1957.md"]
  mentioned_entities: ["Bash", "Read tool", "permission"]
  temporal_group: "2025-09-27"
  similar_chunks: ["chunk_789", "chunk_456"]  (by embedding distance)
```

**Why:** Enables "show me everything related to this constraint"

---

## 📊 **Search & Retrieval Strategies**

### **Multi-Stage Retrieval (Most Common)**

**Stage 1: Vector Search**
- Use embeddings to find top 50 semantically similar chunks

**Stage 2: Reranking**
- Use cross-encoder to deeply score relevance
- Reduce to top 10 chunks

**Stage 3: Metadata Filtering**
- Filter by type: only show decisions
- Filter by date: only last 30 days
- Filter by source: only from specific documents

**Stage 4: Context Expansion**
- For each top chunk, retrieve parent section
- Or retrieve N chunks before/after
- Or retrieve entire document if chunk is small

**Stage 5: Deduplication**
- If multiple chunks from same section, keep highest-ranked
- If overlapping chunks, merge them

**Final result:** 5-10 perfectly relevant sections with full context

---

### **Hybrid Search (Increasingly Popular)**

**Combine:**
- Vector search (semantic: "what's this about?")
- Keyword search (exact: "must contain this word")
- Metadata filters (type, date, source)

**Scoring formula:**
```
Final Score =
  0.5 × vector_similarity +
  0.3 × keyword_match +
  0.2 × metadata_boost
```

**Your use case:**
```
Query: "bash permission failures"

Vector score: Finds chunks about permissions (semantic)
Keyword score: Must contain "bash" (exact)
Metadata boost: Boost chunks with type="failure"

Result: Exact failure about bash permissions, not general permission info
```

---

## 🎨 **Context Assembly for LLM**

After retrieving relevant chunks, production systems assemble context:

### **Strategy 1: Flat List**
```
Retrieved Chunk 1
---
Retrieved Chunk 2
---
Retrieved Chunk 3
```

**Problems:** No structure, no relationships

---

### **Strategy 2: Hierarchical Assembly**
```
# Most Relevant (Score: 0.95)
## From: 250927-2217.md
### Section: Knowledge Capture > Tool Output Limits

[chunk content]

Parent section context:
[parent content]

# Also Relevant (Score: 0.82)
## From: 250920-1534.md
...
```

**Better:** Shows relationships and source

---

### **Strategy 3: Narrative Reconstruction**
```
Your query: "bash output limits"

Main Answer (from 250927-2217.md):
[Direct answer chunk]

Background Context (from same document):
[Previous section that provides setup]

Related Failures (from 250920-1534.md):
[What didn't work]

Related Decisions (from 250918-1422.md):
[Why current approach was chosen]
```

**Best:** Tells a complete story from multiple sources

---

## 🔄 **How They Handle Updates**

### **When document changes:**

**Option 1: Full Re-embedding**
- Delete all chunks from this document
- Re-parse and re-chunk
- Generate new embeddings
- Store everything fresh

**Option 2: Incremental Update**
- Detect which sections changed
- Only re-embed changed sections
- Update relationship metadata
- Keep unchanged sections

**Option 3: Versioning**
- Keep old chunks with version tag
- Add new chunks with new version
- Search can filter by version
- Enables "what changed between versions"

**Your use case:**
- New changelog = add new sections
- Updated changelog = re-parse that file only
- No need to re-index entire corpus

---

## 💾 **Storage Patterns**

### **Pattern 1: Dual Storage**
- Vector DB: Embeddings + minimal metadata
- Document DB: Full content + relationships
- Link them by ID

**Why:** Vector DBs optimized for similarity, document DBs for complex queries

---

### **Pattern 2: Denormalized Storage**
- Store everything in vector DB payload
- Duplicate data across chunks
- Trade space for retrieval speed

**Why:** One query gets everything, no joins needed

---

### **Pattern 3: Graph + Vector Hybrid**
- Vector DB: For similarity search
- Graph DB: For relationship traversal
- Sync between them

**Why:** Best of both worlds - semantic search + relationship walking

**Your use case:**
- Qdrant for vectors
- Could add Neo4j for relationships later
- Start with denormalized (simpler)

---

## 🎯 **What This Means for IMEM**

### **You Should:**

1. **Parse sections** using markdown headers as boundaries
2. **Store metadata** about section type, parent doc, position
3. **Enable filtering** by section type (constraint, decision, failure)
4. **Preserve links** between sections via metadata
5. **Reconstruct context** by fetching parent/sibling sections when needed

### **You Don't Need:**

1. Semantic boundary detection (headers already mark them)
2. Complex overlap strategies (sections are self-contained)
3. Multi-stage reranking (your corpus is small and clean)
4. Graph database (can do relationships in metadata)

---

## 📊 **Production Examples**

### **Notion AI:**
- Every block is separately embedded
- Searches return specific blocks
- UI shows parent page for context
- Can expand to see full page

### **Confluence AI:**
- Sections within pages are separate
- Search highlights relevant section
- Shows page breadcrumb
- Click to see full page

### **GitHub Copilot:**
- Chunks code by function/class
- Metadata: file path, function name, dependencies
- Search finds specific function
- Provides surrounding code for context

### **ChatGPT with documents:**
- Chunks at paragraph level
- Metadata: page number, section title, document name
- Citations show exact chunk
- Can retrieve full page if needed

---

## TL;DR

**Production RAG systems:**
1. **Parse documents** into semantic chunks (paragraphs, sections, blocks)
2. **Store separately** with rich metadata (type, position, relationships)
3. **Search precisely** (find exact relevant chunk)
4. **Reconstruct context** (expand to parent/siblings when needed)
5. **Assemble narratively** (present results as coherent story)

**For your changelogs:**
- Headers = natural chunk boundaries ✅
- Sections already typed (decisions, constraints, failures) ✅
- Relationships already mentioned (related work) ✅
- Just need to formalize into metadata and enable querying ✅

**You're 80% of the way there with your current structure.** Just need section-level indexing. 🎯
