---
type: "research"
timestamp: "2025-10-10T12:55:00-07:00"
---

# Changelog Structure Learning - When IMEM Template Breaks

## Question
> "Review ALL CHANGELOGS. How complementary are they, how redundant etc"

## Key Insights

**The Redundancy Problem**
- Created 12 changelogs during single strategic conversation
- Core 7 (created by assistant): Highly complementary, minimal overlap
- Extended 5 (found in folder): 50-80% redundant with core set
- Problem: Treating everything as "changelog" when they're different artifact types

**Wrong Application of Template**
- IMEM changelog template designed for: code changes, features, bug fixes
- This conversation was: strategic thinking, relationship analysis, meeting prep
- Forcing strategic artifacts into changelog format created bloat

**What Actually Needed Structure**
- Core patterns (reusable insights) - YES, use changelog template
- Evidence/documentation (emails, slack, value audit) - NO, different format
- Active plans (meeting prep, timeline) - NO, living documents
- Synthesis/retrospectives - NO, narrative format

## Explored Ideas

**Domain Separation Approaches**

**Option A: Multiple Subfolders** (rejected - too complex)
```
.develop/
├── .changes/     # Changelogs
├── .evidence/    # Artifacts
├── .strategy/    # Plans
└── .meta/        # Synthesis
```

**Option B: Tier + Minimal Domains** (rejected - still over-engineered)
```
.design/.changes/
.develop/.changes/ + .develop/.modules/
.document/
```

**Option C: Design → Develop → Document** (chosen - simplest)
```
.design/.changes/  # All R&D thinking
.develop/.changes/ # Ground truth events only
.document/         # Current state
```

**Consolidation Strategy Considered**
- Merge redundant changelogs into core set
- Archive older versions if later docs were refinements
- Extract unique insights from synthesis docs
- Keep tactical scripts separate from strategic frameworks

## Outcomes

**Decision: Keep All in .design/.changes/**
- This entire conversation = R&D/brainstorming
- All 12 docs represent thinking process (valuable for archaeology)
- Don't force consolidation during exploration phase
- Can consolidate LATER when extracting proven patterns

**Changelog Template Usage Rules**
1. **Use for**: Repeatable patterns, proven approaches, technical decisions
2. **Don't use for**: Meeting scripts, evidence compilation, active plans, narrative synthesis
3. **Trigger**: "Would this pattern apply to other situations/clients?" → Yes = changelog

**After-Action Reports Different From Changelogs**
- Monday meeting outcome = event documentation, not pattern
- Format should be: "What happened, decisions made, surprises, next steps"
- Don't force into changelog structure if it's one-time event

**Modules for Repeatable Implementations**
- Monday meeting prep → `.design/.modules/monday-meeting-prep/`
- If approach works → `.develop/.modules/stakeholder-alignment/`
- Bundle of related documents: strategy, scripts, evidence references, templates

## References

**IMEM Changelog Template Analysis**
- Works well for: Code changes, architectural decisions, pattern documentation
- Breaks down for: Strategic planning, relationship analysis, event documentation
- Principle: Template adapts to content, content doesn't force into template

**Redundancy Examples Found**
- organizational-dysfunction-patterns.md (80% overlap with over-delivery-into-void + gaezelle-power-dynamics)
- value-documentation-framework.md (60% overlap with 19-initiatives-audit + leverage-timeline)
- evidence-based-monday-script.md (70% overlap with monday-meeting-strategy, but tactical vs strategic)

**Learning for Future**
During exploration/design phase:
- Let documents emerge naturally
- Don't force structure too early
- Accept redundancy as part of thinking process
- Consolidate AFTER decisions made, not during exploration

**Meta-Insight**
The conversation about "how should we structure these changelogs" revealed the changelogs themselves were mis-categorized. They're design artifacts, not development changelogs. The structure question solved itself through the discussion.
