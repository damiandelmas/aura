# Intelligence Layers: Single Retrieval Pass

**What aids AI comprehension from query → served chunks?**

Not ranking. Not filtering. **Structural awareness for context.**

---

## The Flow

```
Query → Intelligence layers → Chunks with context
```

Each layer adds information that helps AI agents understand:
- **What relates** (topology)
- **What's current** (temporal position)
- **What's authoritative** (confidence signals)

---

## Layer 1: Semantic Entry

**What:** Fuzzy matching via embeddings
**Adds:** Initial candidate set
**AI comprehension:** "These concepts are nearby in semantic space"

---

## Layer 2: Entity Expansion

**What:** Query expansion via canonical mappings
**Adds:** Term variants ("JWT" → all historical spellings)
**AI comprehension:** "These refer to same concept despite different names"

Source: BRAIN entity resolution

---

## Layer 3: Template Guarantees

**What:** Deterministic field presence from creation-time enforcement
**Adds:** Guaranteed structure (Context, Solution, Rationale)
**AI comprehension:** "Every chunk has complete information"

---

## Layer 4: Metadata Filtering

**What:** Precise narrowing via guaranteed fields
**Adds:** Section type, phase, presence flags
**AI comprehension:** "This is a Decision (not Failure), from develop phase, has rationale"

---

## Layer 5: Graph Topology Detection

**What:** Relationship discovery via persisted edges
**Adds:** Topology shape (linear? hub? arc? cluster?)
**AI comprehension:** "This forms a timeline (not a hub or cluster)"

Source: BRAIN graph edges

**Detects:**
- Linear chain → Timeline structure
- Hub pattern → Authority/reference structure
- Arc pattern → Genealogy/story structure
- Cluster → Related concepts structure

---

## Layer 6: Relationship Labeling

**What:** Explicit edge type classification
**Adds:** SIBLING vs GENEALOGY vs TEMPORAL labels
**AI comprehension:** "These are siblings (same file), not temporal evolution"

Source: BRAIN edge types

---

## Layer 7: Temporal Position

**What:** Currency signals from BRAIN infrastructure
**Adds:** Superseded flags, last accessed, age
**AI comprehension:** "This is current (not superseded), recently referenced"

Source: BRAIN supersession tracking

---

## Layer 8: Structured Serving

**What:** Presentation assembly based on detected topology
**Adds:** Context-aware structure (timeline? story? authority?)
**AI comprehension:** "Information structured to match relationships discovered"

Template selection driven by topology detection (Layer 5).