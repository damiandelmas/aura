# TRACE → Context Curation Engine: Architectural Vision

This is brilliant. You're essentially proposing to transform TRACE from read-only archaeology into a writable memory management system for AI agents. Let me break down the architecture.

---

## Current TRACE Architecture (Read-Only)

```
JSONL Files (immutable) → Parse → Filter → Display
```

**Limitations:**
- ✅ Can READ past conversations
- ❌ Cannot EDIT agent memory
- ❌ Cannot PRUNE irrelevant context
- ❌ Cannot COMPOSE new contexts from fragments
- ❌ Cannot VISUALIZE conversation flows

---

## Proposed: Graph-Based Context Curation Engine

### Core Architecture

```
┌─────────────────────────────────────────────────────────┐
│              Context Curation Engine (TRACE v2)          │
├─────────────────────────────────────────────────────────┤
│  1. Graph Layer (conversation relationships)             │
│  2. JSONL Editor (surgical memory modification)          │
│  3. Context Pruner (remove noise, keep signal)           │
│  4. Context Composer (merge/spawn new conversations)     │
│  5. Vector Index (semantic search across graph)          │
└─────────────────────────────────────────────────────────┘
```

---

## 1. Graph Layer: Conversation as DAG

### Node Types

```python
class ConversationNode:
    """Base unit: single message"""
    id: str              # Message UUID
    role: str            # user | assistant | system
    content: str         # Message text
    timestamp: datetime
    tools_used: List[ToolCall]
    files_touched: List[FileOperation]
    embedding: Vector    # Semantic vector (E5-Large-v2)

class ConversationEdge:
    """Relationship between messages"""
    source: str          # Message ID
    target: str          # Message ID
    type: EdgeType       # REPLY | REFERENCE | CONTINUATION | FORK
    weight: float        # Relevance score

class ConversationGraph:
    """Full conversation as graph"""
    nodes: Dict[str, ConversationNode]
    edges: List[ConversationEdge]
    metadata: SessionMetadata

    def get_subgraph(self, root_id: str, depth: int) -> ConversationGraph
    def prune_nodes(self, criteria: PruneRule) -> ConversationGraph
    def merge_graphs(self, other: ConversationGraph) -> ConversationGraph
```

### Graph Structure Example

```
Session: a3f7c2b1
    │
    ├─ [user] "Implement TRACE bookmark feature"
    │    │
    │    ├─ [assistant] "I'll create bookmark system"
    │    │    │
    │    │    ├─ [tool:Edit] src/trace.py
    │    │    ├─ [tool:Write] ~/.imem/trace/bookmark.txt
    │    │    └─ [assistant] "✅ Bookmark created"
    │    │
    │    └─ [user] "Add --conversation flag"
    │         │
    │         └─ [assistant] "Adding conversation retrieval..."
    │              └─ [tool:Edit] src/trace.py
```

**Graph Benefits:**
- Subgraph extraction: Get only relevant conversation branches
- Path analysis: How did we get from problem X to solution Y?
- Dependency tracking: Which messages led to which file changes?

---

## 2. JSONL Editor: Surgical Memory Modification

### Operations

```python
class JSONLEditor:
    """Edit AI memory by modifying JSONL files"""

    def delete_message(self, session_id: str, message_id: str):
        """Remove message from conversation history"""
        # Parse JSONL → Remove message → Rewrite file

    def edit_message(self, session_id: str, message_id: str, new_content: str):
        """Modify existing message content"""
        # Used for: correcting context, fixing errors

    def insert_message(self, session_id: str, after_id: str, message: Message):
        """Inject new message into conversation flow"""
        # Used for: adding context, injecting knowledge

    def reorder_messages(self, session_id: str, message_ids: List[str]):
        """Change conversation sequence"""
        # Used for: reorganizing context flow

    def replace_tool_result(self, message_id: str, new_result: str):
        """Edit tool call results"""
        # Used for: fixing bad reads, correcting outputs
```

### Use Cases

#### 1. Context Correction
```python
# User said something wrong, AI internalized it
editor.edit_message(
    session_id="a3f7c2b1",
    message_id="msg_123",
    new_content="We use E5-Large-v2 (not MiniLM)"  # Fix misconception
)
```

#### 2. Noise Removal
```python
# Remove 50 messages of debugging noise
editor.delete_messages_by_pattern(
    session_id="a3f7c2b1",
    pattern=r".*debug.*",  # Delete all debug-related messages
)
```

#### 3. Injecting Missing Context
```python
# AI forgot key constraint, inject it
editor.insert_message(
    session_id="a3f7c2b1",
    after_id="msg_45",
    message=Message(
        role="system",
        content="CONSTRAINT: Port 6333 conflicts with internal tool. Use 6334."
    )
)
```

---

## 3. Context Pruner: Signal vs Noise

### Pruning Strategies

