# BRAIN: Infrastructure Layer

## The Concept

**BRAIN = post-creation infrastructure substrate.**

Not an intelligence layer. The learned foundation that intelligence layers query.

```
Immutable source
    ↓
BRAIN infrastructure (learned)
    ├── Relationship edges
    ├── Chunk registry
    ├── Supersession tracking
    └── Entity resolution
    ↓
Intelligence layers (query-time)
```

**The Insight:** Separate what was written from what's learned from usage.

---

## Three-Layer Topology

**Layer 1: Static (Never Changes)**
```
Source metadata
    ↓
Copied once, frozen
```
Properties: id, timestamp, type, keywords, content_hash

**Layer 2: Dynamic (Updates From Usage)**
```
Usage events
    ↓
Accumulate in real-time
```
Properties: Reference patterns, access timestamps, frequency metrics

**Layer 3: Computed (Batch Recompute)**
```
Graph topology + usage
    ↓
Periodic analysis
```
Properties: Authority scores, supersession detection, centrality metrics

---

## Update Frequency Stratification

**Real-time (every query):**
- Usage tracking (which chunks queried)
- Access patterns (when, how often)

**Periodic batch:**
- Graph analysis (topology-based metrics)
- Temporal metadata (age, staleness)

**Occasional LLM:**
- Entity clustering
- Supersession detection
- Pattern mining

---

## Dataflow

```
Write time:
  Source → Immutable storage → BRAIN initialization

Query time:
  BRAIN updates (usage tracking)

Background:
  BRAIN enrichment (batch computation)

Serve time:
  Intelligence layers query BRAIN → Assemble context
```

**Property:** Write once, learn continuously, compose at query-time.

---

## The Value

- **Source stays immutable** (archaeological integrity)
- **BRAIN accumulates learned patterns** (relationships, supersession, usage)
- **Intelligence layers query substrate** (not recompute)
- **Ephemeral composition** (assemble views at serve-time)