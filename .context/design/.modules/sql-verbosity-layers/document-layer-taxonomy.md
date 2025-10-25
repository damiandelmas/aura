# Document Layer Taxonomy

## Three-Layer Structure for `.document/`

For any project (code or decision-support), `.document/` contains three distinct layers:

```
.document/
├── schemas/           # Ground truth parameters
├── business-logic/    # Workflows and operations
└── architecture/      # System structure and design
```

---

## 1. schemas/ - Ground Truth Parameters

**Purpose**: Immutable core definitions that define WHAT the system fundamentally IS.

**Characteristics**:
- Sacred data that requires explicit confirmation to modify
- Single source of truth for canonical definitions
- External systems adapt to these, not vice versa
- Changes ripple through entire system

**Code Project Examples**:
- Canonical data models (courses.json, regions.json)
- API schemas and data structures
- Core entity definitions
- Database schema standards
- Prohibited patterns (what NOT to include)

**Non-Code Project Examples**:
- Contract terms and agreements
- Organizational structure
- Core policies and boundaries
- Fundamental constraints
- Sacred commitments

**Governance**:
- ❌ AI agents CANNOT modify without explicit user approval
- ✅ Version controlled with detailed rationale
- ✅ Changes require review and explicit confirmation
- ✅ Document who can modify (product owner, tech lead, user)

**Philosophy**: "When external reality changes, we update mappings and adapters. We NEVER casually change ground truth."

---

## 2. business-logic/ - Workflows & Operations

**Purpose**: Define WHAT the system DOES (operations, behaviors, processes).

**Characteristics**:
- User-facing functionality and workflows
- Business operations and processes
- NOT technical implementation details
- Focus on behavior, not code

**Code Project Examples**:
- User workflows (how users accomplish tasks)
- Feature operations (create, update, delete, 86-mark)
- Business rules and validations
- State transitions and triggers
- Operational procedures

**Non-Code Project Examples**:
- Decision-making workflows
- Communication protocols
- Negotiation processes
- Delegation patterns
- Operational procedures

**Governance**:
- ✅ AI agents can suggest improvements
- ✅ Updated based on discovered patterns
- ✅ Evolves with business needs
- ❌ Must align with schemas/ constraints

**Focus**: WHAT happens, not HOW it's implemented technically.

---

## 3. architecture/ - System Structure & Design

**Purpose**: Define HOW the system is structured and WHY it's designed that way.

**Characteristics**:
- Technical design decisions and rationale
- System structure and organization
- Mental models and conceptual frameworks
- Implementation patterns

**Code Project Examples**:
- System architecture diagrams
- Data flow documentation
- Component structure
- Technical design decisions
- Development patterns

**Non-Code Project Examples**:
- Mental models and metaphors
- Decision frameworks and trees
- Conceptual organization
- How to think about the system
- Strategic patterns

**Governance**:
- ✅ AI agents can suggest architectural improvements
- ✅ Updated as system evolves
- ✅ Documents discovered patterns
- ❌ Must respect schemas/ ground truth

**Focus**: HOW the system works and WHY it's designed that way.

---

## Relationship Between Layers

### Dependency Flow
```
schemas/           (defines WHAT IS)
    ↓ constrains
business-logic/    (defines WHAT DOES)
    ↓ implemented by
architecture/      (defines HOW & WHY)
```

### Change Propagation
- **schemas/ change** → ripples through business-logic/ and architecture/
- **business-logic/ change** → may require architecture/ updates
- **architecture/ change** → should NOT affect schemas/ or business-logic/

### AI Agent Interaction Rules
1. **Reading schemas/**: Always safe, required for context
2. **Modifying schemas/**: REQUIRES explicit user confirmation
3. **Modifying business-logic/**: Allowed with understanding of schemas/ constraints
4. **Modifying architecture/**: Allowed as system evolves

---

## Examples Across Project Types

### Code Project (NPTA Inventory)
```
.document/
├── schemas/
│   ├── courses.json              # Canonical course definitions
│   ├── key-types.json           # Ground truth taxonomy
│   └── essential-schema.md      # Required/prohibited fields
│
├── business-logic/
│   ├── inventory-workflows.md   # How inventory is managed
│   ├── key-generation.md        # How keys are created/assigned
│   └── validation-rules.md      # Business validation logic
│
└── architecture/
    ├── two-database-design.md   # Why we use two databases
    ├── data-flow.md             # How data moves through system
    └── design-principles.md     # Architectural decisions
```

### Code Project (Barbar Restaurant)
```
.document/
├── schemas/
│   ├── beer-schema-standard.md  # Essential beer data structure
│   ├── item-types.md            # Food/drink type taxonomy
│   └── board-structure.md       # Board/slot configuration
│
├── business-logic/
│   ├── core-workflows.md        # Feature, 86, inventory operations
│   ├── user-workflows.md        # How staff use the system
│   └── board-management.md      # Board/slot operations
│
└── architecture/
    ├── firestore-structure.md   # Database design
    ├── ui-patterns.md           # Component architecture
    └── state-management.md      # How state flows
```

### Decision-Support Project (Advisory Board)
```
.document/
├── schemas/
│   ├── engagement-terms.md      # Rate, scope, boundaries (immutable)
│   ├── team-structure.md        # Org chart, roles (ground truth)
│   └── core-commitments.md      # Sacred agreements
│
├── business-logic/
│   ├── negotiation-workflows.md # How rate negotiations happen
│   ├── delegation-patterns.md   # How work gets delegated
│   └── communication-protocols.md # Client interaction rules
│
└── architecture/
    ├── mental-models.md         # How to think about consulting
    ├── decision-trees.md        # When X, consider Y
    └── operational-guide.md     # How AI agents support you
```

---

## Key Distinctions

### schemas/ vs business-logic/
- **schemas/**: "A course has a code, name, region" (WHAT EXISTS)
- **business-logic/**: "To create a key, assign course + region + type" (WHAT HAPPENS)

### business-logic/ vs architecture/
- **business-logic/**: "Users can mark items as 86" (WHAT USERS DO)
- **architecture/**: "86 state is stored in Firestore with timestamp" (HOW IT WORKS)

### schemas/ immutability
- **schemas/**: "Our course codes are CPT, CES, PES" → requires user approval to change
- **business-logic/**: "Courses can be bundled" → can evolve based on needs
- **architecture/**: "Courses stored in Postgres" → can change implementation

---

## Governance Summary

| Layer | Modification Rule | Rationale |
|-------|------------------|-----------|
| **schemas/** | ❌ Requires explicit user confirmation | Core truth that system depends on |
| **business-logic/** | ✅ AI can propose changes | Operations evolve with needs |
| **architecture/** | ✅ AI can propose changes | Implementation can improve |

**Critical Rule**: AI agents must NEVER modify schemas/ without explicit user confirmation, as these are the ground truth parameters that define what the system fundamentally IS.
