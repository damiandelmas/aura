## Architecture: Universal Knowledge Compiler

### Core Identity

**Not RAG. Metadata compilation infrastructure.**

Parse heterogeneous markdown → Canonical typed chunks → Storage-agnostic → Query via modalities

---

### Essential Components

**1. Three Sources**
```
Markdown files    (decisions, intent)
Conversations [jsonl]     (lineage, context)
Git commits       (ground truth, validation)
```

**2. Canonical Schema**
```
Four-phase: design → designate → develop → document
Universal target for ALL workflows
Resolution not validation
```

**3. Atomic Unit**
```
Chunk = queryable atom
Document metadata flows to chunks (inherited context)
Single-level queries, no joins
```

---

### The Three Layers

**CREATE**
- Auto-discovery (Path.rglob with filters)
- Universal resolver (any structure → canonical schema)
- Template-based parsing (changelog, conversation, ADR, etc.)

**MANAGE**
- NEXUS: Metadata network (tier 0→1→2, authority emergence)
- MIND: Intelligence (schema evolution, entity resolution, temporal validation)
- Observes patterns, discovers taxonomy, validates via git

**USE**
- Modalities: metadata (SQLite), semantic (Qdrant), trace (linear), graph (topology)
- Storage choice reflects query needs
- Parse once, query many ways

imem compose {{inline jsonl}}

---

### Key Properties

**Universal Entry:** Works on ANY codebase with markdown + + AI Agent conversations (claude code initially) + git

**Resolution:** Intelligent mapping (their structure → canonical schema)

**Storage Agnostic:** JSONL source of truth, SQLite/Qdrant as derived indexes

**Template Architecture:** Base parser + domain plugins, observer discovers cross-domain taxonomy

**Network Intelligence:** MIND observes across projects, patterns emerge, collective learning

**Self-Validating:** Markdown claims ↔ Git reality → truth scores

---

### The Topology

```
Sources → Resolver → Parser → MANAGE → Storage → Modalities
(any MD)  (intent)  (chunks)  (NEXUS)  (choice)  (query)
                              (MIND)
```

**Compilation stages with feedback loops.**
**Not linear pipeline - observational system that learns.**