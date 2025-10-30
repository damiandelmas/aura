# UX Patterns: Bidirectional Navigation & Workflows

**Date:** 2025-10-18 19:19
**Type:** User Experience Documentation
**Status:** Active Design

---

## Overview

The two-tier retrieval system enables four core user workflows:

1. **Precision Search** - Find validated decisions in changelogs
2. **Source Verification** - Navigate from changelog to original conversation
3. **Discovery** - Find relevant conversations semantically
4. **Intelligent Querying** - Spawn brother agents to query conversations

Each workflow serves a different need. Users can navigate bidirectionally between validated knowledge (changelogs) and source material (conversations).

---

## Workflow 1: Precision Search (Changelog Retrieval)

### Use Case

**User wants:** Validated, structured knowledge about a specific decision.

**Example question:**
- "What did we decide about JWT authentication?"
- "What constraints influenced the database schema?"
- "What patterns did we use for API rate limiting?"

### Workflow

```
User query: "JWT authentication decision"
    ↓
Search changelogs (type='changelog', section='decision')
    ↓
Returns: Section-level results
    - H3: "Core Decision: JWT over Session Cookies"
    - Metadata: session_id, timestamp, h2_category
    ↓
User reads validated decision
    ↓
Optional: Click session_id → Jump to Workflow 2 (source verification)
```

### CLI Commands

**Search changelogs for decisions:**
```bash
imem search "JWT authentication" --type changelog --section decision
```

**Output:**
```
Found 3 results:

1. PostgreSQL Schema Design for Authentication [Score: 0.89]
   Section: Solution Architecture > Core Decision: JWT over Sessions
   Session: abc123def456
   Date: 2025-10-18

   "Chose JWT tokens over session cookies due to stateless API
   gateway requirement. Tokens enable horizontal scaling without
   shared session state..."

2. API Security Patterns [Score: 0.76]
   Section: Implementation > Token Validation Middleware
   Session: def456ghi789
   Date: 2025-10-15

   "Implemented JWT verification middleware using HS256 algorithm.
   Validates signature, checks expiry, extracts user claims..."
```

**Advanced filtering:**
```bash
# Security-related decisions only
imem search "authentication" --type changelog --section decision --category security

# Recent implementations (last 30 days)
imem search "JWT" --type changelog --section implementation --recent-days 30

# Ground truth specifications
imem search "auth schema" --type changelog --phase designate
```

### Benefits

✅ **Validated** - User approved via `/log:develop`
✅ **Structured** - H1→H2→H3 hierarchy
✅ **Surgical** - Section-level precision (not entire document)
✅ **Filtered** - By section_type, category, phase, date
✅ **Linked** - session_id connects to source conversation

---

## Workflow 2: Source Verification (Changelog → Conversation)

### Use Case

**User wants:** To see the original conversation that led to a decision.

**Example scenarios:**
- "Why did we choose JWT? I want to see what alternatives we discussed."
- "This decision seems odd, let me check the original conversation."
- "What was the user's original requirement?"

### Workflow

```
User reading changelog
    ↓
Sees: session_id: abc123def456
    ↓
Clicks session_id (or runs command)
    ↓
TRACE exports full conversation to markdown
    ↓
User views complete source material
    - All alternatives discussed
    - Dead ends explored
    - Full implementation details
    - Tool usage and patches
    ↓
Optional: Spawn brother agent to query conversation (Workflow 4)
```

### CLI Commands

**Export conversation from changelog metadata:**
```bash
# Method 1: Direct session ID
trace --session abc123 --export /tmp/conversation.md --all-messages

# Method 2: Auto-detect from changelog
trace --from-changelog .develop/.changes/251018-1538_abc123.md --export /tmp/context.md
```

**Quick view without export:**
```bash
# Show conversation summary
trace --session abc123 --summary

# Show key decisions (auto-extracted)
trace --session abc123 --decisions

# Show alternatives discussed
trace --session abc123 --alternatives
```

