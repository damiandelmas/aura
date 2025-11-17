---
schema_version: "v3_adaptive"
type: "implementation.embedding-model-migration"
status: "completed"
keywords: "embedding nomic e5 model auto-detection migration"
timestamp: "2025-10-31T17:30:00-0700"
---

# Embedding Model Migration Status

## Request
> "Migrate to the new embedding model while maintaining backward compatibility with existing collections"

## Overview
Migrated to a more efficient embedding model as default with intelligent fallback detection. The system now automatically detects which embedding model a collection uses based on its vector configuration and loads the appropriate model without manual intervention. Existing collections continue to work seamlessly while new collections use the updated model.

## Decisions

### Default Model Selection
- **Context**: Need to standardize on a single embedding model while maintaining backward compatibility with existing collections
- **Solution**: Set newer model (768D, 8k tokens) as default with auto-detection fallback to previous model for older collections
- **Rationale**: Updated model provides better efficiency while smart detection preserves existing infrastructure

## Implementation

### Architecture
The auto-detection mechanism works as follows:
1. Collection reports its vector configuration when accessed
2. System extracts the vector model name from collection metadata
3. MODEL_REGISTRY lookup returns the correct model configuration
4. SentenceTransformer loads the appropriate model
5. Search proceeds with zero manual switching

### Code Signatures

**Smart Model Detection Pattern**
```python
# Auto-detect model from collection vector configuration
collection = client.get_collection(name)
vector_name = collection.config.params.vectors.keys()[0]
model_info = MODEL_REGISTRY[vector_name]
encoder = SentenceTransformer(model_info["model_path"])
```

## Audit

### Modified
- `config.py` - Added MODEL_REGISTRY with updated model defaults
- `enhanced.py` - Implemented auto-detection from collection vector configuration
- `cli.py` - Added collection override flag for manual control
- `ingest.py` - Updated model loading and similarity thresholds

### Deployment
**Re-indexed Collections:**
- Main project collection (aura/main)

**Legacy Collections (auto-detected):**
- Sandbox and other registered project collections
- Will re-index on scheduled migration

**Test Collection:**
- Created temporary collection for A/B comparison testing