# Advisory Board Memory System

## Structure for Decision Support

```
advisory-board/
├── .design/      # Research strategies before decisions
├── .develop/     # Record decisions made + emerging patterns
└── .document/    # Current state of your professional reality
```

## Layer Applications

### `.design/` - Strategic Research
```
.design/
├── .changes/
│   └── 251006-1400_researching-rate-negotiation-tactics.md
└── .modules/
    └── salary-benchmarking-framework/  # Exploring if this approach works
```

**What goes here**:
- Researching negotiation frameworks
- Exploring team delegation models
- Investigating relationship management approaches
- Analyzing competitive positioning strategies

**Omega point**: Your decisions (feeds into `.develop/.changes/` when you act)

### `.develop/` - Decision Log & Proven Patterns
```
.develop/
├── .changes/
│   ├── 251006-1500_negotiated-rate-with-jesse.md
│   ├── 251007-1000_delegated-auth-feature-to-team.md
│   └── 251008-0900_gaezelle-technical-briefing.md
└── .modules/
    ├── weekly-standup-format/       # NEW proven pattern, needs own docs
    ├── client-communication-protocol/
    └── team-delegation-framework/
```

**What goes here**:
- **Changes**: What actually happened (meetings, negotiations, decisions made)
- **Modules**: Proven new systems (weekly standup that works, communication protocol that's effective)

**Omega point**: Real world (your consulting practice, relationships, outcomes)

### `.document/` - Current State Snapshot
```
.document/
├── 01_context-and-state.md          # Jesse, Gaezelle, team, rate, current situation
├── 02_decision-framework.md         # "When X happens, consider Y" decision trees
├── 03_mental-models.md              # How to think about your consulting practice
└── 04_operational-guide.md          # Guide for AI agents supporting you
```

**What goes here**: Mature, integrated understanding of your professional reality

**Omega point**: This IS the artifact (the memory system is the deliverable)

## Example Flow

**Scenario: Negotiating rate increase**

1. **Research phase** (`.design/`)
   ```
   .design/.changes/251006-1400_rate-negotiation-research.md
   - Explored industry benchmarks
   - Researched negotiation tactics
   - Analyzed Jesse's business constraints
   ```

2. **Action taken** (`.develop/.changes/`)
   ```
   .develop/.changes/251006-1500_negotiated-with-jesse.md
   - Requested $20k, settled at $15k
   - Jesse cited budget constraints
   - Agreed to revisit in 3 months
   - Discovered: timing matters, Jesse needs advance notice
   ```

3. **Pattern emerges** (`.develop/.modules/`)
   ```
   .develop/.modules/rate-negotiation-playbook/
   ├── CONTEXT.md       # Why this exists (3 successful negotiations)
   ├── TIMING.md        # Quarter-end is best, needs 6-week notice
   ├── FRAMING.md       # Value demonstration approach that works
   └── EXAMPLES.md      # Real negotiations with outcomes
   ```

4. **Matures into snapshot** (`.document/`)
   ```
   Eventually integrates into:
   .document/02_decision-framework.md
   - Section: "When negotiating rates..."
   - Decision tree with proven approach
   - Discovered constraints included
   ```

## What AI Agents Read

**Agent helping with negotiation**:
1. `.document/01_context-and-state.md` → Current Jesse relationship, rate
2. `.develop/.modules/rate-negotiation-playbook/` → Proven approach
3. `.develop/.changes/251006*negotiated*` → What happened last time
4. `.design/.changes/*benchmarking*` → Research already done

**Agent helping with team delegation**:
1. `.document/01_context-and-state.md` → Current team structure
2. `.develop/.modules/team-delegation-framework/` → What works
3. `.develop/.changes/*delegated*` → Past delegation outcomes

## Key Differences from Code Projects

**Code Project**:
- `.document/` describes the codebase architecture
- Omega point = `src/` (the actual code)

**Advisory Board**:
- `.document/` describes your professional reality
- Omega point = your life (actual relationships, decisions, outcomes)

## Module Graduation Example

**New pattern**: Weekly team standup format

```
Week 1-4: Experimenting in real life
  ↓
.develop/.changes/
  - 251001_tried-new-standup-format.md
  - 251008_standup-format-working-well.md
  - 251015_team-loves-new-standup.md
  ↓
Pattern proven → Create module
  ↓
.develop/.modules/weekly-standup-format/
  ├── FORMAT.md        # Exact agenda that works
  ├── FACILITATION.md  # How to run it effectively
  └── EXAMPLES.md      # 4 weeks of successful standups
  ↓
After 3 months of success → Integrate
  ↓
.document/03_mental-models.md
  - Section: "Team Communication Patterns"
  - Standup format becomes standard practice
  ↓
Module can be archived/deleted (knowledge preserved in .document/)
```