**Output example:**
```
📁 Conversation: abc123def456

**Duration:** 141 minutes
**Messages:** 591 (297 user + 294 assistant)
**Working Dir:** /home/user/projects/app

**Summary:**
Discussion about PostgreSQL schema design for authentication.
Explored MongoDB (rejected: weak consistency) and Redis sessions
(rejected: stateful architecture). Settled on PostgreSQL + JWT
tokens for horizontal scaling...

**Key Decisions:**
1. PostgreSQL over MongoDB - ACID guarantees critical
2. JWT tokens over sessions - Stateless architecture
3. HS256 signing algorithm - Simpler than RS256

**Alternatives Discussed:**
- MongoDB: Document flexibility, but no complex joins
- Redis Sessions: Fast but requires sticky sessions
- OAuth2: Considered, but overkill for simple auth

**Implementation:**
- Files modified: auth/middleware.py, auth/models.py, tests/
- Tool uses: 187 total (45 file edits, 12 test runs)
- Patches: 45 code changes across 23 files

📄 Full conversation: /tmp/conversation.md (2669 lines)
```

### Benefits

✅ **Complete context** - Full conversation, not just summary
✅ **All alternatives** - Including rejected options
✅ **Implementation details** - Full code, not just patterns
✅ **Debugging** - See reasoning behind decisions
✅ **Trust but verify** - Validate changelog against source

---

## Workflow 3: Discovery (Conversation Search)

### Use Case

**User wants:** To find relevant past conversations on a topic.

**Example questions:**
- "What conversations discussed database design?"
- "Have we talked about authentication recently?"
- "Find sessions where we modified auth/middleware.py"

### Workflow

```
User query: "database schema design"
    ↓
Search conversations (type='conversation')
    ↓
Returns: Conversation summaries (semantic match)
    - Summary 1: PostgreSQL schema design (session abc123)
    - Summary 2: MongoDB vs relational debate (session def456)
    - Summary 3: Migration strategy (session ghi789)
    ↓
User picks relevant conversation
    ↓
Option A: View full conversation (TRACE export)
Option B: Check if it has a changelog (has_changelog flag)
Option C: Query it with brother agent (Workflow 4)
```

### CLI Commands

**Search conversations semantically:**
```bash
imem search "database design" --type conversation
```

**Output:**
```
Found 5 conversations:

1. Session: abc123 [Score: 0.89, Duration: 141m, Messages: 591]
   Date: 2025-10-18 13:15
   Changelog: ✅ .develop/.changes/251018-1538_abc123.md

   "PostgreSQL schema design for authentication system. Explored
   alternatives (MongoDB, Redis) before settling on PostgreSQL + JWT.
   Implemented token middleware with refresh strategy..."

   Files: auth/middleware.py, auth/models.py, tests/test_auth.py
   Tools: Read(23), Edit(45), Bash(12)

2. Session: def456 [Score: 0.76, Duration: 89m, Messages: 342]
   Date: 2025-10-15 09:30
   Changelog: ❌ None

   "MongoDB vs relational database discussion. Evaluated trade-offs
   for user profile storage. Document flexibility vs complex joins..."

   Files: db/schema.py
   Tools: Read(12), Edit(8)

3. Session: ghi789 [Score: 0.68, Duration: 52m, Messages: 201]
   Date: 2025-10-12 14:20
   Changelog: ✅ .develop/.changes/251012-1420_ghi789.md

   "Database migration strategy from SQLite to PostgreSQL.
   Zero-downtime migration plan, data validation, rollback strategy..."
```

**Advanced filtering:**
```bash
# Recent conversations only
imem search "auth" --type conversation --recent-days 7

# Long conversations (>60 min, complex discussions)
imem search "schema" --type conversation --min-duration 60

# Conversations with changelogs (validated)
imem search "database" --type conversation --has-changelog

# Conversations without changelogs (orphaned)
imem search "API" --type conversation --no-changelog

# By file modified
imem search "middleware" --type conversation --file "auth/middleware.py"
```

### Benefits

✅ **Semantic discovery** - Find by meaning, not keywords
✅ **Time filtering** - Recent or historical
✅ **Changelog linkage** - See which are validated
✅ **Metadata filtering** - By duration, messages, files, tools
✅ **Full context on demand** - TRACE export available

---

## Workflow 4: Intelligent Querying (Brother Agent)

### Use Case

**User wants:** To ask specific questions about a past conversation.

**Example questions:**
- "Why did we choose PostgreSQL over MongoDB in session abc123?"
- "What security concerns were discussed in the auth conversation?"
- "How did we handle the edge case of expired tokens?"

