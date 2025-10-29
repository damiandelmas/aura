# IMEM Test Coverage Map

## Quick Reference

### Current Test Coverage Status
- **Total Pytest Tests**: 0
- **Manual Test Scripts**: 3
- **CLI Integration Tests**: 10+ implicit workflows
- **Code Coverage**: 0% (no measurement)
- **Test Automation**: None (manual only)

---

## Test Inventory

### 1. Manual Validation Scripts

#### `imem/tests/validate_indexing.py`
```
Purpose:    Pre-indexing validation
Type:       Manual Python script
Scope:      Parsing, chunking, metadata extraction
Coverage:   ~200 lines of test logic
Status:     Working, limited scope
Usage:      python imem/tests/validate_indexing.py [files...]

Tests (implicit):
  • Markdown parsing via LlamaIndex
  • YAML frontmatter extraction
  • H1/H2 vs H3+ filtering
  • Chunk size detection
  • Structured field detection
  • Header level distribution
  • Word/char count analysis
```

#### `test_compose.py`
```
Purpose:    Composition pipeline validation
Type:       Manual async test script
Scope:      Full search + discovery + rendering
Coverage:   ~320 lines of test logic
Status:     Working, requires Qdrant running
Usage:      python test_compose.py (run from root)

Test Cases (5):
  1. Explain Decision      - siblings + genealogy
  2. Trace Evolution       - temporal + siblings
  3. Cross-Phase Journey   - cross-phase + genealogy
  4. Multi-Phase Search    - multiple queries
  5. Authority Ranking     - graph ranking (CRITICAL)
```

#### `tests/251023-1537/test_llamaindex_pipeline.py`
```
Purpose:    LlamaIndex + TRACE integration
Type:       Manual test script
Scope:      Conversation parsing and chunking
Status:     Experimental
Usage:      Manual - requires conversation session ID

Coverage:
  • Conversation file discovery
  • Structured markdown export
  • Node creation
  • Metadata extraction
```

---

## CLI-Based Tests (Implicit)

### Service Management
```bash
imem service start      # Container startup
imem service stop       # Container shutdown
imem service status     # Health check
```
**Tests**: 3 implicit (happy path only)

### Project Initialization
```bash
imem init               # Full indexing pipeline
imem init --force       # Collection recreation
imem status             # Registry verification
```
**Tests**: 3 implicit

### Search Operations
```bash
imem develop search "query" --decisions
imem conversations search "query" --patches-only
imem search "query" --limit N
```
**Tests**: 3+ implicit

### Composition
```bash
imem compose '{"search":{...}, "discovery":{...}}'
```
**Tests**: 1 implicit

**Total CLI Tests**: ~10+ workflows (manual verification only)

---

## Component Coverage Matrix

### CLI Module (`cli.py`)
| Subcommand | Tested | Type | Status |
|------------|--------|------|--------|
| `service start` | ✓ | Manual | Basic |
| `service stop` | ✓ | Manual | Basic |
| `service status` | ✓ | Manual | Basic |
| `init` | ✓ | Manual | Full |
| `update` | ✓ | Manual | Full |
| `status` | ✓ | Manual | Basic |
| `develop search` | ✓ | Manual | Full |
| `design search` | ✓ | Manual | Full |
| `conversations search` | ✓ | Manual | Full |
| `search` (legacy) | ✓ | Manual | Full |
| `compose` | ✓ | Manual | 5 queries |
| Error handling | ✗ | None | 0% |
| Edge cases | ✗ | None | 0% |

### Registry Module (`registry.py`)
| Method | Tested | Type | Status |
|--------|--------|------|--------|
| `__init__` | ✓ | Manual | Basic |
| `_load` | ~ | Implicit | Partial |
| `_save` | ~ | Implicit | Partial |
| `register_project` | ✓ | Manual | Basic |
| `is_registered` | ✓ | Manual | Basic |
| `get_project_info` | ✓ | Manual | Basic |
| `get_project_root` | ✓ | Manual | Basic |
| `list_projects` | ✓ | Manual | Basic |
| Corruption recovery | ✗ | None | 0% |
| JSON validation | ✗ | None | 0% |

