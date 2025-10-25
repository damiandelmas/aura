# Memory System Structure

## Three-Tier Organization

```
project/
├── .design/      # R&D for what to do
├── .develop/     # Record of what happened + new proven patterns
└── .document/    # Current stable state
```

## Layer Responsibilities

### `.design/` - Research & Planning
```
.design/
├── .changes/     # Sequential R&D sessions exploring options
└── .modules/     # Experimental frameworks/approaches (may fail)
```

**Purpose**: Explore possibilities before committing.
**Omega Point**: Feeds into `.develop/` when you take action.

### `.develop/` - Ground Truth & Emergent Patterns
```
.develop/
├── .changes/     # Chronological log of what actually happened
└── .modules/     # NEW proven patterns (100% real, needs own docs)
```

**Purpose**: Record reality as it unfolds. New patterns get dedicated space.
**Omega Point**: Real world. Changes are ground truth. Modules graduate to `.document/`.

### `.document/` - Stable Snapshot
```
.document/        # Current authoritative state (lean, integrated)
├── core-doc-1.md
├── core-doc-2.md
└── ...
```

**Purpose**: The "what is" - cleaned, integrated, authoritative.
**Omega Point**: This IS the artifact (for non-code projects).

## Data Flow

```
.design/
  └─> exploration → decision
                      ↓
                .develop/.changes/
                      ↓
                (pattern emerges)
                      ↓
                .develop/.modules/new-pattern/
                      ↓
                (matures & proves itself)
                      ↓
                .document/
                (integrated into stable docs)
```

## Key Distinctions

**`.design/.modules/`** = might not work, experimental
**`.develop/.modules/`** = 100% works, needs dedicated docs, too fresh to integrate
**`.document/`** = mature, integrated, stable

**Temporal intelligence** = `.changes/` (both design and develop)
**Specialized knowledge** = `.modules/` (both design and develop)
**Current state** = `.document/` (single source of truth)

## For AI Agents

- **Understanding current state** → Read `.document/`
- **Understanding how we got here** → Read `.develop/.changes/`
- **Understanding new patterns** → Read `.develop/.modules/`
- **Understanding what we explored** → Read `.design/.changes/`
- **Understanding experimental ideas** → Read `.design/.modules/`
