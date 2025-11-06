● IMEM Embedding Migration Plan: E5-Large-v2 → Nomic Embed v1.5

  🎯 Goal

  Eliminate 60% content loss from 512-token truncation by upgrading to 8K-token model

  ---
  📋 Task Breakdown

  Task 1: Update Config Defaults to Nomic Embed v1.5

  Status: Foundation task (no dependencies)Effort: 5 minutesRisk: LOW

  Subtasks:
  1. Open imem/src/imem/config.py
  2. Locate lines 25-27 (IMEMConfig dataclass)
  3. Update 3 fields:
    - default_vector_name: str = 'nomic-embed-v1.5'
    - default_model: str = 'nomic-ai/nomic-embed-text-v1.5'
    - default_dimensions: int = 768
  4. Save file
  5. Verify: python -c "from imem.config import config; print(config.default_model)"

  Verification:
  - ✅ Config loads without errors
  - ✅ All 3 values updated correctly
  - ✅ Environment variable overrides still work

  ---
  Task 2: Centralize Model Loading in Ingest Layer

  Status: Depends on Task 1Effort: 10 minutesRisk: LOW

  Subtasks:
  1. Open imem/src/imem/ingest.py
  2. Add import at top: from .config import config
  3. Location 1 (line 632 - markdown ingest):
    - OLD: self.model = SentenceTransformer('intfloat/e5-large-v2')
    - NEW: self.model = SentenceTransformer(config.default_model)
  4. Location 2 (line 840 - conversation ingest):
    - OLD: self.model = SentenceTransformer('intfloat/e5-large-v2')
    - NEW: self.model = SentenceTransformer(config.default_model)
  5. Location 3 (line 776 - vector naming):
    - OLD: 'vector': {"e5-large-v2": embedding.tolist()}
    - NEW: 'vector': {config.default_vector_name: embedding.tolist()}
  6. Update logger messages (lines 631, 839) to use f-string with config.default_model
  7. Save file
  8. Verify: python -m py_compile imem/src/imem/ingest.py

  Verification:
  - ✅ No hardcoded 'intfloat/e5-large-v2' strings remain
  - ✅ Config import present
  - ✅ Syntax check passes
  - ✅ Logger messages show model name dynamically

  ---
  Task 3: Add Embedding Dimension Validation

  Status: Depends on Task 2Effort: 15 minutesRisk: LOW

  Subtasks:
  1. Open imem/src/imem/ingest.py
  2. Add new method to EnhancedModularIngest class (after line 108):
  def _validate_model_dimensions(self):
      """Validate model output dimensions match config."""
      if self.model is None:
          return

      test_embedding = self.model.encode("dimension validation test")
      actual_dim = len(test_embedding)

      if actual_dim != config.default_dimensions:
          raise ValueError(
              f"Model dimension mismatch: {config.default_model} produces "
              f"{actual_dim}D embeddings but 
  config.default_dimensions={config.default_dimensions}. "
              f"Update config.py or choose different model."
          )

      logger.debug(f"Model dimension validation passed: {actual_dim}D")
  3. Call validation after model loading:
    - After line 632: self._validate_model_dimensions()
    - After line 840: self._validate_model_dimensions()
  4. Save file
  5. Test with correct config: validation should pass silently
  6. Test with wrong dimensions: should raise clear error

  Verification:
  - ✅ Method exists with proper docstring
  - ✅ Called after both model load locations
  - ✅ Correct config: passes (debug log only)
  - ✅ Wrong config: raises ValueError with actionable message
  - ✅ Adds <100ms overhead

  ---
  Task 4: Integration Testing with New Model

  Status: Depends on Task 3Effort: 30 minutesRisk: MEDIUM (validation step)

  Subtasks:
  1. Create test changelog (/tmp/test_nomic_migration.md):
  ---
  session_id: "test-123"
  timestamp: "2025-01-30T14:00:00"
  ---

  # Test Migration

  ## Implementation
  ### Large Section Test
  - **Context**: [5000+ characters of test content...]
  - **Solution**: Testing Nomic Embed v1.5 handles large sections
  - **Rationale**: E5-Large-v2 truncated this content
  2. Test indexing:
  python -c "
  from imem.ingest import EnhancedModularIngest
  from pathlib import Path
  ing = EnhancedModularIngest()
  ing.ingest_markdown_chunked(
      Path('/tmp/test_nomic_migration.md'), 
      'develop', 
      'test_migration'
  )
  "
  3. Verify outputs:
    - Model loads: "Loading embedding model: nomic-ai/nomic-embed-text-v1.5"
    - Dimension validation passes
    - NO truncation warnings for 5000+ char section
    - Batch upsert succeeds
  4. Test search:
  imem search develop "content from end of large section" --in test_migration
    - Verify full content returned (not truncated at 2000 chars)
  5. Check Qdrant:
    - Vectors are 768D
    - Vector name is 'nomic-embed-v1.5'
  6. Performance check:
    - Time batch encoding of 50 sections
    - Should be >=100 QPS

  Verification:
  - ✅ Model loads successfully
  - ✅ Zero truncation warnings
  - ✅ Large section fully searchable (content from character 5000+ is retrievable)
  - ✅ Vectors are 768D
  - ✅ Performance: >=100 QPS
  - ✅ No errors in logs

  ---
  Task 5: Update Migration Documentation

  Status: Independent (can run in parallel)Effort: 30 minutesRisk: LOW

  Subtasks:
  1. Open .context/document/runbooks/imem.md
  2. Add new section: "## Embedding Model Migration"
  3. Include subsections:
    - Background: Why we're migrating (E5 truncation problem)
    - Model Specifications: Comparison table (E5 vs Nomic)
    - Migration Process: Step-by-step commands
    - What Changes: Visible vs invisible changes
    - Troubleshooting: Common errors and fixes
    - Rollback: Emergency procedure
    - Performance Comparison: Benchmark results
  4. Key content:
  ### Migration Process

  1. Re-index context changelogs:
     ```bash
     imem index context --force

    b. Re-index conversations:
    imem index conversations --force
    c. Verify:
    imem status
  imem search develop "test query"

  5. Save file
  6. Verify markdown formatting

  Verification:
  - ✅ Section exists with all subsections
  - ✅ Commands are copy-pastable and correct
  - ✅ Troubleshooting covers key errors
  - ✅ Rollback procedure is clear
  - ✅ Markdown formatting correct

  ---
  Task 6: Production Migration Execution

  Status: Depends on Tasks 4 & 5Effort: 3-6 hours (30-60min per project × 6 projects)Risk: MEDIUM
   (data migration)

  Subtasks:

  6.1: Pre-Migration Checks

  1. Verify all code changes merged
  2. Record current state:
  imem status > /tmp/pre_migration_status.txt
  3. Note doc counts for each collection

  6.2: Migration Per Project (repeat for all 6 projects)

  1. Navigate to project:
  cd ~/project-path
  2. Re-index context:
  time imem index context --force
    - Record: duration, doc count, warnings
  3. Re-index conversations:
  time imem index conversations --force
    - Record: duration, doc count, warnings

  6.3: Verification Per Project

  1. Check status:
  imem status
    - Verify doc count matches pre-migration
  2. Quality check (5 test queries):
  imem search develop "authentication"
  imem search develop "error handling"
  imem search develop "database migration"
  imem search design "architecture decision"
  imem conversations search "bug fix"
  3. Check for truncation:
  grep -r "Large chunk" logs/ | wc -l
    - Should be 0

  6.4: Performance Benchmarking

  1. Search latency (10 iterations):
  for i in {1..10}; do
    time imem search develop "test query" --limit 20
  done
  2. Compositional query:
  time imem compose '{"search": {"text": "JWT auth"}, "discovery": {"siblings": true}}'

  6.5: Post-Migration Verification

  1. Final status check:
  imem status > /tmp/post_migration_status.txt
  diff /tmp/pre_migration_status.txt /tmp/post_migration_status.txt
  2. Spot check 3 large sections:
    - Query for content from END of large sections
    - Verify full content returned

  6.6: Document Results

  1. Total migration time
  2. Any errors/warnings
  3. Performance comparison
  4. Search quality assessment
  5. Recommendations

  Verification:
  - ✅ All 6 projects re-indexed
  - ✅ Doc counts match (±1 acceptable)
  - ✅ Zero truncation warnings
  - ✅ Search quality: 5 queries per project, all relevant
  - ✅ Large sections fully searchable
  - ✅ Performance comparable or better
  - ✅ No dimension mismatch errors
  - ✅ All vectors are 768D with 'nomic-embed-v1.5' name

  ---
  📊 Summary

  Total Effort: ~5-7 hours
  - Code changes: 30 minutes
  - Testing: 30 minutes
  - Documentation: 30 minutes
  - Migration: 3-6 hours (depends on doc count)

  Risk Level: LOW → MEDIUM
  - Tasks 1-3: LOW (code changes, well-isolated)
  - Task 4: MEDIUM (validation)
  - Task 5: LOW (documentation)
  - Task 6: MEDIUM (data migration, irreversible)

  Critical Path: 1 → 2 → 3 → 4 → 6

  Parallel Work: Task 5 (documentation) can be done anytime