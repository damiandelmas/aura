# IMEM Embedding Model A/B Testing Guide

## Overview

IMEM now supports **automatic model detection** and **collection override** for A/B testing different embedding models on the same content.

## Features

### 1. Auto-Detection (Default Behavior)

Collections are **self-describing** via their vector name:
- E5 collections → automatically load E5 model
- Nomic collections → automatically load Nomic model
- No manual configuration needed

**How it works:**
```python
# When you search, IMEM:
1. Reads collection's vector config from Qdrant
2. Maps vector name to model via MODEL_REGISTRY
3. Loads correct model automatically
4. Searches with matching embeddings
```

### 2. Collection Override (A/B Testing)

Create alternate collections with different models to compare quality.

---

## A/B Testing Workflow

### Step 1: Index with Original Model (E5)

```bash
# Existing collection uses E5
cd /home/axp/projects/npta_ava
imem search develop "authentication" --limit 5

# Note scores (e.g., 0.82, 0.79, 0.76...)
```

### Step 2: Create Alternate Collection with Nomic

```bash
# Change default model to Nomic
vim imem/src/imem/config.py
# Set: default_model = 'nomic-ai/nomic-embed-text-v1.5'

# Index to NEW collection (don't destroy E5)
imem index develop --force --collection imem_77eb0e65_nomic

# ~10 min for 87 docs
```

### Step 3: Compare Results

```bash
# Search E5 collection (auto-detects E5)
imem search develop "authentication" --collection imem_77eb0e65

# Search Nomic collection (auto-detects Nomic)
imem search develop "authentication" --collection imem_77eb0e65_nomic

# Compare:
# - Top-3 relevance
# - Score distributions
# - Result ordering
```

### Step 4: Decide Winner

**Evaluate:**
- Are results more relevant?
- Do scores align with perceived quality?
- Which handles edge cases better?

**Choose:**
```bash
# If Nomic wins → re-index main collection
imem index develop --force  # Destroys E5, replaces with Nomic

# If E5 wins → revert config, delete test collection
vim imem/src/imem/config.py  # Back to E5
qdrant delete collection imem_77eb0e65_nomic
```

---

## Model Registry

Located in `imem/src/imem/config.py`:

```python
MODEL_REGISTRY = {
    "e5-large-v2": {
        "model_path": "intfloat/e5-large-v2",
        "dimensions": 1024,
        "trust_remote_code": False
    },
    "nomic-embed-v1.5": {
        "model_path": "nomic-ai/nomic-embed-text-v1.5",
        "dimensions": 768,
        "trust_remote_code": True
    }
}
```

**To add new model:**
1. Add entry to MODEL_REGISTRY
2. Set as default in IMEMConfig
3. Re-index collections

---

## Example: Comparing E5 vs Nomic

```bash
# Query 1: Semantic concepts
imem search develop "compositional memory primitives" --collection imem_1ba1fff1_context
# E5:    Score: 0.823
# Nomic: Score: 0.695

# Query 2: Code patterns  
imem search develop "parse header markdown" --collection imem_1ba1fff1_context
# E5:    Score: 0.791
# Nomic: Score: 0.662

# Query 3: Multi-concept
imem search develop "embedding model vector database configuration" 
# E5:    Score: 0.741
# Nomic: Score: 0.619
```

**Analysis:**
- E5 scores ~0.15-0.20 higher on average
- Nomic handles long content better (no truncation)
- Both return relevant results

**Decision:** Test with real use cases, not just scores.

---

## Clean Up Test Collections

```bash
# List all collections
imem collections list

# Delete test collection
qdrant-client delete-collection <name>
```

---

## Notes

- **Auto-detect always works** - No manual model switching needed
- **Collection override is for A/B testing only** - Not daily use
- **Score distributions differ per model** - Compare relative rankings, not absolute scores
- **Old collections still work** - Auto-detect handles migration

