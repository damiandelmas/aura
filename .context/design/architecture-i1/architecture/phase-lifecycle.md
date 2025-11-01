# Phase Lifecycle: Four-Stage Memory Evolution

---

## The Four Phases

```
design → designate → develop → document
```

**design**
- Abstract decisions
- Architectural choices
- Trade-off analysis
- High-level reasoning

**designate**
- Planning breakdown
- Task decomposition
- Implementation approach
- Execution strategy

**develop**
- Implementation changelogs
- Code decisions
- Technical details
- What was built, how

**document**
- Architecture explanations
- User guides
- System documentation
- Knowledge synthesis

---

## Genealogy Linking

**Each phase links back via session_id:**

```
Conversation (raw thinking)
    ↓ session_id
design (abstract decisions)
    ↓ session_id
develop (implementation)
    ↓ session_id
document (knowledge synthesis)
```

**Property:** Full reasoning chain from idea → implementation → documentation.

---

## Phase Transitions

**design → develop:**
- Abstract decisions become concrete implementations
- Architectural choices inform code structure

**develop → document:**
- Technical changelogs inform documentation
- Patterns extracted for knowledge transfer

**Genealogy traversal:**
- Query develop chunk → trace back to design reasoning
- Query document → see full implementation chain