### Workflow

```
User identifies relevant conversation (via Workflow 1, 2, or 3)
    ↓
User asks specific question
    ↓
TRACE exports conversation to markdown
    ↓
Brother agent (claude -p) spawned with:
  - Full conversation context (markdown)
  - User's specific question
    ↓
Brother analyzes conversation and answers
    ↓
Returns intelligent response based on conversation content
```

### CLI Commands

**Query a conversation:**
```bash
trace --session abc123 --ask "Why did we choose PostgreSQL over MongoDB?"
```

**Behind the scenes:**
```bash
# 1. Export conversation
trace --session abc123 --export /tmp/abc123.md --all-messages

# 2. Spawn brother agent
claude -p "You are answering on behalf of a past conversation.

CONTEXT:
$(cat /tmp/abc123.md)

QUESTION: Why did we choose PostgreSQL over MongoDB?

Answer based ONLY on the conversation above. If the answer isn't
discussed in the conversation, say so."
```

**Output example:**
```
Based on the conversation from 2025-10-18:

You chose PostgreSQL over MongoDB for three key reasons:

1. **ACID Guarantees**: The authentication system required strong
   consistency. MongoDB's eventual consistency model was considered
   too weak for auth tokens.

2. **Complex Joins**: You anticipated needing to join user profiles,
   roles, and permissions tables. PostgreSQL's relational model
   made this straightforward, while MongoDB would require application-
   level joins or denormalization.

3. **Production Experience**: The team had more production experience
   with PostgreSQL. MongoDB was discussed as "learning curve not
   worth it for this use case."

MongoDB was considered for its document flexibility and schema-less
design, but you decided the benefits didn't outweigh the trade-offs
for this specific use case.
```

**Advanced querying:**
```bash
# Multi-question query
trace --session abc123 --ask "1. Why PostgreSQL? 2. What alternatives were discussed? 3. Any security concerns?"

# Query with context from changelog
trace --session abc123 --with-changelog --ask "Does the changelog match what was actually discussed?"

# Batch querying (multiple sessions)
trace --sessions abc123,def456,ghi789 --ask "How did we approach authentication across these conversations?"
```

### Benefits

✅ **Intelligent analysis** - LLM understands context
✅ **Specific answers** - Targeted to user's question
✅ **Source-grounded** - Brother only uses conversation content
✅ **Multi-conversation** - Can query across sessions
✅ **Verification** - Check changelog against source

---

## Bidirectional Navigation Patterns

### Pattern 1: Precision → Source

**User journey:**
1. Search changelogs for decision
2. Read validated knowledge
3. Want more context → Click session_id
4. View full conversation
5. Optional: Query with brother

**Commands:**
```bash
# Step 1: Find decision
imem search "JWT" --type changelog --section decision

# Step 2: From result, get session_id
SESSION_ID=abc123

# Step 3: View source
trace --session $SESSION_ID --summary

# Step 4: Deep dive
trace --session $SESSION_ID --export /tmp/context.md --all-messages

# Step 5: Query
trace --session $SESSION_ID --ask "What security concerns were discussed?"
```

### Pattern 2: Discovery → Validation

**User journey:**
1. Search conversations for topic
2. Find relevant discussion
3. Check if validated → has_changelog flag
4. If yes, jump to changelog
5. If no, maybe create one with `/log:develop`

**Commands:**
```bash
# Step 1: Discover
imem search "database design" --type conversation

# Step 2: Check result
# Output shows: Changelog: ✅ .develop/.changes/251018-1538_abc123.md

# Step 3: View changelog
cat .develop/.changes/251018-1538_abc123.md

# Or search changelog directly
imem search "database" --type changelog --session abc123
```

### Pattern 3: Orphan Discovery

**User journey:**
1. Find conversations without changelogs
2. Review to see if they need validation
3. Run `/log:develop` to create changelog
4. Bidirectional link established

**Commands:**
```bash
# Find orphaned conversations
imem search "authentication" --type conversation --no-changelog

# Output:
# Session: xyz789 [No changelog]
# "JWT implementation discussion..."

# User decides: This should be validated!
# In Claude Code conversation:
User: "/log:develop xyz789"

# Changelog created, link established
```