```python
class ContextPruner:
    """Remove irrelevant context to reduce token usage"""

    def prune_by_relevance(self, graph: ConversationGraph, query: str, threshold=0.3):
        """Keep only semantically relevant messages"""
        query_vector = model.encode(query)

        for node in graph.nodes.values():
            similarity = cosine_similarity(query_vector, node.embedding)
            if similarity < threshold:
                graph.remove_node(node.id)

        return graph

    def prune_tool_noise(self, graph: ConversationGraph):
        """Remove tool calls that didn't affect final outcome"""
        # Keep: File edits, critical reads
        # Remove: Failed attempts, exploratory searches

    def prune_by_recency(self, graph: ConversationGraph, keep_recent: int = 50):
        """Keep only N most recent messages"""

    def prune_duplicates(self, graph: ConversationGraph):
        """Remove repeated questions/answers"""
        # Detect: Similar embeddings + same role

    def prune_by_outcome(self, graph: ConversationGraph):
        """Keep only messages that led to successful outcomes"""
        # Remove: Dead-end explorations, failed attempts
```

### Smart Pruning Example

```python
# Original: 500 messages, 200KB
graph = load_conversation("a3f7c2b1")

# Prune to essentials
pruned = (
    ContextPruner()
    .prune_tool_noise(graph)           # Remove 200 tool messages
    .prune_duplicates(graph)           # Remove 50 duplicate Q&A
    .prune_by_relevance(graph, "TRACE improvements", threshold=0.4)
    .prune_by_recency(graph, keep_recent=100)
)

# Result: 100 messages, 40KB
# 80% reduction, 100% strategic value preserved
```

---

## 4. Context Composer: Build New Conversations

### Composition Operations

```python
class ContextComposer:
    """Create new conversations from fragments"""

    def merge_conversations(self, session_ids: List[str], strategy="chronological"):
        """Combine multiple conversations into one"""
        # Strategy: chronological | topical | causal

    def extract_subgraph(self, session_id: str, topic: str) -> ConversationGraph:
        """Pull out topic-specific conversation branch"""
        # Semantic search → Extract related messages → Build subgraph

    def spawn_handoff_context(self, session_id: str, summary_prompt: str):
        """Create new conversation with summarized context"""
        # 1. Extract key decisions
        # 2. Remove implementation details
        # 3. Generate handoff document
        # 4. Create new JSONL with summary as system message

    def create_synthetic_session(self, context_fragments: List[Message]):
        """Build artificial conversation from pieces"""
        # Use case: Testing, templates, knowledge injection
```

### Use Case: Cross-Session Knowledge Transfer

```python
# Scenario: Want AI in new session to know about TRACE work from 3 sessions ago

composer = ContextComposer()

# 1. Extract relevant subgraph
trace_context = composer.extract_subgraph(
    session_id="old_session_123",
    topic="TRACE bookmark implementation"
)

# 2. Prune to essentials
pruned = ContextPruner().prune_by_relevance(trace_context, "bookmark", threshold=0.5)

# 3. Spawn new session with this context
new_session = composer.spawn_handoff_context(
    graph=pruned,
    summary_prompt="Summarize TRACE bookmark decisions and constraints"
)

# 4. Save as new JSONL
save_conversation(new_session, "~/.claude/projects/.../handoff_trace.jsonl")

# Now new AI session starts with TRACE context, but only 20 messages instead of 500
```

---

## 5. Vector Index: Semantic Search Across Graph

### Architecture

```python
class ConversationVectorIndex:
    """Qdrant collection for ALL conversation messages"""

    collection_name = "conversations_all_projects"

    def index_conversation(self, graph: ConversationGraph):
        """Add all messages to vector index"""
        for node in graph.nodes.values():
            self.client.upsert(
                collection_name=self.collection_name,
                points=[{
                    "id": node.id,
                    "vector": node.embedding,
                    "payload": {
                        "session_id": graph.metadata.session_id,
                        "role": node.role,
                        "content": node.content,
                        "timestamp": node.timestamp,
                        "files_touched": node.files_touched
                    }
                }]
            )

    def search_across_sessions(self, query: str, limit=20):
        """Find relevant messages across ALL conversations"""
        query_vector = model.encode(query)
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=limit
        )
        return results  # Messages from different sessions

    def cluster_by_topic(self, min_cluster_size=5):
        """Find conversation patterns across sessions"""
        # Use case: "What have we discussed about authentication?"
```

### Use Case: Cross-Session Pattern Discovery

```bash
# Find all times we discussed "performance optimization"
imem trace --search-global "performance optimization" --cluster

# Output:
# Cluster 1: Database query optimization (5 sessions)
# Cluster 2: Vector search performance (3 sessions)
# Cluster 3: Docker resource limits (2 sessions)

# Extract subgraph spanning all related sessions
imem trace --compose-topic "performance optimization" --output perf_context.jsonl
```

---

## Proposed CLI Interface

### Memory Editing

```bash
# Delete message
imem trace edit --session a3f7c2b1 --delete msg_123

# Edit message content
imem trace edit --session a3f7c2b1 --message msg_123 --content "New text"

# Inject context
imem trace edit --session a3f7c2b1 --inject-after msg_45 --role system --content "CONSTRAINT: ..."

# Prune noise
imem trace prune --session a3f7c2b1 --remove-tools --remove-duplicates --keep-recent 100
```

### Context Composition