### Ingest Module (`ingest.py`)
| Capability | Tested | Type | Status |
|------------|--------|------|--------|
| File scanning | ✓ | Manual | Basic |
| Markdown parsing | ✓ | Script | Good |
| H3 filtering | ✓ | Script | Good |
| Metadata extraction | ✓ | Script | Good |
| Embedding generation | ✓ | Manual | Basic |
| Batch upsert | ✓ | Manual | Basic |
| Deduplication | ✓ | Manual | Basic |
| Path migration | ✗ | None | 0% |
| Corruption handling | ✗ | None | 0% |
| Large files (>100K) | ✗ | None | 0% |

### Search Module (`search.py`)
| Capability | Tested | Type | Status |
|------------|--------|------|--------|
| Model loading | ✓ | Manual | Basic |
| Vector generation | ✓ | Manual | Basic |
| Qdrant search | ✓ | Manual | Basic |
| Filter building | ~ | Implicit | Minimal |
| Timestamp parsing | ✓ | Script | Basic |
| Result ranking | ✓ | Manual | Basic |
| Filter validation | ✗ | None | 0% |
| Error handling | ✗ | None | 0% |

### Compose Module (`compose.py`)
| Stage | Tested | Type | Status |
|-------|--------|------|--------|
| Search execution | ✓ | test_compose.py | 5 queries |
| Discovery enrichment | ✓ | test_compose.py | 3 queries |
| Graph operations | ~ | test_compose.py | 1 query |
| Template rendering | ✓ | Manual | Basic |
| Async coordination | ✓ | test_compose.py | 5 queries |
| Error recovery | ✗ | None | 0% |
| Config validation | ✗ | None | 0% |

### Primitives Module (`primitives/discovery.py`)
| Function | Tested | Type | Status |
|----------|--------|------|--------|
| `get_siblings` | ✗ | None | 0% |
| `get_genealogy` | ✗ | None | 0% |
| `get_temporal` | ✗ | None | 0% |
| `get_cross_phase` | ✗ | None | 0% |
| Filter building | ✗ | None | 0% |
| Result ordering | ✗ | None | 0% |

### Service Module (`qdrant_service.py`)
| Operation | Tested | Type | Status |
|-----------|--------|------|--------|
| `start` | ✓ | Manual | Basic |
| `stop` | ✓ | Manual | Basic |
| `is_running` | ✓ | Manual | Basic |
| `ensure_running` | ✓ | Manual | Basic |
| Container health | ~ | Manual | Partial |
| Error recovery | ✗ | None | 0% |

### Config Module (`config.py`)
| Item | Tested | Type | Status |
|------|--------|------|--------|
| Default values | ~ | Implicit | Minimal |
| Env var override | ✗ | None | 0% |
| Type validation | ✗ | None | 0% |
| Path normalization | ✗ | None | 0% |

---

## Validation Layer Coverage

### Schema Validation
- **Point payloads**: Not validated
- **Required fields**: Not checked
- **Field types**: Not validated
- **Enum values**: Not enforced
- **Custom rules**: Not implemented

### Collection Validation
- **Collection exists**: Not checked
- **Schema compatibility**: Not validated
- **Field mappings**: Not verified
- **Index health**: Not checked

### Data Validation
- **File paths**: Basic null checks only
- **Metadata consistency**: Not validated
- **Cross-references**: Not verified
- **Content deduplication**: Implemented (tested manually)

### Migration Validation
- **Schema versions**: No versioning
- **Backward compatibility**: Not tested
- **Data migrations**: None implemented
- **Registry upgrades**: None implemented

---

## Error Handling Coverage