### Pattern 4: Historical Research

**User journey:**
1. "How did we approach X over time?"
2. Search both changelogs AND conversations
3. Compare validated vs exploratory discussions
4. Identify pattern evolution

**Commands:**
```bash
# Search both tiers
imem search "authentication" --type changelog
imem search "authentication" --type conversation

# Compare:
# - Changelogs show: Final decisions, validated patterns
# - Conversations show: All alternatives, evolution over time

# Merge results by date to see evolution
trace --topic "auth" --timeline
```

---

## CLI Integration Roadmap

### Phase 1: Conversation Indexing (MVP)

**Goal:** Enable semantic conversation discovery

**Commands to add:**
```bash
# Index conversations
trace --index-all                    # One-time: all conversations
trace --index-recent 10              # Incremental: last 10

# Search conversations
imem search "query" --type conversation
```

**Status:** 🔄 In progress (30 lines of code)

### Phase 2: Bidirectional Navigation

**Goal:** Enable jumping between changelogs and conversations

**Commands to add:**
```bash
# Changelog → Conversation
trace --session abc123 --export /tmp/context.md
trace --from-changelog path.md --show-conversation

# Conversation → Changelog
trace --session abc123 --show-changelog
imem search "query" --type conversation --has-changelog
```

**Status:** ⏳ Future

### Phase 3: Intelligent Querying

**Goal:** Brother agent querying of conversations

**Commands to add:**
```bash
# Single conversation
trace --session abc123 --ask "Why PostgreSQL?"

# Multiple conversations
trace --sessions abc123,def456 --ask "Auth approach evolution?"

# With changelog context
trace --session abc123 --with-changelog --ask "Does changelog match conversation?"
```

**Status:** ⏳ Future

### Phase 4: Advanced Features

**Goal:** Hybrid scoring, timeline views, pattern analysis

**Commands to add:**
```bash
# Hybrid scoring
imem search "auth" --boost-recent --boost-complex

# Timeline view
trace --topic "database" --timeline

# Pattern discovery
imem patterns "authentication" --across-conversations
```

**Status:** ⏳ Future

---

## User Scenarios

### Scenario 1: New Developer Onboarding

**Context:** New developer joins, needs to understand auth system.

**Workflow:**
```bash
# Step 1: Find validated decisions
imem search "authentication" --type changelog --section decision

# Returns: 3 changelogs about auth

# Step 2: Read ground truth
cat .develop/.changes/251018-1538_abc123.md

# Step 3: Want more context
trace --session abc123 --summary

# Step 4: Deep dive on specific question
trace --session abc123 --ask "Why JWT over sessions? What alternatives were considered?"

# Step 5: Check implementation details
trace --session abc123 --files
```

**Result:** Developer understands not just WHAT we decided, but WHY, plus alternatives considered.

### Scenario 2: Debugging Production Issue

**Context:** Auth tokens expiring unexpectedly, need to understand implementation.

**Workflow:**
```bash
# Step 1: Find recent auth implementations
imem search "JWT token expiry" --type changelog --recent-days 60

# Step 2: Check conversation for edge cases
trace --session abc123 --ask "How did we handle token expiration edge cases?"

# Step 3: Look for related conversations
imem search "token refresh" --type conversation

# Step 4: Compare implementation vs discussion
trace --session abc123 --export /tmp/original.md
cat .develop/.changes/251018-1538_abc123.md
diff /tmp/original.md .develop/.changes/251018-1538_abc123.md
```

**Result:** Found edge case discussion that wasn't fully captured in changelog.

### Scenario 3: Architecture Review

**Context:** Planning to refactor auth, want to understand current approach and alternatives.

**Workflow:**
```bash
# Step 1: Get validated architecture
imem search "authentication architecture" --type changelog --section decision

# Step 2: Find all related conversations
imem search "auth" --type conversation --has-changelog

# Step 3: Build timeline
trace --topic "authentication" --sessions abc123,def456,ghi789 --timeline

# Step 4: Extract patterns
imem patterns "auth middleware" --across-sessions

# Step 5: Query for alternatives
trace --sessions abc123,def456,ghi789 --ask "What alternatives were discussed but rejected?"
```