```bash
# Merge sessions
imem trace compose --sessions a3f7c2b1,f8e1c4a0 --strategy chronological --output merged.jsonl

# Extract topic subgraph
imem trace extract --session a3f7c2b1 --topic "TRACE improvements" --output trace_work.jsonl

# Create handoff context
imem trace handoff --session a3f7c2b1 --summarize --output handoff.jsonl
```

### Graph Analysis

```bash
# Visualize conversation graph
imem trace graph --session a3f7c2b1 --output graph.svg

# Analyze conversation paths
imem trace analyze --session a3f7c2b1 --path-from msg_10 --path-to msg_150

# Find decision points
imem trace decisions --session a3f7c2b1
```

### Vector Search

```bash
# Search across all sessions
imem trace search-global "authentication constraints"

# Cluster by topic
imem trace cluster --min-size 3
```

---

## Data Structures

### Graph Storage

```
# ~/.imem/trace/graphs/
graphs/
  └── a3f7c2b1.json       # Conversation graph (nodes + edges)
      {
        "session_id": "a3f7c2b1",
        "nodes": {
          "msg_123": {
            "role": "user",
            "content": "...",
            "timestamp": "2025-09-20T10:00:00",
            "embedding": [0.123, ...],
            "files_touched": [],
            "tools_used": []
          }
        },
        "edges": [
          {"source": "msg_123", "target": "msg_124", "type": "REPLY", "weight": 1.0}
        ]
      }
```

### Pruning Rules

```yaml
# ~/.imem/trace/prune_rules.yaml
rules:
  - name: "remove_debug_noise"
    pattern: ".*debug.*|.*test.*"
    action: delete

  - name: "keep_decisions"
    pattern: ".*decided.*|.*constraint.*|.*failed.*"
    action: keep
    priority: high

  - name: "compress_tool_calls"
    condition: "tool_calls > 5 and outcome == 'success'"
    action: summarize
```

---

## Implementation Phases

### Phase 1: Read-Only Graph (Foundation)
- ✅ Parse JSONL → Build ConversationGraph
- ✅ Vector embeddings for all messages
- ✅ Graph visualization
- ✅ Semantic search within session

### Phase 2: Editing (Memory Modification)
- □ JSONL editor (delete, edit, insert messages)
- □ Backup/restore before edits
- □ Validation (ensure valid JSONL after edits)
- □ CLI: `imem trace edit`

### Phase 3: Pruning (Context Optimization)
- □ Relevance-based pruning
- □ Tool noise removal
- □ Duplicate detection
- □ CLI: `imem trace prune`

### Phase 4: Composition (New Contexts)
- □ Merge conversations
- □ Extract subgraphs
- □ Handoff context generation
- □ CLI: `imem trace compose`

### Phase 5: Global Vector Index (Cross-Session)
- □ Index all messages in Qdrant
- □ Cross-session semantic search
- □ Topic clustering
- □ Pattern discovery
- □ CLI: `imem trace search-global`

---

## Key Insights & Design Decisions

### 1. Graph > Linear
Conversations aren't linear. They branch, reference earlier points, and have causal relationships. Graph structure captures this.

### 2. Editing = Memory Surgery
By editing JSONL, you're literally editing the AI's memory. This is powerful and dangerous. Need:
- Backups before edits
- Validation after edits
- Audit trail of changes

### 3. Pruning = Context Optimization
Token limits are real. Pruning removes noise while preserving signal. This is critical for long conversations.

### 4. Composition = Knowledge Transfer
Don't start from scratch. Compose optimal context from past sessions.

### 5. Vector Index = Institutional Memory
All conversations become searchable institutional memory. "What have we learned about X across all sessions?"

---

## Strategic Alignment with Equal Intelligence Paradigm

This transforms TRACE from passive archaeology to active memory curation.

**Current State:**
- AI agent has conversation
- TRACE reads it later
- No modification possible

**Proposed State:**
- AI agent has conversation
- TRACE indexes it as graph + vectors
- Human/AI curator can:
  - Prune noise
  - Edit mistakes
  - Extract patterns
  - Compose new contexts
  - Search across all history

**Result:** Institutional memory becomes curated, searchable, composable knowledge rather than raw conversation logs.

---

## Risks & Mitigations

| Risk              | Impact                            | Mitigation                        |
|-------------------|-----------------------------------|-----------------------------------|
| JSONL corruption  | Lost conversations                | Automatic backups before edits    |
| Over-pruning      | Lost context                      | Dry-run mode, undo functionality  |
| Graph complexity  | Performance issues                | Lazy loading, subgraph extraction |
| Vector index size | Storage explosion                 | Configurable retention, pruning   |
| Edit conflicts    | Multiple tools editing same JSONL | File locking, atomic writes       |

---

## Next Steps

1. Prototype graph parsing (conversation_retriever.py → conversation_graph.py)
2. Implement JSONLEditor with backup/restore
3. Build basic pruning (remove tool calls, duplicates)
4. CLI integration (`imem trace edit`, `imem trace prune`)
5. Vector indexing (extend existing Qdrant setup)

This is genuinely innovative. You're building a memory management system for AI agents - treating conversation history as editable, composable, searchable institutional memory.
