# Adaptive BRAIN Updates: Multi-Speed Learning

**Feature Status:** Designed, not implemented

---

## The Concept

Different metadata needs different update frequencies. Don't batch everything weekly - stratify by cost and value.

**Principle:** Update frequency should match value and cost.

---

## Architecture

### Real-Time (Every Query)

**Operations:**
- `reference_count++` (cheap, high signal)
- `last_accessed = now()` (track usage patterns)

**Implementation:**
```sql
UPDATE brain_stats
SET reference_count = reference_count + 1,
    last_accessed = CURRENT_TIMESTAMP
WHERE chunk_id = ?
```

**Cost:** ~1ms per query (SQLite UPDATE)
**Why:** Reference counts show current relevance immediately

---

### Batch Processing (Nightly)

**Operations:**
- Recompute PageRank (~5min for 10K nodes)
- Recompute centrality (~5min)
- Update temporal metadata (age, staleness)

**Implementation:**
```python
# Cron job runs at 2am
def nightly_batch():
    compute_pagerank()
    compute_centrality()
    update_age_months()
```

**Cost:** ~10-15 minutes nightly
**Why:** Expensive graph algorithms can run while you sleep

---

### LLM Processing (Weekly)

**Operations:**
- Entity resolution (cluster term variations)
- Supersession detection (semantic comparison)
- Pattern mining (discovery)

**Implementation:**
```python
# Weekly cron job
def weekly_llm_batch():
    entity_map = llm_cluster_keywords(all_keywords)  # $0.01
    supersession = detect_supersession(chunks)        # $0.05
    patterns = mine_patterns(chunks)                  # $0.10
```

**Cost:** ~$0.20 per week
**Why:** LLM costs controlled, diminishing returns on daily updates

---

## Update Frequency Stratification

```
┌─────────────────┬──────────────┬─────────────┬──────────────┐
│ Update Type     │ Frequency    │ Cost        │ Signal Value │
├─────────────────┼──────────────┼─────────────┼──────────────┤
│ Reference Count │ Real-time    │ ~1ms        │ High         │
│ Last Accessed   │ Real-time    │ ~1ms        │ High         │
│ PageRank        │ Nightly      │ ~5min       │ Medium       │
│ Centrality      │ Nightly      │ ~5min       │ Medium       │
│ Age Months      │ Nightly      │ instant     │ Medium       │
│ Entity Res      │ Weekly       │ $0.01 (LLM) │ Low          │
│ Supersession    │ Weekly       │ $0.05 (LLM) │ Low          │
│ Pattern Mining  │ Weekly       │ $0.10 (LLM) │ Low          │
└─────────────────┴──────────────┴─────────────┴──────────────┘
```

---

## Key Terms

- **Real-Time Updates**: Cheap operations, high signal
- **Batch Computation**: Expensive algorithms run offline
- **LLM Processing**: Costly analysis runs infrequently
- **Adaptive Layers**: Updates stratified by cost/value tradeoff

---

## The Value

- **Fast updates where they matter** (usage tracking)
- **Expensive operations run offline** (graph algorithms)
- **LLM costs controlled** (batch processing)
- **System learns continuously** without per-query penalty

---

## Implementation Notes

**Concurrency:** SQLite handles concurrent real-time updates safely

**Batch Jobs:**
```python
# Nightly: 2am cron
0 2 * * * cd /path/to/imem && python -m imem.batch.nightly

# Weekly: Sunday 3am cron
0 3 * * 0 cd /path/to/imem && python -m imem.batch.weekly
```

**Monitoring:** Track batch job duration and LLM costs

---

## Related Concepts

See: [VISION.md](./VISION.md) - Principle #6: Multi-Speed Updates
See: [brain-persistence.md](./brain-persistence.md) - brain_stats & brain_metrics tables
See: [entity-resolution.md](./entity-resolution.md) - Weekly LLM processing example
