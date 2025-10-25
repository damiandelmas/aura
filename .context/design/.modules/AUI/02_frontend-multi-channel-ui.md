# Multi-Channel Conversation UI: Vision

**Part of:** TRACE-TALK vision (`00_vision-trace-talk.md`)
**Enables:** Agent-to-agent communication through visual context surfacing
**Backend:** Context Curation Engine (`01_backend-curation-engine.md`)
**Status:** Vision (not implemented)

---

## Core Vision

Transform TRACE from CLI-only to visual multi-channel interface where:
- Multiple conversations visible simultaneously
- Relevant context surfaces while coding
- Conversation becomes queryable dashboard
- Agent memory becomes spatial, not linear

**This is NOT about real-time extraction** - it's about better UX for post-conversation archaeology.

**Connection to TRACE-TALK:** Visual interface enables agent-to-agent communication by surfacing relevant past conversations automatically, removing query friction.

---

## Key UX Concepts

### 1. Multi-Conversation View

**Visual Layout:**
```
┌─────────────────────────────────────────────────┐
│ Active Conversation (Main)                      │
│ Current work-in-progress                        │
├─────────────────────────────────────────────────┤
│ Related Conversations (Side Panels)             │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐│
│ │ TRACE impl  │ │ Auth work   │ │ DB refactor ││
│ │ (3 days ago)│ │ (1 week ago)│ │ (2 weeks)   ││
│ └─────────────┘ └─────────────┘ └─────────────┘│
└─────────────────────────────────────────────────┘
```

**Benefits:**
- See current work + relevant history simultaneously
- Spatial memory (conversations in quadrants, not lists)
- Quick context switching (click panel, not CLI query)

---

### 2. Visual Context Surfacing

**Semantic Proximity:**
When working on auth, automatically show panels for:
- Past auth conversations
- Related security discussions
- Constraint decisions about auth

**Visual Indicators:**
- Color coding by topic (auth=blue, DB=green, etc.)
- Recency fade (older = more transparent)
- Relevance glow (highly related = highlighted border)

---

### 3. Conversation as Dashboard

**Not a chat log - a knowledge dashboard:**

```
┌─────────────────────────────────────────────────┐
│ Authentication Implementation (Oct 15)          │
├─────────────────────────────────────────────────┤
│ Key Decisions:                                  │
│   • JWT tokens (rejected: sessions)            │
│   • 24hr expiry                                 │
│   • Refresh token rotation                     │
├─────────────────────────────────────────────────┤
│ Constraints Found:                              │
│   • Port 6333 conflicts (use 6334)             │
│   • Claude API rate limits                     │
├─────────────────────────────────────────────────┤
│ Files Changed:                                  │
│   • auth/middleware.py                         │
│   • api/endpoints.py                           │
└─────────────────────────────────────────────────┘
```

**Dashboard vs Chat:**
- Extract: Decisions, Constraints, Failures
- Hide: Debug noise, failed attempts
- Show: Outcomes, not process

---

### 4. Thread Visualization

**Conversation Graph (not linear):**
```
User: "Implement auth"
  ├─→ Assistant: "Using JWT"
  │     └─→ [Edit: auth/middleware.py]
  │           └─→ User: "Add refresh tokens"
  │                 └─→ Assistant: "Done"
  │
  └─→ User: "What about rate limiting?" (fork)
        └─→ Assistant: "Separate concern..."
```

**Visual Benefits:**
- See conversation branches (not just linear flow)
- Identify decision points (where we forked)
- Understand causal relationships (this led to that)

---

### 5. Cross-Conversation Patterns

**Pattern View:**
```
┌─────────────────────────────────────────────────┐
│ Pattern: "Port Conflicts"                       │
├─────────────────────────────────────────────────┤
│ Occurrences across 3 conversations:             │
│   • Oct 10: Qdrant port 6333 → 6334            │
│   • Oct 15: Redis port conflict                 │
│   • Oct 20: Postgres port remapping            │
├─────────────────────────────────────────────────┤
│ Pattern: Always check port availability first   │
└─────────────────────────────────────────────────┘
```

