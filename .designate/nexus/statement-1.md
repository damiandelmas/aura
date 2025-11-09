# Knowledge System Architecture

## Core Primitives

**1. PROJECT**
- Boundary: Git repo (.git directory)
- Isolation: Per-project knowledge stays isolated
- Portability: .nexus/ or .brain/.nexus/ travels with repo

**2. CORPUS**
- Documents: All .md files (four-phase lifecycle)
- Conversations: All .jsonl (decision traces)
- Code: All git-tracked files (implementation reality)
- Discovery: fd/rg (auto-discovery, no manual registration)

**3. PHASES**
design → designate → develop → document
(explore)  (plan)    (build)   (reference)
24 document types across phases

**4. VALIDATION**
- Git diff = ground truth
- What discussed vs what built
- Sources gain/lose credibility based on outcomes

**5. AUTHORITY**
- Contextual, not intrinsic
- Same document = different authority per project
- Determined at serve time, not index time

---

## Three-Tier Data Architecture

**Tier 0: Raw Sources**
- Heterogeneous: URLs, codebases, markdown, PDFs, APIs
- No standard format
- Things as they exist

**Tier 1: Normalized Interface**
- Always: markdown + frontmatter
- Universal adapter pattern
```yaml
---
source: https://example.com/doc
retrieval_method: webfetch
authority: 1
tags: [official, documentation]
---
[Summary of Tier 0 content]

Tier 2: Project Context
- Per-project wrappers in .brain/ or .nexus/
- Qualify sources at serve time
---
ref: tier1-entry-id
attention: 0.95
serve_as: "ground truth for this project"
---

---
Intelligence Stack

Layer 1: Structure Creation (Foundation Models)
Raw HTML/URL → GPT-4 → Structured markdown
*note* this is usually the AI Agent that one is using; Claude Code, Codex, Gemini CLI.
Cost: $0.01-0.02 per document (one-time)
When: Initial semantic understanding needed

Layer 2: Classification (Tiny Models)
Markdown chunk → Tiny classifier → Type + Confidence
Cost: $100-500 training (one-time), free inference
When: Repetitive, bounded tasks
Examples: Document type, domain, confidence scoring

Layer 3: Composition (AI Agents + Tools)
Agent with tools:
- compose (semantic + programmatic retrieval)
- temporal_cortex (validate against git)
- graph_api (materialize relationships)
- introspection (query capabilities)

Cost: $0.01-0.05 per complex task
When: Higher-order structures (KG, reports, synthesis)

Layer 4: Validation (Git Oracle)
Documentation claim → Git history → Validate/Invalidate
Credibility scoring per source
Pattern: hypothesis → implementation → verification

---
Data Flow

Index Time

1. Discovery (fd/rg)
   Sources discovered automatically
   ↓
2. Normalization (Foundation Model, one-time)
   Tier 0 → Tier 1 markdown
   Cost: ~$20 per 1000 sources
   ↓
3. Classification (Tiny Model)
   Chunk → Type + Metadata
   Cost: Free after training
   ↓
4. Storage
   Vector store (chunks + embeddings)
   Metadata (programmatic queries)
   Graph (relationships)

Query Time

1. User Query
   ↓
2. Retrieval (compose tool)
   Semantic: Vector similarity
   + Programmatic: Metadata filters
   ↓
3. Package Structuring
   Chunks grouped by:
   - Genealogy (session_id)
   - Temporal (evolution)
   - Graph (relationships)
   ↓
4. Authority Qualification (Tier 2)
   Same chunk → different authority per project
   Based on: attention, validation status, context
   ↓
5. Serve
   Structured package with context

Validation Loop

Source accessed → Implementation → Git commit
   ↓                                  ↓
Claim made                      Reality recorded
   ↓                                  ↓
   └──────→ Temporal Cortex ←────────┘
               ↓
         Credibility updated

---
Economic Model

One-Time Costs:
- Structure 1000 URLs: ~$20 (foundation model)
- Train tiny classifier: ~$200 (task-specific)
- Setup infrastructure: Manual

Ongoing Costs:
- Classification: Free (tiny model, local)
- Retrieval: Free (deterministic)
- Complex tasks: ~$0.05 (AI agent composition)
- Hosting: ~$50/month (small GPU optional)

Break-even vs API-only: ~2 months

---
Key Architectural Decisions

1. Self-Assembling
- No manual registration
- Git repos = project boundaries
- fd/rg discovery
- Zero bootstrap

2. Self-Validating
- Git diff adjudicates truth
- Sources ranked by outcomes
- Hypotheses tested automatically

3. Self-Documenting
- Conversations = decision rationale
- Session IDs = genealogy links
- Git history = timeline

4. Pluggable Components
Foundation model: GPT-4 | Claude | Local
Tiny models: Custom trained | HuggingFace packages
Vector store: Qdrant | Pinecone | ChromaDB
Graph: Ephemeral (runtime) | Neo4j (persistent)

5. Authority at Serve
- Index: Objective facts only
- Query: Context qualifies authority
- Same source = different meaning per project
