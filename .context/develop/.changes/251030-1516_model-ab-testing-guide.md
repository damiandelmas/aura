---
schema_version: "v3_adaptive"
type: "design.model-ab-testing-guide"
status: "completed"
keywords: "embedding-model a-b-testing e5 nomic model-comparison vector-search"
timestamp: "2025-10-30T15:16:00-0700"
---

# Model A/B Testing Guide

## Request
> "Document how IMEM's automatic model detection and collection override system works for comparing embedding models"

## Overview
The system supports automatic embedding model detection and collection override functionality, enabling comparative analysis of different models on identical indexed content. Vector configuration metadata is read from storage, and the appropriate model is loaded automatically during search operations, eliminating manual switching. Collections can be overridden to create parallel test environments for side-by-side performance evaluation of alternative models.

## Implementation

### Architecture
The model detection system operates through four key steps:
1. Collection vector configuration is read from persistent storage
2. Vector name is mapped to embedding model via registry lookup
3. Correct model is loaded automatically on search initiation
4. Search operations execute with matching embeddings

### Code Signatures

**Model Registry Configuration** (`imem/src/imem/config.py`)
```python
MODEL_REGISTRY = {
    "model-identifier": {
        "model_path": "provider/model-name",
        "dimensions": <vector_size>,
        "trust_remote_code": <boolean>
    }
}
```

## Patterns

### Auto-Detection (Default Behavior)
- **Pattern**: Collections are self-describing via their vector configuration metadata
- **When**: Starting search operations across multiple collections with different models
- **Approach**: Collection name or vector configuration implicitly identifies the model required
- **Benefit**: Eliminates manual model configuration and reduces setup complexity
- **Anti-Pattern**: Hardcoding model names in search queries instead of relying on collection metadata

### Collection Override (A/B Testing)
- **Pattern**: Create parallel collections with alternate models to enable comparative evaluation
- **When**: Evaluating different embedding models for improved search quality
- **Approach**: Index content to separate collection with different default model, then compare results across both collections
- **Benefit**: Side-by-side comparison of model performance on identical content
- **Why**: Different models have different scoring distributions and may excel at different query types
- **Anti-Pattern**: Destroying original collection before confirming the alternate model performs better

## Constraints

### Scoring Distribution Variation
- **What**: Each embedding model produces different absolute scores making direct score comparison unreliable
- **Discovery**: Different models show varying score ranges with offsets up to 0.15-0.20, though relative rankings may differ
- **Workaround**: Compare result relevance and ranking order rather than absolute score values
- **Impact**: Evaluation requires semantic assessment, not just numerical comparison

## Audit

### Configuration
- Model registry - Contains model definitions with paths and vector dimensions
- Default model setting - Determines which model is used for new indexing operations
- Collection naming convention - Test collections appended with model identifier for tracking

### Deployment
A/B testing workflow:
1. Index with original model - note baseline scores for reference queries
2. Create alternate collection with different model
3. Run identical queries against both collections
4. Compare result relevance, score distributions, and edge case handling
5. Select winning model and either re-index main collection or revert configuration

---

## A/B Testing Workflow

### Step 1: Index with Original Model
```bash
cd /home/axp/projects/npta_ava
imem search develop "authentication" --limit 5
# Note scores for comparison (e.g., 0.82, 0.79, 0.76)
```

### Step 2: Create Alternate Collection
```bash
# Change default model configuration
vim imem/src/imem/config.py
# Set: default_model = 'nomic-ai/nomic-embed-text-v1.5'

# Index to new collection without destroying E5
imem index develop --force --collection imem_77eb0e65_nomic
# Approximately 10 minutes for 87 documents
```

### Step 3: Compare Results
```bash
# Search E5 collection (auto-detects E5)
imem search develop "authentication" --collection imem_77eb0e65

# Search Nomic collection (auto-detects Nomic)
imem search develop "authentication" --collection imem_77eb0e65_nomic

# Evaluate: Top-3 relevance, score distributions, result ordering
```

### Step 4: Finalize Selection
```bash
# If alternate model wins → re-index main collection
imem index develop --force
# Destroys original, replaces with new model

# If original model wins → revert and clean up
vim imem/src/imem/config.py  # Revert to original
qdrant delete collection imem_77eb0e65_nomic
```

### Example Comparison Results
```bash
# Semantic concepts query
<search command> "compositional memory primitives" --collection <collection_name>
# Model A Score: 0.823  |  Model B Score: 0.695

# Code pattern query
<search command> "parse header markdown" --collection <collection_name>
# Model A Score: 0.791  |  Model B Score: 0.662

# Multi-concept query
<search command> "embedding model vector database configuration"
# Model A Score: 0.741  |  Model B Score: 0.619
```

Analysis shows one model producing higher absolute scores on average, while the alternate model may handle longer content differently. Evaluation should prioritize actual search quality over score values.

### Collection Management
```bash
# List all collections
imem collections list

# Delete test collection
qdrant-client delete-collection <name>
```

## Notes

- Auto-detection functions without manual model switching between searches
- Collection override exists primarily for A/B testing, not routine operations
- Score distributions vary per model, requiring relative ranking comparison rather than absolute score matching
- Legacy collections remain compatible with the auto-detection system