**Visual Pattern Recognition:**
- Cluster similar conversations
- Show recurring constraints
- Surface common solutions

---

## Design Principles

### 1. Context-Aware, Not Interruptive
- Surface context **without prompting**
- No validation popups during active conversation
- Passive awareness, not active distraction

### 2. Spatial Memory
- Conversations have visual location (panels, quadrants)
- Muscle memory: "Auth work is top-right panel"
- Not searchable archive - browsable workspace

### 3. Multi-Temporal
- Show past (related conversations)
- Show present (active conversation)
- Show future (extracted patterns, recommendations)

### 4. Query-Free Discovery
- Relevant context auto-surfaces
- Visual proximity = semantic proximity
- Don't need to know what to ask for

---

## Implementation Notes

**Backend (Already Exists):**
- ✅ TRACE retrieval (finder, retrieval, formatter)
- ✅ IMEM vector search (semantic similarity)
- ✅ Graph structures (from curation engine spec)

**Frontend (Not Built):**
- ❌ Multi-panel UI framework
- ❌ Visual conversation renderer
- ❌ Semantic proximity detection
- ❌ Pattern clustering visualization

**Separation:**
Backend = data/retrieval (TRACE + IMEM)
Frontend = presentation/UX (future work)

---

## Use Cases

### Use Case 1: Continuation from Past Work
**Scenario:** Starting new session about auth, 3 days after previous auth work

**Without Multi-Channel UI:**
```bash
# Must remember and query
imem conversations search "authentication"
trace show <session_id>
# Read output, mentally reconstruct context
```

**With Multi-Channel UI:**
```
Opens editor → UI auto-surfaces auth panel
Previous auth conversation visible in side panel
Click decision card → instant context
No CLI query needed
```

---

### Use Case 2: Cross-Project Intelligence
**Scenario:** Similar problem encountered in different project

**Without Multi-Channel UI:**
```bash
# Must know similar work exists
imem search "JSONB performance" --all-projects
# Sift through results
```

**With Multi-Channel UI:**
```
Working on Project B → UI detects similarity to Project A work
Project A conversation auto-surfaces in panel
Visual indicator: "Similar constraint found"
Click to see how Project A solved it
```

---

### Use Case 3: Pattern Recognition
**Scenario:** Repeating same mistake across conversations

**Without Multi-Channel UI:**
```bash
# No awareness of pattern until explicit analysis
```

**With Multi-Channel UI:**
```
Pattern detection running in background
Visual alert: "Port conflict pattern detected (3rd occurrence)"
Shows previous instances + pattern summary
Prevents repeat mistake
```

---

## Future Exploration

**Advanced Features (Phase 2+):**
- Conversation timelines (temporal visualization)
- 3D conversation graphs (spatial exploration)
- Collaborative curation (multi-user annotations)
- Conversation templates (reusable contexts)
- Cross-platform bridge (import claude.ai conversations)

**Integration Points:**
- VS Code extension (side panel integration)
- Browser extension (floating window)
- Desktop app (standalone conversation manager)
- CLI remains primary (UI is enhancement, not replacement)

---

## What This Is NOT

❌ **Not real-time extraction during conversation**
- No interruptions while coding
- No validation prompts
- No brothers spawning during active work

❌ **Not chat UI redesign**
- Not replacing Claude Code interface
- Complementary view, not replacement

❌ **Not automatic decision-making**
- UI surfaces context, human decides
- Recommendations, not automation

---

## Success Metrics

**Vision achieved when:**
- ✅ Relevant context visible without querying
- ✅ Conversation history feels spatial, not archived
- ✅ Patterns discovered visually, not analytically
- ✅ Context switches are instant (click, not command)
- ✅ Past work enhances present work seamlessly

---

## Related Documents

- `00_vision-trace-talk.md` - TRACE-TALK philosophical foundation
- `01_backend-curation-engine.md` - Backend graph/editing/composition spec
- `.context/document/architecture_imem.md` - Vector search implementation
- `.context/document/architecture_trace.md` - TRACE retrieval system

---

**This is UX vision only. Implementation details belong in future technical specs.**