### Tested Error Paths
- ✓ Registry not found (during search)
- ✓ Project not registered
- ✓ JSON parse errors (compose command)
- ✓ Qdrant connection timeout (basic)

### Untested Error Paths
- ✗ Qdrant collection missing during ingest
- ✗ File encoding errors (non-UTF8)
- ✗ Model download failures
- ✗ Embedding out-of-memory
- ✗ Concurrent access conflicts
- ✗ Registry file corruption
- ✗ Payload schema mismatch
- ✗ Vector dimension mismatch

---

## Edge Cases Coverage

### Tested
- ✓ Empty search results
- ✓ Large result sets
- ✓ Multi-term queries

### Untested
- ✗ Empty projects (no files)
- ✗ Very large files (>100K chars)
- ✗ Non-UTF8 file encodings
- ✗ Circular metadata references
- ✗ Special characters in paths
- ✗ Deep directory nesting
- ✗ Symlinked files
- ✗ Files in .context but outside tracked dirs

---

## Integration Points Tested

### Tested
- ✓ Filesystem → Ingest (basic files)
- ✓ Ingest → Qdrant (basic documents)
- ✓ Qdrant → Search (basic queries)
- ✓ Search → Composition (5 patterns)

### Untested
- ✗ TRACE export → Ingest (experimental only)
- ✗ Multi-project Qdrant sharing
- ✗ Registry ↔ Collection sync
- ✗ Conversation session linking
- ✗ Cross-phase reference resolution

---

## Performance Testing

**Current**: None
**Needed**:
- Indexing speed (files/sec)
- Search latency (ms)
- Embedding performance (vectors/sec)
- Memory usage (MB)
- Batch optimization (10x claims)

---

## Test Execution Capability

### Manual Testing
- ✓ CLI commands
- ✓ Python scripts
- ✓ Required setup (start Qdrant, init project)
- ✗ Automated pass/fail
- ✗ Coverage tracking
- ✗ CI/CD integration

### Automated Testing
- ✗ Pytest suite
- ✗ GitHub Actions
- ✗ Regression detection
- ✗ Performance tracking

---

## Files That Need Tests

### High Priority (Critical for Refactor)
1. **`ingest.py`** (400+ lines)
   - Current: validate_indexing.py covers parsing only
   - Needs: Unit tests for all methods, edge cases, error handling
   - Target: 20+ tests

2. **`cli.py`** (700+ lines)
   - Current: Manual CLI testing only
   - Needs: Unit tests for each command, argument validation
   - Target: 15+ tests

3. **`primitives/discovery.py`** (300+ lines)
   - Current: Used by test_compose.py indirectly
   - Needs: Unit tests for each primitive, filter combinations
   - Target: 15+ tests

4. **`registry.py`** (75 lines)
   - Current: Basic manual testing
   - Needs: Unit tests for all methods, corruption scenarios
   - Target: 10+ tests

5. **`search.py`** (200+ lines)
   - Current: Manual CLI testing only
   - Needs: Unit tests for search logic, filter building
   - Target: 12+ tests

### Medium Priority (Should Have)
6. **`compose.py`** (200+ lines)
   - Current: test_compose.py (async integration tests)
   - Needs: Unit tests for orchestration, stage ordering
   - Target: 10+ tests

7. **`enhanced.py`** (300+ lines)
   - Current: Manual CLI testing only
   - Needs: Unit tests for metadata parsing, filtering
   - Target: 10+ tests

8. **`qdrant_service.py`** (150+ lines)
   - Current: Manual CLI testing (start/stop/status)
   - Needs: Unit tests for container lifecycle, health checks
   - Target: 8+ tests

### Low Priority (Nice to Have)
9. **`config.py`** (30 lines)
   - Current: Implicit testing via imports
   - Needs: Unit tests for config loading, env vars
   - Target: 5+ tests

---

## New Modules Needed

### 1. Validation Module (`validation.py`)
**Purpose**: Centralized schema/data validation
**Coverage**:
- Point payload schema validation
- Required field checking
- Type validation
- Enum enforcement
- Custom rule checking

