---
type: "design"
timestamp: "2025-10-10T12:55:00-07:00"
---

# Knowledge Structure Design - Advisory Board System

## Question
> "Can we structure these differently? perhaps we want to have highly condensed, clean, and repeatable CORE changelogs and have a different format, or folder for different domains of data extracted from these conversations?"

## Key Insights

**Domain Separation is Critical**
- Strategic thinking (design) ≠ Ground truth events (develop) ≠ Current state (document)
- Mixing all insights into `.changes/` created 12 docs with 50-80% redundancy
- Each domain has different update frequency, audience, and purpose

**Design → Develop → Document Flow**
- `.design/` = R&D thinking, exploring options before decisions
- `.develop/` = Ground truth of what actually happened (created AFTER events)
- `.document/` = Maintained current state (updated, not accumulated)

**Not Just for Code - For Strategies Too**
- Monday meeting prep = feature being designed
- Can create modules in `.design/.modules/` for strategic implementations
- If approach works, becomes runbook in `.develop/.modules/`
- Eventually consolidated into `.document/architecture/` or `.document/schemas/`

## Explored Ideas

**Initial Complexity (Rejected)**
- Separate folders for: `.evidence/`, `.strategy/`, `.meta/`
- Too many buckets, over-engineered for use case
- Violated simplicity principle

**IMEM 3-Tier Applied Directly (Modified)**
- Started with code-focused tier model
- Adapted to business/relationship context
- Simplified to natural progression: design → develop → document

**Changelog Redundancy Problem**
- 12 changelogs created during conversation
- High overlap: organizational-dysfunction + over-delivery + gaezelle-dynamics
- Solution: Keep all in `.design/.changes/` as R&D artifacts
- Extract core patterns only when validated through real events

## Outcomes

**Final Structure**

```
.design/
├── .changes/              # R&D thinking (this entire conversation)
└── .modules/              # Designing approaches/strategies
    └── monday-meeting-prep/

.develop/
├── .changes/              # Ground truth events (written AFTER they happen)
└── .modules/              # Proven runbooks/patterns

.document/
├── architecture/          # Current relationship structures
│   └── README.md
└── schemas/               # Data formats/templates
    └── README.md

.conversations/
└── .vision/
    └── core-user-messages.md  # Pivotal moments
```

**Key Decisions**
1. All 12 strategic changelogs stay in `.design/.changes/` (they're R&D)
2. Meeting brief goes in `.design/.modules/monday-meeting-prep/`
3. After Monday: create `.develop/.changes/251014-monday-outcome.md`
4. If approach works: promote to `.develop/.modules/stakeholder-alignment/`
5. Current state lives in `.document/architecture/` and `.document/schemas/`

**Archaeological Retrieval Patterns**
- "What were we thinking?" → `.design/.changes/`
- "What actually happened?" → `.develop/.changes/`
- "What's the current state?" → `.document/`
- "What was the pivotal moment?" → `.conversations/.vision/`

## References

**IMEM Architecture Model**
- 3-tier progression: design → develop → document
- Modules concept: bundled runbooks for features/patterns
- Ground truth principle: never trust document alone, combine stable map + recent momentum

**Advisory Board Context**
- Jesse/Gaezelle relationship dynamics
- Monday alignment meeting preparation
- 3-month leverage building timeline
- Inventory system as mission-critical bottleneck
