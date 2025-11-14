# NEXUS: The Essential Architecture

---

## The Two Networks

**KNOWLEDGE (Visibility)**
- Everything touchable: files, URLs, folders, repos
- Tier 1: What exists (source, format)
- Tier 2: How used (access logs per project)

**CONTENT (Search)**
- Indexed subset: markdown chunks
- Multi-label types: ["Decision", "Implementation"]
- Embeddings: Semantic position
- Inheritance: Document metadata → chunk metadata

---

## The Three Files

```
.nexus/
├── access.jsonl      # Tier 2: Resource touches (when, why, session)
├── chunks.jsonl      # Content: Vectors + types + metadata
└── registry/         # Tier 1: Minimal wrappers (source, format, retrieved)

.git/                 # Truth oracle
```

---

## The Two Operations

**Write:**
Log access + optionally index content

**Query:**
Semantic (embeddings) + Structural (metadata filters)

---

## The Key Insight

**Tier 1 = Inert Facts**
```
source: "https://graphiti.ai/docs"
format: url
retrieved: "timestamp"
```

**Tier 2 = Emergent Understanding**
```
{"source":"...", "session":"abc", "context":"graph research"}
{"source":"...", "session":"def", "context":"temporal validation"}
```

Understanding emerges from usage patterns, not declarations.