**Result:** Complete picture of auth evolution, validated decisions, and rejected alternatives.

### Scenario 4: Code Review Reference

**Context:** Reviewing PR that changes auth approach, want to check if it aligns with past decisions.

**Workflow:**
```bash
# Step 1: Find original auth decision
imem search "JWT authentication decision" --type changelog

# Step 2: Check conversation for full context
trace --session abc123 --ask "What was the rationale for current auth approach?"

# Step 3: Query about proposed change
trace --session abc123 --ask "Was OAuth2 discussed? If so, why was it rejected?"

# Step 4: Verify alignment
# Read PR description
# Compare against conversation + changelog
```

**Result:** PR either aligns with past rationale or surfaces need to revisit decision.

---

## UI/UX Best Practices

### 1. Always Show Metadata

**Bad:**
```
Found: PostgreSQL Schema Design
```

**Good:**
```
Found: PostgreSQL Schema Design [Score: 0.89]
Session: abc123def456
Date: 2025-10-18 13:15
Type: Changelog (develop phase)
Section: Solution Architecture > Core Decision
Has conversation: ✅ (click to view)
```

**Why:** Users need context to evaluate relevance and navigate.

### 2. Make Links Clickable

**Bad:**
```
session_id: abc123def456
```

**Good:**
```
session_id: abc123def456
📄 View conversation: trace --session abc123
💬 Ask question: trace --session abc123 --ask "..."
```

**Why:** Clear affordances for navigation.

### 3. Show Bidirectional Status

**In changelogs:**
```yaml
---
session_id: abc123def456
conversation: ✅ Available
📄 View: trace --session abc123
---
```

**In conversation search results:**
```
Session: abc123
Changelog: ✅ .develop/.changes/251018-1538_abc123.md
📋 Read validated knowledge: cat .develop/.changes/251018-1538_abc123.md
```

**Why:** Users know what's available before clicking.

### 4. Progressive Disclosure in Outputs

**Summary view (default):**
```
Found 3 results:
1. PostgreSQL Schema Design [Score: 0.89] - abc123 - 2025-10-18
2. API Security Patterns [Score: 0.76] - def456 - 2025-10-15
3. Rate Limiting Implementation [Score: 0.68] - ghi789 - 2025-10-12
```

**Detailed view (--verbose):**
```
1. PostgreSQL Schema Design [Score: 0.89]
   Session: abc123def456
   Date: 2025-10-18 13:15
   Type: Changelog (develop phase)
   Section: Solution Architecture > Core Decision

   "Chose PostgreSQL over MongoDB for ACID guarantees and complex
   joins. Stateless JWT authentication with HS256 signing..."

   Files: auth/middleware.py, auth/models.py
   Related: Session def456 (MongoDB discussion)

   📄 View conversation: trace --session abc123
   💬 Ask question: trace --session abc123 --ask "..."
```

**Why:** Show summary by default, details on demand.

### 5. Error Handling with Suggestions

**Bad:**
```
Error: No changelog found for session abc123
```

**Good:**
```
⚠️  No changelog found for session abc123

This conversation hasn't been validated yet. You can:
1. View the conversation: trace --session abc123 --summary
2. Create a changelog: /log:develop abc123
3. Search for related changelogs: imem search "topic" --type changelog
```

**Why:** Errors should guide next actions.

---

## Summary

### Four Core Workflows

1. **Precision Search** - Find validated decisions (changelogs)
2. **Source Verification** - Navigate to original conversation
3. **Discovery** - Find relevant conversations semantically
4. **Intelligent Querying** - Ask questions to brother agent

### Key UX Principles

✅ **Bidirectional navigation** - Always show both directions
✅ **Metadata rich** - Session ID, timestamps, links
✅ **Progressive disclosure** - Summary → Details → Full context
✅ **Clear affordances** - Show what actions are available
✅ **Error guidance** - Suggest next steps, not just failures

### Implementation Priority

1. **MVP:** Conversation indexing + semantic search
2. **Phase 2:** Bidirectional linking in UI
3. **Phase 3:** Brother agent querying
4. **Phase 4:** Advanced features (hybrid scoring, timelines, patterns)

**The goal:** Make both changelogs and conversations easy to discover, navigate between, and query intelligently.
