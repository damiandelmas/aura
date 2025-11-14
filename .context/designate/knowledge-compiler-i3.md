# IMEM: Institutional Memory for AI-Native Development

---

## The Core Geometry

```
THREE SOURCES → UNIVERSAL RESOLVER → CANONICAL SCHEMA → QUERY LAYER
```

---

## The Three Sources

**1. Markdown Documents**
- AI-generated or human-written
- Any structure, any format
- Contains: Decisions, patterns, context, implementation notes

**2. Conversation Logs**
- AI agent sessions (.jsonl)
- Intent → discussion → decision trace
- Links: session_id connects conversation to documents

**3. Git History**
- Code commits
- Truth oracle
- Validates: Did implementation match decision?

---

## The Universal Resolver

**Input:** Any markdown structure (four-phase, ADRs, READMEs, scattered notes)

**Process:**
1. Parse markdown → Extract headers + metadata
2. Observe patterns → Discover section types
3. Cluster variations → Resolve to canonical types
4. Infer phase → Map to: design | designate | develop | document

**Output:** Typed chunks with canonical metadata

**Property:** Works on ANY AI-assisted codebase without configuration

---

## The Canonical Schema

**Document Level (inherited by chunks):**
```
source: file_path | url | conversation_id
phase: design | designate | develop | document
session_id: links to originating conversation
timestamp: when created
category: resolved from document type
```

**Chunk Level (atomic queryable units):**
```
section_type: canonical type (decision, pattern, context, etc.)
section_name: specific instance name
content: the actual text
metadata: phase, session_id, + custom fields
```

**Property:** Single query level - chunks with inherited context

---

## The Intelligence Layer (MIND)

**Schema Evolution:**
- Observes headers across corpus
- Clusters variations → canonical types
- Exposes via introspection
- Evolves with usage

**Entity Resolution:**
- Normalizes terminology variations
- Maps: jwt, JWT, jwt-tokens → canonical "jwt"
- Enables query expansion

**Temporal Validation:**
- Compares documents vs git commits
- Detects: code diverged from documented decision
- Updates: authority scores based on outcomes

**Graph Composition:**
- Materializes relationships at query time
- Siblings (same file), genealogy (session_id), temporal (evolution)
- Ephemeral - computed from metadata, not stored

---

## The Query Layer

**Storage (pluggable):**
- Minimal: SQLite (metadata queries only)
- Extended: Qdrant (+ semantic search via embeddings)

**Both operate on same typed chunks - different query capabilities**

**Retrieval modes:**
- Metadata: section_type, phase, file_path filters
- Semantic: Vector similarity (if embeddings stored)
- Lineage: session_id → full conversation + documents + commits
- Temporal: Show evolution chains, detect supersession

---

## The Essential Flow

```
Index Time:
  Markdown/Conversations/Git → Resolver → Canonical chunks → Storage

Query Time:
  User intent → Query composer → Retrieve chunks → Qualify authority → Serve
```

**Authority qualification happens at serve:**
- Same chunk = different authority per project context
- Based on: usage patterns, validation status, temporal position

---

## The Key Properties

**1. Universal Ingestion**
- Any AI workflow → canonical schema
- No configuration required
- Works day 1, improves with use

**2. Self-Validating**
- Git commits = truth oracle
- Documents validated against reality
- Authority emerges from outcomes

**3. Complete Lineage**
- session_id links: conversation → document → commit
- Full trace: intent → decision → implementation → outcome

**4. Schema Emergence**
- Types discovered from observation
- Not predefined enums
- Adapts to any domain

**5. Pluggable Storage**
- Metadata layer = foundation
- Storage backend = implementation detail
- SQLite → Qdrant = just add embeddings

---

## The Geometric Essence

```
         SOURCES
    (markdown, logs, git)
            ↓
       RESOLVER
    (observe, cluster,
     resolve, infer)
            ↓
    CANONICAL CHUNKS
   (typed, with metadata)
            ↓
      INTELLIGENCE
   (schema, entities,
    temporal, graph)
            ↓
      QUERY LAYER
    (metadata/semantic)
            ↓
         SERVE
   (authority qualified
     by context)
```

**Each layer:**
- Independent
- Composable
- Observable
- Replaceable

**No coupling. Clean interfaces. Emergent intelligence.**

---

## What This Creates

**A self-validating knowledge compiler for AI-native development**

- Ingests: Any AI workflow → canonical form
- Validates: Against git reality continuously
- Learns: Patterns across projects
- Serves: Context-aware, authority-qualified knowledge

**The metadata network that makes software development knowledge queryable, validated, and connected.**

---

**This is the essential geometry. The shape that must hold.**