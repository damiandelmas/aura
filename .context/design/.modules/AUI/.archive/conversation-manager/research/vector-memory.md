# Vector Memory Systems for Conversation Retrieval - Analysis

**Date:** 2025-10-18
**Context:** Evaluating christian-byrne/claude-code-vector-memory for TRACE + IMEM integration

---

## Christian-Byrne's Architecture

### **Tech Stack**
- **Vector DB:** ChromaDB (persistent vector storage)
- **Embeddings:** sentence-transformers (likely `all-MiniLM-L6-v2`)
- **Indexing:** Session summaries (not full transcripts)
- **Integration:** `/system:semantic-memory-search` command

### **Scoring Strategy (Hybrid)**
```python
score = (
    0.70 * semantic_similarity +  # Vector cosine similarity
    0.20 * recency_score +         # Newer = better
    0.10 * complexity_score        # More context = better
)
```

### **What They Index**
- ✅ Session summaries (Claude's built-in summary)
- ✅ Session metadata (duration, message count)
- ❌ NOT full conversation text
- ❌ NOT individual messages
- ❌ NOT patches/diffs

### **Search Flow**
1. User query → embeddings
2. ChromaDB vector search (cosine similarity)
3. Apply recency/complexity boosting
4. Return top-K sessions with metadata
5. Claude loads full session if needed

---

## Alternative: sqlite-vec (Lightweight Option)

### **What is sqlite-vec?**
- SQLite extension for vector search (successor to sqlite-vss)
- Single-file database (no server needed)
- SIMD-accelerated performance
- Runs everywhere (MacOS, Linux, Windows, WASM)

### **Performance**
| Dimension | Query Time |
|-----------|------------|
| 384 (MiniLM) | <25ms |
| 768 (standard) | <50ms |
| 1024 (large) | <75ms |

**Perfect for:** <100K embeddings on single machine

### **Python Integration**
```python
from langchain.vectorstores import SQLiteVec
from sentence_transformers import SentenceTransformer

# Create embedder
embedder = SentenceTransformer('all-MiniLM-L6-v2')

# Create vector store
vectorstore = SQLiteVec(
    connection_string="conversations.db",
    embedding_function=embedder
)

# Add documents
vectorstore.add_texts(
    texts=[summary1, summary2],
    metadatas=[meta1, meta2]
)

# Search
results = vectorstore.similarity_search("authentication design", k=5)
```

---

## What We Can Steal from Christian-Byrne

### **1. Summary-First Indexing Pattern**

**Their approach:**
- Index session summaries (200-500 words)
- NOT full transcripts (10K-100K words)

**Why it works:**
- Summaries capture essence
- Smaller embeddings = faster search
- Lower storage costs

**For TRACE + IMEM:**
```python
from aura.services.trace import ConversationFinder, ConversationRetrieval
from aura.services.imem import EnhancedModularIngest

finder = ConversationFinder()
for conv_file in finder.list_all():
    retrieval = ConversationRetrieval()
    entries = retrieval.load_conversation(conv_file)
    summary_data = retrieval.get_summary(entries)
    
    # Index SUMMARY, not full conversation
    imem.ingest_text(
        content=summary_data['summary'],  # 200-500 words
        metadata={
            'type': 'conversation',
            'session_id': summary_data['session_id'],
            'duration': summary_data['duration_minutes'],
            'message_count': summary_data['message_count'],
            'working_directory': summary_data['working_directory'],
            'start_time': summary_data['start_time'].isoformat(),
            'file_path': str(conv_file)
        }
    )
```

**Benefits:**
- ✅ Fast indexing (summaries only)
- ✅ Fast search (small vector space)
- ✅ Semantic discovery works
- ✅ Full conversation retrieved on demand

---

### **2. Hybrid Scoring Strategy**

**Their formula:**
```
final_score = 0.7 * cosine_similarity + 0.2 * recency + 0.1 * complexity
```

**For IMEM:**
```python
from datetime import datetime

def hybrid_score(result, query_time=None):
    """Combine semantic similarity with metadata boosting"""
    query_time = query_time or datetime.now()
    
    # Base semantic score
    semantic = result['score']  # 0-1 from Qdrant
    
    # Recency boost (exponential decay)
    session_time = datetime.fromisoformat(result['metadata']['start_time'])
    days_ago = (query_time - session_time).days
    recency = math.exp(-0.1 * days_ago)  # Recent = higher
    
    # Complexity boost (more messages = more context)
    msg_count = result['metadata']['message_count']
    complexity = min(msg_count / 100, 1.0)  # Cap at 100 messages
    
    return 0.7 * semantic + 0.2 * recency + 0.1 * complexity
```

**Use case:**
```python
# Semantic search returns older but very relevant session
# Hybrid scoring can boost recent sessions with similar relevance
results = imem.search("database schema design")
ranked = sorted(results, key=lambda r: hybrid_score(r), reverse=True)
```

---

### **3. Metadata-Rich Indexing**

**They store:**
- Session ID
- Timestamp
- Duration
- Message count
- Working directory
- Summary text

**Why it matters:**
- Enables filtering: "Recent conversations about auth"
- Enables boosting: Recent + complex = prioritized
- Enables context: Show metadata before loading full conversation

**For TRACE:**
```python
# Already have this in conversation_retrieval.py get_summary()
summary = {
    'summary': 'Discussion about PostgreSQL schema...',
    'session_id': 'abc-123',
    'working_directory': '/path/to/project',
    'message_count': 45,
    'user_messages': 20,
    'assistant_messages': 25,
    'start_time': datetime(...),
    'end_time': datetime(...),
    'duration_minutes': 32.5
}

# Add more metadata
summary['tools_used'] = len(set(tool['name'] for tool in tools))
summary['files_modified'] = len(file_ops)
summary['has_patches'] = len(patches) > 0
```

---

### **4. Two-Tier Retrieval Pattern**

**Their workflow:**
1. **Discovery (Vector Search)** - Find relevant sessions by summary
2. **Retrieval (Full Load)** - Load complete conversation on demand

**NOT:**
- ❌ Searching full conversation text
- ❌ Indexing every message

**For TRACE:**
```python
# Tier 1: Semantic discovery
results = imem.search("authentication strategy", k=5)
# Returns: [
#   {'session_id': 'abc123', 'summary': 'JWT vs session cookies...'},
#   {'session_id': 'def456', 'summary': 'OAuth2 implementation...'}
# ]

# Tier 2: Full conversation retrieval
finder = ConversationFinder()
conv_file = finder.find_by_session_id(results[0]['session_id'])

query = ConversationQuery()
full_markdown = query.export_to_markdown(conv_file, max_messages=None)

# Tier 3: Agent querying (if needed)
answer = subprocess.run([
    'claude', '-p', 
    f"Question: How did we implement JWT?\n\nContext:\n{full_markdown.read_text()}"
], capture_output=True, text=True).stdout
```

**Performance:**
- Discovery: Fast (vector search on summaries)
- Retrieval: On-demand (only load when needed)
- Querying: Intelligent (spawn brother with context)

---

## Comparison: ChromaDB vs sqlite-vec vs Qdrant

| Feature | ChromaDB | sqlite-vec | Qdrant (IMEM) |
|---------|----------|------------|---------------|
| **Storage** | Persistent file | Single SQLite file | Server + disk |
| **Setup** | `pip install chromadb` | `pip install sqlite-vec` | Already running |
| **Performance** | Good | Very fast (<50ms) | Excellent (production) |
| **Scale** | <1M vectors | <100K vectors | Millions |
| **Dependencies** | Moderate | Minimal | Heavy (Docker) |
| **Integration** | New | New | **Already have** |

**Verdict:** Use Qdrant (already have infrastructure)

---

## Implementation Plan for TRACE + IMEM

### **Phase 1: Index Conversation Summaries**

**Add to TRACE CLI:**
```bash
trace --index-all  # One-time: Index all conversations
trace --index-recent 10  # Incremental: Index last 10
```

**Implementation:**
```python
# aura-v2/src/aura/cli/trace.py

@click.option('--index-all', is_flag=True, help='Index all conversations into IMEM')
@click.option('--index-recent', type=int, help='Index N recent conversations')
def trace(..., index_all, index_recent):
    if index_all or index_recent:
        from ..services.imem import EnhancedModularIngest
        
        imem = EnhancedModularIngest()
        finder = ConversationFinder()
        
        conversations = (
            finder.list_all() if index_all 
            else finder.find_recent(index_recent)
        )
        
        for conv_file in conversations:
            retrieval = ConversationRetrieval()
            entries = retrieval.load_conversation(conv_file)
            summary = retrieval.get_summary(entries)
            
            # Index summary with rich metadata
            imem.ingest_text(
                content=summary['summary'],
                metadata={
                    'type': 'conversation',
                    'session_id': summary['session_id'],
                    'file_path': str(conv_file),
                    'start_time': summary['start_time'].isoformat(),
                    'duration': summary['duration_minutes'],
                    'messages': summary['message_count'],
                    'working_dir': summary['working_directory']
                }
            )
        
        click.echo(f"✅ Indexed {len(conversations)} conversations")
```

---

### **Phase 2: Semantic Discovery**

**Add search filter:**
```bash
imem search "database design decisions" --type conversation --recent-days 30
```

**Returns:**
```
Found 3 conversations:

1. Session: abc123 (2025-10-15, 45 mins, 32 messages)
   Summary: PostgreSQL vs MongoDB schema design...
   Score: 0.89

2. Session: def456 (2025-10-12, 28 mins, 18 messages)
   Summary: Normalizing user authentication tables...
   Score: 0.76
```

---

### **Phase 3: Hybrid Scoring**

**Enhance IMEM search with metadata boosting:**

```python
# aura-v2/src/aura/services/imem/enhanced_search.py

def search_conversations(self, query: str, k: int = 5, 
                        boost_recent: bool = True,
                        boost_complex: bool = True):
    """Search conversations with hybrid scoring"""
    
    # Base semantic search
    results = self.qdrant.search(
        query=query,
        filter={'type': 'conversation'},
        limit=k * 2  # Over-retrieve for re-ranking
    )
    
    # Apply hybrid scoring
    if boost_recent or boost_complex:
        for result in results:
            result['hybrid_score'] = self._hybrid_score(
                result, 
                boost_recent=boost_recent,
                boost_complex=boost_complex
            )
        
        results = sorted(results, key=lambda r: r['hybrid_score'], reverse=True)
    
    return results[:k]
```

---

### **Phase 4: MCP Tool Integration**

**Create MCP tool for conversation querying:**

```python
# New file: aura-v2/src/aura/mcp/conversation_query_tool.py

from mcp import Tool
from aura.services.trace import ConversationFinder, ConversationQuery
from aura.services.imem import EnhancedQdrantSearch

@Tool
def discover_conversations(query: str, limit: int = 5):
    """Discover conversations by semantic search"""
    imem = EnhancedQdrantSearch()
    results = imem.search(query, filter={'type': 'conversation'}, limit=limit)
    
    return [
        {
            'session_id': r['metadata']['session_id'][:12],
            'summary': r['content'][:200],
            'score': r['score'],
            'date': r['metadata']['start_time'][:10],
            'duration': f"{r['metadata']['duration']:.0f}m"
        }
        for r in results
    ]

@Tool
def query_conversation(session_id: str, question: str):
    """Query a specific conversation with AI agent"""
    finder = ConversationFinder()
    conv = finder.find_by_session_id(session_id, search_globally=True)
    
    query = ConversationQuery()
    md = query.export_to_markdown(conv, max_messages=None)
    
    # Spawn brother agent
    result = subprocess.run(
        ['claude', '-p', f"""
You are answering on behalf of a past conversation.

CONTEXT:
{md.read_text()}

QUESTION: {question}

Answer based ONLY on the conversation above.
        """],
        capture_output=True, text=True
    )
    
    return result.stdout
```

**Usage in Claude Code:**
```
User: "What did we decide about authentication in past conversations?"

Claude: Let me search for relevant conversations...
[Invokes discover_conversations("authentication design decisions")]

Claude: I found 3 conversations. The most relevant is from 2025-10-15.
       Let me ask that conversation directly...
[Invokes query_conversation("abc123", "What authentication approach did you choose and why?")]

Brother Agent Response: "In that conversation, we chose JWT tokens over 
session cookies because of the stateless requirement for the API gateway..."

Claude: Based on the conversation from Oct 15th, you decided to use JWT 
       tokens over session cookies due to the stateless API gateway requirement.
```

---

## Key Takeaways

### **What to Steal:**

1. ✅ **Summary-first indexing** - Index summaries, not full transcripts
2. ✅ **Hybrid scoring** - Combine semantic + recency + complexity
3. ✅ **Rich metadata** - Store session metadata for filtering/boosting
4. ✅ **Two-tier retrieval** - Discover via vectors, retrieve full on demand

### **What NOT to Copy:**

1. ❌ **Don't use ChromaDB** - You already have Qdrant
2. ❌ **Don't use sqlite-vec** - Qdrant is more powerful
3. ❌ **Don't index full conversations** - Summaries are sufficient

### **Your Advantage:**

You already have:
- ✅ Qdrant running (production-grade)
- ✅ TRACE parsing (summaries, tools, files, patches)
- ✅ Markdown export (for agent consumption)
- ✅ Brother spawning (intelligent querying)

**Just need:** Indexing pipeline (summary → Qdrant)

---

## Recommended Architecture

```
┌─────────────────────────────────────────────────────────┐
│ TRACE: Conversation Archaeology                         │
│ - Finds JSONL files                                     │
│ - Parses conversations                                  │
│ - Extracts summaries, tools, files, patches           │
└─────────────────────────┬───────────────────────────────┘
                          │
                          │ Summary + Metadata
                          ▼
┌─────────────────────────────────────────────────────────┐
│ IMEM: Vector Indexing (Qdrant)                         │
│ - Embed summaries (sentence-transformers)              │
│ - Store in Qdrant with rich metadata                   │
│ - Hybrid scoring (semantic + recency + complexity)     │
└─────────────────────────┬───────────────────────────────┘
                          │
                          │ Semantic Search
                          ▼
┌─────────────────────────────────────────────────────────┐
│ Discovery: "database schema decisions"                  │
│ Returns: [session_abc123, session_def456, ...]         │
└─────────────────────────┬───────────────────────────────┘
                          │
                          │ User picks session
                          ▼
┌─────────────────────────────────────────────────────────┐
│ TRACE: Full Conversation Retrieval                     │
│ - Loads JSONL file                                      │
│ - Exports to markdown                                   │
└─────────────────────────┬───────────────────────────────┘
                          │
                          │ Markdown context
                          ▼
┌─────────────────────────────────────────────────────────┐
│ Brother Agent: Intelligent Querying                     │
│ - claude -p with full conversation context             │
│ - Answers questions on behalf of conversation          │
└─────────────────────────────────────────────────────────┘
```

**This is your complete conversation querying system.**

