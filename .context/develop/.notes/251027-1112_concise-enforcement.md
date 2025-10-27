# Concise Output Enforcement

**Problem:** Output style "concise" forgotten after ~10 messages

**Solution:**
1. Hook: `/home/axp/.claude/hooks/concise-reminder.sh`
   - Fires every 5th user message
   - Reminds: "Tone = Concise, Spartan. Architecture-first. TodoWrite = state. No code unless asked."

2. Output style: `/home/axp/.claude/output-styles/concise-architecture-first.md`
   - Architecture > implementation
   - Technical terms: topology, data flow, abstraction boundaries
   - TodoWrite state changes = progress communication

**Hook structure:**
```
~/.claude/hooks/
├── aura-session-init.sh       (SessionStart)
├── aura-session-inject.sh     (UserPromptSubmit - AURA tracking)
└── concise-reminder.sh        (UserPromptSubmit - every 5th)
```

**Key insight:** TodoWrite state changes replace prose narration. Architecture diagrams > code.
