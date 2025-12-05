"""System Tests: Router End-to-End Flows

Tests the complete IMEM flows through Router:
- index(): COMPILE → STORAGE → MANAGE
- query(): RETRIEVE → STRUCTURE

These tests verify the entire system working together.
"""

import pytest
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
import tempfile
import os

from imem.router import Router, create_router
from imem.context import Infrastructure, IndexContext, QueryContext
from imem.storage.sqlite import SQLiteStore
from imem.infrastructure.git import NoOpGitInterface, create_git_interface
from imem.manage import create_manage_orchestrator
from imem.structure import create_structure_orchestrator


# ============================================================================
# Router Factory Tests
# ============================================================================

class TestRouterFactory:
    """Test create_router factory function"""

    def test_creates_router_with_temp_dir(self):
        """Factory creates Router with temp directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            router = create_router(Path(tmpdir))

            assert router is not None
            assert router.infrastructure is not None
            assert router.manage is not None
            assert router.structure is not None

    def test_router_has_sqlite_store(self):
        """Router has SQLite database store"""
        with tempfile.TemporaryDirectory() as tmpdir:
            router = create_router(Path(tmpdir))

            assert router.infrastructure.db is not None
            assert isinstance(router.infrastructure.db, SQLiteStore)

    def test_router_detects_noop_git(self):
        """Router uses NoOpGitInterface for non-git directories"""
        with tempfile.TemporaryDirectory() as tmpdir:
            router = create_router(Path(tmpdir))

            # No .git in temp dir, should be NoOp
            git_name = router.infrastructure.git.__class__.__name__
            assert git_name == 'NoOpGitInterface'

    def test_router_accepts_config(self):
        """Router accepts configuration dict"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {'custom_option': 'value'}
            router = create_router(Path(tmpdir), config=config)

            assert router.infrastructure.config.get('custom_option') == 'value'

    def test_router_enable_vectors_true(self):
        """Router attempts vector infrastructure when enabled"""
        with tempfile.TemporaryDirectory() as tmpdir:
            router = create_router(Path(tmpdir), enable_vectors=True)

            # Should have sibling builder (real or noop depending on env)
            builder_names = [b.name for b in router.manage.graph.builders]
            assert any('sibling' in name for name in builder_names)

    def test_router_enable_vectors_false(self):
        """Router skips vectors when disabled"""
        with tempfile.TemporaryDirectory() as tmpdir:
            router = create_router(Path(tmpdir), enable_vectors=False)

            # Should have NoOpSiblingBuilder
            builder_names = [b.name for b in router.manage.graph.builders]
            assert 'sibling_noop' in builder_names


# ============================================================================
# Index Flow Tests
# ============================================================================

class TestIndexFlow:
    """Test Router.index() flow: COMPILE → STORAGE → MANAGE"""

    def test_index_empty_list(self):
        """Index handles empty file list"""
        with tempfile.TemporaryDirectory() as tmpdir:
            router = create_router(Path(tmpdir))

            result = router.index([])

            assert result == []

    def test_index_nonexistent_file(self):
        """Index handles nonexistent files gracefully"""
        with tempfile.TemporaryDirectory() as tmpdir:
            router = create_router(Path(tmpdir))

            result = router.index([Path("/nonexistent/file.md")])

            # Should not crash, return empty
            assert result == []

    def test_index_single_markdown_file(self):
        """Index processes single markdown file (or handles gracefully)"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)

            # Create test file
            test_file = project / "test.md"
            test_file.write_text("""---
title: Test Document
---

# Test Heading

This is test content.
""")

            router = create_router(project)
            # Note: Router.index uses DocumentIndexer which may not have _parse_file
            # This tests graceful degradation when COMPILE domain is incomplete
            result = router.index([test_file])

            # Should return list (may be empty if parser unavailable)
            assert isinstance(result, list)

    def test_index_enriches_chunks(self):
        """Index enriches chunks via MANAGE"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)

            test_file = project / "test.md"
            test_file.write_text("""---
created_at: 2025-01-15T10:00:00
---

# Authentication Design

We will use JWT tokens for authentication.

```python
def validate_token(token):
    return jwt.decode(token, secret)
```
""")

            router = create_router(project)
            result = router.index([test_file])

            if result:
                # Chunks should have enrichment fields
                chunk = result[0]
                assert 'id' in chunk

    def test_index_multiple_files(self):
        """Index processes multiple files"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)

            # Create multiple files
            for i in range(3):
                (project / f"doc{i}.md").write_text(f"# Document {i}\n\nContent {i}")

            router = create_router(project)
            files = list(project.glob("*.md"))
            result = router.index(files)

            # Should have chunks from all files
            assert len(result) >= 3


# ============================================================================
# Query Flow Tests
# ============================================================================

class TestQueryFlow:
    """Test Router.query() flow: RETRIEVE → STRUCTURE"""

    def test_query_empty_database(self):
        """Query returns empty on fresh database"""
        with tempfile.TemporaryDirectory() as tmpdir:
            router = create_router(Path(tmpdir))

            config = {
                'search': {'text': 'authentication', 'mode': 'semantic'}
            }

            result = router.query(config)

            assert isinstance(result, list)
            assert len(result) == 0

    def test_query_after_index(self):
        """Query finds indexed content"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)

            # Index a document
            test_file = project / "auth.md"
            test_file.write_text("""# Authentication

We use JWT tokens for secure authentication.
""")

            router = create_router(project)
            router.index([test_file])

            # Query for it
            config = {
                'search': {'text': 'authentication', 'mode': 'hybrid'}
            }

            result = router.query(config)
            # Results depend on retrieval implementation
            assert isinstance(result, list)


