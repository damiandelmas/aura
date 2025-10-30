TRACE vs IMEM Vector Search - Different Jobs

What IMEM Does Better (Semantic)

- "Find conversations about authentication" → Semantic similarity across all indexed conversations
- "Show me error handling patterns" → Conceptual search across scattered discussions
- Cross-session patterns → "How have we solved rate limiting across all projects?"

What TRACE Does Better (Structural)

1. Deterministic Session Operations
# TRACE: "Give me THIS session"
trace show chronicle abc123

# IMEM: "Find sessions about X" (might miss the one you want)
imem search conversations "authentication"
→ When you know the session, TRACE is direct access

2. Structured Views
trace show files abc123     # Just the files modified
trace show patches abc123   # Just the diffs
trace show tools abc123     # Just tool usage stats
→ IMEM returns chunks, TRACE returns structured data

3. Programmatic Access
# TRACE: Parse JSONL directly
retrieval = ConversationRetrieval()
entries = retrieval.load_conversation(path)
patches = retrieval.get_patches(entries)

# IMEM: Query vectors, reconstruct from chunks
results = client.search("show me patches", filter={'chunk_type': 'patch'})
→ TRACE gives you raw data structures, IMEM gives you search results

4. Zero-Setup Discovery
# Project not indexed yet?
trace list --marker "bug fix"  # Works immediately
→ TRACE is filesystem-direct, IMEM requires indexing

---
TRACE's Unique Value Propositions

1. Cold Start Tool (Pre-Indexing)

New project, not indexed yet:
trace list                    # Instant discovery
trace show chronicle xyz      # Read session
trace export chronicle xyz    # Context for next agent
No Qdrant running, no collection created, no waiting.

2. Agent Handoff Format

trace export chronicle abc123 -o handoff.md
# → Clean H2-section markdown optimized for agent reading
IMEM search returns scored chunks. TRACE export returns complete chronological story.

3. Debugging/Archaeology

# "What files did we change in that session?"
trace show files abc123

# "What tools did we use?"
trace show tools abc123

# "Show me just the code diffs"
trace show patches abc123
Structured queries that IMEM search can't easily replicate.

4. API for Programmatic Tools

# Build custom analysis tools
from aura_trace import ConversationRetrieval

retrieval = ConversationRetrieval()
for session in all_sessions:
     entries = retrieval.load_conversation(session)
     patches = retrieval.get_patches(entries)
     # Analyze code churn, file frequency, etc.
TRACE is a library. IMEM is a search service.

5. Global Discovery (Cross-Project)

trace list  # Shows ALL conversations across ALL projects
IMEM is per-project. TRACE is global filesystem view.

---
Complementary Architecture

┌─────────────────────────────────────────┐
│  User Query Intent                      │
└─────────────────────────────────────────┘
               │
     ┌────────┴────────┐
     │                 │
Semantic          Deterministic
"Find..."         "Give me..."
     │                 │
     ▼                 ▼
┌─────────┐       ┌─────────┐
│  IMEM   │       │  TRACE  │
│ Search  │       │ Retrieve│
└─────────┘       └─────────┘
     │                 │
Vector Similarity  Direct Access
Conceptual Match   Structural Query
Ranked Results     Complete Data

Use Cases by Tool

Use IMEM when:
- "Find conversations about X" (don't know session ID)
- "Show me patterns across all authentication discussions"
- "What did we say about rate limiting?" (semantic)

Use TRACE when:
- "Show me session abc123" (know the ID)
- "What files changed in that session?" (structured query)
- "Export this session for agent handoff" (complete timeline)
- "List all recent conversations" (no indexing needed)
- "Parse this JSONL programmatically" (API usage)

---
Recommendation: Keep Both, Different Layers

TRACE = Data Access Layer
- Filesystem-direct
- Zero-setup discovery
- Structured queries
- Programmatic API
- Agent handoff format

IMEM = Intelligence Layer
- Semantic search
- Cross-session patterns
- Conceptual queries
- Ranked relevance

Workflow:
1. TRACE discovers sessions (fast, no indexing)
2. User finds relevant session via content marker
3. TRACE exports chronicle for agent
4. Agent analyzes, creates changelog
5. IMEM indexes changelog + conversation
6. Future semantic search enabled

They don't compete - they stack:
- TRACE = "Give me the raw data"
- IMEM = "Find relevant insights"

Example:
# Discovery phase (TRACE)
trace list --marker "authentication bug"
# → Found session abc123

# Direct access (TRACE)
trace show files abc123
# → Modified: auth.py, middleware.py

# Semantic search (IMEM)
imem search conversations "authentication bug fix patterns"
# → Returns relevant chunks from multiple sessions

Make sense? TRACE is infrastructure, IMEM is intelligence on top of that infrastructure.