### 2. Test Utilities (`tests/conftest.py`)
**Purpose**: Shared pytest fixtures
**Coverage**:
- Mock Qdrant client
- Test data fixtures
- Temporary collections
- Sample markdown files
- Mock model loader

### 3. Migrations Module (`migrations.py`)
**Purpose**: Schema upgrade framework
**Coverage**:
- Version tracking
- Migration registration
- Rollback support
- Validation after migration

---

## Test Metrics

### Baseline (Current State)
- Lines of code tested: ~500 (via validation script)
- Lines of code untested: ~3000+
- Test coverage: 0% (no pytest, no measurement)
- Test automation: 0%
- CI/CD integration: 0%

### Target (After Refactor)
- Lines of code tested: ~2500+
- Lines of code untested: ~500
- Test coverage: 70%+
- Test automation: 100%
- CI/CD integration: Yes

---

## Testing Strategy by Phase

### Phase 1: Setup (Week 1)
```
Files to create:
  ✓ pytest.ini
  ✓ tests/conftest.py
  ✓ tests/__init__.py
  ✓ tests/test_config.py (5 tests)
  ✓ tests/test_registry.py (10 tests)
  ✓ tests/fixtures/ (sample data)

Tests created: ~15
Target coverage: 10%
```

### Phase 2: Core (Week 2)
```
Files to create:
  ✓ tests/test_ingest.py (20 tests)
  ✓ tests/test_search.py (12 tests)
  ✓ tests/test_qdrant_service.py (8 tests)

Tests created: ~40
Target coverage: 35%
```

### Phase 3: Integration (Week 3)
```
Files to create/refactor:
  ✓ tests/test_integration_e2e.py (10 tests)
  ✓ tests/test_compose_integration.py (convert 5 tests)
  ✓ tests/test_validation_integration.py (8 tests)

Tests created: ~23
Target coverage: 55%
```

### Phase 4: Validation (Week 4)
```
Files to create:
  ✓ imem/src/imem/validation.py (module)
  ✓ tests/test_validation.py (15 tests)
  ✓ tests/test_migration.py (8 tests)

Tests created: ~23
Target coverage: 70%
```

### Phase 5: CLI (Week 5)
```
Files to create:
  ✓ tests/test_cli.py (20 tests)
  ✓ tests/test_primitives.py (15 tests)

Tests created: ~35
Target coverage: 80%+
```

---

## Verification Checklist

### Before Refactor
- [ ] Run all manual tests
- [ ] Document current behavior
- [ ] Test error scenarios manually
- [ ] Verify Qdrant data consistency
- [ ] Check registry integrity

### During Refactor
- [ ] Convert manual scripts to pytest
- [ ] Add unit tests (aim for 50% coverage)
- [ ] Add validation layer
- [ ] Create pytest infrastructure
- [ ] Document test patterns

### After Refactor
- [ ] Achieve 70% coverage
- [ ] Add integration tests
- [ ] Set up CI/CD
- [ ] Performance benchmarks
- [ ] Document test suite

---

## References

### Test Files
- `/imem/tests/validate_indexing.py` - Parsing validation
- `/test_compose.py` - Composition testing
- `/tests/251023-1537/test_llamaindex_pipeline.py` - TRACE integration

### Documentation
- `/imem/README.md` - Usage examples
- `/imem/architecture_imem-i2.md` - Architecture (1000+ lines)
- `/.context/document/runbooks/imem.md` - Operational runbook

### Key Components
- `imem/src/imem/cli.py` - CLI commands (700 lines)
- `imem/src/imem/ingest.py` - Indexing engine (400+ lines)
- `imem/src/imem/search.py` - Search system (200 lines)
- `imem/src/imem/compose.py` - Orchestration (200 lines)
- `imem/src/imem/primitives/discovery.py` - Discovery primitives (300 lines)