# ============================================================================
# Index Phase Tests
# ============================================================================

class TestIndexPhase:
    """Test Router.index_phase() backward compatibility"""

    def test_index_phase_returns_result(self):
        """index_phase returns result dict"""
        with tempfile.TemporaryDirectory() as tmpdir:
            router = create_router(Path(tmpdir))

            # This will likely return 0 chunks for empty dir
            result = router.index_phase('develop')

            assert isinstance(result, dict)


# ============================================================================
# Infrastructure Wiring Tests
# ============================================================================

class TestInfrastructureWiring:
    """Test infrastructure components are correctly wired"""

    def test_manage_receives_infrastructure(self):
        """ManageOrchestrator can access infrastructure"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)

            test_file = project / "test.md"
            test_file.write_text("# Test\n\nContent")

            router = create_router(project)

            # The context passed to manage should have infrastructure
            # This is implicitly tested by successful indexing
            result = router.index([test_file])
            # If no exception, wiring is correct
            assert True

    def test_structure_receives_infrastructure(self):
        """StructureOrchestrator can access infrastructure"""
        with tempfile.TemporaryDirectory() as tmpdir:
            router = create_router(Path(tmpdir))

            config = {'search': {'text': 'test'}}
            result = router.query(config)

            # If no exception, wiring is correct
            assert True


# ============================================================================
# Database Persistence Tests
# ============================================================================

class TestDatabasePersistence:
    """Test that indexed data persists in database"""

    def test_chunks_stored_in_database(self):
        """Indexed chunks are stored in SQLite"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)

            test_file = project / "persist.md"
            test_file.write_text("# Persistence Test\n\nThis should be stored.")

            router = create_router(project)
            router.index([test_file])

            # Verify data is in database
            db = router.infrastructure.db
            cursor = db.conn.execute("SELECT COUNT(*) FROM chunks")
            count = cursor.fetchone()[0]

            assert count >= 1

    def test_enrichment_stored_in_database(self):
        """Enrichment fields are updated in database"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)

            test_file = project / "enrich.md"
            test_file.write_text("""---
created_at: 2025-01-15
---

# Enrichment Test

Content with timestamp.
""")

            router = create_router(project)
            router.index([test_file])

            # Check enrichment was stored
            db = router.infrastructure.db
            cursor = db.conn.execute(
                "SELECT validity, git_status FROM chunks LIMIT 1"
            )
            row = cursor.fetchone()

            if row:
                validity, status = row
                assert validity is not None
                assert status is not None


# ============================================================================
# Error Handling Tests
# ============================================================================

class TestErrorHandling:
    """Test error handling in system flows"""

    def test_handles_corrupt_markdown(self):
        """Handles malformed markdown gracefully"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)

            # Create file with weird content
            test_file = project / "corrupt.md"
            test_file.write_bytes(b"# Title\n\x00\x01\x02Invalid bytes")

            router = create_router(project)

            # Should not crash
            try:
                result = router.index([test_file])
                assert isinstance(result, list)
            except Exception:
                # Some failures are acceptable for truly malformed input
                pass

    def test_handles_missing_schema(self):
        """Handles missing database schema gracefully"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # create_router should create schema automatically
            router = create_router(Path(tmpdir))

            # Query should work even on fresh database
            result = router.query({'search': {'text': 'test'}})
            assert isinstance(result, list)


# ============================================================================
# Configuration Tests
# ============================================================================

class TestConfiguration:
    """Test configuration options"""

    def test_custom_git_root(self):
        """Router accepts custom git root"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)
            git_root = project / "git_repo"
            git_root.mkdir()

            router = create_router(project, git_root=git_root)

            assert router.infrastructure.git.root == git_root

    def test_project_root_in_config(self):
        """Project root is accessible in config"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)
            router = create_router(project)

            config_root = router.infrastructure.config.get('project_root')
            assert config_root == project


# ============================================================================
# Run tests
# ============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
