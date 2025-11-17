---
schema_version: "v3_adaptive"
type: "planning.embedding-migration"
status: "planning"
keywords: "embedding-model nomic e5-large-v2 token-truncation vector-migration imem"
timestamp: "2025-10-30T14:26:00-0700"
---

# Nomic Embed Migration Plan

## Request
Eliminate 60% content loss from E5-Large-v2's 512-token truncation limit by migrating to Nomic Embed v1.5 with 8K-token capacity

## Overview
Planned migration to eliminate 60% embedding content loss by upgrading to a higher-capacity embedding model with 16x token capacity. The current model truncates large document sections at 512 tokens, losing semantic context from detailed technical content. Migration involves centralizing model configuration to enable future flexibility, adding runtime validation to prevent dimension mismatches, and re-indexing all existing document collections. The approach preserves vector dimensionality while eliminating truncation, enabling full-context semantic search across large sections.

## Decisions

### Adopt Nomic Embed v1.5 Over Alternatives
- **Context**: E5-Large-v2 truncates tokens at 512, causing 60% content loss for large changelog sections
- **Solution**: Upgrade to Nomic Embed v1.5 (8K tokens, 768 dimensions) with centralized config-driven model loading
- **Alternatives**: Implement custom truncation strategies (rejected - loses data semantics), split sections further with E5 (rejected - loses context windows)
- **Rationale**: 8K tokens preserve full context of large sections without truncation; maintains 768-dimensional vector standard
- **Implications**: Requires re-indexing all conversations and context across 6 projects; creates future flexibility for embedding model swaps via config

### Centralize Model Loading in Config
- **Context**: Model hardcoding in two locations (markdown and conversation ingest) prevents easy testing and migration
- **Solution**: Create config fields for default_model, default_vector_name, default_dimensions; replace hardcoded references everywhere
- **Rationale**: Single source of truth enables A/B testing of embedding models without code changes
- **Implications**: All future embedding model upgrades become config-only operations

## Constraints

### Model Dimension Validation Gap
- **What**: No runtime validation that loaded embedding model produces expected dimension count
- **Discovery**: Identified during planning - mismatched model configs could silently produce wrong vector dimensions
- **Workaround**: Add _validate_model_dimensions() method called after each model load; raises ValueError if mismatch detected
- **Impact**: Minimal overhead (<100ms) but prevents silent vector dimension failures
- **Testing**: Validation passes with correct config (debug log only); fails with actionable error on dimension mismatch

## Implementation

### Architecture
Six-task migration with dependency chain:

1. Task 1 (5 min): Update config defaults → Task 2
2. Task 2 (10 min): Centralize model loading (3 locations) → Task 3
3. Task 3 (15 min): Add dimension validation → Task 4
4. Task 4 (30 min): Integration test with 5K+ char sections → Task 6
5. Task 5 (30 min): Update runbooks [parallel path]
6. Task 6 (3-6 hours): Production re-indexing (6 projects with pre/post verification)

Critical path: 1 → 2 → 3 → 4 → 6 (total ~6.5 hours minimum)
Parallel work: Task 5 during any point

### Code Signatures

**Config Model Parameters** (`imem/src/imem/config.py`, lines 25-27)
```python
default_vector_name: str = 'nomic-embed-v1.5'
default_model: str = 'nomic-ai/nomic-embed-text-v1.5'
default_dimensions: int = 768
```

**Ingest Layer Model Loading** (`imem/src/imem/ingest.py`)
```python
# Location 1 (line 632 - markdown ingest)
self.model = SentenceTransformer(config.default_model)

# Location 2 (line 840 - conversation ingest)
self.model = SentenceTransformer(config.default_model)

# Location 3 (line 776 - vector naming)
'vector': {config.default_vector_name: embedding.tolist()}
```

**Dimension Validation Method** (`imem/src/imem/ingest.py`)
```python
def _validate_model_dimensions(self):
    """Validate model output dimensions match config."""
    if self.model is None:
        return
    test_embedding = self.model.encode("dimension validation test")
    actual_dim = len(test_embedding)
    if actual_dim != config.default_dimensions:
        raise ValueError(f"Dimension mismatch: {config.default_model} produces "
                        f"{actual_dim}D but config expects {config.default_dimensions}D")
    logger.debug(f"Model validation passed: {actual_dim}D")
```

## Patterns

### Config-Driven Model Selection
- **Pattern**: Define embedding model parameters as configuration; reference via config object instead of hardcoding
- **When**: Multiple model options exist or future model swaps are anticipated
- **Approach**: Create config fields for model name, vector name, dimensions; inject config into ingest classes
- **Benefit**: Eliminates hardcoded model strings; enables testing different embeddings without code changes
- **Anti-Pattern**: Hardcoding model names across multiple ingest locations

### Runtime Dimension Validation
- **Pattern**: Encode test string immediately after model load; compare actual dimensions to expected config; fail fast if mismatch
- **When**: Vector dimensions are critical to downstream operations (schema, search accuracy)
- **Approach**: Lightweight validation method called after each model instantiation
- **Benefit**: Prevents silent failures from config/model mismatches
- **Anti-Pattern**: Hoping dimension mismatches will be caught at search time (too late - bad vectors already stored)

## Audit

### Created
- No new files (all changes to existing modules)

### Modified
- `imem/src/imem/config.py` - Add three embedding model configuration fields to IMEMConfig dataclass
- `imem/src/imem/ingest.py` - Centralize model loading (3 locations), add config import, add dimension validation method, update logger messages
- `.context/document/runbooks/imem.md` - Add "Embedding Model Migration" section with background, specifications, migration steps, troubleshooting, rollback procedure, and performance comparison

### Configuration
- `default_vector_name: 'nomic-embed-v1.5'` - Vector field identifier in Qdrant
- `default_model: 'nomic-ai/nomic-embed-text-v1.5'` - HuggingFace model identifier
- `default_dimensions: 768` - Expected vector output dimensions

### Deployment
Production migration per project:
1. Pre-state capture: `imem status > /tmp/pre_migration_status.txt`
2. Re-index context: `imem index context --force`
3. Re-index conversations: `imem index conversations --force`
4. Verification: 5 test queries per project; zero truncation warnings; spot-check large sections
5. Post-comparison: `diff /tmp/pre_migration_status.txt /tmp/post_migration_status.txt`
6. Performance: 10-iteration latency test; compositional query performance check