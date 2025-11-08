---
type: "ideation"
timestamp: "2025-10-11T01:47:00-0700"
---

# Design vs Designate: The Critical Distinction

## Question
> "What makes 'designate' different from 'design'? Why do we need both?"

## Key Insights

### Design = Exploration & Decision-Making
- **Input**: Question, problem, uncertainty
- **Process**: Explore multiple approaches, evaluate trade-offs
- **Output**: Decision + rationale + principles
- **State**: Fluid, exploratory, may change
- **Example**: "Should we use two schemas or one?"

### Designate = Refined Plan Staging
- **Input**: Design decisions (from design phase)
- **Process**: Refine into clear, actionable specifications
- **Output**: Clear plans, schemas, refined specifications
- **State**: Staged for implementation, clearly articulated
- **Example**: `courses.json` = clearly defined course list ready for implementation

### The Critical Distinction

**Design asks:** "What should we do?"
**Designate states:** "Here's the plan, clearly articulated."

**Design explores:** Multiple approaches, trade-offs, alternatives
**Designate refines:** Chosen approach into clear, implementable plan

**Design produces:** Decisions, principles, rationale
**Designate produces:** Plans, schemas, refined specifications

## Explored Ideas

### Why Not Just "Design" for Everything?

**Problem if we conflate them:**
```
design/251004-1830_schema-separation.md
  "We decided: Two schemas with cross-FK"

[Developer implements...]
  "Wait, which tables go in which schema?"
  "What are the exact foreign key constraints?"
  "What's the canonical list of courses?"
```

**Solution with separate phases:**
```
design/251004-1830_schema-separation.md
  "We decided: Two schemas with cross-FK"
  ↓
designate/inventory-schema-spec.md
  "inventory schema contains: keys, courses, providers"
  "orders schema contains: sales, sale_items, installments"
  "Cross-FK: sale_items.content_key_id → inventory.keys.id"
  ↓
designate/courses.json
  {"course_code": "CPT", "course_name": "Certified Personal Trainer", ...}
```

### Real-World Analogy

**Design = Architecture Review**
- Architects debate: "Should we use steel or concrete?"
- Consider trade-offs: cost, strength, time
- Decision: "Steel frame with concrete floors"
- Document rationale in design review notes

**Designate = Blueprint**
- Exact dimensions: "24" I-beam at grid line A3"
- Material specs: "Grade 50 steel, ASTM A992"
- Every detail specified
- Contractors build from THIS, not from design notes

### NPTA Project Example

**Design Phase:**
```markdown
# 251004-2050_course-code-normalization-strategy.md

## Question
> "Should we normalize NASM product names into clean course codes?"

## Exploration
### Approach 1: Use NASM codes directly
### Approach 2: Create our own abbreviations
### Approach 3: Hybrid with alias mapping ✓

## Decision
Hybrid normalization - canonical codes + alias table
```

**Designate Phase:**
```json
// ground-truth/courses.json (THE canonical course list)
[
  {
    "course_code": "CPT",
    "course_name": "Certified Personal Trainer",
    "provider": "NASM",
    "requires_content_key": true,
    "requires_exam_key": true,
    "regions": ["CANADA"]
  },
  {
    "course_code": "CNC",
    "course_name": "Certified Nutrition Coach",
    ...
  }
]
```

```json
// ground-truth/aliases/nasm-aliases.json (THE mapping table)
{
  "CPT 7 (COURSE)": {"course_code": "CPT", "key_type": "content"},
  "CPT 7 (EXAM)": {"course_code": "CPT", "key_type": "exam"},
  "Certified Personal Trainer + 5% GST": {"course_code": "CPT", "key_type": "combined"}
}
```

**Without designate:**
- Developer reads design doc: "We decided on hybrid normalization"
- Developer asks: "What are the canonical course codes?"
- Developer asks: "Which NASM names map to which codes?"
- Developer asks: "Who maintains the alias list?"

**With designate:**
- Developer imports `courses.json` (THE source of truth)
- Developer uses `nasm-aliases.json` (THE mapping)
- No ambiguity, no questions

## Outcomes

### Principle: Design Explores, Designate Declares

**Design Phase (Exploration):**
- Multiple approaches considered
- Trade-offs evaluated
- Decision made with rationale
- Principles established
- **Audience**: Decision-makers, architects, future designers

**Designate Phase (Plan Staging):**
- Clear, refined plans created
- Specifications articulated for implementation
- Ready-to-implement artifacts produced
- **Audience**: Implementers, developers, systems

### When to Create Designate Artifacts

**Triggers:**
1. Design decision needs concrete specification
2. Multiple people will reference the same data
3. System needs canonical source of truth
4. Implementation requires precise details

**Examples:**
- Design decision: "Use normalized course codes" → Designate: `courses.json`
- Design decision: "Four-phase roadmap" → Designate: `phase-one-plan.md`
- Design decision: "Hybrid architecture" → Designate: `architecture-spec.md`
- Design decision: "RESTful API" → Designate: `api-schema.yaml`

### Designate Artifact Types

**1. Data Schemas (JSON, YAML)**
```json
// courses.json - THE course definitions
// bundles.json - THE bundle configurations
// aliases.json - THE vendor mappings
```

**2. Plans & Roadmaps (Markdown)**
```markdown
// phase-one-plan.md - THE implementation sequence
// deployment-plan.md - THE rollout strategy
// migration-plan.md - THE data migration steps
```

**3. Specifications (Markdown, YAML, OpenAPI)**
```yaml
// api-spec.yaml - THE API contract
// database-schema.md - THE table definitions
// integration-spec.md - THE webhook formats
```

**4. Configuration Templates**
```yaml
// .env.example - THE required environment variables
// config.template.yaml - THE configuration structure
```

### RAG Implications

**Query: "What are the course codes?"**

Without `phase:` field:
```python
# Returns both design discussion AND staged plans
# User must manually figure out which is which
results = qdrant.search("course codes")
# → 251004-2050_course-code-normalization-strategy.md (design)
# → courses.json conceptual discussion
```

With `phase:` field:
```python
# Returns ONLY staged plans
results = qdrant.search(
  query="course codes",
  filter={'phase': 'designate'}
)
# → courses.json (refined, ready-to-implement list)
```

## References

### Similar Concepts in Other Domains

**Software Architecture:**
- Architecture Decision Records (ADR) = design
- System Design Document (SDD) = designate
- Implementation = develop
- API Documentation = document

**Construction:**
- Design review = design
- Blueprint = designate
- Building = develop
- As-built drawings = document

**Product Management:**
- Discovery = design
- PRD (Product Requirements Document) = designate
- Development = develop
- User documentation = document

### IMEM Integration

**Section-level chunking applies to both:**
- Design changelog: H3 per approach explored
- Designate spec: H3 per entity/concept defined

**Progressive disclosure:**
- Design: Variable field count (2-6 fields per decision)
- Designate: Variable depth (simple schema vs complex spec)

**Language-agnostic:**
- Design: Focus on concepts, not syntax
- Designate: Focus on structure, not implementation details
